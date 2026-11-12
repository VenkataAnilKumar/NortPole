"""Draft a cited answer for a running task, through the route policy.

The model sees only the passages the owner was allowed to retrieve. Each
citation `[n]` must name a passage that was provided; any other citation is
removed before the draft is stored, so a draft can never point to a source
the run did not have. With no passages, the model is told to state the
evidence gap rather than answer from memory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from evolvxsi.db.models import User
from evolvxsi.llm.factory import get_default_llm
from evolvxsi.llm.interfaces import GenerationContext
from evolvxsi.llm.models import GenerationOptions, GenerationRequest, UserMessage
from evolvxsi.route_policy.enforce import enforce_route
from evolvxsi.tasks.evidence import Evidence
from evolvxsi.tracing.flows import LLMFlow

DRAFT_SYSTEM_PROMPT = (
    "Write a draft answer to the request using only the numbered sources given. "
    "Cite every factual sentence with its source number in square brackets, like [1]. "
    "If the sources do not cover something, say so plainly instead of guessing. "
    "If no sources are given, say that no permitted source covers the request."
)
_CITE = re.compile(r"\[(\d{1,2})\]")


@dataclass(frozen=True)
class DraftResult:
    text: str
    cited: list[int]
    removed_citations: int
    route_kind: str | None


def build_prompt(title: str, request: str, plan: list[str], evidence: list[Evidence]) -> str:
    lines = [f"Title: {title}", f"Request: {request}", "Plan:"]
    lines += [f"{i}. {step}" for i, step in enumerate(plan, start=1)]
    if evidence:
        lines.append("Sources:")
        for e in evidence:
            lines.append(f"[{e.n}] {e.title}: {e.passage}")
    else:
        lines.append("Sources: none")
    return "\n".join(lines)


def keep_valid_citations(text: str, valid: set[int]) -> tuple[str, list[int], int]:
    """Drop citations to sources that were not provided. Returns the cleaned
    text, the cited source numbers in order of first use, and how many were
    removed."""
    removed = 0
    cited: list[int] = []

    def repl(m: re.Match[str]) -> str:
        nonlocal removed
        n = int(m.group(1))
        if n in valid:
            if n not in cited:
                cited.append(n)
            return m.group(0)
        removed += 1
        return ""

    cleaned = _CITE.sub(repl, text)
    cleaned = re.sub(r"[ \t]+([.,;:])", r"\1", cleaned)
    return cleaned.strip(), cited, removed


def draft_answer(
    db_session: Session, user: User, title: str, request: str, plan: list[str], evidence: list[Evidence]
) -> DraftResult:
    llm = get_default_llm()
    decision = enforce_route(db_session, llm.config.model_configuration_id, actor=user)
    reply = llm.invoke(
        GenerationRequest(
            system_prompt=DRAFT_SYSTEM_PROMPT,
            messages=[UserMessage(content=build_prompt(title, request, plan, evidence))],
            options=GenerationOptions(max_tokens=1200),
        ),
        context=GenerationContext(flow=LLMFlow.CHAT_RESPONSE),
    )
    text, cited, removed = keep_valid_citations(reply.text or "", {e.n for e in evidence})
    if not text:
        raise ValueError("The model returned an empty draft.")
    return DraftResult(text=text, cited=cited, removed_citations=removed, route_kind=decision.kind)
