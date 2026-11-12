"""Claims in a draft: one per sentence, supported when it cites a source the
run had, unsupported otherwise. The owner must keep or remove every
unsupported claim before the draft can be approved; a kept one is labelled
unsupported in the export."""

from __future__ import annotations

import re
from typing import Any

_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[\"'])")
_CITE = re.compile(r"\[(\d{1,2})\]")

KEEP = "keep"
REMOVE = "remove"


def split_claims(text: str) -> list[dict[str, Any]]:
    parts = [p.strip() for p in _SENTENCE.split(text.strip()) if p.strip()]
    out: list[dict[str, Any]] = []
    for i, p in enumerate(parts):
        cites = sorted({int(n) for n in _CITE.findall(p)})
        out.append({"i": i, "text": p, "cites": cites,
                    "status": "supported" if cites else "unsupported", "decision": None})
    return out


def open_unsupported(claims: list[dict[str, Any]] | None) -> int:
    return sum(1 for c in (claims or []) if c["status"] == "unsupported" and c.get("decision") is None)


def visible_text(claims: list[dict[str, Any]] | None, label_unsupported: bool = False) -> str:
    kept = []
    for c in claims or []:
        if c.get("decision") == REMOVE:
            continue
        t = c["text"]
        if label_unsupported and c["status"] == "unsupported":
            t = f"{t} _(unsupported)_"
        kept.append(t)
    return " ".join(kept)


def carry_decisions(new: list[dict[str, Any]], old: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Keep the owner's decision only for unsupported sentences whose text is
    unchanged; any new or edited sentence needs a fresh decision."""
    decided = {c["text"]: c.get("decision") for c in (old or []) if c["status"] == "unsupported" and c.get("decision")}
    for c in new:
        if c["status"] == "unsupported" and c["text"] in decided:
            c["decision"] = decided[c["text"]]
    return new


def unknown_citations(text: str, valid: set[int]) -> list[int]:
    return sorted({int(n) for n in _CITE.findall(text)} - valid)
