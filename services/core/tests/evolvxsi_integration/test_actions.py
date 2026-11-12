"""Outbound actions on the real database, delivered to a local webhook sink."""

import json
import threading
import uuid
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
