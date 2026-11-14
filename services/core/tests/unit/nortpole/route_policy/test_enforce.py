from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.governance.route_policy import enforce
from nortpole.governance.route_policy.policy import RoutePolicy


def session_with_provider(provider_id: int | None) -> MagicMock:
    s = MagicMock()
    s.get.return_value = (
        SimpleNamespace(llm_provider_id=provider_id) if provider_id is not None else None
    )
    return s


@pytest.fixture(autouse=True)
def policy(monkeypatch: pytest.MonkeyPatch) -> None:
    p = RoutePolicy(route_kinds={"1": "local", "2": "cloud"})
    monkeypatch.setattr(enforce, "load_policy", lambda: p)


def test_allowed_route_passes() -> None:
    d = enforce.enforce_route(session_with_provider(1), 10)
    assert d.allowed and d.kind == "local"


def test_blocked_route_raises_policy_blocked_with_reason() -> None:
    with pytest.raises(NortPoleError) as exc:
        enforce.enforce_route(session_with_provider(2), 20)
    assert exc.value.error_code is NortPoleErrorCode.POLICY_BLOCKED
    assert "confidential" in str(exc.value)


def test_unknown_model_configuration_fails_closed() -> None:
    with pytest.raises(NortPoleError) as exc:
        enforce.enforce_route(session_with_provider(None), 999)
    assert exc.value.error_code is NortPoleErrorCode.POLICY_BLOCKED


def test_missing_model_configuration_id_fails_closed() -> None:
    with pytest.raises(NortPoleError):
        enforce.enforce_route(MagicMock(), None)


def test_public_data_may_use_a_cloud_route() -> None:
    d = enforce.enforce_route(session_with_provider(2), 20, "public")
    assert d.allowed and d.kind == "cloud"
