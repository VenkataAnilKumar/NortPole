"""The integration definition format: what it accepts and what it refuses (decision 0008)."""

import copy

import pytest
from pydantic import ValidationError

from nortpole.work.integrations.manifest import CATEGORIES, Integration

GOOD = {
    "schema_version": 1,
    "id": "example-notes",
    "name": "Example notes",
    "version": "1.0.0",
    "description": "Read notes from an example service.",
    "kind": "plugin",
    "group": "horizontal",
    "category": "product",
    "auth": {"mode": "oauth", "provider": "example", "scopes": ["notes.read"]},
    "hosts": ["api.example.com"],
    "data_classes": ["internal"],
    "policy_default": "needs_approval",
    "actions": [
        {
            "id": "list_notes",
            "name": "List notes",
            "description": "List notes.",
            "effect": "read",
            "params": {
                "folder": {"type": "string", "description": "Folder id.", "required": True},
                "limit": {"type": "integer", "description": "How many.", "fill": "user", "default": 10, "minimum": 1, "maximum": 50},
            },
            "request": {
                "method": "GET",
                "url": "https://api.example.com/v1/folders/{folder}/notes",
                "query": {"limit": "{limit}"},
                "headers": {"Authorization": "Bearer {credential.access_token}"},
            },
            "response": {"outputs": {"notes": {"path": "$.notes[*]", "type": "array", "description": "Notes."}}},
        }
    ],
}


def make(**changes) -> dict:  # type: ignore[no-untyped-def]
    data = copy.deepcopy(GOOD)
    data.update(changes)
    return data


def action(data: dict, **changes) -> dict:  # type: ignore[no-untyped-def]
    data["actions"][0].update(changes)
    return data


def request(data: dict, **changes) -> dict:  # type: ignore[no-untyped-def]
    data["actions"][0]["request"].update(changes)
    return data


def test_a_good_definition_is_accepted() -> None:
    assert Integration.model_validate(GOOD).actions[0].id == "list_notes"


def test_a_vertical_definition_in_a_known_category_is_accepted() -> None:
    data = make(group="vertical", category="life-science", data_classes=["restricted"])
    assert Integration.model_validate(data).category == "life-science"


@pytest.mark.parametrize(
    "build, why",
    [
        (lambda: make(extra="x"), "unknown field"),
        (lambda: make(category="finance"), "a vertical category in a horizontal group"),
        (lambda: make(group="vertical"), "a horizontal category in a vertical group"),
        (lambda: make(version="1.0"), "version format"),
        (lambda: make(hosts=["*.example.com"]), "wildcard host"),
        (lambda: make(hosts=["API.example.com"]), "upper-case host"),
        (lambda: make(hosts=["api.example.com", "api.example.com"]), "host listed twice"),
        (lambda: make(data_classes=[]), "no data class"),
        (lambda: make(actions=[]), "no actions"),
        (lambda: make(auth={"mode": "none", "provider": "example"}), "provider with no sign-in"),
        (lambda: make(auth={"mode": "oauth"}), "sign-in without a provider"),
        (lambda: make(auth={"mode": "api_key", "provider": "example", "scopes": ["x"]}), "scopes on an api key"),
        (lambda: request(make(), url="http://api.example.com/v1/x"), "plain http"),
        (lambda: request(make(), url="https://{folder}.example.com/x"), "placeholder in the host"),
        (lambda: request(make(), url="https://other.example.org/x"), "host not listed"),
        (lambda: request(make(), url="https://user:pw@api.example.com/x"), "credentials in the url"),
        (lambda: request(make(), url="https://api.example.com:8443/x"), "a port"),
        (lambda: request(make(), url="https://api.example.com/{missing}"), "placeholder that is not a parameter"),
        (lambda: request(make(), query={"limit": "{limit}", "token": "{credential.access_token}"}), "sign-in in a query"),
        (lambda: request(make(), headers={"Authorization": "Bearer abc123"}), "literal secret in a header"),
        (lambda: request(make(), headers={"X-Api-Key": "{credential.api_key}"}), "api key placeholder with oauth"),
        (lambda: request(make(), headers={}), "signs in but never sends the credential"),
        (lambda: request(make(), body={"a": "b"}), "a GET with a body"),
        (lambda: action(make(), effect="write"), "a write that starts as read-only GET"),
        (lambda: make(actions=[GOOD["actions"][0], GOOD["actions"][0]]), "duplicate action ids"),
        (lambda: action(make(), response={"outputs": {"x": {"path": "notes", "type": "array", "description": "d"}}}), "bad output path"),
        (lambda: action(make(), params={"bad name": {"type": "string", "description": "d"}}), "bad parameter name"),
        (lambda: action(make(), params={"folder": {"type": "string", "description": "d", "default": 3}}), "default of the wrong type"),
        (lambda: action(make(), params={"folder": {"type": "string", "description": "d", "minimum": 1}}), "minimum on a string"),
    ],
)
def test_refused(build, why) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError):
        Integration.model_validate(build())


def test_a_write_action_can_never_default_to_allowed() -> None:
    data = make(policy_default="allowed")
    data["actions"][0]["effect"] = "write"
    data["actions"][0]["request"].update(method="POST", body={"title": "{folder}"})
    with pytest.raises(ValidationError, match="needs_approval"):
        Integration.model_validate(data)
    data["policy_default"] = "needs_approval"
    assert Integration.model_validate(data).actions[0].effect == "write"


def test_no_sign_in_needs_no_credential() -> None:
    data = make(auth={"mode": "none"}, policy_default="allowed")
    data["actions"][0]["request"]["headers"] = {"Accept": "application/json"}
    assert Integration.model_validate(data).auth.mode == "none"


def test_the_category_lists_have_no_overlap_and_are_slugs() -> None:
    horizontal, vertical = set(CATEGORIES["horizontal"]), set(CATEGORIES["vertical"])
    assert not horizontal & vertical, "an item sits in one group, so a name is not in both"
    assert all(c == c.lower() and " " not in c for c in horizontal | vertical)
