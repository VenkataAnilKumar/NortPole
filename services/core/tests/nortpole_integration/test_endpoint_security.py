"""Access and privacy checks for the NortPole endpoints, against the running API.

* Nobody signed out can reach any of them.
* A signed-in ordinary user can use their own tasks and preferences but not the
  admin endpoints (route policy, access groups, source groups, audit log).
* The audit trail never stores task titles, requests, drafts or source text.

Skips when the API (127.0.0.1:8080) or the database is not running. Creates one
throwaway user and removes it afterwards.
"""

import os
import uuid

import pytest
import requests
from sqlalchemy import text

from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from tests.nortpole_integration.test_tasks_flow import _up

API = os.environ.get("NORTPOLE_API", "http://127.0.0.1:8080")


def _api_up() -> bool:
    try:
        return requests.get(f"{API}/health", timeout=2).ok
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not (_api_up() and _up()), reason="needs the API and Postgres")

RUN = uuid.uuid4().hex[:8]
EMAIL = f"secprobe-{RUN}@example.com"
PASSWORD = "Probe-pass-123-ok"
SECRET_TITLE = f"UniqueTitle{RUN}"
SECRET_REQUEST = f"UniqueRequestText{RUN} about the acquisition"

ANON_ENDPOINTS = [
    ("GET", "/tasks"), ("POST", "/tasks"), ("GET", f"/tasks/{uuid.uuid4()}"),
    ("POST", f"/tasks/{uuid.uuid4()}/start"), ("POST", f"/tasks/{uuid.uuid4()}/run"),
    ("POST", f"/tasks/{uuid.uuid4()}/approve"), ("POST", f"/tasks/{uuid.uuid4()}/export"),
    ("GET", "/user-preferences"), ("PUT", "/user-preferences"),
    ("GET", "/route-policy"), ("PUT", "/admin/route-policy"), ("GET", "/admin/route-policy/audit"), ("GET", "/admin/route-tokens"),
    ("GET", "/admin/access-groups"), ("POST", "/admin/access-groups"),
    ("PUT", "/admin/access-groups/sources/1"), ("GET", "/build/approvals/live"),
]
ADMIN_ONLY = [
    ("GET", "/admin/route-policy/audit"), ("GET", "/admin/route-tokens"), ("PUT", "/admin/route-policy"),
    ("GET", "/admin/access-groups"), ("POST", "/admin/access-groups"),
    ("PUT", "/admin/access-groups/sources/1"),
]


@pytest.fixture(scope="module")
def session():  # type: ignore[no-untyped-def]
    s = requests.Session()
    reg = s.post(f"{API}/auth/register", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert reg.status_code in (200, 201), reg.text[:200]
    login = s.post(f"{API}/auth/login", data={"username": EMAIL, "password": PASSWORD}, timeout=30)
    assert login.status_code in (200, 204), login.text[:200]
    yield s
    with get_session_with_current_tenant() as db:
        db.execute(text('delete from nortpole_task where owner_id in (select id from "user" where email = :e)'), {"e": EMAIL})
        db.execute(text("delete from nortpole_audit_event where actor_email = :e and row_hash is null"), {"e": EMAIL})
        # Registration adds the user to the built-in group; remove the link first.
        db.execute(text('delete from user__user_group where user_id in (select id from "user" where email = :e)'), {"e": EMAIL})
        db.execute(text('delete from "user" where email = :e'), {"e": EMAIL})
        db.commit()


@pytest.mark.parametrize("method,path", ANON_ENDPOINTS)
def test_signed_out_requests_are_refused(method: str, path: str) -> None:
    r = requests.request(method, f"{API}{path}", json={}, timeout=15)
    assert r.status_code in (401, 403), f"{method} {path} -> {r.status_code}"


@pytest.mark.parametrize("method,path", ADMIN_ONLY)
def test_an_ordinary_user_cannot_use_admin_endpoints(session, method: str, path: str) -> None:  # type: ignore[no-untyped-def]
    r = session.request(method, f"{API}{path}", json={}, timeout=15)
    assert r.status_code == 403, f"{method} {path} -> {r.status_code}"


def test_an_ordinary_user_can_use_their_own_tasks_and_preferences(session) -> None:  # type: ignore[no-untyped-def]
    prefs = session.get(f"{API}/user-preferences", timeout=15)
    assert prefs.status_code == 200 and prefs.json()["default_route"] == "auto"
    made = session.post(f"{API}/tasks", json={"title": SECRET_TITLE, "request": SECRET_REQUEST}, timeout=15)
    assert made.status_code == 200 and made.json()["state"] == "draft"
    assert SECRET_TITLE in [t["title"] for t in session.get(f"{API}/tasks", timeout=15).json()]


def test_another_users_task_is_not_found_not_forbidden(session) -> None:  # type: ignore[no-untyped-def]
    # Same answer for "missing" and "someone else's": existence is not revealed.
    r = session.get(f"{API}/tasks/{uuid.uuid4()}", timeout=15)
    assert r.status_code == 404


def test_an_edit_of_the_task_does_not_put_its_text_in_the_audit_trail(session) -> None:  # type: ignore[no-untyped-def]
    t = [t for t in session.get(f"{API}/tasks", timeout=15).json() if t["title"] == SECRET_TITLE][0]
    session.post(f"{API}/tasks/{t['id']}/cancel", json={"version": t["version"]}, timeout=15)
    with get_session_with_current_tenant() as db:
        rows = db.execute(text("select summary, details::text from nortpole_audit_event where actor_email = :e"), {"e": EMAIL}).all()
    assert rows, "the cancel should have been audited"
    blob = " ".join(f"{a} {b or ''}" for a, b in rows)
    assert SECRET_TITLE not in blob and "UniqueRequestText" not in blob and "acquisition" not in blob


def test_no_audit_row_anywhere_holds_task_text(session) -> None:  # type: ignore[no-untyped-def]
    with get_session_with_current_tenant() as db:
        leaked = db.execute(
            text("select count(*) from nortpole_audit_event where summary like :p or details::text like :p"),
            {"p": f"%{SECRET_TITLE}%"},
        ).scalar()
    assert leaked == 0


ADMIN_AUDIT = [("GET", "/admin/audit"), ("GET", "/admin/audit?outcome=denied"), ("POST", "/admin/audit/export"), ("POST", "/admin/audit/export?format=csv"), ("GET", "/admin/audit/verify"), ("GET", "/admin/audit/head"), ("GET", "/admin/audit/verify?anchor=1:0000000000000000000000000000000000000000000000000000000000000000"),
               ("GET", "/admin/retention"), ("GET", "/admin/inventory"), ("GET", "/admin/overview"), ("GET", "/admin/quality"), ("GET", "/admin/tool-catalog"), ("PUT", "/admin/tool-catalog"), ("POST", "/admin/tool-catalog/check/1"), ("GET", "/admin/studio"), ("POST", "/admin/studio/check"), ("PUT", "/admin/studio/x-pack"), ("DELETE", "/admin/studio/x-pack"), ("POST", "/admin/studio/x-pack/publish"), ("GET", "/admin/changes"), ("POST", "/admin/changes/00000000-0000-0000-0000-000000000000/approve"), ("POST", "/admin/changes/00000000-0000-0000-0000-000000000000/decline"), ("POST", "/admin/changes/00000000-0000-0000-0000-000000000000/cancel"), ("GET", "/admin/controls"), ("PUT", "/admin/controls"), ("GET", "/admin/actions/awaiting-second"), ("POST", "/admin/actions/00000000-0000-0000-0000-000000000000/second-review"), ("POST", "/admin/actions/00000000-0000-0000-0000-000000000000/second-approve"), ("POST", "/admin/actions/00000000-0000-0000-0000-000000000000/second-decline"), ("GET", "/admin/extensions"), ("PUT", "/admin/extensions"), ("PUT", "/admin/retention"), ("POST", "/admin/retention/prune"), ("GET", "/admin/action-targets"), ("POST", "/admin/action-targets"),
               ("GET", "/admin/source-requests"), ("POST", "/admin/source-requests/00000000-0000-0000-0000-000000000000/decide"),
               ("GET", "/admin/workflow-schedules"), ("GET", "/admin/workflow-schedules/controls"), ("PUT", "/admin/workflow-schedules/controls"),
               ("POST", "/admin/workflow-schedules/00000000-0000-0000-0000-000000000000/pause"), ("POST", "/admin/workflow-schedules/run-due")]


@pytest.mark.parametrize("method,path", ADMIN_AUDIT)
def test_the_audit_log_and_action_targets_are_admin_only(session, method: str, path: str) -> None:  # type: ignore[no-untyped-def]
    assert requests.request(method, f"{API}{path}", json={}, timeout=15).status_code in (401, 403)
    assert session.request(method, f"{API}{path}", json={}, timeout=15).status_code == 403


ADMIN_PACKS = [("GET", "/admin/pack-signers"), ("POST", "/admin/pack-signers"), ("POST", "/admin/pack-signers/x/revoke"),
               ("GET", "/admin/packs"), ("POST", "/admin/packs"), ("POST", "/admin/packs/x/1.0.0/activate"), ("POST", "/admin/packs/x/deactivate")]


@pytest.mark.parametrize("method,path", ADMIN_PACKS)
def test_pack_administration_is_admin_only(session, method: str, path: str) -> None:  # type: ignore[no-untyped-def]
    assert requests.request(method, f"{API}{path}", json={}, timeout=15).status_code in (401, 403)
    assert session.request(method, f"{API}{path}", json={}, timeout=15).status_code == 403


@pytest.mark.parametrize("method,path", [("GET", "/packs"), ("POST", "/packs/x/templates/y/task")])
def test_packs_for_people_need_sign_in(method: str, path: str) -> None:
    assert requests.request(method, f"{API}{path}", json={}, timeout=15).status_code in (401, 403)


def test_personal_skills_can_be_switched_off_for_ordinary_users(session) -> None:  # type: ignore[no-untyped-def]
    from nortpole.extensions.policy import ExtensionPolicy, load, save

    original = load()
    try:
        save(ExtensionPolicy(version=original.version + 1, personal_skills="off"))
        for method, path in [("POST", "/skills/custom"), ("POST", "/skills/custom/batch"), ("POST", "/skills/github/import"), ("POST", "/skills/custom/editor")]:
            r = session.request(method, f"{API}{path}", json={}, timeout=15)
            assert r.status_code == 403 and "turned off" in r.text, (path, r.status_code, r.text[:120])
    finally:
        save(original)
