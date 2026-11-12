"""Precision and recall of the redaction detectors on the labelled synthetic set.
  PYTHONPATH=. python scripts/redaction_report.py
Counts per (case, kind): a hit is a true positive, a wrong kind a false positive, a miss a false negative."""

import json
from pathlib import Path

from evolvxsi.redaction.redact import redact_text

SET = Path(__file__).resolve().parents[1] / "tests/unit/evolvxsi/redaction/redaction_set.json"


def score() -> dict:
    tp = fp = fn = 0
    wrong: list[str] = []
    for c in json.loads(SET.read_text())["cases"]:
        _, counts = redact_text(c["text"])
        got, want = set(counts), set(c["expect"])
        tp += len(got & want)
        fp += len(got - want)
        fn += len(want - got)
        if got != want:
            wrong.append(f"{c['text'][:60]!r}: got {sorted(got)} want {sorted(want)}")
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 3), "recall": round(r, 3), "wrong": wrong}


if __name__ == "__main__":
    out = score()
    print({k: v for k, v in out.items() if k != "wrong"})
    for w in out["wrong"]:
        print("  -", w)
