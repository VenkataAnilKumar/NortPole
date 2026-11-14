import base64
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from nortpole.work.packs.manifest import Manifest, canonical_bytes, digest, version_key
from nortpole.work.packs.signing import SignatureProblem, verify

SAMPLE = json.loads((Path(__file__).parents[4] / "tests/common/fixtures/finance-policy-review-1.1.0.json").read_text())


def _keys():  # type: ignore[no-untyped-def]
    k = Ed25519PrivateKey.generate()
    pub = base64.b64encode(k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    return k, pub


def test_the_sample_pack_is_valid() -> None:
    m = Manifest.model_validate(SAMPLE)
    assert m.id == "finance-policy-review" and len(m.templates) == 3


@pytest.mark.parametrize("change", [
    {"id": "Bad Id"}, {"version": "1.0"}, {"extra_field": 1}, {"templates": []},
    {"requires": {"data_classes": ["secret"], "route_kinds": ["local"]}},
    {"requires": {"data_classes": ["public"], "route_kinds": ["moon"]}},
    {"requires": {"data_classes": [], "route_kinds": ["local"]}},
    {"schema_version": 2},
])
def test_invalid_manifests_are_refused(change: dict) -> None:
    with pytest.raises(ValidationError):
        Manifest.model_validate({**SAMPLE, **change})


def test_duplicate_template_ids_are_refused() -> None:
    t = SAMPLE["templates"][0]
    with pytest.raises(ValidationError):
        Manifest.model_validate({**SAMPLE, "templates": [t, t]})


def test_canonical_form_ignores_key_order_but_not_content() -> None:
    reordered = dict(reversed(list(SAMPLE.items())))
    assert canonical_bytes(SAMPLE) == canonical_bytes(reordered) and digest(SAMPLE) == digest(reordered)
    assert digest(SAMPLE) != digest({**SAMPLE, "version": "1.0.1"})


def test_a_valid_signature_verifies_and_any_change_breaks_it() -> None:
    k, pub = _keys()
    sig = base64.b64encode(k.sign(canonical_bytes(SAMPLE))).decode()
    verify(pub, sig, canonical_bytes(SAMPLE))
    with pytest.raises(SignatureProblem):
        verify(pub, sig, canonical_bytes({**SAMPLE, "name": "Changed"}))
    other, other_pub = _keys()
    with pytest.raises(SignatureProblem):
        verify(other_pub, sig, canonical_bytes(SAMPLE))
    with pytest.raises(SignatureProblem):
        verify(pub, "not base64 !!", canonical_bytes(SAMPLE))
    with pytest.raises(SignatureProblem):
        verify("short", sig, canonical_bytes(SAMPLE))


def test_versions_order_numerically() -> None:
    assert version_key("1.10.0") > version_key("1.2.9") and version_key("2.0.0") > version_key("1.99.99")
