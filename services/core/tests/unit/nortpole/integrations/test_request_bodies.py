"""JSON bodies and the full set of methods in the integration format (decision 0008)."""

import copy

import pytest
from pydantic import ValidationError

from nortpole.work.integrations.executor import IntegrationCallError, prepare
from nortpole.work.integrations.manifest import Integration

from .test_manifest import GOOD

TOKEN = {"access_token": "tok-SECRET-123"}


def writer(method: str = "POST", body=None, params=None, effect: str = "write", **request) -> dict:  # type: ignore[no-untyped-def]
    data = copy.deepcopy(GOOD)
    a = data["actions"][0]
    a.update(effect=effect, params=params or {
        "title": {"type": "string", "description": "Title.", "required": True},
        "count": {"type": "integer", "description": "How many."},
        "done": {"type": "boolean", "description": "Done."},
        "props": {"type": "object", "description": "Free fields."},
        "note": {"type": "string", "description": "Optional note."},
    })
    a["request"] = {
        "method": method, "url": "https://api.example.com/v1/notes",
        "headers": {"Authorization": "Bearer {credential.access_token}"}, **request,
    }
    if body is not None:
        a["request"]["body"] = body
    if effect == "write":
        data["policy_default"] = "needs_approval"
    return data


BODY = {"title": "{title}", "meta": {"count": "{count}", "done": "{done}", "tags": ["fixed", "{note}"]}, "props": "{props}"}


def test_a_nested_body_keeps_each_parameters_own_type_and_leaves_out_what_is_missing() -> None:
    integration = Integration.model_validate(writer(body=BODY))
    req = prepare(integration, "list_notes", model_params={"title": "Hi", "count": 3, "done": False, "props": {"a": [1, "x"]}}, credential=TOKEN)
    assert req.method == "POST"
    assert req.body == {"title": "Hi", "meta": {"count": 3, "done": False, "tags": ["fixed"]}, "props": {"a": [1, "x"]}}
    only = prepare(integration, "list_notes", model_params={"title": "Hi"}, credential=TOKEN)
    assert only.body == {"title": "Hi", "meta": {"tags": ["fixed"]}}


def test_text_around_a_placeholder_is_filled_as_text() -> None:
    integration = Integration.model_validate(writer(body={"subject": "Re: {title} ({count})"}))
    req = prepare(integration, "list_notes", model_params={"title": "Hi", "count": 2}, credential=TOKEN)
    assert req.body == {"subject": "Re: Hi (2)"}


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
def test_put_and_patch_are_writes_with_a_body(method: str) -> None:
    assert Integration.model_validate(writer(method=method, body={"title": "{title}"})).actions[0].request.method == method


def test_delete_is_a_write_without_a_body() -> None:
    assert Integration.model_validate(writer(method="DELETE")).actions[0].request.method == "DELETE"


@pytest.mark.parametrize(
    "build, why",
    [
        (lambda: writer(method="DELETE", body={"a": "b"}), "a body on DELETE"),
        (lambda: writer(method="PUT", body={"title": "{title}"}, effect="read"), "PUT labelled as a read"),
        (lambda: writer(method="PATCH", body={"title": "{title}"}, effect="read"), "PATCH labelled as a read"),
        (lambda: writer(method="DELETE", effect="read"), "DELETE labelled as a read"),
        (lambda: writer(body={"t": "{credential.access_token}"}), "the sign-in in a body"),
        (lambda: writer(body={"t": "{nope}"}), "a placeholder that is not a parameter"),
        (lambda: writer(body={"{title}": "x"}), "a placeholder in a body key"),
        (lambda: writer(body={"t": "pre {props}"}), "an object parameter inside other text"),
        (lambda: writer(url="https://api.example.com/{props}"), "an object parameter in the address"),
        (lambda: writer(body={"a": {"b": {"c": {"d": {"e": {"f": {"g": "x"}}}}}}}), "a body that is too deep"),
        (lambda: writer(body={f"k{i}": "x" for i in range(201)}), "a body that is too large"),
        (lambda: writer(body={"a": 1.5}), "a decimal number in a body"),
    ],
)
def test_refused(build, why) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError):
        Integration.model_validate(build())


def test_an_object_parameter_must_be_plain_json_and_not_too_big() -> None:
    integration = Integration.model_validate(writer(body={"props": "{props}", "title": "{title}"}))
    with pytest.raises(IntegrationCallError, match="must be an object"):
        prepare(integration, "list_notes", model_params={"title": "x", "props": "text"}, credential=TOKEN)
    with pytest.raises(IntegrationCallError, match="larger than"):
        prepare(integration, "list_notes", model_params={"title": "x", "props": {"k": "v" * 6000}}, credential=TOKEN)
    with pytest.raises(IntegrationCallError, match="plain JSON"):
        prepare(integration, "list_notes", model_params={"title": "x", "props": {"k": {1, 2}}}, credential=TOKEN)


def test_an_object_parameter_has_no_default() -> None:
    data = writer(body={"props": "{props}"})
    data["actions"][0]["params"]["props"]["default"] = "x"
    with pytest.raises(ValidationError):
        Integration.model_validate(data)
