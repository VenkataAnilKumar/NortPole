"""The admin inventory lists what is active, with the last use where one is kept."""

import uuid

import pytest

from evolvxsi.work.actions.models import EvolvXSIAction, EvolvXSIActionTarget
from evolvxsi.db.engine.sql_engine import get_session_with_current_tenant
from evolvxsi.insight.inventory.api import build, host_only
from evolvxsi.work.packs.models import EvolvXSIPackSigner, EvolvXSIPackVersion
from tests.evolvxsi_integration.test_tasks_flow import _up

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres")

TAG = uuid.uuid4().hex[:8]


def test_hosts_only_never_paths_queries_or_credentials() -> None:
    assert host_only("https://user:tok@mcp.example.com:8443/v1/x?key=SECRET") == "mcp.example.com"
    assert host_only(None) == "unknown host" and host_only("not a url") == "unknown host"
    assert "SECRET" not in host_only("https://h.example/?key=SECRET")


def test_active_packs_destinations_and_routes_are_listed_with_their_tier_and_status() -> None:
    pid = f"inv-{TAG}"
    with get_session_with_current_tenant() as s:
        s.add(EvolvXSIPackSigner(key_id=f"k-{TAG}", label="t", public_key="x", revoked=True))
        s.add(EvolvXSIPackVersion(pack_id=pid, version="1.0.0", signature="s", digest="d", signer_key_id=f"k-{TAG}", active=True,
                                  manifest={"name": "Inventory pack", "vertical": "test", "templates": [{"id": "a"}], "autonomy": "draft_only"}))
        s.add(EvolvXSIPackVersion(pack_id=f"off-{TAG}", version="1.0.0", signature="s", digest="d2", signer_key_id=f"k-{TAG}", active=False,
                                  manifest={"name": "Not active", "vertical": "test", "templates": []}))
        t = EvolvXSIActionTarget(name=f"dest-{TAG}", kind="email", url="mailto:a@example.com", allowed_data_classes=["public"], enabled=False, tier="draft_only")
        s.add(t)
        s.commit()
        try:
            inv = build(s)
            by = {(i.kind, i.name): i for i in inv.items}
            pack = by[("pack", "Inventory pack")]
            assert pack.status == "signer revoked" and pack.version == "1.0.0" and "autonomy: draft_only" in pack.notes
            assert pack.last_use == "not recorded", "no task has started from it"
            assert ("pack", "Not active") not in by, "inactive versions are not listed"
            dest = by[("destination", f"dest-{TAG}")]
            assert dest.status == "disabled" and "tier: draft_only" in dest.notes and dest.uses == 0
            assert any(i.kind == "model_route" for i in inv.items)
            assert inv.counts["pack"] >= 1 and inv.limits
            assert all("mailto:" not in i.detail for i in inv.items), "a destination's address is not shown here"
        finally:
            s.query(EvolvXSIAction).filter_by(target_id=t.id).delete()
            s.query(EvolvXSIActionTarget).filter_by(id=t.id).delete()
            s.query(EvolvXSIPackVersion).filter(EvolvXSIPackVersion.pack_id.in_([pid, f"off-{TAG}"])).delete(synchronize_session=False)
            s.query(EvolvXSIPackSigner).filter_by(key_id=f"k-{TAG}").delete()
            s.commit()
