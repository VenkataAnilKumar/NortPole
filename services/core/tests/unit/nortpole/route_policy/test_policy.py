import pytest

from nortpole.governance.route_policy.policy import (
    DATA_CLASSES,
    RoutePolicy,
    decide,
    kind_for,
)


def make_policy() -> RoutePolicy:
    return RoutePolicy(route_kinds={"1": "local", "2": "private", "3": "cloud"})


def test_confidential_blocks_cloud_and_names_the_reason() -> None:
    d = decide(make_policy(), 3, "confidential")
    assert d.allowed is False
    assert d.kind == "cloud"
    assert "confidential" in (d.reason or "")
    assert "Policy v1" in (d.reason or "")


def test_default_class_is_used_when_none_given() -> None:
    p = make_policy()
    assert p.default_data_class == "confidential"
    assert decide(p, 1).allowed is True
    assert decide(p, 3).allowed is False


def test_public_data_may_use_every_route() -> None:
    p = make_policy()
    assert all(decide(p, pid, "public").allowed for pid in (1, 2, 3))


def test_restricted_data_only_on_local() -> None:
    p = make_policy()
    assert [decide(p, pid, "restricted").allowed for pid in (1, 2, 3)] == [True, False, False]


def test_unassigned_provider_is_treated_as_cloud() -> None:
    p = make_policy()
    assert kind_for(p, 99) == "cloud"
    d = decide(p, 99, "internal")
    assert d.allowed is False
    assert "treated as cloud" in (d.reason or "")


def test_unknown_data_class_falls_back_to_the_default() -> None:
    d = decide(make_policy(), 3, "made-up")
    assert d.data_class == "confidential"
    assert d.allowed is False


def test_empty_allowed_list_blocks_everything_for_that_class() -> None:
    p = make_policy()
    p = RoutePolicy(
        route_kinds=p.route_kinds,
        allowed={**p.allowed, "restricted": []},
    )
    assert not any(decide(p, pid, "restricted").allowed for pid in (1, 2, 3))


@pytest.mark.parametrize("bad", ["", "edge", "LOCAL"])
def test_rejects_unknown_route_kind(bad: str) -> None:
    with pytest.raises(ValueError):
        RoutePolicy(route_kinds={"1": bad})


def test_rejects_unknown_data_class_in_allowed() -> None:
    with pytest.raises(ValueError):
        RoutePolicy(allowed={"secret": ["local"]})


def test_every_data_class_is_present_after_validation() -> None:
    p = RoutePolicy(allowed={"public": ["cloud"]})
    assert set(p.allowed) == set(DATA_CLASSES)
    assert p.allowed["confidential"] == []
