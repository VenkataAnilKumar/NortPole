"""Run a pack's review rules against a draft. Pure: no database, no model."""

from __future__ import annotations

import re
from typing import Any


def _words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def evaluate(rules: list[dict[str, Any]] | None, text: str | None, sources: list[dict] | None, claims: list[dict] | None) -> list[dict[str, Any]]:
    """One result per rule: {kind, severity, message, passed, detail}."""
    text = text or ""
    low = text.lower()
    out = []
    for r in rules or []:
        kind, value = r.get("kind"), r.get("value")
        if kind == "min_citations":
            # Sources hold every passage the run gathered; what counts is how many the text actually cites.
            have = {s.get("n") for s in (sources or [])}
            n = len({int(m) for m in re.findall(r"\[(\d{1,2})\]", text) if int(m) in have})
            passed, detail = n >= int(value), f"{n} cited"
        elif kind == "max_words":
            n = _words(text)
            passed, detail = n <= int(value), f"{n} words"
        elif kind == "must_include":
            passed, detail = str(value).lower() in low, f"looking for {value!r}"
        elif kind == "must_not_include":
            passed, detail = str(value).lower() not in low, f"looking for {value!r}"
        elif kind == "all_claims_supported":
            bad = sum(1 for c in (claims or []) if c.get("status") == "unsupported")
            passed, detail = bad == 0, f"{bad} unsupported"
        else:  # an unknown kind in a stored snapshot fails closed
            passed, detail = False, "unknown rule"
        out.append({"kind": kind, "severity": r.get("severity", "block"), "message": r.get("message", ""), "passed": passed, "detail": detail})
    return out


def blocking_failures(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in results if not r["passed"] and r["severity"] == "block"]
