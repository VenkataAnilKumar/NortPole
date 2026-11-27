"""Evaluate local SQuAD 2.0 ONNX readers on answer support and abstention."""

import argparse
import json
import math
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from benchmark_passage_verifier import SCENARIOS, Scenario


@dataclass(frozen=True)
class Question:
    name: str
    text: str
    passages: tuple[str, ...]
    expected: int | None
    anchors: tuple[str, ...] = ()


CALIBRATION_ANCHORS = (
    ("on-call service owner",), ("keeps running",), ("settled amount",),
    ("25 dollars",), ("designate a teammate", "monitor the shared inbox"),
    ("confirming receipt of the termination notice",),
    ("unavailable for multiple customers",), ("three years",),
)

HELD_OUT = (
    (Scenario(
        "contractor-access",
        (
            "Project leads approve initial contractor access requests.",
            "Only the data steward may approve a one-time extension after a contractor's first access period expires.",
            "Contractor credentials expire seven days after a grant is issued.",
            "A service owner can remove contractor access before it expires.",
        ),
        "Who can keep a contractor authorized past their first access window?", 2,
        "Who can grant a second extension after the contractor already used their one renewal?",
    ), ("data steward",)),
    (Scenario(
        "manual-run",
        (
            "Pausing a schedule prevents new timer runs while it is paused.",
            "The job owner can view manual run results in History.",
            "Starting a workflow on demand leaves its next scheduled occurrence unchanged.",
            "If a run is queued, the current owner can cancel it from the run details.",
        ),
        "What happens to the next timer slot if I launch the workflow myself now?", 3,
        "How many minutes before a manual run finishes if the recurring schedule is paused?",
    ), ("unchanged",)),
    (Scenario(
        "membership-dues",
        (
            "The department director must approve professional membership renewals costing over $300 before payment.",
            "Finance reimburses approved travel after reviewing the expense report.",
            "A purchasing coordinator may renew a software subscription below $300.",
            "Employees can submit membership reimbursement requests after paying their dues.",
        ),
        "Whose sign-off do I need before paying $450 to renew my professional association membership?", 1,
        "Which approver can waive a professional association's membership reinstatement surcharge?",
    ), ("department director",)),
    (Scenario(
        "payroll-deposit",
        (
            "Payroll publishes the direct deposit cutoff on the employee portal calendar.",
            "Bank changes take effect only after the new account information passes validation.",
            "Payroll issues a check if the active bank account rejects a deposit.",
            "Valid direct deposit changes received after the cutoff take effect on the second payday after submission.",
        ),
        "I missed the payroll deadline for changing banks. Which payday will use my new account?", 4,
        "How many days after a bank validation failure will Payroll retry account verification?",
    ), ("second payday",)),
    (Scenario(
        "support-queue",
        (
            "Billing disputes use a dedicated finance queue with an acknowledgement target of one business day.",
            "Open a billing dispute when a customer says the final settled charge differs from the invoice total.",
            "For duplicate invoices, use the existing account support request.",
            "Escalate an open service outage through the incident queue.",
        ),
        "What type of case should I open when a customer's processed payment is higher than the invoice?", 2,
        "How soon will Finance issue a refund when the settled charge exceeds the invoice?",
    ), ("billing dispute",)),
    (Scenario(
        "termination-backups",
        (
            "Purge primary service data 30 days after the termination date.",
            "A data processing addendum remains available to the customer after termination.",
            "Encrypted backups roll off 60 calendar days after the contract end date.",
            "A backup restored during scheduled maintenance requires a ticket for review.",
        ),
        "How long do the encrypted recovery copies remain after the commercial agreement ends?", 3,
        "How long are copies restored from backup during a legal hold kept after that hold is released?",
    ), ("60 calendar days", "60 days")),
    (Scenario(
        "reviewer-invite",
        (
            "Read-only reviewer invitations expire automatically after 72 hours if they are unused.",
            "A project owner can resend an expired invitation after verifying the reviewer's identity.",
            "A reviewer who accepts the invitation can see documents shared with that project.",
            "Workflow review deadlines are listed separately in the Approvals inbox.",
        ),
        "When does an unopened view-only invitation become unusable?", 1,
        "When does project access end for a reviewer who clicked the invitation and already accepted it?",
    ), ("72 hours",)),
    (Scenario(
        "expedited-supplier",
        (
            "The requester records a rejected delivery window in the purchase order notes.",
            "Regional buyers approve changes to a supplier's standard shipping address.",
            "The supplier invoices any agreed expedited fees separately.",
            "If the supplier cannot accept a revised delivery window, the procurement manager must authorize the rush fee.",
        ),
        "Who authorizes a rush charge when the vendor won't accept the new delivery date?", 4,
        "Who authorizes a refund of a rush fee if the supplier later misses the new delivery date?",
    ), ("procurement manager",)),
)


def questions(scenarios: tuple[tuple[Scenario, tuple[str, ...]], ...]) -> list[Question]:
    return [
        question
        for scenario, anchors in scenarios
        for question in (
            Question(scenario.name, scenario.question, scenario.passages, scenario.expected, anchors),
            Question(scenario.name + "/no-answer", scenario.near_miss, scenario.passages, None),
        )
    ]


@dataclass(frozen=True)
class Candidate:
    passage: int
    span: str
    margin: float


class ExtractiveReader:
    def __init__(self, model_dir: Path, threads: int) -> None:
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(model_dir / "model.onnx"), options, providers=["CPUExecutionProvider"])
        self.inputs = {item.name for item in self.session.get_inputs()}
        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        pad = next(token for token in ("[PAD]", "<pad>") if self.tokenizer.token_to_id(token) is not None)
        self.tokenizer.enable_padding(pad_id=self.tokenizer.token_to_id(pad), pad_token=pad)
        self.tokenizer.enable_truncation(max_length=384, strategy="only_second")

    def predict(self, question: Question) -> Candidate:
        encoded = self.tokenizer.encode_batch([(question.text, passage) for passage in question.passages])
        data = {
            "input_ids": [item.ids for item in encoded],
            "attention_mask": [item.attention_mask for item in encoded],
            "token_type_ids": [item.type_ids for item in encoded],
        }
        start, end = self.session.run(
            ["start_logits", "end_logits"], {key: np.asarray(data[key], dtype=np.int64) for key in self.inputs},
        )
        candidates = []
        for index, item in enumerate(encoded):
            context = [i for i, source in enumerate(item.sequence_ids) if source == 1]
            first, last = max(
                ((first, last) for offset, first in enumerate(context) for last in context[offset:offset + 32]),
                key=lambda pair: start[index, pair[0]] + end[index, pair[1]],
            )
            left, right = item.offsets[first][0], item.offsets[last][1]
            span = question.passages[index][left:right]
            margin = (start[index, first] + end[index, last]) - (start[index, 0] + end[index, 0])
            candidates.append(Candidate(index + 1, span, float(margin)))
        return max(candidates, key=lambda candidate: candidate.margin)


def normalize(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold()))


def outcome(question: Question, candidate: Candidate, threshold: float) -> str:
    if candidate.margin <= threshold:
        return "correct abstention" if question.expected is None else "missed answer"
    if question.expected is None:
        return "unsupported citation"
    if candidate.passage == question.expected and any(
        normalize(anchor) in normalize(candidate.span) for anchor in question.anchors
    ):
        return "correct evidence"
    return "wrong evidence"


def measure(reader: ExtractiveReader, items: list[Question]) -> list[tuple[Question, Candidate, float]]:
    results = []
    for item in items:
        start = time.perf_counter()
        candidate = reader.predict(item)
        results.append((item, candidate, time.perf_counter() - start))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_dirs", type=Path, nargs="+", help="Directories with model.onnx and tokenizer.json")
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()
    calibration = questions(tuple(zip(SCENARIOS, CALIBRATION_ANCHORS, strict=True)))
    held_out = questions(HELD_OUT)
    for model_dir in args.model_dirs:
        reader = ExtractiveReader(model_dir, args.threads)
        reader.predict(calibration[0])
        calibration_scores = measure(reader, calibration)
        # The lowest threshold above every incorrect citation keeps the most
        # correct calibration answers while withholding all known bad evidence.
        threshold = max((
            candidate.margin for item, candidate, _ in calibration_scores
            if outcome(item, candidate, -math.inf) != "correct evidence"
        ), default=-math.inf)
        for split, rows in (("calibration", calibration_scores), ("held-out", measure(reader, held_out))):
            counts: Counter[str] = Counter()
            for item, candidate, elapsed in rows:
                result = outcome(item, candidate, threshold)
                counts[result] += 1
                print(json.dumps({
                    "model": model_dir.name, "split": split, "case": item.name,
                    "expected": item.expected, "candidate": candidate.passage, "span": candidate.span,
                    "margin": round(candidate.margin, 4), "result": result,
                    "default_result": outcome(item, candidate, 0), "seconds": round(elapsed, 4),
                }), flush=True)
            times = sorted(elapsed for _, _, elapsed in rows)
            print(json.dumps({
                "model": model_dir.name, "split": split, "threshold": round(threshold, 4),
                "results": counts, "p95_seconds": round(times[math.ceil(0.95 * len(times)) - 1], 4),
            }), flush=True)


if __name__ == "__main__":
    main()
