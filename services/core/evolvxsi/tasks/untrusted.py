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
