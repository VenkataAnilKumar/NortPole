"""Sensitive-text redaction: detectors, the labelled set, and the request rewrite."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

from evolvxsi.llm.models import AssistantMessage, GenerationRequest, SystemMessage, TextContent, TextContentPart, ToolResultMessage, UserMessage
from evolvxsi.redaction import request as req
from evolvxsi.redaction.redact import redact_text
from evolvxsi.route_policy.policy import RoutePolicy

_spec = importlib.util.spec_from_file_location("redaction_report", Path(__file__).parents[4] / "scripts/redaction_report.py")
report = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(report)  # type: ignore[union-attr]


def test_each_kind_is_replaced_with_a_typed_placeholder() -> None:
    text, counts = redact_text("a@b.com, +1 415 555 0132, 4111 1111 1111 1111, 123-45-6789, sk-abcdefghijklmnop1234")
    assert text == "[REDACTED:EMAIL], [REDACTED:PHONE], [REDACTED:CARD], [REDACTED:SSN], [REDACTED:SECRET]"
    assert counts == {"EMAIL": 1, "PHONE": 1, "CARD": 1, "SSN": 1, "SECRET": 1}


def test_numbers_that_fail_their_checksum_or_are_plain_stay() -> None:
    for t in ["order 1234567890123456", "2024-11-12 14:30", "total 1,250.00", "v3.12.4", "123-45-678", "IBAN GB00 0000 0000 0000 00"]:
        assert redact_text(t)[0] == t


def test_citation_markers_survive() -> None:
    assert redact_text("Receipts are due in 30 days [1], contact a@b.com [2].")[0] == "Receipts are due in 30 days [1], contact [REDACTED:EMAIL] [2]."


def test_the_labelled_set_stays_above_its_recorded_floor() -> None:
    out = report.score()
    # Recorded 2026-11-12: precision 0.966, recall 1.0. One known false positive: a
    # 16-digit number that happens to pass the card checksum looks like a card.
    assert out["recall"] >= 0.95 and out["precision"] >= 0.95
    assert len(out["wrong"]) <= 1


def _request() -> GenerationRequest:
    return GenerationRequest(
        system_prompt="Support line +1 415 555 0132",
        messages=[
            SystemMessage(content="mail root@corp.com"),
            UserMessage(content="my card is 4111 1111 1111 1111"),
            UserMessage(content=[TextContentPart(text="ssn 123-45-6789")]),
            AssistantMessage(content=[TextContent(text="noted a@b.com")]),
            ToolResultMessage(content="key sk-abcdefghijklmnop1234", tool_call_id="t1", tool_name="lookup"),
        ],
    )


def _all_text(r: GenerationRequest) -> str:
    out = [r.system_prompt]
    for m in r.messages:
        if isinstance(m.content, str):
            out.append(m.content)
        else:
            out += [getattr(p, "text", "") for p in m.content]
    return "\n".join(out)


def test_a_cloud_request_is_redacted_in_every_message_type_and_counted() -> None:
    recorded: list = []
    with patch.object(req, "_route_kind", return_value="cloud"), patch.object(req, "load_policy", return_value=RoutePolicy()), \
         patch.object(req, "_record", lambda kind, counts: recorded.append((kind, counts))):
        out = req.redact_request(_request(), 1)
    text = _all_text(out)
    for original in ["+1 415 555 0132", "root@corp.com", "4111", "123-45-6789", "a@b.com", "sk-abcdefghijklmnop1234"]:
        assert original not in text
    assert recorded == [("cloud", {"PHONE": 1, "EMAIL": 2, "CARD": 1, "SSN": 1, "SECRET": 1})]


def test_a_local_request_is_left_alone_by_default() -> None:
    r = _request()
    with patch.object(req, "_route_kind", return_value="local"), patch.object(req, "load_policy", return_value=RoutePolicy()):
        assert req.redact_request(r, 1) is r


def test_the_policy_can_redact_local_routes_too() -> None:
    with patch.object(req, "_route_kind", return_value="local"), \
         patch.object(req, "load_policy", return_value=RoutePolicy(redact_route_kinds=["local", "cloud"])), patch.object(req, "_record", lambda *a: None):
        assert "root@corp.com" not in _all_text(req.redact_request(_request(), 1))


def test_an_unknown_route_is_treated_as_cloud() -> None:
    from evolvxsi.route_policy import enforce

    with patch.object(enforce, "check_route", side_effect=RuntimeError("db down")), patch.object(req, "get_session_with_current_tenant"):
        assert req._route_kind(1) == "cloud"


def test_a_failure_to_redact_stops_the_request() -> None:
    with patch.object(req, "_route_kind", return_value="cloud"), patch.object(req, "load_policy", return_value=RoutePolicy()), \
         patch.object(req, "redact_text", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            req.redact_request(_request(), 1)


def test_the_policy_rejects_an_unknown_route_kind() -> None:
    with pytest.raises(ValueError):
        RoutePolicy(redact_route_kinds=["cloudy"])
