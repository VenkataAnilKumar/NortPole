"""Chat proposals on Postgres and the confirmed workflow worker."""

import datetime as dt
from unittest.mock import patch

import pytest
from sqlalchemy import select

from nortpole.agents.tools import ToolInvocation
from nortpole.configs.constants import MessageType
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.enums import Permission
from nortpole.db.models import ChatMessage, ChatSession, User
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.llm.cancellation import CancellationSignal
from nortpole.llm.models import ToolResult
from nortpole.tools.models import ToolContext
from nortpole.work.tasks import api as tasks_api
from nortpole.work.workflow_schedules import api, chat_tools, controls, proposals
from nortpole.work.workflow_schedules.models import NortPoleWorkflowRun, NortPoleWorkflowSchedule
from tests.nortpole_integration.test_tasks_flow import _up
from tests.nortpole_integration.test_workflow_schedules import PLAN, world  # noqa: F401

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")


def _chat(db, owner):  # type: ignore[no-untyped-def]
    owner.effective_permissions = [Permission.BASIC_ACCESS.value]
    chat = ChatSession(user_id=owner.id)
    db.add(chat)
    db.flush()
    message = ChatMessage(chat_session_id=chat.id, message="Schedule this", token_count=2, message_type=MessageType.USER)
    db.add(message)
    db.commit()
    return chat.id, message.id


def _create_args() -> proposals.CreateScheduleArguments:
    return proposals.CreateScheduleArguments(
        name="Weekly policy update", request="Summarize policy changes.",
        desired_output="A cited summary", cadence="weekly", weekday=4, at_time="09:00",
        timezone="America/Toronto",
    )


def test_create_proposal_executes_once_after_owner_confirmation(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as db:
        owner = db.get(User, world["ann"])
        other = db.get(User, world["bob"])
        chat_id, message_id = _chat(db, owner)
        available = chat_tools.tools_for(owner, chat_id, message_id, set())
        tool = next(tool for tool in available if tool.name == "propose_schedule")
        assert "timezone" in tool.tool_definition().parameters["required"]
        for _ in range(2):
            result = tool.bind(ToolContext).execute(ToolInvocation(
                call_id="propose", arguments=_create_args().model_dump(mode="json"),
                cancellation=CancellationSignal(), update=lambda _: None,
            ))
            assert isinstance(result, ToolResult) and not result.is_error
        proposal, = proposals.list_proposals(chat_id, user=owner, db=db)
        assert proposal.state == "pending"
        assert proposal.preview.when == "Fridays at 09:00 (America/Toronto)"
        assert proposal.preview.request == "Summarize policy changes."
        assert not api.list_mine(user=owner, db_session=db).schedules
        with pytest.raises(NortPoleError, match="not found"):
            proposals.list_proposals(chat_id, user=other, db=db)
        with pytest.raises(NortPoleError, match="not found"):
            proposals.decide_proposal(proposal.id, "confirm", user=other, db=db)
        with patch.object(proposals.celery_app, "send_task") as enqueue:
            for _ in range(2):
                assert proposals.decide_proposal(proposal.id, "confirm", user=owner, db=db).state == "queued"
        enqueue.assert_called_once()
        for _ in range(2):
            proposals.process_confirmed(proposal.id)
        saved, = api.list_mine(user=owner, db_session=db).schedules
        completed, = proposals.list_proposals(chat_id, user=owner, db=db)
        assert completed.state == "completed"
        assert completed.result.schedule_id == saved.id
        assert saved.when == proposal.preview.when


def test_confirmed_run_honors_version_and_scheduling_access(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as db:
        owner = db.get(User, world["ann"])
        chat_id, msg = _chat(db, owner)
        saved = api.create_schedule(
            api.NewSchedule(**_create_args().model_dump(), title="Policy"), user=owner, db_session=db,
        )
        args = proposals.RunScheduleArguments(schedule_name=saved.name.lower())
        proposals.propose(db, owner, chat_id, msg, args)
        first, = proposals.list_proposals(chat_id, user=owner, db=db)
        assert first.preview.schedule_id == saved.id

        with patch.object(proposals.celery_app, "send_task"):
            queued = proposals.decide_proposal(first.id, "confirm", user=owner, db=db)
            run = db.get(NortPoleWorkflowRun, queued.result.run_id)
            assert (run.trigger, run.outcome, run.started_at) == ("chat", "queued", None)
            controls.save(controls.ScheduleControls(enabled=False))
            proposals.process_confirmed(first.id)
            assert proposals.list_proposals(chat_id, user=owner, db=db)[0].state == "failed"

            controls.save(controls.ScheduleControls(enabled=True))
            changed = db.get(NortPoleWorkflowSchedule, saved.id)
            changed.version += 1
            db.commit()
            proposals.propose(db, owner, chat_id, msg, args)
            second = proposals.list_proposals(chat_id, user=owner, db=db)[0]
            proposals.decide_proposal(second.id, "confirm", user=owner, db=db)
            changed.version += 1
            db.commit()
            proposals.process_confirmed(second.id)
            assert proposals.list_proposals(chat_id, user=owner, db=db)[0].state == "failed"

            proposals.propose(db, owner, chat_id, msg, args)
            latest = proposals.list_proposals(chat_id, user=owner, db=db)[0]
            proposals.decide_proposal(latest.id, "confirm", user=owner, db=db)
        with patch.object(tasks_api, "draft_plan", return_value=PLAN):
            proposals.process_confirmed(latest.id)
            proposals.process_confirmed(latest.id)
        done = proposals.list_proposals(chat_id, user=owner, db=db)[0]
        assert (done.state, done.result.outcome) == ("completed", "plan_ready")
        runs = db.scalars(select(NortPoleWorkflowRun).where(
            NortPoleWorkflowRun.schedule_id == saved.id,
        ).execution_options(populate_existing=True)).all()
        assert sorted(run.outcome for run in runs) == ["failed", "failed", "plan_ready"]
        completed = db.get(NortPoleWorkflowRun, done.result.run_id)
        assert completed.trigger == "chat"
        assert completed.fired_at <= completed.started_at <= completed.completed_at
        db.refresh(changed)
        assert changed.next_run_at == saved.next_run_at


def test_expired_and_dismissed_proposals_cannot_execute(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as db:
        owner = db.get(User, world["ann"])
        chat_id, msg = _chat(db, owner)
        for name in ["Expired", "Dismissed"]:
            proposals.propose(db, owner, chat_id, msg, _create_args().model_copy(update={"name": name}))
        dismissed, expired = proposals.list_proposals(chat_id, user=owner, db=db)
        row = db.get(proposals.ScheduleProposal, expired.id)
        row.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
        db.commit()

        assert proposals.decide_proposal(dismissed.id, "dismiss", user=owner, db=db).state == "dismissed"
        assert proposals.decide_proposal(dismissed.id, "confirm", user=owner, db=db).state == "dismissed"
        assert proposals.decide_proposal(expired.id, "confirm", user=owner, db=db).state == "expired"
        proposals.process_confirmed(dismissed.id)
        proposals.process_confirmed(expired.id)
        assert not api.list_mine(user=owner, db_session=db).schedules
