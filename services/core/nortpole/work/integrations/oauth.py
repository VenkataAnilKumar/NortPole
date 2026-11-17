"""Sign in to an integration's service with the person's own account (OAuth 2.0 authorization code with PKCE).

An administrator registers an OAuth app per service and sets `NORTPOLE_OAUTH_<PROVIDER>_CLIENT_ID` and `..._CLIENT_SECRET`
(provider in capitals, dashes as underscores); without them the person pastes a token instead.

`start` builds the service's address. Its `state` is sealed (same key as stored accounts) and carries the person, the
integration, the PKCE secret and an expiry, so the server keeps nothing between steps. The service returns to a page of the
web app, which POSTs the code and state to `finish`; that trades the code for tokens through the same outbound transport as
every call. `refresh` renews tokens. The provider endpoints were written from the services' public descriptions and have not
been tried against the live services."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets as stdlib_secrets
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

from nortpole.work.integrations import executor, secrets
from nortpole.work.integrations.executor import IntegrationCallError, PreparedRequest

STATE_SECONDS = 600
SKEW_SECONDS = 60


class OAuthError(Exception):
    """A sign-in step failed. The message is safe to show: it never holds a token, a code or a client secret."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Provider:
    authorize_url: str
    token_url: str
    scope_separator: str = " "
    scope_param: str = "scope"
    # How the client id and secret reach the token address: in the form body, or as HTTP Basic.
    client_auth: str = "body"
    pkce: bool = True
    extra_authorize: dict[str, str] = field(default_factory=dict)
    # Whether the token address wants JSON instead of a form body.
    json_body: bool = False


GOOGLE = dict(authorize_url="https://accounts.google.com/o/oauth2/v2/auth", token_url="https://oauth2.googleapis.com/token",
              extra_authorize={"access_type": "offline", "prompt": "consent"})

PROVIDERS: dict[str, Provider] = {
    "github": Provider("https://github.com/login/oauth/authorize", "https://github.com/login/oauth/access_token", pkce=False),
    "google-drive": Provider(**GOOGLE),
    "google-email": Provider(**GOOGLE),
    "google-calendar": Provider(**GOOGLE),
    "hubspot": Provider("https://app.hubspot.com/oauth/authorize", "https://api.hubapi.com/oauth/v1/token", pkce=False),
    "dropbox": Provider("https://www.dropbox.com/oauth2/authorize", "https://api.dropboxapi.com/oauth2/token", extra_authorize={"token_access_type": "offline"}),
    "spotify": Provider("https://accounts.spotify.com/authorize", "https://accounts.spotify.com/api/token", client_auth="basic"),
    "webflow": Provider("https://webflow.com/oauth/authorize", "https://api.webflow.com/oauth/access_token", pkce=False),
    "notion": Provider("https://api.notion.com/v1/oauth/authorize", "https://api.notion.com/v1/oauth/token", client_auth="basic", pkce=False,
                       extra_authorize={"owner": "user"}, json_body=True),
    "airtable": Provider("https://airtable.com/oauth2/v1/authorize", "https://airtable.com/oauth2/v1/token", client_auth="basic"),
}

# Transport override for tests: an httpx transport used for the token address.
token_transport: Any = None
# Address check override for tests; the real check (the administrator's outbound-address setting) is used when None.
token_validate: Any = None


def _env_name(provider: str, part: str) -> str:
    return f"NORTPOLE_OAUTH_{provider.upper().replace('-', '_')}_{part}"


def client_for(provider: str) -> tuple[str, str] | None:
    client_id, client_secret = os.environ.get(_env_name(provider, "CLIENT_ID")), os.environ.get(_env_name(provider, "CLIENT_SECRET"))
    return (client_id, client_secret) if client_id and client_secret else None


def available(provider: str | None) -> bool:
    """Whether people can sign in with this provider here: it is known and an administrator set its client."""
    return bool(provider) and provider in PROVIDERS and client_for(provider) is not None  # type: ignore[arg-type]


def redirect_uri() -> str:
    from nortpole.configs.app_configs import WEB_DOMAIN

    return f"{WEB_DOMAIN.rstrip('/')}/app/sources/oauth"


def _challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def start(*, user_id: str, integration_id: str, provider: str, scopes: list[str], now: float | None = None) -> str:
    config = PROVIDERS.get(provider)
    client = client_for(provider)
    if config is None or client is None:
        raise OAuthError("oauth_not_configured", "Signing in with this service is not set up here. Paste a token instead, or ask an administrator.")
    verifier = stdlib_secrets.token_urlsafe(48)
    try:
        state = secrets.seal({"u": user_id, "i": integration_id, "p": provider, "v": verifier, "exp": int((now or time.time()) + STATE_SECONDS), "n": stdlib_secrets.token_urlsafe(8)})
    except secrets.SecretsError as exc:
        raise OAuthError(exc.code, str(exc)) from exc
    params: dict[str, str] = {"client_id": client[0], "redirect_uri": redirect_uri(), "response_type": "code", "state": state}
    if scopes:
        params[config.scope_param] = config.scope_separator.join(scopes)
    if config.pkce:
        params.update(code_challenge=_challenge(verifier), code_challenge_method="S256")
    params.update(config.extra_authorize)
    return f"{config.authorize_url}?{urlencode(params)}"


def open_state(state: str, *, user_id: str, now: float | None = None) -> dict[str, Any]:
    try:
        data = secrets.unseal(state)
    except secrets.SecretsError:
        raise OAuthError("bad_state", "That sign-in link is not valid. Start again.") from None
    if not isinstance(data.get("exp"), int) or data["exp"] < (now or time.time()):
        raise OAuthError("state_expired", "That sign-in took too long. Start again.")
    if data.get("u") != user_id:
        raise OAuthError("bad_state", "That sign-in link was started by someone else.")
    if data.get("p") not in PROVIDERS:
        raise OAuthError("bad_state", "That sign-in link is not valid. Start again.")
    return data


def _token_call(provider: str, fields: dict[str, str]) -> dict[str, Any]:
    config, client = PROVIDERS[provider], client_for(provider)
    if client is None:
        raise OAuthError("oauth_not_configured", "Signing in with this service is not set up here.")
    headers = {"Accept": "application/json", "Content-Type": "application/json" if config.json_body else "application/x-www-form-urlencoded"}
    body = dict(fields)
    if config.client_auth == "basic":
        headers["Authorization"] = "Basic " + base64.b64encode(f"{client[0]}:{client[1]}".encode()).decode()
    else:
        body.update(client_id=client[0], client_secret=client[1])
    request = PreparedRequest("POST", config.token_url, {}, body, headers)
    try:
        status, raw, ctype = executor.http_transport(request, httpx_transport=token_transport, validate=token_validate)
    except IntegrationCallError as exc:
        raise OAuthError("token_failed", f"The service could not be reached to finish signing in ({exc.code}).") from None
    if status >= 400 or "json" not in ctype.lower():
        raise OAuthError("token_failed", f"The service refused the sign-in (HTTP {status}). Start again.")
    try:
        data = json.loads(raw)
    except ValueError:
        raise OAuthError("token_failed", "The service answered with something unreadable. Start again.") from None
    if not isinstance(data, dict) or not isinstance(data.get("access_token"), str) or not data["access_token"]:
        raise OAuthError("token_failed", "The service did not give an access token. Start again.")
    return data


def _account(data: dict[str, Any], previous_refresh: str | None = None, now: float | None = None) -> dict[str, Any]:
    account: dict[str, Any] = {"access_token": data["access_token"]}
    refresh = data.get("refresh_token") if isinstance(data.get("refresh_token"), str) and data.get("refresh_token") else previous_refresh
    if refresh:
        account["refresh_token"] = refresh
    expires_in = data.get("expires_in")
    if isinstance(expires_in, (int, float)) and not isinstance(expires_in, bool) and expires_in > 0:
        account["expires_at"] = int((now or time.time()) + expires_in)
    return account


def finish(*, state: str, code: str, user_id: str, now: float | None = None) -> tuple[str, dict[str, Any]]:
    """Check the state and trade the code for tokens. Returns the integration id and the account to store."""
    data = open_state(state, user_id=user_id, now=now)
    config = PROVIDERS[data["p"]]
    fields = {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri()}
    if config.pkce:
        fields["code_verifier"] = data["v"]
    return data["i"], _account(_token_call(data["p"], fields), now=now)


def needs_refresh(account: dict[str, Any], now: float | None = None) -> bool:
    expires_at = account.get("expires_at")
    return bool(account.get("refresh_token")) and isinstance(expires_at, int) and expires_at <= (now or time.time()) + SKEW_SECONDS


def refresh(provider: str, account: dict[str, Any], now: float | None = None) -> dict[str, Any]:
    if provider not in PROVIDERS or not account.get("refresh_token"):
        raise OAuthError("cannot_refresh", "This sign-in cannot be renewed. Connect again.")
    data = _token_call(provider, {"grant_type": "refresh_token", "refresh_token": account["refresh_token"]})
    return _account(data, previous_refresh=account["refresh_token"], now=now)
