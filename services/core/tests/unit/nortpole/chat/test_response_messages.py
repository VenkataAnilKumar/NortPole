"""Saved messages retain identity, completion, and explicit answer selection."""

import pytest

from nortpole.agents.models import RunStatus, StepResult
from nortpole.agents.runtime import Agent, Run
from nortpole.chat.response import response_record, response_snapshot
from nortpole.llm.cancellation import AgentCancelled, CancellationSignal
from nortpole.llm.interfaces import GenerationContext
from nortpole.llm.models import AssistantMessage, GenerationRequest, TextContent
from nortpole.tracing.flows import LLMFlow
from tests.unit.nortpole.agents.fakes import FakeModelClient, run_agent


def test_harness_selects_answer_and_message_ids_survive_restore() -> None:
    replies = iter(
        [
            AssistantMessage(content=[TextContent(text="Checking the context")]),
            AssistantMessage(content=[TextContent(text="The answer")]),
        ]
    )

    def after_step(result: StepResult) -> bool:
        return result.message.text != "The answer"

    agent = Agent(
        FakeModelClient(lambda _request, _signal: next(replies)),
        generation_context=GenerationContext(flow=LLMFlow.CHAT_RESPONSE),
        after_step=after_step,
    )
    runs: list[Run] = []
    run_agent(agent, max_steps=2, runs=runs)
    snapshot = runs[0].snapshot()
    record = response_record(snapshot)
    assert record.answer_step_index == 1
    restored = response_snapshot(record)
    assert restored.messages == snapshot.messages
    assert restored.steps == snapshot.steps
    assert restored.answer_step_index == snapshot.answer_step_index
    assert snapshot.answer_step_index == 1


def test_empty_cancelled_generation_survives_storage_round_trip() -> None:
    def cancel(
        _request: GenerationRequest, _signal: CancellationSignal
    ) -> AssistantMessage:
        raise AgentCancelled()

    runs: list[Run] = []
    with pytest.raises(AgentCancelled):
        run_agent(
            Agent(
                FakeModelClient(cancel),
                generation_context=GenerationContext(flow=LLMFlow.CHAT_RESPONSE),
            ),
            max_steps=1,
            runs=runs,
        )
    snapshot = runs[0].snapshot()
    record = response_record(snapshot)
    assert record.answer_step_index is None
    assert len(record.messages) == 1
    assert record.steps[0].generation_status == RunStatus.CANCELLED
    assert response_snapshot(record).messages == snapshot.messages
