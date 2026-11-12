"""Treat source text as data, never as instructions or structure (A9).

Passages come from documents anyone with write access to a source could have
edited, so they may carry text aimed at the model ("ignore your instructions",
fake citations, fake extra sources). These controls do not rely on the model
behaving well:

* `neutralize_passage` stops a passage from minting citations (`[3]` becomes
  `(3)`) or pretending to start a new source or prompt section (line breaks are
  collapsed, so a passage is always one line inside its delimiters).
* Passages are wrapped in clearly marked delimiters, and the system prompt says
  text inside them is quoted data.
* Planning and drafting requests carry no tools, so text cannot trigger an action.
* Citations in the output are kept only for sources the run really had
  (`drafter.keep_valid_citations`), whatever the text asked for.
"""

from __future__ import annotations

import re

_BRACKET_NUM = re.compile(r"\[(\s*\d{1,3}\s*)\]")
_WS = re.compile(r"\s+")
SOURCE_OPEN = "<<source"
SOURCE_CLOSE = "source>>"


def neutralize_passage(text: str, limit: int) -> str:
    text = _BRACKET_NUM.sub(lambda m: f"({m.group(1).strip()})", text)
    # Delimiter look-alikes inside a passage cannot close or open a source.
    text = text.replace(SOURCE_OPEN, "<< source").replace(SOURCE_CLOSE, "source >>")
    text = _WS.sub(" ", text).strip()
    return text[:limit]


def neutralize_title(text: str) -> str:
    return neutralize_passage(text, 200)


_INSTRUCTION_LIKE = re.compile(
    r"(ignore|disregard|forget|override)\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier|your)\s+(instructions?|rules?|prompts?)"
    r"|you\s+are\s+now\b"
    r"|\b(reveal|print|show|repeat|quote)\s+(your\s+|the\s+)?(full\s+|complete\s+)?(system\s+)?(prompt|instructions)"
    r"|\binstructions\s+you\s+were\s+given"
    r"|\bsystem\s*:"
    r"|do\s+not\s+follow\s+(the\s+)?(above|previous|earlier)"
    # text addressed to the model rather than to a reader
    r"|\b(note|message|instructions?)\s+(for|to)\s+(the\s+)?(ai|assistant|model|llm|chatbot)\b"
    r"|\bdisregard\s+(the\s+)?(user'?s?\s+)?(question|request)"
    r"|\b(reply|respond|answer|output)\s+(only|exactly)\b"
    r"|\bnothing\s+else\b.{0,20}$"
    r"|\b(end|finish|start|begin)\s+(every|each|your)\s+(answer|reply|response)\b"
    r"|\b(append|add|include|insert|put)\b.{0,60}\b(to|at\s+the\s+end\s+of|in)\s+(your|the)\s+(answer|reply|response|draft)\b"
    r"|\bwhen\s+you\s+(answer|respond|reply|write)\b"
    r"|\b(email|send|forward|post)\b.{0,50}\b(draft|answer|summary|conversation)\b.{0,30}\bto\s+\S+@"
    r"|<\s*img\b|!\[[^\]]*\]\(\s*https?://"
    r"|\bdecode\b.{0,40}\b(and|then)\s+(do|follow|execute|run)\b",
    re.IGNORECASE | re.DOTALL,
)
_HIDDEN = re.compile("[\u200b-\u200f\u2060\ufeff]")
_SPACED = re.compile(r"\b(?:[A-Za-z]\s){3,}[A-Za-z]\b")


def _normalised(text: str) -> str:
    """Undo two cheap disguises before matching: invisible characters between letters and letters
    spaced apart (I G N O R E)."""
    text = _HIDDEN.sub("", text)
    return _SPACED.sub(lambda m: re.sub(r"\s", "", m.group(0)), text)


def looks_like_instructions(text: str) -> bool:
    """A cheap signal, not a defence: text in a source that reads like an
    instruction to a model. The reviewer is told; the source is not dropped."""
    return bool(_INSTRUCTION_LIKE.search(_normalised(text)))
