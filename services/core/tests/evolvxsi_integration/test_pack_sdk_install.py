"""A pack signed by the pack SDK installs on the server (decision 0006, phase 4)."""

import shutil
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from sqlalchemy import text

from evolvxsi.db.engine.sql_engine import get_session_with_current_tenant
from evolvxsi.work.packs import api as packs
from evolvxsi.work.packs.models import EvolvXSIPackSigner, EvolvXSIPackVersion
from tests.evolvxsi_integration.test_tasks_flow import _up

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "packages" / "pack-sdk"))
import evolvxsi_pack_sdk as sdk  # noqa: E402

pytestmark = pytest.mark.skipif(not _up(), reason="needs Postgres with the pack tables")

RUN = uuid.uuid4().hex[:8]
ADMIN = SimpleNamespace(id=uuid.uuid4(), email=f"sdk-admin-{RUN}@example.com")


def test_an_sdk_signed_pack_installs_and_activates(tmp_path: Path) -> None:
    pack_id = f"sdk-brief-{RUN}"
    pack = tmp_path / "packs" / "horizontal" / pack_id
    shutil.copytree(REPO / "packs" / "horizontal" / "everyday-brief", pack)
    source = yaml.safe_load((pack / "manifest.yaml").read_text())
    source["id"] = pack_id
    (pack / "manifest.yaml").write_text(yaml.safe_dump(source, sort_keys=False))

    key = sdk.keygen(f"sdk-{RUN}")
    package = sdk.sign(sdk.validate(pack), key["private_key"], key["key_id"])
    try:
        with get_session_with_current_tenant() as s:
            packs.add_signer(packs.SignerIn(key_id=key["key_id"], public_key=key["public_key"], label="sdk test"), user=ADMIN, db_session=s)
            installed = packs.install_pack(packs.Package(**package), user=ADMIN, db_session=s)
            assert installed.signer_key_id == key["key_id"]
            stored = s.query(EvolvXSIPackVersion).filter_by(pack_id=pack_id).one()
            assert stored.digest == sdk.digest(package["manifest"])
            # everyday-brief leaves defaults out: the stored signed bytes are the SDK's, and they re-verify.
            assert stored.signed_manifest.encode("utf-8") == sdk.canonical_bytes(package["manifest"])
            assert sdk.digest(stored.manifest) != stored.digest, "the normalized copy alone could not be re-verified"
            check = next(c for c in packs.verify_versions(_=None, db_session=s).versions if c.pack_id == pack_id)
            assert check.status == "verified", check.problems
            assert packs.activate(pack_id, source["version"], user=ADMIN, db_session=s).active
    finally:
        with get_session_with_current_tenant() as s:
            s.query(EvolvXSIPackVersion).filter_by(pack_id=pack_id).delete()
            s.query(EvolvXSIPackSigner).filter_by(key_id=key["key_id"]).delete()
            s.execute(text("delete from evolvxsi_audit_event where actor_email = :e and row_hash is null"), {"e": ADMIN.email})
            s.commit()
