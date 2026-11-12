"""Outbound actions on the real database, delivered to a local webhook sink."""

import json
import threading
import uuid
from types import SimpleNamespace
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from sqlalchemy import text

from evolvxsi.actions import api as actions
from evolvxsi.actions.delivery import UnsafeTarget, check_target_url
from evolvxsi.actions.models import EvolvXSIAction, EvolvXSIActionTarget
from evolvxsi.db.engine.sql_engine import get_session_with_current_tenant
from evolvxsi.db.models import User, User__UserGroup
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.tasks import api as tasks
from tests.evolvxsi_integration.test_task_approval_export import _ready, world  # noqa: F401  (fixture)
from tests.evolvxsi_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres with the action tables")


class Sink:
    """Records every request; answers with whatever status it is told to."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.statuses: list[int] = []
        sink = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):  # type: ignore[no-untyped-def]
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                sink.requests.append({"key": self.headers.get("Idempotency-Key"), "body": body})
                code = sink.statuses.pop(0) if sink.statuses else 200
                self.send_response(code)
                self.end_headers()
                self.wfile.write(b"ignored response body")

            def log_message(self, *a):  # type: ignore[no-untyped-def]
                pass

        self.server = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_port}/hook"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        self.server.shutdown()


@pytest.fixture()
def sink():  # type: ignore[no-untyped-def]
    s = Sink()
    yield s
    s.stop()


@pytest.fixture()
def target(sink):  # type: ignore[no-untyped-def]
    name = f"sink-{uuid.uuid4().hex[:8]}"
    with get_session_with_current_tenant() as s:
        t = EvolvXSIActionTarget(name=name, url=sink.url, allowed_data_classes=["confidential", "internal", "public"], enabled=True)
        s.add(t)
        s.commit()
        tid = t.id
    yield tid
    with get_session_with_current_tenant() as s:
        s.query(EvolvXSIAction).filter_by(target_id=tid).delete()
        s.query(EvolvXSIActionTarget).filter_by(id=tid).delete()
        s.commit()


def _approved_task(s, uid):  # type: ignore[no-untyped-def]
    u, t = _ready(s, uid)
    t = tasks.approve_draft(t.id, tasks.Approve(version=t.version, draft_hash=t.draft_hash), user=u, db_session=s)
    return u, t


def _approved_action(s, uid, tid):  # type: ignore[no-untyped-def]
    u, t = _approved_task(s, uid)
    a = actions.propose_action(t.id, actions.Propose(target_id=tid), user=u, db_session=s)
    a = actions.approve_action(a.id, actions.ApproveAction(version=a.version, fingerprint=a.fingerprint), user=u, db_session=s)
    return u, t, a


def test_only_an_approved_draft_can_be_proposed(world, target) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t = _ready(s, world["u"])  # a ready draft, not yet approved
        with pytest.raises(EvolvXSIError):
            actions.propose_action(t.id, actions.Propose(target_id=target), user=u, db_session=s)


def test_the_payload_is_built_from_the_draft_and_nothing_is_sent_before_approval(world, target, sink) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t = _approved_task(s, world["u"])
        a = actions.propose_action(t.id, actions.Propose(target_id=target), user=u, db_session=s)
        assert a.state == "proposed" and "Receipts are due in 30 days" in a.payload["markdown"]
        with pytest.raises(EvolvXSIError):
            actions.execute_action(a.id, actions.VersionOnly(version=a.version), user=u, db_session=s)
    assert sink.requests == []


def test_approval_must_name_the_exact_payload(world, target) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t = _approved_task(s, world["u"])
        a = actions.propose_action(t.id, actions.Propose(target_id=target), user=u, db_session=s)
        with pytest.raises(EvolvXSIError):
            actions.approve_action(a.id, actions.ApproveAction(version=a.version, fingerprint="0" * 64), user=u, db_session=s)


def test_an_approved_action_is_sent_once_with_a_request_key(world, target, sink) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t, a = _approved_action(s, world["u"], target)
        done = actions.execute_action(a.id, actions.VersionOnly(version=a.version), user=u, db_session=s)
        assert done.state == "succeeded" and done.result_status == 200 and done.attempts == 1
        assert len(sink.requests) == 1 and sink.requests[0]["key"] and "Receipts are due" in sink.requests[0]["body"]["markdown"]
        with pytest.raises(EvolvXSIError):
            actions.execute_action(a.id, actions.VersionOnly(version=done.version), user=u, db_session=s)
        assert len(sink.requests) == 1, "a second send must not reach the target"
        assert "ignored response body" not in json.dumps(done.model_dump(mode="json")), "the response body is not stored"


def test_a_failed_send_can_be_retried_with_the_same_key(world, target, sink) -> None:  # type: ignore[no-untyped-def]
    sink.statuses = [500, 200]
    with get_session_with_current_tenant() as s:
        u, t, a = _approved_action(s, world["u"], target)
        failed = actions.execute_action(a.id, actions.VersionOnly(version=a.version), user=u, db_session=s)
        assert failed.state == "failed" and failed.result_status == 500 and failed.attempts == 1
        ok = actions.execute_action(a.id, actions.VersionOnly(version=failed.version), user=u, db_session=s)
        assert ok.state == "succeeded" and ok.attempts == 2
    assert len(sink.requests) == 2 and sink.requests[0]["key"] == sink.requests[1]["key"]


def test_policy_blocks_a_data_class_the_target_does_not_allow(world, target, sink) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t, a = _approved_action(s, world["u"], target)
        s.query(EvolvXSIActionTarget).filter_by(id=target).update({"allowed_data_classes": ["public"]})
        s.commit()
        with pytest.raises(EvolvXSIError) as err:
            actions.execute_action(a.id, actions.VersionOnly(version=a.version), user=u, db_session=s)
        assert "Blocked by policy" in err.value.detail
        denied = s.execute(text("select count(*) from evolvxsi_audit_event where action='action.execute' and outcome='denied' and actor_email like 'approver-%'")).scalar()
        assert denied >= 1
    assert sink.requests == []


def test_a_disabled_target_blocks_the_send(world, target, sink) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t, a = _approved_action(s, world["u"], target)
        s.query(EvolvXSIActionTarget).filter_by(id=target).update({"enabled": False})
        s.commit()
        with pytest.raises(EvolvXSIError):
            actions.execute_action(a.id, actions.VersionOnly(version=a.version), user=u, db_session=s)
    assert sink.requests == []


def test_losing_access_to_a_cited_source_blocks_the_send(world, target, sink) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t, a = _approved_action(s, world["u"], target)
        s.query(User__UserGroup).filter_by(user_id=world["u"], user_group_id=world["g"]).delete()
        s.commit()
        try:
            with pytest.raises(EvolvXSIError) as err:
                actions.execute_action(a.id, actions.VersionOnly(version=a.version), user=u, db_session=s)
            assert "no longer open" in err.value.detail
        finally:
            s.add(User__UserGroup(user_id=world["u"], user_group_id=world["g"]))
            s.commit()
    assert sink.requests == []


def test_an_expired_approval_is_refused(world, target, sink) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t, a = _approved_action(s, world["u"], target)
        s.execute(text("update evolvxsi_action set approved_at = now() - interval '31 minutes' where id = :i"), {"i": str(a.id)})
        s.commit()
        with pytest.raises(EvolvXSIError) as err:
            actions.execute_action(a.id, actions.VersionOnly(version=a.version), user=u, db_session=s)
        assert "expired" in err.value.detail
    assert sink.requests == []


def test_audit_holds_the_fingerprint_but_not_the_draft_text(world, target, sink) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t, a = _approved_action(s, world["u"], target)
        actions.execute_action(a.id, actions.VersionOnly(version=a.version), user=u, db_session=s)
        rows = s.execute(text("select summary, details::text from evolvxsi_audit_event where resource_id = :i"), {"i": str(a.id)}).all()
        blob = " ".join(f"{x} {y}" for x, y in rows)
        assert a.fingerprint in blob and "Receipts are due" not in blob and len(rows) >= 3


def test_another_user_cannot_see_or_send_the_action(world, target, sink) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t, a = _approved_action(s, world["u"], target)
        other = User(id=uuid.uuid4(), email=f"other-act-{uuid.uuid4().hex[:6]}@example.com", hashed_password="x", is_active=True, is_verified=True)
        s.add(other)
        s.commit()
        try:
            with pytest.raises(EvolvXSIError):
                actions.execute_action(a.id, actions.VersionOnly(version=a.version), user=other, db_session=s)
            with pytest.raises(EvolvXSIError):
                actions.list_actions(t.id, user=other, db_session=s)
        finally:
            s.query(User).filter_by(id=other.id).delete()
            s.commit()
    assert sink.requests == []


@pytest.mark.parametrize("url", ["http://169.254.169.254/latest/meta-data/", "ftp://example.com/x", "http://0.0.0.0/x", "not a url"])
def test_unsafe_target_urls_are_refused(url: str) -> None:
    with pytest.raises(UnsafeTarget):
        check_target_url(url)


def test_a_loopback_target_is_allowed_for_local_testing() -> None:
    check_target_url("http://127.0.0.1:9/x")


def test_an_email_target_sends_the_approved_draft_to_its_fixed_recipients(world) -> None:  # type: ignore[no-untyped-def]
    from unittest.mock import patch

    from evolvxsi.configs import app_configs as cfg
    from tests.unit.evolvxsi.actions.test_email import _Sink

    admin = SimpleNamespace(id=uuid.uuid4(), email="mail-admin@example.com")
    with get_session_with_current_tenant() as s:
        for bad in ("mailto:nobody", "http://example.com/x"):
            with pytest.raises(EvolvXSIError):
                actions.create_target(actions.TargetIn(name=f"bad-{uuid.uuid4().hex[:6]}", kind="email", url=bad,
                                                       allowed_data_classes=["confidential"]), user=admin, db_session=s)
        view = actions.create_target(actions.TargetIn(name=f"mail-{uuid.uuid4().hex[:8]}", kind="email", url="mailto:finance@example.com",
                                                      allowed_data_classes=["confidential", "internal", "public"]), user=admin, db_session=s)
        assert view.kind == "email"
        tid = view.id
    smtp = _Sink()
    try:
        with get_session_with_current_tenant() as s:
            u, t, a = _approved_action(s, world["u"], tid)
            with patch.object(cfg, "SMTP_SERVER", "127.0.0.1"), patch.object(cfg, "SMTP_PORT", smtp.port), \
                 patch.object(cfg, "SMTP_STARTTLS", False), patch.object(cfg, "SMTP_USER", ""), patch.object(cfg, "EMAIL_FROM", "noreply@example.com"):
                done = actions.execute_action(a.id, actions.VersionOnly(version=a.version), user=u, db_session=s)
            assert done.state == "succeeded"
            assert smtp.rcpt == ["finance@example.com"] and "Receipts are due" in smtp.data
    finally:
        with get_session_with_current_tenant() as s:
            s.query(EvolvXSIAction).filter_by(target_id=tid).delete()
            s.query(EvolvXSIActionTarget).filter_by(id=tid).delete()
            s.commit()


def _set_tier(tid: int, tier: str) -> None:
    with get_session_with_current_tenant() as s:
        s.query(EvolvXSIActionTarget).filter_by(id=tid).update({"tier": tier})
        s.commit()


def test_a_read_only_destination_refuses_proposals_and_audits_it(world, target) -> None:  # type: ignore[no-untyped-def]
    _set_tier(target, "read_only")
    with get_session_with_current_tenant() as s:
        u, t = _approved_task(s, world["u"])
        with pytest.raises(EvolvXSIError) as err:
            actions.propose_action(t.id, actions.Propose(target_id=target), user=u, db_session=s)
        assert "read-only" in err.value.detail
        assert s.query(EvolvXSIAction).filter_by(target_id=target).count() == 0
        last = s.execute(text("select outcome, summary from evolvxsi_audit_event where action='action.propose' order by id desc limit 1")).one()
        assert last.outcome == "denied" and "read-only" in last.summary


def test_a_draft_only_destination_prepares_but_cannot_approve_or_send(world, target, sink) -> None:  # type: ignore[no-untyped-def]
    _set_tier(target, "draft_only")
    with get_session_with_current_tenant() as s:
        u, t = _approved_task(s, world["u"])
        a = actions.propose_action(t.id, actions.Propose(target_id=target), user=u, db_session=s)
        assert a.state == "proposed" and "Receipts are due" in a.payload["markdown"], "the exact content can be reviewed"
        with pytest.raises(EvolvXSIError) as err:
            actions.approve_action(a.id, actions.ApproveAction(version=a.version, fingerprint=a.fingerprint), user=u, db_session=s)
        assert "draft-only" in err.value.detail
        assert sink.requests == []


def test_lowering_the_tier_after_approval_still_stops_the_send(world, target, sink) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as s:
        u, t, a = _approved_action(s, world["u"], target)
        _set_tier(target, "draft_only")
        with pytest.raises(EvolvXSIError):
            actions.execute_action(a.id, actions.VersionOnly(version=a.version), user=u, db_session=s)
        assert sink.requests == []
        _set_tier(target, "act_with_approval")
        assert actions.execute_action(a.id, actions.VersionOnly(version=a.version), user=u, db_session=s).state == "succeeded"


def test_a_draft_only_pack_lowers_a_destination_that_would_allow_sending(world, target, sink) -> None:  # type: ignore[no-untyped-def]
    from evolvxsi.actions.autonomy import effective_tier
    from evolvxsi.packs.models import EvolvXSIPackVersion

    pid = f"tier-{uuid.uuid4().hex[:6]}"
    with get_session_with_current_tenant() as s:
        s.add(EvolvXSIPackVersion(pack_id=pid, version="1.0.0", manifest={"autonomy": "draft_only"}, digest="d", signature="s",
                                  signer_key_id="k", active=False))
        s.commit()
        try:
            assert effective_tier(s, "act_with_approval", pid, "1.0.0") == "draft_only"
            assert effective_tier(s, "read_only", pid, "1.0.0") == "read_only", "a pack never raises a destination's tier"
            assert effective_tier(s, "act_with_approval", pid, "9.9.9") == "read_only", "a missing pack version fails closed"
            assert effective_tier(s, "act_with_approval", None, None) == "act_with_approval"
        finally:
            s.query(EvolvXSIPackVersion).filter_by(pack_id=pid).delete()
            s.commit()
