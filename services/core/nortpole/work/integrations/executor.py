"""Run one action of an integration definition (decision 0008, phase 2).

`prepare` turns a definition, an action and parameters into one request. `extract` reads the named outputs out of the
response. `run` does both around a real call, and logs it. The rules the definition format promised are enforced again
here, so a definition that was built in code and never validated still cannot reach another host or leak a secret:

* each parameter is set only by who its `fill` allows (the person's settings or the model), is type-checked and capped,
  and a value with a line break is refused (no header or request splitting);
* the destination host must be one the definition lists, over https, with no redirects followed;
* the credential comes only from the person's connected account and is never part of a log, an error or a repr;
* the response must be JSON and is read up to a size limit; an error response is reported by status only, because the
  body can hold anyone's data.

Policy ("may this person use this integration?") is decided before this module is called; it checks nothing about who.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import quote, urlsplit

from nortpole.work.integrations.manifest import Action, Integration, PLACEHOLDER, Param, body_strings

MAX_RESPONSE_BYTES = 2_000_000
TIMEOUT_SECONDS = 15.0
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
CREDENTIAL_KEYS = {"credential.access_token": "access_token", "credential.api_key": "api_key"}


class IntegrationCallError(Exception):
    """A call that was refused or failed. The message is safe to show: it never holds a secret or a response body."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PreparedRequest:
    method: str
    url: str
    query: dict[str, str]
    body: Any
    # Headers can hold the credential, so they never appear in a repr or a log.
    headers: dict[str, str] = field(repr=False)

    @property
    def host(self) -> str:
        return urlsplit(self.url).hostname or ""


def _check(name: str, param: Param, value: Any) -> Any:
    if param.type == "string":
        if not isinstance(value, str):
            raise IntegrationCallError("bad_parameter", f"{name} must be text")
        if len(value) > param.max_length:
            raise IntegrationCallError("bad_parameter", f"{name} is longer than {param.max_length} characters")
        if CONTROL.search(value):
            raise IntegrationCallError("bad_parameter", f"{name} may not contain a line break or control character")
        if param.enum is not None and value not in param.enum:
            raise IntegrationCallError("bad_parameter", f"{name} must be one of {', '.join(param.enum)}")
        return value
    if param.type == "integer":
        if isinstance(value, str) and re.fullmatch(r"-?\d{1,9}", value.strip()):
            value = int(value)
        if not isinstance(value, int) or isinstance(value, bool):
            raise IntegrationCallError("bad_parameter", f"{name} must be a whole number")
        if param.minimum is not None and value < param.minimum:
            raise IntegrationCallError("bad_parameter", f"{name} must be at least {param.minimum}")
        if param.maximum is not None and value > param.maximum:
            raise IntegrationCallError("bad_parameter", f"{name} must be at most {param.maximum}")
        return value
    if param.type == "object":
        if not isinstance(value, dict):
            raise IntegrationCallError("bad_parameter", f"{name} must be an object")
        try:
            body_strings(value)
            size = len(json.dumps(value))
        except (ValueError, TypeError):
            raise IntegrationCallError("bad_parameter", f"{name} holds something other than plain JSON data")
        if size > param.max_length * 10:
            raise IntegrationCallError("bad_parameter", f"{name} is larger than {param.max_length * 10} characters")
        return value
    if not isinstance(value, bool):
        raise IntegrationCallError("bad_parameter", f"{name} must be true or false")
    return value


def _text(value: Any) -> str:
    return "true" if value is True else "false" if value is False else str(value)


def _values(action: Action, user: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    """Merge the two suppliers' values after checking who may set what, then apply defaults and check each one."""
    merged: dict[str, Any] = {}
    for supplier, given, allowed in (("the person", user, ("user", "user_or_model")), ("the model", model, ("model", "user_or_model"))):
        for name, value in given.items():
            param = action.params.get(name)
            if param is None:
                raise IntegrationCallError("bad_parameter", f"{name} is not a parameter of {action.id}")
            if param.fill not in allowed:
                raise IntegrationCallError("bad_parameter", f"{name} can't be set by {supplier}")
            if name in merged:
                raise IntegrationCallError("bad_parameter", f"{name} was given twice")
            merged[name] = value
    values: dict[str, Any] = {}
    for name, param in action.params.items():
        value = merged.get(name)
        if value is None:
            value = param.default
        if value is None:
            if param.required:
                raise IntegrationCallError("missing_parameter", f"{name} is required")
            continue
        values[name] = _check(name, param, value)
    return values


def prepare(
    integration: Integration,
    action_id: str,
    *,
    user_params: dict[str, Any] | None = None,
    model_params: dict[str, Any] | None = None,
    credential: dict[str, str] | None = None,
) -> PreparedRequest:
    action = next((a for a in integration.actions if a.id == action_id), None)
    if action is None:
        raise IntegrationCallError("unknown_action", f"{integration.id} has no action {action_id}")
    values = _values(action, user_params or {}, model_params or {})

    def fill(text: str, *, encode: bool) -> str | None:
        """Fill placeholders; None when an optional parameter in it has no value."""
        missing = False

        def one(match: re.Match[str]) -> str:
            nonlocal missing
            ref = match.group(1)
            if ref in CREDENTIAL_KEYS:
                secret = (credential or {}).get(CREDENTIAL_KEYS[ref])
                if not secret:
                    raise IntegrationCallError("not_connected", f"{integration.name} is not connected for this person")
                if CONTROL.search(secret):
                    raise IntegrationCallError("not_connected", "the saved sign-in is not usable")
                return secret
            if ref not in values:
                missing = True
                return ""
            return quote(_text(values[ref]), safe="") if encode else _text(values[ref])

        result = PLACEHOLDER.sub(one, text)
        return None if missing else result

    request = action.request
    url = fill(request.url, encode=True)
    if url is None:
        raise IntegrationCallError("missing_parameter", "a value needed in the address is missing")
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in integration.hosts or parts.username or parts.password:
        raise IntegrationCallError("host_not_allowed", "the address is not one this integration may call")
    query = {k: v for k, raw in request.query.items() if (v := fill(raw, encode=False)) is not None}
    headers = {k: v for k, raw in request.headers.items() if (v := fill(raw, encode=False)) is not None}
    _MISSING = object()

    def fill_node(node: Any) -> Any:
        """Fill a body tree: a whole-placeholder text takes the parameter's own type; a missing optional one is dropped."""
        if isinstance(node, str):
            whole = PLACEHOLDER.fullmatch(node)
            if whole and whole.group(1) not in CREDENTIAL_KEYS:
                return values[whole.group(1)] if whole.group(1) in values else _MISSING
            text = fill(node, encode=False)
            return _MISSING if text is None else text
        if isinstance(node, list):
            items = [fill_node(i) for i in node]
            return [i for i in items if i is not _MISSING]
        if isinstance(node, dict):
            kept = {k: fill_node(v) for k, v in node.items()}
            return {k: v for k, v in kept.items() if v is not _MISSING}
        return node

    body = fill_node(request.body) if request.body is not None else None
    return PreparedRequest(method=request.method, url=url, query=query, body=body, headers=headers)


_STEP = re.compile(r"\.([A-Za-z_][A-Za-z0-9_]*)|\[(\d{1,3})\]|\[\*\]")


def read_path(payload: Any, path: str) -> Any:
    """Read `$.a.b[0]` or `$.items[*]` from parsed JSON; None where the path leads nowhere."""
    nodes: list[Any] = [payload]
    fan_out = False
    for match in _STEP.finditer(path[1:]):
        key, index = match.group(1), match.group(2)
        nxt: list[Any] = []
        for node in nodes:
            if key is not None:
                if isinstance(node, dict) and key in node:
                    nxt.append(node[key])
            elif index is not None:
                if isinstance(node, list) and int(index) < len(node):
                    nxt.append(node[int(index)])
            elif isinstance(node, list):
                nxt.extend(node)
                fan_out = True
        nodes = nxt
    if fan_out:
        return nodes
    return nodes[0] if nodes else None


def extract(action: Action, payload: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, spec in action.response.outputs.items():
        value = read_path(payload, spec.path)
        kinds = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict}
        if value is not None and (not isinstance(value, kinds[spec.type]) or (spec.type in ("integer", "number") and isinstance(value, bool))):
            value = None
        if value is None and spec.type == "array" and "[*]" in spec.path:
            value = []
        out[name] = value
    return out


Transport = Callable[[PreparedRequest], tuple[int, bytes, str]]


def http_transport(request: PreparedRequest, *, httpx_transport: Any = None, validate: Callable[[str], str] | None = None) -> tuple[int, bytes, str]:
    """The real call: web-address safety check, no redirects, a time limit and a size limit."""
    import httpx

    if validate is None:
        validate = _default_validate
    validate(request.url)
    with httpx.Client(transport=httpx_transport, follow_redirects=False, timeout=TIMEOUT_SECONDS) as client:
        with client.stream(
            request.method, request.url, params=request.query or None, headers=request.headers,
            json=request.body if request.body is not None else None,
        ) as response:
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    raise IntegrationCallError("too_large", "the response is larger than the limit")
                chunks.append(chunk)
            return response.status_code, b"".join(chunks), response.headers.get("content-type", "")


def _default_validate(url: str) -> str:
    from nortpole.server.features.mcp.ssrf import validate_mcp_outbound_url

    return validate_mcp_outbound_url(url)


def run(
    integration: Integration,
    action_id: str,
    *,
    user_params: dict[str, Any] | None = None,
    model_params: dict[str, Any] | None = None,
    credential: dict[str, str] | None = None,
    user_id: str | None = None,
    transport: Transport | None = None,
) -> dict[str, Any]:
    start = time.monotonic()
    outcome, status, size = "refused", None, 0
    host = None
    try:
        size = len(json.dumps({"user": user_params or {}, "model": model_params or {}}, default=str))
        request = prepare(integration, action_id, user_params=user_params, model_params=model_params, credential=credential)
        host = request.host
        status, body, content_type = (transport or http_transport)(request)
        if 300 <= status < 400:
            raise IntegrationCallError("redirect", "the service tried to send the call somewhere else; it was not followed")
        if not 200 <= status < 300:
            outcome = "service_error"
            raise IntegrationCallError("service_error", f"{integration.name} answered with status {status}")
        if "json" not in content_type.lower():
            raise IntegrationCallError("not_json", "the service did not answer with JSON")
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise IntegrationCallError("not_json", "the service did not answer with valid JSON") from exc
        action = next(a for a in integration.actions if a.id == action_id)
        result = extract(action, payload)
        outcome = "returned"
        return result
    finally:
        _log(integration, action_id, host, user_id, outcome, status, size, int((time.monotonic() - start) * 1000))


def _log(integration: Integration, action_id: str, host: str | None, user_id: str | None, outcome: str, status: int | None, size: int, ms: int) -> None:
    """One audit row per call: which integration and action, which host, for whom, how long, how big the parameters were and
    how it ended. Never the parameters, the credential or the response."""
    try:
        from nortpole.governance.route_policy.audit import record_audit
        from nortpole.utils.audit import AuditAction, AuditOutcome

        record_audit(
            AuditAction.TOOL_CALL, AuditOutcome.SUCCESS if outcome == "returned" else AuditOutcome.FAILURE, actor=None,
            summary=f"Integration {integration.name} {action_id} {outcome}" + (f" ({host})" if host else ""),
            details={"integration": integration.id, "version": integration.version, "action": action_id, "host": host,
                     "user_id": user_id, "argument_bytes": size, "status": status, "ms": ms, "outcome": outcome},
            resource_type="integration", resource_id=integration.id,
        )
    except Exception:  # noqa: BLE001 - logging must never change what the call returned
        from nortpole.utils.logger import setup_logger

        setup_logger().warning("integration call was not logged", exc_info=True)
