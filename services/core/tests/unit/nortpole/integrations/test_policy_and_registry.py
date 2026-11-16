"""Who may use an integration (policy) and which definitions the deployment offers (registry)."""

import copy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from nortpole.key_value_store.interface import KvKeyNotFoundError
from nortpole.work.integrations import policy, registry
from nortpole.work.integrations.manifest import Integration
from tests.unit.nortpole.integrations.test_manifest import GOOD

ROOT = Path(__file__).resolve().parents[6] / "integrations"


def item(**changes) -> Integration:  # type: ignore[no-untyped-def]
    data = copy.deepcopy(GOOD)
    data.update(changes)
    return Integration.model_validate(data)


def test_the_definitions_default_is_used_when_nothing_is_set() -> None:
    assert policy.resolve(item(policy_default="needs_approval"), policy.PolicyConfig()) == "needs_approval"
    assert policy.resolve(item(policy_default="allowed"), policy.PolicyConfig()) == "allowed"


def test_an_override_on_the_integration_beats_one_on_its_category() -> None:
    cfg = policy.PolicyConfig(categories={"horizontal/product": "allowed"}, integrations={"example-notes": "needs_approval"})
    assert policy.resolve(item(), cfg) == "needs_approval"
    assert policy.resolve(item(), policy.PolicyConfig(categories={"horizontal/product": "allowed"})) == "allowed"


def test_blocked_anywhere_above_the_default_wins() -> None:
    assert policy.resolve(item(), policy.PolicyConfig(categories={"horizontal/product": "blocked"}, integrations={"example-notes": "allowed"})) == "blocked"
    assert policy.resolve(item(), policy.PolicyConfig(integrations={"example-notes": "blocked"}, categories={"horizontal/product": "allowed"})) == "blocked"


@pytest.mark.parametrize(
    "build",
    [
        lambda: policy.PolicyConfig(integrations={"Not A Slug": "allowed"}),
        lambda: policy.PolicyConfig(categories={"horizontal/finance": "allowed"}),
        lambda: policy.PolicyConfig(categories={"product": "allowed"}),
        lambda: policy.PolicyConfig(integrations={"x-y": "maybe"}),
        lambda: policy.PolicyConfig.model_validate({"surprise": 1}),
    ],
)
def test_a_bad_policy_is_refused(build) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError):
        build()


class FakeStore:
    def __init__(self, value=None, missing=False):  # type: ignore[no-untyped-def]
        self.value, self.missing = value, missing

    def load(self, key: str):  # type: ignore[no-untyped-def]
        if self.missing:
            raise KvKeyNotFoundError()
        return self.value


def test_no_saved_policy_means_the_definitions_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(policy, "get_kv_store", lambda: FakeStore(missing=True))
    assert policy.load() == policy.PolicyConfig()


def test_a_damaged_policy_blocks_everything_instead_of_opening_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(policy, "get_kv_store", lambda: FakeStore(value={"integrations": "garbage"}))
    cfg = policy.load()
    assert policy.resolve(item(policy_default="allowed"), cfg) == "blocked"
    assert policy.resolve(item(group="vertical", category="finance", policy_default="allowed"), cfg) == "blocked"


# ---- registry -----------------------------------------------------------------------------------------------------------


def test_the_repository_definitions_are_offered() -> None:
    registry.reload()
    assert set(registry.all_integrations()) >= {"wikipedia", "airtable"}
    assert registry.get("wikipedia").auth.mode == "none"  # type: ignore[union-attr]
    assert registry.get("nope") is None


def test_one_bad_definition_does_not_hide_the_others(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    good = copy.deepcopy(GOOD)
    (tmp_path / "horizontal/product/example-notes").mkdir(parents=True)
    (tmp_path / "horizontal/product/example-notes/integration.yaml").write_text(yaml.safe_dump(good))
    (tmp_path / "horizontal/product/broken").mkdir(parents=True)
    (tmp_path / "horizontal/product/broken/integration.yaml").write_text("id: broken\nnot: valid\n")
    wrong = copy.deepcopy(GOOD) | {"id": "wrong-place"}
    (tmp_path / "vertical/finance/wrong-place").mkdir(parents=True)
    (tmp_path / "vertical/finance/wrong-place/integration.yaml").write_text(yaml.safe_dump(wrong))  # says horizontal/product
    monkeypatch.setenv("NORTPOLE_INTEGRATIONS_DIR", str(tmp_path))
    registry.reload()
    try:
        assert set(registry.all_integrations()) == {"example-notes"}
    finally:
        monkeypatch.delenv("NORTPOLE_INTEGRATIONS_DIR")
        registry.reload()


def test_no_folder_means_nothing_is_offered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NORTPOLE_INTEGRATIONS_DIR", str(tmp_path / "missing"))
    registry.reload()
    try:
        assert registry.all_integrations() == {}
    finally:
        monkeypatch.delenv("NORTPOLE_INTEGRATIONS_DIR")
        registry.reload()
