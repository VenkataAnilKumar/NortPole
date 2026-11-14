"""Draft a plan for a started task with the default model, through the route
policy. A blocked route raises before any task text is sent."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from nortpole.db.models import User
from nortpole.llm.factory import get_default_llm
from nortpole.llm.interfaces import GenerationContext
from nortpole.llm.models import GenerationOptions, GenerationRequest, UserMessage
from nortpole.governance.route_policy.enforce import enforce_route
from nortpole.tracing.flows import LLMFlow

PLAN_SYSTEM_PROMPT = (
    "You write a work plan. You do NOT answer the request and you state no facts about it. "
    "Reply with a numbered plan of 3 to 6 short steps describing how someone would find the "
    "answer using documents and cite them. Each step is an action that starts with a verb. "
    "One step per line, each starting with its number and a full stop. No other text.\n"
    "Example for the request 'What is our refund policy?':\n"
    "1. Search the policy documents for refund rules.\n"
    "2. Compare the versions and note any changes.\n"
    "3. Draft the answer and cite the passage for each rule."
)
MAX_STEPS = 8
MAX_STEP_CHARS = 300
_STEP = re.compile(r"^\s*(\d{1,2})[.)]\s+(.+?)\s*$")


@dataclass(frozen=True)
class PlanResult:
    steps: list[str]
    route_kind: str | None
    input_tokens: int = 0
    output_tokens: int = 0


class PlanError(Exception):
    """No usable plan came back. The message is safe to show the owner."""


def parse_plan(text: str) -> list[str]:
    steps = [m.group(2)[:MAX_STEP_CHARS] for line in text.splitlines() if (m := _STEP.match(line))]
    return steps[:MAX_STEPS]


def _prompt(title: str, request: str, desired_output: str, guides: "list[tuple[str, str]] | tuple" = ()) -> str:
    from nortpole.work.tasks.drafter import guide_lines

    parts = [f"Title: {title}", f"Request: {request}"]
    if desired_output.strip():
        parts.append(f"Desired output: {desired_output}")
    parts += guide_lines(guides)
    return "\n".join(parts)


def draft_plan(db_session: Session, user: User, title: str, request: str, desired_output: str, guides: "list[tuple[str, str]] | tuple" = ()) -> PlanResult:
    llm = get_default_llm()
    # Raises POLICY_BLOCKED (and records it) before anything is sent.
    decision = enforce_route(db_session, llm.config.model_configuration_id, actor=user, purpose="task_plan")
    reply = llm.invoke(
        GenerationRequest(
            system_prompt=PLAN_SYSTEM_PROMPT + (" " + _GUIDE_RULE() if guides else ""),
            messages=[UserMessage(content=_prompt(title, request, desired_output, guides))],
            options=GenerationOptions(max_tokens=400),
        ),
        context=GenerationContext(flow=LLMFlow.CHAT_RESPONSE),
    )
    steps = parse_plan(reply.text or "")
    if not steps:
        raise PlanError("The model did not return a numbered plan. Edit the request and start again.")
    return PlanResult(steps=steps, route_kind=decision.kind, **_tokens(reply))


def _GUIDE_RULE() -> str:  # noqa: N802 - the same rule as the drafter's, read lazily to avoid an import cycle
    from nortpole.work.tasks.drafter import GUIDE_RULE

    return GUIDE_RULE


def draft_agent_plan(db_session: Session, user: User, title: str, request: str, desired_output: str, agent) -> PlanResult:  # type: ignore[no-untyped-def]
    """A workflow agent's plan: only named tool steps, within its limit (see packs/agents.py)."""
    from nortpole.work.packs.agents import parse_agent_plan, plan_prompt, plan_system_prompt

    llm = get_default_llm()
    decision = enforce_route(db_session, llm.config.model_configuration_id, actor=user, purpose="task_plan")
    reply = llm.invoke(
        GenerationRequest(
            system_prompt=plan_system_prompt(agent),
            messages=[UserMessage(content=plan_prompt(title, request, desired_output, agent))],
            options=GenerationOptions(max_tokens=300),
        ),
        context=GenerationContext(flow=LLMFlow.CHAT_RESPONSE),
    )
    steps = parse_agent_plan(reply.text or "", agent)
    if not steps:
        raise PlanError("The agent did not propose any search it is allowed to run. Edit the request and start again.")
    return PlanResult(steps=steps, route_kind=decision.kind, **_tokens(reply))


def _tokens(reply) -> dict[str, int]:  # type: ignore[no-untyped-def]
    """The call's token counts, for a scheduled run's cost. Zero when the provider reports none."""
    u = getattr(reply, "usage", None)

    def count(name: str) -> int:
        v = getattr(u, name, 0)
        return v if isinstance(v, int) and not isinstance(v, bool) else 0

    return {"input_tokens": count("prompt_tokens"), "output_tokens": count("completion_tokens")}
