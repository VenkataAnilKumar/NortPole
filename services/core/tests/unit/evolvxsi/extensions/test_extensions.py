"""Extension rules: the MCP host allowlist and the personal-skills switch."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.extensions import enforce
from evolvxsi.extensions.policy import ExtensionPolicy, host_allowed, host_of


def _p(*hosts: str, on: bool = True) -> ExtensionPolicy:
    return ExtensionPolicy(mcp_allowlist_enabled=on, mcp_allowed_hosts=list(hosts))


def test_with_the_allowlist_off_everything_is_allowed() -> None:
    assert host_allowed("https://anything.example/x", _p(on=False))


def test_with_it_on_only_listed_hosts_pass_and_nothing_is_allowed_when_empty() -> None:
    p = _p("mcp.example.com", "*.corp.test")
    assert host_allowed("https://mcp.example.com/sse?token=x", p)
    assert host_allowed("https://a.b.corp.test:8443/", p)
    assert not host_allowed("https://corp.test/", p), "a wildcard does not cover the bare domain"
    assert not host_allowed("https://evilcorp.test/", p), "a wildcard needs the dot boundary"
    assert not host_allowed("https://mcp.example.com.evil.io/", p)
    assert not host_allowed("https://user@other.example/", p)
    assert not host_allowed("not a url", p) and not host_allowed(None, p)
    assert not host_allowed("https://mcp.example.com/", _p())


def test_hosts_are_checked_for_shape_and_deduplicated() -> None:
    assert _p("MCP.Example.com ", "mcp.example.com").mcp_allowed_hosts == ["mcp.example.com"]
    for bad in ["http://x.com", "x", "*.com.", "a b.com", "*example.com", ""]:
        with pytest.raises(ValidationError):
            _p(bad)


def test_the_host_comes_from_the_url_not_its_credentials_or_path() -> None:
    assert host_of("https://u:p@Mcp.Example.com:1/a?h=evil.com") == "mcp.example.com"


def test_a_blocked_server_is_refused_and_audited() -> None:
    audited: list = []
    with patch.object(enforce, "load", return_value=_p("ok.example")), patch("evolvxsi.extensions.policy.load", return_value=_p("ok.example")), \
         patch.object(enforce, "record_audit", lambda *a, **k: audited.append(k)):
        enforce.assert_mcp_url_allowed("https://ok.example/", None)
        with pytest.raises(EvolvXSIError) as err:
            enforce.assert_mcp_url_allowed("https://bad.example/", None)
    assert "allowlist" in err.value.detail and len(audited) == 1 and "bad.example" in audited[0]["summary"]


def test_personal_skills_off_refuses_and_audits() -> None:
    audited: list = []
    with patch.object(enforce, "load", return_value=ExtensionPolicy(personal_skills="off")), patch.object(enforce, "record_audit", lambda *a, **k: audited.append(k)):
        with pytest.raises(EvolvXSIError):
            enforce.personal_skills_allowed(user=SimpleNamespace(email="a@b.c"))
    with patch.object(enforce, "load", return_value=ExtensionPolicy()):
        assert enforce.personal_skills_allowed(user=SimpleNamespace(email="a@b.c")) is None
    assert len(audited) == 1


def test_a_call_to_a_server_off_the_allowlist_is_not_made() -> None:
    from evolvxsi.tools.tool_implementations.mcp.mcp_tool import MCPTool

    audited: list = []
    fake = SimpleNamespace(mcp_server=SimpleNamespace(server_url="https://bad.example/sse", name="srv", id=3), _name="lookup",
                           _error_result=lambda msg: ("error", msg))
    with patch("evolvxsi.extensions.policy.load", return_value=_p("ok.example")), patch("evolvxsi.route_policy.audit.record_audit", lambda *a, **k: audited.append(k)):
        out = MCPTool._run(fake, None, None)  # type: ignore[arg-type]
    assert out[0] == "error" and "allowlist" in out[1] and len(audited) == 1


def test_an_unreadable_policy_store_fails_closed() -> None:
    from evolvxsi.extensions import policy

    with patch.object(policy, "get_kv_store", side_effect=RuntimeError("down")):
        p = policy.load()
    assert p.mcp_allowlist_enabled and p.mcp_allowed_hosts == []
