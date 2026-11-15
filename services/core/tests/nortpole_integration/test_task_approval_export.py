"""Approving one exact draft, and exporting it after a fresh access check, on
the real database."""

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import text

from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.enums import AccessType
from nortpole.db.models import (
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
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.work.tasks import api
from nortpole.work.tasks.drafter import DraftResult
from nortpole.work.tasks.evidence import Evidence
from nortpole.work.tasks.models import NortPoleTask
from nortpole.work.tasks.planner import PlanResult
from nortpole.work.tasks.states import TaskState
from tests.nortpole_integration.test_group_access import _doc, _source
from tests.nortpole_integration.test_tasks_flow import _up

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
        s.query(NortPoleTask).filter_by(owner_id=ids["u"]).delete()
        s.query(DocumentByConnectorCredentialPair).filter_by(id=DOC).delete()
        s.query(Document).filter_by(id=DOC).delete()
        s.query(UserGroup__CCPairDataAccess).filter_by(cc_pair_id=ids["cc"]).delete()
        s.query(User__UserGroup).filter_by(user_group_id=ids["g"]).delete()
        s.query(ConnectorCredentialPair).filter_by(id=ids["cc"]).delete()
        s.query(Credential).filter_by(id=ids["cr"]).delete()
        s.query(Connector).filter_by(id=ids["c"]).delete()
        s.query(UserGroup).filter_by(id=ids["g"]).delete()
        s.execute(text("delete from nortpole_audit_event where actor_email = :e and row_hash is null"), {"e": f"approver-{RUN}@example.com"})
        s.query(User).filter_by(id=ids["u"]).delete()
        s.commit()


def _ready(s, uid, draft="Receipts are due in 30 days [1]."):  # type: ignore[no-untyped-def]
    """A task with a draft that cites the test document."""
    u = s.get(User, uid)
    t = api.create_draft(api.TaskDraft(title="Receipt rules", request="When are receipts due?"), user=u, db_session=s)
    with patch.object(api, "draft_plan", return_value=PlanResult(["Find", "Draft"], "local")):
        t = api.start_task(t.id, api.VersionOnly(version=t.version), user=u, db_session=s)
    t = api.accept_plan(t.id, api.VersionOnly(version=t.version), user=u, db_session=s)
    ev = [Evidence(n=1, doc_id=DOC, title="Receipt rules doc", link="https://example.com/r", passage="Due in 30 days.")]
    # The relevance check asks the live model; these tests are about approval and export, so it is left out.
    with patch.object(api, "gather_evidence", return_value=ev), patch.object(api, "filter_relevant", side_effect=lambda *a, **k: a[-1]), \
         patch.object(api, "draft_answer", return_value=DraftResult(draft, [1], 0, "local")):
        t = api.run_task(t.id, api.VersionOnly(version=t.version), user=u, db_session=s)
    assert t.state is TaskState.DRAFT_READY and t.draft_hash
    return u, t


def test_approval_must_name_the_exact_draft(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t = _ready(s, world["u"])
        with pytest.raises(NortPoleError):
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
        with pytest.raises(NortPoleError):
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
            with pytest.raises(NortPoleError) as err:
                api.export_draft(t.id, api.VersionOnly(version=a.version), user=u, db_session=s)
            assert "withheld" in err.value.detail and "Receipt rules doc" not in err.value.detail
            denied = s.execute(text("select count(*) from nortpole_audit_event where actor_email = :e and action = 'task.export' and outcome = 'denied'"),
                               {"e": f"approver-{RUN}@example.com"}).scalar()
            assert denied >= 1
        finally:
            s.add(User__UserGroup(user_id=world["u"], user_group_id=world["g"]))
            s.commit()


MIXED = "Receipts are due in 30 days [1]. Late receipts are probably fine. Ask finance if unsure."


def test_approval_waits_for_every_unsupported_claim(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t = _ready(s, world["u"], MIXED)
        assert [c["status"] for c in t.draft_claims] == ["supported", "unsupported", "unsupported"]
        with pytest.raises(NortPoleError) as err:
            api.approve_draft(t.id, api.Approve(version=t.version, draft_hash=t.draft_hash), user=u, db_session=s)
        assert "2 unsupported" in err.value.detail


def test_keep_and_remove_shape_the_approved_export(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t = _ready(s, world["u"], MIXED)
        old_hash = t.draft_hash
        t = api.decide_claim(t.id, 1, api.ClaimDecision(version=t.version, decision="remove"), user=u, db_session=s)
        t = api.decide_claim(t.id, 2, api.ClaimDecision(version=t.version, decision="keep"), user=u, db_session=s)
        assert "probably fine" not in t.draft_text and t.draft_hash != old_hash
        with pytest.raises(NortPoleError):
            api.approve_draft(t.id, api.Approve(version=t.version, draft_hash=old_hash), user=u, db_session=s)
        a = api.approve_draft(t.id, api.Approve(version=t.version, draft_hash=t.draft_hash), user=u, db_session=s)
        out = api.export_draft(t.id, api.VersionOnly(version=a.version), user=u, db_session=s)
        assert "probably fine" not in out.markdown
        assert "Ask finance if unsure. _(unsupported)_" in out.markdown
        assert "Receipts are due in 30 days [1]." in out.markdown


def test_supported_claims_need_no_decision(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t = _ready(s, world["u"], MIXED)
        with pytest.raises(NortPoleError):
            api.decide_claim(t.id, 0, api.ClaimDecision(version=t.version, decision="keep"), user=u, db_session=s)


def test_editing_a_draft_makes_a_new_version_and_keeps_history(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t = _ready(s, world["u"], MIXED)
        assert t.draft_version == 1 and len(t.draft_versions) == 1 and t.draft_versions[0]["by"] == "model"
        t = api.decide_claim(t.id, 2, api.ClaimDecision(version=t.version, decision="keep"), user=u, db_session=s)
        old_hash = t.draft_hash
        edited = "Receipts are due in 30 days [1]. Late receipts need a manager's note. Ask finance if unsure."
        t2 = api.edit_ready_draft(t.id, api.DraftEdit(version=t.version, text=edited), user=u, db_session=s)
        assert t2.draft_version == 2 and [v["by"] for v in t2.draft_versions] == ["model", "owner"]
        assert t2.draft_versions[0]["text"] == MIXED, "the first version stays readable"
        decisions = {c["text"]: c["decision"] for c in t2.draft_claims}
        assert decisions["Ask finance if unsure."] == "keep", "unchanged sentence keeps its decision"
        assert decisions["Late receipts need a manager's note."] is None, "an edited sentence needs a new decision"
        with pytest.raises(NortPoleError):
            api.approve_draft(t.id, api.Approve(version=t2.version, draft_hash=old_hash), user=u, db_session=s)


def test_an_edit_may_only_cite_this_runs_sources(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t = _ready(s, world["u"])
        with pytest.raises(NortPoleError) as err:
            api.edit_ready_draft(t.id, api.DraftEdit(version=t.version, text="Something [4]."), user=u, db_session=s)
        assert "[4]" in err.value.detail


def test_export_uses_the_edited_draft_and_updates_cited_sources(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t = _ready(s, world["u"])
        t = api.edit_ready_draft(t.id, api.DraftEdit(version=t.version, text="Receipts are due within a month."), user=u, db_session=s)
        assert not t.draft_sources[0]["cited"], "the edit no longer cites the source"
        t = api.decide_claim(t.id, 0, api.ClaimDecision(version=t.version, decision="keep"), user=u, db_session=s)
        a = api.approve_draft(t.id, api.Approve(version=t.version, draft_hash=t.draft_hash), user=u, db_session=s)
        out = api.export_draft(t.id, api.VersionOnly(version=a.version), user=u, db_session=s)
        assert "Receipts are due within a month. _(unsupported)_" in out.markdown
        assert "_No sources were cited._" in out.markdown


def test_a_draft_is_hidden_once_access_to_a_cited_source_is_gone(world) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t = _ready(s, world["u"])
        assert t.draft_text and not t.withheld
        s.query(User__UserGroup).filter_by(user_id=world["u"], user_group_id=world["g"]).delete()
        s.commit()
        try:
            hidden = api.get_task(t.id, user=u, db_session=s)
            assert hidden.withheld and "no longer open" in hidden.withheld_message
            assert hidden.draft_text is None and hidden.draft_sources is None and hidden.draft_claims is None
            assert hidden.title == t.title, "the owner still sees their own request"
            assert all(x.draft_text is None for x in api.list_tasks(user=u, db_session=s) if x.id == t.id)
            for call in (
                lambda: api.approve_draft(t.id, api.Approve(version=t.version, draft_hash=t.draft_hash), user=u, db_session=s),
                lambda: api.edit_ready_draft(t.id, api.DraftEdit(version=t.version, text="new text"), user=u, db_session=s),
            ):
                with pytest.raises(NortPoleError):
                    call()
        finally:
            s.add(User__UserGroup(user_id=world["u"], user_group_id=world["g"]))
            s.commit()
        back = api.get_task(t.id, user=u, db_session=s)
        assert not back.withheld and back.draft_text, "access restored, the draft is visible again"
