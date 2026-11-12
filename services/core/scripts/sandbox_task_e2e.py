"""Sandbox only. Runs the same travel-receipts task as the group member and as the outsider over HTTP, then removes and restores the member's group membership to show the draft is hidden and returns. Usage: sandbox_task_e2e.py <run-id> <group-id> (both printed by sandbox_ingest_corpus.py)."""
import sys, time, requests
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from evolvxsi.db.engine.sql_engine import SqlEngine, get_session_with_current_tenant
from evolvxsi.db.models import User, User__UserGroup
SqlEngine.init_engine(pool_size=2, max_overflow=0)
API = "http://127.0.0.1:8080"; RUN = sys.argv[1]; GID = int(sys.argv[2])
def login(email):
    s = requests.Session()
    assert s.post(f"{API}/auth/login", data={"username": email, "password": "Passw0rd-test-123"}, timeout=30).status_code in (200, 204)
    return s
def run_task(s, title, request):
    t = s.post(f"{API}/tasks", json={"title": title, "request": request}, timeout=30).json()
    t = s.post(f"{API}/tasks/{t['id']}/start", json={"version": t["version"]}, timeout=600).json()
    t = s.post(f"{API}/tasks/{t['id']}/plan/accept", json={"version": t["version"]}, timeout=60).json()
    t0 = time.time()
    t = s.post(f"{API}/tasks/{t['id']}/run", json={"version": t["version"]}, timeout=900).json()
    return t, time.time() - t0
member, outsider = login(f"member-{RUN}@example.com"), login(f"outsider-{RUN}@example.com")
Q = "When do I have to submit travel receipts, and what if I am late?"
for who, s in (("member (in Finance group)", member), ("outsider", outsider)):
    t, secs = run_task(s, "Travel receipts", Q)
    print(f"\n[{who}] state={t['state']} in {secs:.0f}s error={t['run_error']}")
    print("  sources:", [(x["doc_id"].split('-',1)[1], x["cited"]) for x in (t["draft_sources"] or [])])
    print("  draft  :", (t["draft_text"] or "")[:330].replace("\n", " "))
    print("  claims :", [c["status"] for c in (t["draft_claims"] or [])])
    if who.startswith("member"): member_task = t
# remove the member from the group: the draft must be hidden
with get_session_with_current_tenant() as db:
    uid = db.query(User).filter_by(email=f"member-{RUN}@example.com").one().id
    db.query(User__UserGroup).filter_by(user_id=uid, user_group_id=GID).delete(); db.commit()
v = member.get(f"{API}/tasks/{member_task['id']}", timeout=30).json()
print("\nafter removing the member from the group: withheld =", v["withheld"], "| draft_text =", v["draft_text"], "|", (v["withheld_message"] or "")[:80])
with get_session_with_current_tenant() as db:
    db.add(User__UserGroup(user_id=uid, user_group_id=GID)); db.commit()
v = member.get(f"{API}/tasks/{member_task['id']}", timeout=30).json()
print("group restored: withheld =", v["withheld"], "| draft visible =", bool(v["draft_text"]))
