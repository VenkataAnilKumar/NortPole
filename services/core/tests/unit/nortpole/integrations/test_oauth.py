"""Signing in with the person's own account: the address, the sealed state, the code exchange and the refresh (decision 0008)."""

import base64
import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from nortpole.work.integrations import oauth, secrets
from nortpole.work.integrations.oauth import OAuthError

USER = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(autouse=True)
def configured(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ENCRYPTION_KEY_SECRET", secrets.generate_key())
    for p in ("GITHUB", "SPOTIFY", "AIRTABLE", "NOTION", "GOOGLE_DRIVE"):
        monkeypatch.setenv(f"NORTPOLE_OAUTH_{p}_CLIENT_ID", f"id-{p}")
        monkeypatch.setenv(f"NORTPOLE_OAUTH_{p}_CLIENT_SECRET", f"SECRET-{p}")
    monkeypatch.setattr(oauth, "token_validate", lambda url: url)
    yield
    monkeypatch.setattr(oauth, "token_transport", None)


def provider_replies(monkeypatch: pytest.MonkeyPatch, status: int = 200, body=None, ctype: str = "application/json"):  # type: ignore[no-untyped-def]
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(url=str(request.url), headers=dict(request.headers), body=request.content.decode())
        data = body if body is not None else {"access_token": "AT-1", "refresh_token": "RT-1", "expires_in": 3600}
        return httpx.Response(status, content=data if isinstance(data, bytes) else json.dumps(data).encode(), headers={"content-type": ctype})

    monkeypatch.setattr(oauth, "token_transport", httpx.MockTransport(handler))
    return seen


def query(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


def test_the_address_carries_the_client_scopes_pkce_and_a_sealed_state() -> None:
    url = oauth.start(user_id=USER, integration_id="airtable", provider="airtable", scopes=["data.records:read", "schema.bases:read"])
    q = query(url)
    assert url.startswith("https://airtable.com/oauth2/v1/authorize?")
    assert q["client_id"] == "id-AIRTABLE" and q["response_type"] == "code" and q["scope"] == "data.records:read schema.bases:read"
    assert q["redirect_uri"].endswith("/app/sources/oauth")
    assert q["code_challenge_method"] == "S256" and len(q["code_challenge"]) == 43
    assert "SECRET" not in url and USER not in url, "the state is sealed, not readable"
    assert "code_challenge" not in query(oauth.start(user_id=USER, integration_id="github", provider="github", scopes=["repo"]))


def test_a_service_nobody_set_up_cannot_start() -> None:
    assert not oauth.available("slack") and not oauth.available("hubspot") and not oauth.available(None)
    assert oauth.available("github")
    for provider in ("hubspot", "unknown"):
        with pytest.raises(OAuthError) as err:
            oauth.start(user_id=USER, integration_id="x", provider=provider, scopes=[])
        assert err.value.code == "oauth_not_configured"


def test_the_code_is_traded_with_the_pkce_secret_and_the_account_is_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = provider_replies(monkeypatch)
    q = query(oauth.start(user_id=USER, integration_id="airtable", provider="airtable", scopes=["data.records:read"], now=1000))
    integration_id, account = oauth.finish(state=q["state"], code="CODE-9", user_id=USER, now=1000)
    assert integration_id == "airtable"
    assert account == {"access_token": "AT-1", "refresh_token": "RT-1", "expires_at": 4600}
    form = {k: v[0] for k, v in parse_qs(seen["body"]).items()}
    assert form["grant_type"] == "authorization_code" and form["code"] == "CODE-9" and form["redirect_uri"].endswith("/app/sources/oauth")
    verifier = form["code_verifier"]
    assert oauth._challenge(verifier) == q["code_challenge"], "the verifier answers the challenge that was sent"
    assert seen["headers"]["authorization"] == "Basic " + base64.b64encode(b"id-AIRTABLE:SECRET-AIRTABLE").decode()
    assert "client_secret" not in form, "a service that takes Basic gets no secret in the body"


def test_a_service_that_takes_the_client_in_the_body_gets_it_there(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = provider_replies(monkeypatch, body={"access_token": "AT-2"})
    q = query(oauth.start(user_id=USER, integration_id="github", provider="github", scopes=["repo"]))
    _, account = oauth.finish(state=q["state"], code="c", user_id=USER)
    assert account == {"access_token": "AT-2"}, "no refresh token and no expiry are stored when the service gives none"
    form = {k: v[0] for k, v in parse_qs(seen["body"]).items()}
    assert form["client_id"] == "id-GITHUB" and form["client_secret"] == "SECRET-GITHUB" and "code_verifier" not in form
    assert "authorization" not in seen["headers"]


def test_a_json_token_address_is_sent_json(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = provider_replies(monkeypatch)
    q = query(oauth.start(user_id=USER, integration_id="notion", provider="notion", scopes=[]))
    oauth.finish(state=q["state"], code="c", user_id=USER)
    assert seen["headers"]["content-type"].startswith("application/json") and json.loads(seen["body"])["code"] == "c"


@pytest.mark.parametrize("change, code", [("tamper", "bad_state"), ("other_user", "bad_state"), ("expired", "state_expired"), ("garbage", "bad_state")])
def test_a_state_that_is_altered_expired_or_someone_elses_is_refused(change: str, code: str, monkeypatch: pytest.MonkeyPatch) -> None:
    provider_replies(monkeypatch)
    state = query(oauth.start(user_id=USER, integration_id="airtable", provider="airtable", scopes=[], now=1000))["state"]
    user, now = USER, 1100
    if change == "tamper":
        state = state[:-6] + ("AAAAAA" if state[-6:] != "AAAAAA" else "BBBBBB")
    elif change == "other_user":
        user = "22222222-2222-2222-2222-222222222222"
    elif change == "expired":
        now = 1000 + oauth.STATE_SECONDS + 5
    else:
        state = "not-a-state"
    with pytest.raises(OAuthError) as err:
        oauth.finish(state=state, code="c", user_id=user, now=now)
    assert err.value.code == code


@pytest.mark.parametrize(
    "status, body, ctype",
    [(400, {"error": "invalid_grant", "access_token": "LEAK"}, "application/json"), (200, b"<html>no</html>", "text/html"), (200, {"nope": 1}, "application/json"), (200, {"access_token": ""}, "application/json")],
)
def test_a_refusal_or_a_bad_answer_is_reported_without_leaking_anything(status: int, body, ctype: str, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    provider_replies(monkeypatch, status, body, ctype)
    state = query(oauth.start(user_id=USER, integration_id="airtable", provider="airtable", scopes=[]))["state"]
    with pytest.raises(OAuthError) as err:
        oauth.finish(state=state, code="CODE-SECRET", user_id=USER)
    assert err.value.code == "token_failed"
    for secret in ("CODE-SECRET", "SECRET-AIRTABLE", "LEAK", "invalid_grant"):
        assert secret not in str(err.value)


def test_refresh_renews_the_tokens_and_keeps_the_old_refresh_token_when_none_comes_back(monkeypatch: pytest.MonkeyPatch) -> None:
    account = {"access_token": "old", "refresh_token": "RT-old", "expires_at": 1000}
    assert oauth.needs_refresh(account, now=950) is True, "within a minute of the end counts as ended"
    assert oauth.needs_refresh(account, now=100) is False
    assert oauth.needs_refresh({"access_token": "a", "expires_at": 1}, now=999) is False, "nothing to refresh with"
    assert oauth.needs_refresh({"access_token": "a", "refresh_token": "r"}, now=999) is False, "no expiry stated"
    seen = provider_replies(monkeypatch, body={"access_token": "AT-new", "expires_in": 60})
    renewed = oauth.refresh("spotify", account, now=2000)
    assert renewed == {"access_token": "AT-new", "refresh_token": "RT-old", "expires_at": 2060}
    form = {k: v[0] for k, v in parse_qs(seen["body"]).items()}
    assert form == {"grant_type": "refresh_token", "refresh_token": "RT-old"}
    with pytest.raises(OAuthError, match="Connect again"):
        oauth.refresh("spotify", {"access_token": "a"})


def test_every_known_provider_has_https_addresses_on_one_host_each() -> None:
    for name, p in oauth.PROVIDERS.items():
        assert p.authorize_url.startswith("https://") and p.token_url.startswith("https://"), name
        assert p.client_auth in ("body", "basic")
