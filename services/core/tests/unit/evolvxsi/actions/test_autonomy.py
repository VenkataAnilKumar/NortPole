"""Autonomy tiers: ordering and the lower-of rule."""

import pytest

from evolvxsi.work.actions.autonomy import at_least, lowest
from evolvxsi.work.packs.manifest import Manifest


def test_the_lower_tier_wins() -> None:
    assert lowest("act_with_approval", "draft_only") == "draft_only"
    assert lowest("draft_only", "read_only") == "read_only"
    assert lowest("act_with_approval", "act_with_approval") == "act_with_approval"


def test_an_unknown_tier_fails_closed() -> None:
    assert lowest("act_with_approval", "wide_open") == "act_with_approval"  # unknown values are ignored...
    assert lowest("wide_open") == "read_only"                                 # ...and nothing known means no access


def test_each_tier_allows_only_what_it_names() -> None:
    assert not at_least("read_only", "draft_only")
    assert at_least("draft_only", "draft_only") and not at_least("draft_only", "act_with_approval")
    assert at_least("act_with_approval", "draft_only") and at_least("act_with_approval", "act_with_approval")
    assert not at_least("wide_open", "draft_only")


def test_a_pack_declares_autonomy_and_the_default_is_unchanged() -> None:
    import json
    from pathlib import Path

    raw = json.loads((Path(__file__).parents[4] / "scripts/sample_packs/finance-policy-review.json").read_text())
    assert Manifest.model_validate(raw).autonomy == "act_with_approval"
    raw["autonomy"] = "draft_only"
    assert Manifest.model_validate(raw).autonomy == "draft_only"
    raw["autonomy"] = "anything"
    with pytest.raises(ValueError):
        Manifest.model_validate(raw)
