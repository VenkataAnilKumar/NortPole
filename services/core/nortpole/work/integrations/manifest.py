"""The integration definition: a connector or plugin written as data, not code.

An integration says which outside service it talks to, how a person signs in, and what each action sends and returns.
It runs nothing itself: a fixed executor reads it. The format is strict so a definition cannot carry surprises:

* **Fixed destination.** Every request goes to an exact host the definition lists in `hosts`. A placeholder can fill a
  path or a query value but never the host, so no parameter can point a call somewhere else.
* **Secrets only from the account.** A token or key is written as `{credential.access_token}` or `{credential.api_key}`
  and is filled in from the person's connected account. A literal secret in a header is refused.
* **Who fills each parameter** (`fill`): the person, the model, or either. A `user` parameter is never offered to the
  model, so a person can fix a value (a base, a limit) that the model must not choose.
* **Reads and writes are labelled.** An action with `effect: write` can never default to "allowed"; it starts as
  "needs approval", so a write always passes an administrator first.

Placeholders are written `{name}`. A query value that is exactly one placeholder is left out when that parameter has no
value. Path placeholders are URL-encoded by the executor.

"""

from __future__ import annotations

import re
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
SEMVER = re.compile(r"^\d{1,4}\.\d{1,4}\.\d{1,4}$")
PARAM_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,40}$")
ACTION_ID = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
HOST = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")
PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_.]*)\}")
JSON_PATH = re.compile(r"^\$(\.[A-Za-z_][A-Za-z0-9_]*|\[\d{1,3}\]|\[\*\])*$")
CREDENTIAL_FIELDS = {"credential.access_token": "oauth", "credential.api_key": "api_key"}

KINDS = ("connector", "plugin")
GROUPS = ("horizontal", "vertical")
# The categories people browse by. Adding one is a change to these lists, so the set stays reviewed.
HORIZONTAL_CATEGORIES = ("engineering", "design", "product", "code", "automations", "legal", "sales", "gtm")
VERTICAL_CATEGORIES = (
    "law", "finance", "health", "bio", "life-science", "voice", "video", "media", "entertainment",
    "insurance", "energy", "education", "retail", "public-sector",
)
CATEGORIES = {"horizontal": HORIZONTAL_CATEGORIES, "vertical": VERTICAL_CATEGORIES}
DATA_CLASSES = ("public", "internal", "confidential", "restricted")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Auth(_Strict):
    """How a person signs in. `oauth` and `api_key` use the person's own connected account."""

    mode: Literal["none", "oauth", "api_key"]
    provider: str | None = Field(default=None, pattern=SLUG.pattern)
    scopes: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _shape(self) -> "Auth":
        if self.mode == "none" and (self.provider or self.scopes):
            raise ValueError("an integration with no sign-in names no provider or scopes")
        if self.mode != "none" and not self.provider:
            raise ValueError("a provider is required when people sign in")
        if self.mode != "oauth" and self.scopes:
            raise ValueError("only oauth has scopes")
        if any(not s or len(s) > 100 or " " in s for s in self.scopes):
            raise ValueError("a scope is one word of 1 to 100 characters")
        return self


class Param(_Strict):
    # "object" is a JSON object the person or model supplies; it may be placed only as a whole value in a body.
    type: Literal["string", "integer", "boolean", "object"]
    description: str = Field(min_length=1, max_length=300)
    required: bool = False
    # Who may set it: the person only, the model only, or either.
    fill: Literal["user", "model", "user_or_model"] = "user_or_model"
    default: StrictStr | StrictInt | StrictBool | None = None
    enum: list[str] | None = Field(default=None, max_length=30)
    minimum: StrictInt | None = None
    maximum: StrictInt | None = None
    max_length: StrictInt = Field(default=500, ge=1, le=5000)

    @model_validator(mode="after")
    def _shape(self) -> "Param":
        if self.type != "integer" and (self.minimum is not None or self.maximum is not None):
            raise ValueError("minimum and maximum are for integers")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum is above maximum")
        if self.enum is not None and self.type != "string":
            raise ValueError("enum is for strings")
        if self.type == "object" and (self.default is not None or self.enum is not None):
            raise ValueError("an object parameter has no default or enum")
        if self.default is not None:
            kinds = {"string": str, "integer": int, "boolean": bool}[self.type]
            if not isinstance(self.default, kinds) or (self.type == "integer" and isinstance(self.default, bool)):
                raise ValueError(f"the default must be a {self.type}")
            if self.required:
                raise ValueError("a required parameter has no default")
        return self


BODY_MAX_DEPTH = 6
BODY_MAX_NODES = 200


def body_strings(node: Any, depth: int = 0) -> list[str]:
    """Every text value in a body tree; raises when the tree is too deep, too large or holds anything but JSON data."""
    if depth > BODY_MAX_DEPTH:
        raise ValueError(f"a body is at most {BODY_MAX_DEPTH} levels deep")
    if node is None or isinstance(node, (bool, int)):
        return []
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        out: list[str] = []
        for item in node:
            out += body_strings(item, depth + 1)
        return out
    if isinstance(node, dict):
        out = []
        for key, item in node.items():
            if not isinstance(key, str) or not key or len(key) > 80 or PLACEHOLDER.search(key):
                raise ValueError("a body key is a plain name and holds no placeholder")
            out += body_strings(item, depth + 1)
        return out
    raise ValueError("a body holds only text, numbers, true or false, null, lists and objects")


def _body_nodes(node: Any) -> int:
    if isinstance(node, dict):
        return 1 + sum(_body_nodes(v) for v in node.values())
    if isinstance(node, list):
        return 1 + sum(_body_nodes(v) for v in node)
    return 1


class Request(_Strict):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    url: str = Field(min_length=10, max_length=500)
    query: dict[str, str] = Field(default_factory=dict, max_length=20)
    headers: dict[str, str] = Field(default_factory=dict, max_length=10)
    # A JSON tree. A text value that is exactly one placeholder takes that parameter's own type (a number stays a number,
    # an object stays an object); a missing optional parameter leaves its key or list item out.
    body: dict[str, Any] | None = None


class Output(_Strict):
    path: str = Field(min_length=1, max_length=120)
    type: Literal["string", "integer", "number", "boolean", "array", "object"]
    description: str = Field(min_length=1, max_length=300)

    @field_validator("path")
    @classmethod
    def _path(cls, value: str) -> str:
        if not JSON_PATH.match(value):
            raise ValueError("a path looks like $.a.b[0] or $.items[*]")
        return value


class Response(_Strict):
    outputs: dict[str, Output] = Field(min_length=1, max_length=20)


class Action(_Strict):
    id: str = Field(pattern=ACTION_ID.pattern)
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=300)
    # "write" changes something in the outside system. Writes always start as "needs approval".
    effect: Literal["read", "write"]
    params: dict[str, Param] = Field(default_factory=dict, max_length=20)
    request: Request
    response: Response


class Integration(_Strict):
    schema_version: Literal[1] = 1
    id: str = Field(pattern=SLUG.pattern)
    name: str = Field(min_length=1, max_length=80)
    version: str = Field(pattern=SEMVER.pattern)
    description: str = Field(min_length=1, max_length=300)
    kind: Literal["connector", "plugin"]
    group: Literal["horizontal", "vertical"]
    category: str
    auth: Auth
    # Exact hosts this integration may call; nothing else is reachable.
    hosts: list[str] = Field(min_length=1, max_length=10)
    data_classes: list[Literal["public", "internal", "confidential", "restricted"]] = Field(min_length=1)
    # What an administrator's policy starts as: people may use it, or each use needs approval.
    policy_default: Literal["allowed", "needs_approval"] = "needs_approval"
    actions: list[Action] = Field(min_length=1, max_length=30)

    @field_validator("hosts")
    @classmethod
    def _hosts(cls, hosts: list[str]) -> list[str]:
        bad = [h for h in hosts if not HOST.match(h)]
        if bad:
            raise ValueError(f"hosts must be exact lower-case host names, not {bad}")
        if len(set(hosts)) != len(hosts):
            raise ValueError("a host is listed once")
        return hosts

    @model_validator(mode="after")
    def _rules(self) -> "Integration":
        if self.category not in CATEGORIES[self.group]:
            raise ValueError(f"{self.category!r} is not a {self.group} category")
        ids = [a.id for a in self.actions]
        if len(set(ids)) != len(ids):
            raise ValueError("action ids are unique")
        for action in self.actions:
            self._check_action(action)
            if action.effect == "write" and self.policy_default != "needs_approval":
                raise ValueError(f"{action.id}: an integration with a write action starts as needs_approval")
        return self

    def _check_action(self, action: Action) -> None:
        where = action.id
        for name in action.params:
            if not PARAM_NAME.match(name):
                raise ValueError(f"{where}: parameter name {name!r} is not a plain name")
        request = action.request
        parts = urlsplit(request.url)
        if parts.scheme != "https":
            raise ValueError(f"{where}: the url must start with https://")
        if "{" in (parts.netloc or ""):
            raise ValueError(f"{where}: the host in a url is fixed and cannot hold a placeholder")
        if parts.hostname not in self.hosts:
            raise ValueError(f"{where}: {parts.hostname} is not in hosts")
        if parts.username or parts.password or parts.port not in (None, 443):
            raise ValueError(f"{where}: no user, password or port in a url")
        texts: list[tuple[str, str]] = [("url", request.url)]
        texts += [(f"query {k}", v) for k, v in request.query.items()]
        texts += [(f"header {k}", v) for k, v in request.headers.items()]
        try:
            body_texts = body_strings(request.body)
        except ValueError as e:
            raise ValueError(f"{where}: {e}")
        if request.body is not None and _body_nodes(request.body) > BODY_MAX_NODES:
            raise ValueError(f"{where}: a body has at most {BODY_MAX_NODES} parts")
        texts += [("body", v) for v in body_texts]
        for label, text in texts:
            for ref in PLACEHOLDER.findall(text):
                if ref in CREDENTIAL_FIELDS:
                    if not label.startswith("header "):
                        raise ValueError(f"{where}: {label} may not hold the sign-in; only a header may")
                    if CREDENTIAL_FIELDS[ref] != self.auth.mode:
                        raise ValueError(f"{where}: {ref} needs auth mode {CREDENTIAL_FIELDS[ref]}")
                elif ref not in action.params:
                    raise ValueError(f"{where}: {label} uses {{{ref}}}, which is not a parameter")
                elif action.params[ref].type == "object" and not (label == "body" and text == "{" + ref + "}"):
                    raise ValueError(f"{where}: an object parameter ({ref}) is placed only as a whole value in the body")
        for key, value in request.headers.items():
            if key.lower() in ("authorization", "cookie", "x-api-key") and not PLACEHOLDER.search(value):
                raise ValueError(f"{where}: header {key} must take its value from the account, not a literal")
        if request.method in ("GET", "DELETE") and request.body:
            raise ValueError(f"{where}: a {request.method} has no body")
        if request.method == "GET" and action.effect == "write":
            raise ValueError(f"{where}: a GET is a read; a write uses another method")
        if request.method in ("PUT", "PATCH", "DELETE") and action.effect != "write":
            raise ValueError(f"{where}: {request.method} changes something, so the action is a write")
        if self.auth.mode != "none" and not any(
            ref in CREDENTIAL_FIELDS for v in request.headers.values() for ref in PLACEHOLDER.findall(v)
        ):
            raise ValueError(f"{where}: the integration signs in but this action never sends the credential")
