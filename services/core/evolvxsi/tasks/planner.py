"""Draft a plan for a started task with the default model, through the route
policy. A blocked route raises before any task text is sent."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from evolvxsi.db.models import User
from evolvxsi.llm.factory import get_default_llm
from evolvxsi.llm.interfaces import GenerationContext
from evolvxsi.llm.models import GenerationOptions, GenerationRequest, UserMessage
from evolvxsi.route_policy.enforce import enforce_route
from evolvxsi.tracing.flows import LLMFlow

PLAN_SYSTEM_PROMPT = (
    "You plan work before doing it. Reply with a numbered plan of 3 to 6 short "
    "steps that would answer the request with cited evidence. One step per line, "
    "each starting with its number and a full stop. No other text."
)
MAX_STEPS = 8
MAX_STEP_CHARS = 300
_STEP = re.compile(r"^\s*(\d{1,2})[.)]\s+(.+?)\s*$")


@dataclass(frozen=True)
class PlanResult:
    steps: list[str]
    route_kind: str | None


class PlanError(Exception):
    """No usable plan came back. The message is safe to show the owner."""


def parse_plan(text: str) -> list[str]:
    steps = [m.group(2)[:MAX_STEP_CHARS] for line in text.splitlines() if (m := _STEP.match(line))]
    return steps[:MAX_STEPS]


def _prompt(title: str, request: str, desired_output: str) -> str:
    parts = [f"Title: {title}", f"Request: {request}"]
    if desired_output.strip():
        parts.append(f"Desired output: {desired_output}")
    return "\n".join(parts)


def draft_plan(db_session: Session, user: User, title: str, request: str, desired_output: str) -> PlanResult:
    llm = get_default_llm()
    # Raises POLICY_BLOCKED (and records it) before anything is sent.
    decision = enforce_route(db_session, llm.config.model_configuration_id, actor=user)
    reply = llm.invoke(
        GenerationRequest(
            system_prompt=PLAN_SYSTEM_PROMPT,
            messages=[UserMessage(content=_prompt(title, request, desired_output))],
            options=GenerationOptions(max_tokens=400),
        ),
        context=GenerationContext(flow=LLMFlow.CHAT_RESPONSE),
    )
    steps = parse_plan(reply.text or "")
    if not steps:
        raise PlanError("The model did not return a numbered plan. Edit the request and start again.")
    return PlanResult(steps=steps, route_kind=decision.kind)
