"""Sandbox only. Creates a Finance group, two users (member, outsider) and a PRIVATE source readable by the group, then ingests the synthetic corpus through the core's own ingestion API (real chunking, real embeddings, real OpenSearch). The six finance passages go to the private source; the rest to the public default source. Usage: sandbox_ingest_corpus.py <run-id>. Needs the full-mode API (see infrastructure/profiles/local/README.md)."""
import json, sys, time, uuid, requests
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from evolvxsi.db.engine.sql_engine import SqlEngine, get_session_with_current_tenant
from evolvxsi.db.enums import AccessType
from evolvxsi.db.models import User, UserGroup, User__UserGroup, UserGroup__CCPairDataAccess
from tests.evolvxsi_integration.test_group_access import _source
SqlEngine.init_engine(pool_size=2, max_overflow=0)
API = "http://127.0.0.1:8080"
RUN = (sys.argv[1] if len(sys.argv) > 1 else uuid.uuid4().hex[:6])
corpus = json.load(open(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "tests/evolvxsi_integration/retrieval_quality_set.json")))
FIN = {"travel-receipts", "travel-class", "hotel-cap", "meal-allowance", "expense-approval", "procurement-limit"}

def session(email, pw="Passw0rd-test-123"):
    s = requests.Session()
    s.post(f"{API}/auth/register", json={"email": email, "password": pw}, timeout=30)
    assert s.post(f"{API}/auth/login", data={"username": email, "password": pw}, timeout=30).status_code in (200, 204)
    return s

member_email, outsider_email = f"member-{RUN}@example.com", f"outsider-{RUN}@example.com"
member, outsider = session(member_email), session(outsider_email)
admin = session("admin@example.com")

with get_session_with_current_tenant() as s:
    group = UserGroup(name=f"Finance {RUN}", is_up_to_date=True); s.add(group); s.flush()
    mu = s.query(User).filter_by(email=member_email).one()
    s.add(User__UserGroup(user_id=mu.id, user_group_id=group.id))
    connector, cred, cc = _source(s, f"finance{RUN}", AccessType.PRIVATE)
    s.add(UserGroup__CCPairDataAccess(cc_pair_id=cc.id, user_group_id=group.id, access_type=AccessType.PRIVATE))
    s.commit()
    gid, ccid = group.id, cc.id
print("group", gid, "private source cc_pair", ccid)

def ingest(doc, cc_pair_id):
    body = {"cc_pair_id": cc_pair_id, "document": {"id": f"{RUN}-{doc['doc_id']}", "semantic_identifier": doc["title"], "source": "ingestion_api",
            "sections": [{"text": doc["text"], "link": f"https://example.com/{doc['doc_id']}"}], "metadata": {}}}
    r = admin.post(f"{API}/evolvxsi-api/ingestion", json=body, timeout=300)
    return r.status_code, r.text[:120]
t0 = time.time(); results = []
for d in corpus["documents"]:
    cc = ccid if d["doc_id"] in FIN else 1
    results.append((d["doc_id"], cc, *ingest(d, cc)))
bad = [r for r in results if r[2] != 200]
print(f"ingested {len(results)-len(bad)}/{len(results)} in {time.time()-t0:.0f}s", bad[:3])
