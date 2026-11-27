"""Benchmark whether a local NLI verifier supports the conditions in a claim."""

import argparse
import json
import math
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from benchmark_extractive_qa import (
    CALIBRATION_ANCHORS,
    HELD_OUT,
    SCENARIOS,
    ExtractiveReader,
    measure,
    outcome,
    questions,
)


@dataclass(frozen=True)
class Pair:
    name: str
    source: str
    supported: str
    changed_condition: str


CALIBRATION = (
    Pair(
        "temporary-approval",
        "The on-call service owner approves the initial after-hours production grant. Emergency grants expire after four hours.",
        "The service owner approves the initial after-hours grant.",
        "The service owner approves any extension beyond the four-hour emergency grant.",
    ),
    Pair(
        "archive-duration",
        "After a replacement procedure is approved, retain its predecessor for three years.",
        "A procedure that has been replaced with an approved version is kept for three years.",
        "A procedure subject to litigation hold may be deleted three years after its replacement is approved.",
    ),
    Pair(
        "queued-cancellation",
        "Owners may cancel a run until the worker starts. After that the worker continues.",
        "The owner can cancel a run that is still queued.",
        "The owner can cancel a run that already started.",
    ),
    Pair(
        "business-day-cutoff",
        "The payroll team takes three business days to acknowledge requests received before cutoff.",
        "Payroll acknowledges requests received before cutoff within three business days.",
        "Payroll acknowledges requests received after cutoff within three calendar days.",
    ),
)

HELD_OUT_CLAIMS = (
    Pair("one-renewal",
         "The data owner can approve a single renewal of an expired contractor grant.",
         "The data owner can approve one renewal after contractor access expires.",
         "The data owner can approve another renewal for a contractor who already renewed once."),
    Pair("used-invite",
         "Unused reviewer invitations expire after 72 hours. Reviewers who accept an invitation join the project.",
         "An unused invitation stops working after 72 hours.",
         "Reviewers lose granted project access 72 hours after accepting their invitations."),
    Pair("refund-exception",
         "The purchasing lead authorizes rush charges for a revised delivery. After delivery, payment disputes go to Finance.",
         "The purchasing lead authorizes a rush charge for revised delivery.",
         "The purchasing lead authorizes refunding a rush charge after delivery."),
    Pair("acknowledgement-versus-resolution",
         "The support team acknowledges a billing dispute within one business day.",
         "Support acknowledges billing disputes within a business day.",
         "Support resolves billing disputes within a business day."),
    Pair("deadline-units",
         "A supplier must delete primary data within 30 calendar days of contract termination.",
         "The contract sets the primary data deletion deadline at 30 calendar days after termination.",
         "The contract sets the primary data deletion deadline at 30 business days after termination."),
    Pair("hold-exception",
         "The records team may purge the archive after five years, except for records subject to a legal hold.",
         "An archived record without a legal hold can be purged after five years.",
         "A record subject to a legal hold can be purged at the five-year mark."),
    Pair("amount-boundary",
         "A director approves dues above $300. Employees may pay dues of $300 or less without that approval.",
         "A director must approve dues of $450.",
         "A director must approve dues of exactly $300."),
    Pair("pause-versus-manual",
         "Pausing a schedule prevents timer runs. A manually started run leaves the next timer slot unchanged.",
         "Running the workflow manually does not alter the next timer slot.",
         "Pausing a schedule cancels an already-started manual run."),
)

QA_CLAIMS = (
    ("The person who may approve a one-time extension after initial contractor access ends is {answer}.",
     "The person who may approve a second extension after the first renewal has been used is {answer}."),
    ("If the workflow is launched on demand, its next scheduled occurrence is {answer}.",
     "If the recurring schedule is paused, a manual run takes {answer} to finish."),
    ("The person who approves a $450 professional membership renewal before payment is {answer}.",
     "The person who can waive a membership reinstatement surcharge is {answer}."),
    ("Valid direct deposit changes received after cutoff take effect on the {answer}.",
     "Payroll retries account verification after a failed validation in {answer}."),
    ("A complaint about a higher settled payment than the invoice is opened as {answer}.",
     "Finance issues a refund in {answer} when the settled charge exceeds the invoice."),
    ("After the contract ends, encrypted recovery backups remain for {answer}.",
     "Data restored from backup during a legal hold remains for {answer} after the hold is released."),
    ("A read-only invitation expires in {answer} if it is unused.",
     "A reviewer who already accepted the invitation loses project access after {answer}."),
    ("The person who authorizes a rush charge when the vendor refuses a new delivery date is {answer}.",
     "The person who approves a refund of the rush fee after a missed delivery is {answer}."),
)


class ClaimVerifier:
    def __init__(self, directory: Path, threads: int) -> None:
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(directory / "model.onnx"), options, providers=["CPUExecutionProvider"])
        self.inputs = {item.name for item in self.session.get_inputs()}
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=384, strategy="only_first")
        config = json.loads((directory / "config.json").read_text())
        self.entailment = next(index for index, name in config["id2label"].items() if name.casefold() == "entailment")

    def margin(self, passage: str, claim: str) -> float:
        encoded = self.tokenizer.encode(passage, claim)
        data = {"input_ids": encoded.ids, "attention_mask": encoded.attention_mask, "token_type_ids": encoded.type_ids}
        (logits,) = self.session.run(["logits"], {key: np.asarray([data[key]], dtype=np.int64) for key in self.inputs})
        index = int(self.entailment)
        return float(logits[0, index] - max(np.delete(logits[0], index)))


def measure_claims(verifier: ClaimVerifier, pairs: tuple[Pair, ...]) -> list[tuple[str, bool, float, float]]:
    rows = []
    for pair in pairs:
        for expected, claim in ((True, pair.supported), (False, pair.changed_condition)):
            start = time.perf_counter()
            margin = verifier.margin(pair.source, claim)
            rows.append((pair.name, expected, margin, time.perf_counter() - start))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_dirs", type=Path, nargs="+", help="ONNX, tokenizer, and model config directories")
    parser.add_argument("--qa-model", type=Path, help="Optional extractive reader to test with explicit claims")
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()
    qa_candidates = []
    if args.qa_model:
        reader = ExtractiveReader(args.qa_model, args.threads)
        calibration = measure(reader, questions(tuple(zip(SCENARIOS, CALIBRATION_ANCHORS, strict=True))))
        qa_cutoff = max(c.margin for q, c, _ in calibration if outcome(q, c, -math.inf) != "correct evidence")
        qa_candidates = measure(reader, questions(HELD_OUT))

    for directory in args.model_dirs:
        verifier = ClaimVerifier(directory, args.threads)
        verifier.margin(CALIBRATION[0].source, CALIBRATION[0].supported)
        calibration_scores = measure_claims(verifier, CALIBRATION)
        threshold = max(0, max(score for _, expected, score, _ in calibration_scores if not expected))
        for split, scores in (("calibration", calibration_scores), ("held-out", measure_claims(verifier, HELD_OUT_CLAIMS))):
            counts: Counter[str] = Counter()
            for case, expected, score, seconds in scores:
                accepted = score > threshold
                result = ("correct support" if expected else "unsupported claim") if accepted else (
                    "missed support" if expected else "correct abstention"
                )
                counts[result] += 1
                print(json.dumps({"model": directory.name, "split": split, "case": case,
                                  "expected": expected, "score": round(score, 4), "result": result,
                                  "default_accepted": score > 0, "seconds": round(seconds, 4)}))
            timings = sorted(seconds for _, _, _, seconds in scores)
            print(json.dumps({"model": directory.name, "split": split, "threshold": round(threshold, 4),
                              "results": counts, "p95_seconds": round(timings[math.ceil(.95 * len(timings)) - 1], 4)}))
        if qa_candidates:
            original: Counter[str] = Counter()
            verified: Counter[str] = Counter()
            timings = []
            templates = (template for pair in QA_CLAIMS for template in pair)
            for (question, candidate, qa_seconds), template in zip(qa_candidates, templates, strict=True):
                baseline = outcome(question, candidate, qa_cutoff)
                original[baseline] += 1
                seconds = qa_seconds
                result = baseline
                if candidate.margin > qa_cutoff:
                    start = time.perf_counter()
                    claim = template.format(answer=candidate.span.rstrip("."))
                    margin = verifier.margin(question.passages[candidate.passage - 1], claim)
                    seconds += time.perf_counter() - start
                    if margin <= threshold:
                        result = outcome(question, candidate, math.inf)
                    print(json.dumps({"model": directory.name, "split": "extractive QA", "case": question.name,
                                      "claim": claim, "baseline": baseline, "result": result, "score": round(margin, 4)}))
                timings.append(seconds)
                verified[result] += 1
            p95 = sorted(timings)[math.ceil(.95 * len(timings)) - 1]
            print(json.dumps({"model": directory.name, "split": "extractive QA", "baseline": original,
                              "results": verified, "p95_seconds": round(p95, 4)}))


if __name__ == "__main__":
    main()
