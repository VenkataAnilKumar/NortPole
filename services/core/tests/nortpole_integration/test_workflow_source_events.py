"""Knowledge-trigger admission, event deduplication and access rechecks."""

import datetime as dt
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.enums import AccessType, Permission
from nortpole.db.models import (
    Connector, ConnectorCredentialPair, Credential, Document,
    DocumentByConnectorCredentialPair, DocumentSet, DocumentSet__ConnectorCredentialPair, User,
)
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.work.tasks import api as tasks_api
from nortpole.work.tasks.drafter import DraftResult
from nortpole.work.tasks.models import NortPoleTask
from nortpole.work.workflow_schedules import api, controls, runner, source_events
from nortpole.work.workflow_schedules.models import KnowledgeChange, NortPoleWorkflowRun
from tests.nortpole_integration.test_group_access import _doc, _source
from tests.nortpole_integration.test_tasks_flow import _up
from tests.nortpole_integration.test_workflow_schedules import PLAN, world  # noqa: F401

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")


@pytest.fixture()
def connected_library(world):  # type: ignore[no-untyped-def]
    tag = uuid4().hex[:10]
    doc_id = f"workflow-source-{tag}"
    with get_session_with_current_tenant() as db:
        owner = db.get(User, world["ann"])
        owner.effective_permissions = [Permission.BASIC_ACCESS.value]
        connector, credential, pair = _source(db, tag, AccessType.PUBLIC)
        library = DocumentSet(name=f"Workflow library {tag}", user_id=owner.id, is_public=True)
        db.add(library)
        db.flush()
        db.add(DocumentSet__ConnectorCredentialPair(
            document_set_id=library.id, connector_credential_pair_id=pair.id,
        ))
        _doc(db, doc_id, connector, credential)
        ids = (owner.id, library.id, pair.id, connector.id, credential.id, doc_id)
        db.commit()
    yield ids
    _, library_id, pair_id, connector_id, credential_id, doc_id = ids
    with get_session_with_current_tenant() as db:
        db.execute(delete(KnowledgeChange).where(KnowledgeChange.document_id == doc_id))
        db.execute(delete(DocumentSet__ConnectorCredentialPair).where(
            DocumentSet__ConnectorCredentialPair.document_set_id == library_id,
        ))
        db.execute(delete(DocumentSet).where(DocumentSet.id == library_id))
        db.execute(delete(DocumentByConnectorCredentialPair).where(DocumentByConnectorCredentialPair.id == doc_id))
        db.execute(delete(Document).where(Document.id == doc_id))
        db.execute(delete(ConnectorCredentialPair).where(ConnectorCredentialPair.id == pair_id))
        db.execute(delete(Credential).where(Credential.id == credential_id))
        db.execute(delete(Connector).where(Connector.id == connector_id))
        db.commit()


def _claim(db):  # type: ignore[no-untyped-def]
    source_events.claim_changes(db, dt.datetime.now(dt.timezone.utc), limit=20)


def _runs(db, schedule_id):  # type: ignore[no-untyped-def]
    return db.scalars(select(NortPoleWorkflowRun).where(
        NortPoleWorkflowRun.schedule_id == schedule_id,
    ).order_by(NortPoleWorkflowRun.fired_at, NortPoleWorkflowRun.id)).all()


def test_knowledge_changes_are_opt_in_once_per_revision_and_checked_as_owner(connected_library) -> None:  # type: ignore[no-untyped-def]
    owner_id, library_id, _, connector_id, credential_id, doc_id = connected_library
    request = api.NewSchedule(
        name="Policy changes", title="Summarize the policy", request="Summarize the triggering document.",
        cadence="source", at_time="00:00", timezone="UTC", source_library_id=library_id,
    )
    with get_session_with_current_tenant() as db:
        owner = db.get(User, owner_id)
        doc = db.get(Document, doc_id)
        doc.content_hash = "before-subscription"
        db.commit()
        with pytest.raises(NortPoleError, match="Knowledge triggers are turned off"):
            api.create_schedule(request, user=owner, db_session=db)
        db.rollback()
        controls.save(controls.load().model_copy(update={"source_events_enabled": True}))
        schedule = api.create_schedule(request, user=owner, db_session=db)
        assert schedule.next_run_at is None and schedule.source_library_id == library_id
        assert api.list_mine(user=owner, db_session=db).source_events_allowed
        _claim(db)
        assert not _runs(db, schedule.id)

        doc.content_hash = "first-change"
        db.commit()
        _claim(db)
        _claim(db)
        queued, = _runs(db, schedule.id)
        assert queued.outcome == "queued" and queued.trigger == "source"
        assert queued.source_event_id and queued.source_content_hash == "first-change"
        assert queued.source_document_id == doc_id

        pair = db.get(ConnectorCredentialPair, (connector_id, credential_id))
        pair.access_type = AccessType.PRIVATE
        db.commit()
        with patch.object(tasks_api, "draft_plan") as planner:
            skipped = runner.fire_one(db, schedule.id, run_id=queued.id)
        planner.assert_not_called()
        assert skipped.outcome == "skipped" and skipped.task_id is None
        _claim(db)
        assert len(_runs(db, schedule.id)) == 1

        pair.access_type = AccessType.PUBLIC
        doc.content_hash = "second-change"
        db.commit()
        _claim(db)
        new = _runs(db, schedule.id)[-1]
        with patch.object(tasks_api, "draft_plan", return_value=PLAN):
            planned = runner.fire_one(db, schedule.id, run_id=new.id)
        assert planned.outcome == "plan_ready"
        task = db.get(NortPoleTask, planned.task_id)
        assert task.owner_id == owner.id and task.state == "plan_review"
        assert task.knowledge_trigger.model_dump() == {
            "library_id": library_id, "document_id": doc_id, "content_hash": "second-change",
        }
        approved = tasks_api.accept_plan(task.id, tasks_api.VersionOnly(version=task.version), user=owner, db_session=db)
        doc.content_hash = "changed-after-approval"
        db.commit()
        with patch.object(tasks_api, "draft_answer") as drafter:
            result = tasks_api.run_task(task.id, tasks_api.VersionOnly(version=approved.version), user=owner, db_session=db)
        drafter.assert_not_called()
        assert result.state == "run_failed" and "triggering document changed" in result.run_error

        with pytest.raises(NortPoleError, match="This workflow starts when"):
            api.run_now(schedule.id, api.VersionOnly(version=schedule.version), user=owner, db_session=db)

        paused = api.pause_schedule(schedule.id, api.VersionOnly(version=schedule.version), user=owner, db_session=db)
        doc.content_hash = "while-paused"
        db.commit()
        resumed = api.resume_schedule(schedule.id, api.VersionOnly(version=paused.version), user=owner, db_session=db)
        assert resumed.next_run_at is None
        _claim(db)
        assert len(_runs(db, schedule.id)) == 2

        doc.content_hash = "ready-to-use"
        db.commit()
        _claim(db)
        with patch.object(tasks_api, "draft_plan", return_value=PLAN):
            next_plan = runner.fire_one(db, schedule.id, run_id=_runs(db, schedule.id)[-1].id)
        approved = tasks_api.accept_plan(
            next_plan.task_id, tasks_api.VersionOnly(version=db.get(NortPoleTask, next_plan.task_id).version),
            user=owner, db_session=db,
        )
        chunk = SimpleNamespace(
            document_id=doc_id, hidden=False, semantic_identifier="Test policy", title="Policy",
            source_links={}, content="The policy was updated.", blurb="",
        )
        draft = DraftResult("The policy was updated. [1]", [1], 0, "local")
        with (
            patch("nortpole.document_index.factory.get_default_document_index") as get_index,
            patch.object(tasks_api, "draft_answer", return_value=draft),
        ):
            get_index.return_value.id_based_retrieval.return_value = [chunk]
            completed = tasks_api.run_task(
                next_plan.task_id, tasks_api.VersionOnly(version=approved.version), user=owner, db_session=db,
            )
        request, filters = get_index.return_value.id_based_retrieval.call_args.args
        assert request[0].document_id == doc_id and filters.forced_document_set
        assert completed.state == "draft_ready" and completed.draft_sources[0]["doc_id"] == doc_id
