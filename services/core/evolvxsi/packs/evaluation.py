"""Run a pack version's evaluation cases on the model route now in use.

The result is recorded for the exact (pack version, model). A pack that
declares cases is offered to run only on models it has passed on, because a
template that works on one model can fail on another.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from evolvxsi.db.models import User
from evolvxsi.packs.manifest import Manifest
from evolvxsi.tasks.drafter import NO_SOURCE_TEXT, draft_answer
from evolvxsi.tasks.evidence import Evidence


@dataclass(frozen=True)
class CaseResult:
    question: str
    passed: bool
    reason: str


def _run_case(db: Session, user: User, case, title: str) -> CaseResult:  # type: ignore[no-untyped-def]
    ev = [Evidence(n=i, doc_id=f"case-{i}", title=f"Evidence {i}", link=None, passage=p) for i, p in enumerate(case.evidence, start=1)]
    try:
        result = draft_answer(db, user, title, case.question, ["Find sources", "Draft with citations"], ev)
    except Exception as e:  # a blocked route or a model failure is a failed case, not a crash
        return CaseResult(case.question, False, f"The model could not answer: {getattr(e, 'detail', None) or type(e).__name__}")
    text = result.text
    if case.expect.lower() not in text.lower():
        return CaseResult(case.question, False, f"The draft does not contain the expected text ({case.expect!r}).")
    if ev:
        if not result.cited:
            return CaseResult(case.question, False, "The draft cites none of the evidence it was given.")
    elif text != NO_SOURCE_TEXT:
        return CaseResult(case.question, False, "With no evidence the draft must state that no source covers the request.")
    return CaseResult(case.question, True, "passed")


def evaluate(db: Session, user: User, manifest: Manifest) -> list[CaseResult]:
    return [_run_case(db, user, c, manifest.name) for c in manifest.evaluation_cases]
