"""Approving one exact draft, and exporting it after a fresh access check, on
the real database."""

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import text

from evolvxsi.db.engine.sql_engine import get_session_with_current_tenant
from evolvxsi.db.enums import AccessType
from evolvxsi.db.models import (
    Connector,
    ConnectorCredentialPair,
    Credential,
    Document,
    DocumentByConnectorCredentialPair,
    User,
    User__UserGroup,
    UserGroup,
    UserGroup__CCPairDataAccess,
)
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.tasks import api
from evolvxsi.tasks.drafter import DraftResult
from evolvxsi.tasks.evidence import Evidence
from evolvxsi.tasks.models import EvolvXSITask
from evolvxsi.tasks.planner import PlanResult
from evolvxsi.tasks.states import TaskState
from tests.evolvxsi_integration.test_group_access import _doc, _source
from tests.evolvxsi_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres with the task table")
RUN = uuid.uuid4().hex[:8]
DOC = f"appr-doc-{RUN}"


@pytest.fixture(scope="module")
def world():  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u = User(id=uuid.uuid4(), email=f"approver-{RUN}@example.com", hashed_password="x", is_active=True, is_verified=True)
        g = UserGroup(name=f"appr-group-{RUN}", is_up_to_date=True)
        s.add_all([u, g])
        s.flush()
        c, cr, cc = _source(s, f"appr{RUN}", AccessType.PRIVATE)
        s.add_all([User__UserGroup(user_id=u.id, user_group_id=g.id),
                   UserGroup__CCPairDataAccess(cc_pair_id=cc.id, user_group_id=g.id, access_type=AccessType.PRIVATE)])
        _doc(s, DOC, c, cr)
        s.commit()
        ids = {"u": u.id, "g": g.id, "cc": cc.id, "c": c.id, "cr": cr.id}
    yield ids
    with get_session_with_current_tenant() as s:
        s.query(EvolvXSITask).filter_by(owner_id=ids["u"]).delete()
        s.query(DocumentByConnectorCredentialPair).filter_by(id=DOC).delete()
        s.query(Document).filter_by(id=DOC).delete()
        s.query(UserGroup__CCPairDataAccess).filter_by(cc_pair_id=ids["cc"]).delete()
        s.query(User__UserGroup).filter_by(user_group_id=ids["g"]).delete()
        s.query(ConnectorCredentialPair).filter_by(id=ids["cc"]).delete()
        s.query(Credential).filter_by(id=ids["cr"]).delete()
        s.query(Connector).filter_by(id=ids["c"]).delete()
        s.query(UserGroup).filter_by(id=ids["g"]).delete()
        s.execute(text("delete from evolvxsi_audit_event where actor_email = :e"), {"e": f"approver-{RUN}@example.com"})
        s.query(User).filter_by(id=ids["u"]).delete()
        s.commit()


def _ready(s, uid):  # type: ignore[no-untyped-def]
    """A task with a draft that cites the test document."""
    u = s.get(User, uid)
    t = api.create_draft(api.TaskDraft(title="Receipt rules", request="When are receipts due?"), user=u, db_session=s)
    with patch.object(api, "draft_plan", return_value=PlanResult(["Find", "Draft"], "local")):
        t = api.start_task(t.id, api.VersionOnly(version=t.version), user=u, db_session=s)
    t = api.accept_plan(t.id, api.VersionOnly(version=t.version), user=u, db_session=s)
    ev = [Evidence(n=1, doc_id=DOC, title="Receipt rules doc", link="https://example.com/r", passage="Due in 30 days.")]
    with patch.object(api, "gather_evidence", return_value=ev), \
         patch.object(api, "draft_answer", return_value=DraftResult("Receipts are due in 30 days [1].", [1], 0, "local")):
        t = api.run_task(t.id, api.VersionOnly(version=t.version), user=u, db_session=s)
    assert t.state is TaskState.DRAFT_READY and t.draft_hash
    return u, t


def test_approval_must_name_the_exact_draft(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t = _ready(s, world["u"])
        with pytest.raises(EvolvXSIError):
            api.approve_draft(t.id, api.Approve(version=t.version, draft_hash="0" * 64), user=u, db_session=s)
        ok = api.approve_draft(t.id, api.Approve(version=t.version, draft_hash=t.draft_hash), user=u, db_session=s)
        assert ok.state is TaskState.APPROVED and ok.approved_hash == t.draft_hash


def test_export_gives_markdown_with_the_cited_source(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t = _ready(s, world["u"])
        a = api.approve_draft(t.id, api.Approve(version=t.version, draft_hash=t.draft_hash), user=u, db_session=s)
        out = api.export_draft(t.id, api.VersionOnly(version=a.version), user=u, db_session=s)
        assert out.filename == "Receipt-rules.md"
        assert "Receipts are due in 30 days [1]." in out.markdown
        assert "1. [Receipt rules doc](https://example.com/r)" in out.markdown
        assert out.task.exported_at is not None


def test_export_needs_approval(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t = _ready(s, world["u"])
        with pytest.raises(EvolvXSIError):
            api.export_draft(t.id, api.VersionOnly(version=t.version), user=u, db_session=s)


def test_revise_from_a_ready_draft_clears_the_way_for_a_new_run(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t = _ready(s, world["u"])
        back = api.revise_plan(t.id, api.Revise(version=t.version, note="Add the flight rules"), user=u, db_session=s)
        assert back.state is TaskState.DRAFT and back.revision_note == "Add the flight rules"


def test_export_is_withheld_once_access_to_a_cited_source_is_gone(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t = _ready(s, world["u"])
        a = api.approve_draft(t.id, api.Approve(version=t.version, draft_hash=t.draft_hash), user=u, db_session=s)
        s.query(User__UserGroup).filter_by(user_id=world["u"], user_group_id=world["g"]).delete()
        s.commit()
        try:
            with pytest.raises(EvolvXSIError) as err:
                api.export_draft(t.id, api.VersionOnly(version=a.version), user=u, db_session=s)
            assert "withheld" in err.value.detail and "Receipt rules doc" not in err.value.detail
            denied = s.execute(text("select count(*) from evolvxsi_audit_event where actor_email = :e and action = 'task.export' and outcome = 'denied'"),
                               {"e": f"approver-{RUN}@example.com"}).scalar()
            assert denied >= 1
        finally:
            s.add(User__UserGroup(user_id=world["u"], user_group_id=world["g"]))
            s.commit()
