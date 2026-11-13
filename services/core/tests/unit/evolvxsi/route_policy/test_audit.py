from evolvxsi.route_policy.audit import describe_policy_change
from evolvxsi.route_policy.policy import RoutePolicy


def base() -> RoutePolicy:
    return RoutePolicy(version=3, route_kinds={"1": "local", "2": "cloud"})


def test_no_changes_is_stated() -> None:
    old = base()
    new = RoutePolicy(version=4, route_kinds=old.route_kinds, allowed=old.allowed)
    summary, details = describe_policy_change(old, new)
    assert summary == "Policy v3 to v4: no changes"
    assert details["changes"] == {}


def test_allowed_route_change_is_listed_with_plus_and_minus() -> None:
    old = base()
    allowed = {**old.allowed, "confidential": ["local", "private", "cloud"], "restricted": []}
    new = RoutePolicy(version=4, route_kinds=old.route_kinds, allowed=allowed)
    summary, details = describe_policy_change(old, new)
    assert "confidential: +cloud" in summary
    assert "restricted: -local" in summary
    assert details["changes"]["allowed"]["confidential"] == {"added": ["cloud"], "removed": []}
    assert details["from_version"] == 3 and details["to_version"] == 4


def test_route_kind_and_default_class_changes() -> None:
    old = base()
    new = RoutePolicy(
        version=4,
        default_data_class="internal",
        route_kinds={"1": "private", "2": "cloud", "3": "local"},
        allowed=old.allowed,
    )
    summary, details = describe_policy_change(old, new)
    assert "workspace data class confidential to internal" in summary
    assert "provider 1 local to private" in summary
    assert "provider 3 unset to local" in summary
    assert details["changes"]["route_kinds"]["3"] == {"from": None, "to": "local"}


def test_a_change_to_redaction_is_described_not_reported_as_no_changes() -> None:
    old = RoutePolicy(version=3, redact_route_kinds=["cloud"])
    new = RoutePolicy(version=4, redact_route_kinds=["private"])
    summary, details = describe_policy_change(old, new)
    assert "no changes" not in summary and "redaction before sending to: +private -cloud" in summary
    assert details["changes"]["redact_route_kinds"] == {"added": ["private"], "removed": ["cloud"]}
    same, _ = describe_policy_change(old, RoutePolicy(version=4, redact_route_kinds=["cloud"]))
    assert same.endswith("no changes"), "an unchanged redaction list is still reported as no change"
