import hashlib
import json
import time
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from mcp.server.auth.provider import construct_redirect_uri
from mcp.shared.auth import InvalidRedirectUriError
from starlette.concurrency import run_in_threadpool

from evolvxsi.auth.constants import (
    NO_STORE_HEADERS,
    OAUTH_PROVIDER_SECRET_PATTERN,
)
from evolvxsi.auth.permissions import has_global_permission, require_permission
from evolvxsi.auth.schemas import AuthBackend
from evolvxsi.auth.users import current_limited_user, get_jwt_strategy
from evolvxsi.configs import app_configs
from evolvxsi.configs.constants import FASTAPI_USERS_AUTH_COOKIE_NAME
from evolvxsi.db.engine.sql_engine import get_session_with_current_tenant
from evolvxsi.db.enums import AccountType, Permission
from evolvxsi.db.models import User
from evolvxsi.db.oauth_provider import (
    OAUTH_PROVIDER_STORAGE_ERRORS,
    list_oauth_provider_grants,
    oauth_provider_owner_is_member,
    oauth_provider_owner_snapshot,
    revoke_oauth_provider_grant__no_commit,
)
from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.oauth_provider.attempts import (
    AUTHORIZATION_CODE_TTL_SECONDS,
    bind_authorization_request,
    consume_authorization_request,
    get_authorization_request,
    store_authorization_code,
)
from evolvxsi.oauth_provider.auth import get_oauth_provider_token_info
from evolvxsi.oauth_provider.config import require_oauth_provider_settings
from evolvxsi.oauth_provider.models import (
    OAuthProviderGrantInfo,
    OAuthProviderIntrospection,
    StoredOAuthProviderCode,
)
from evolvxsi.server.oauth_provider.models import (
    OAuthConsentDecision,
    OAuthConsentInfo,
    OAuthConsentResult,
)
from evolvxsi.server.oauth_provider.provider import EvolvXSIOAuthProvider
from evolvxsi.server.settings.store import load_settings
from shared_configs.configs import MULTI_TENANT
from shared_configs.contextvars import UsageCredentialIdentity, get_current_tenant_id
from shared_configs.enums import UsageCredentialType

router = APIRouter(prefix="/oauth-provider")


def _session_hash(request: Request, user: User) -> str:
    state = request.scope.get("state", {})
    credential = state.get("usage_credential")
    if (
        user.account_type != AccountType.STANDARD
        or not isinstance(credential, UsageCredentialIdentity)
        or credential.credential_type
        not in {UsageCredentialType.SESSION, UsageCredentialType.JWT}
        # JWT passthrough does not bind the request to a tenant.
        or (MULTI_TENANT and credential.credential_type == UsageCredentialType.JWT)
    ):
        raise EvolvXSIError(
            EvolvXSIErrorCode.UNAUTHENTICATED, "Sign in to manage connected apps"
        )
    cookie = request.cookies.get(FASTAPI_USERS_AUTH_COOKIE_NAME)
    authorization = request.headers.get("Authorization")
    if not cookie and not authorization:
        raise EvolvXSIError(EvolvXSIErrorCode.UNAUTHENTICATED)
    cookie_identity: str | tuple[str, str] | None = cookie
    authorization_identity: str | tuple[str, str] | None = authorization
    if (
        app_configs.AUTH_BACKEND == AuthBackend.JWT
        and credential.credential_type == UsageCredentialType.SESSION
    ):
        token = state.get("authenticated_session_token")
        if not isinstance(token, str) or not token:
            raise EvolvXSIError(EvolvXSIErrorCode.UNAUTHENTICATED)
        session_id = get_jwt_strategy().get_session_id(token, user)
        if session_id is None:
            raise EvolvXSIError(EvolvXSIErrorCode.UNAUTHENTICATED)
        if cookie == token:
            cookie_identity = ("jwt-session", session_id)
        elif authorization is not None:
            scheme, _, bearer = authorization.partition(" ")
            if scheme.lower() != "bearer" or bearer != token:
                raise EvolvXSIError(EvolvXSIErrorCode.UNAUTHENTICATED)
            authorization_identity = ("jwt-session", session_id)
        else:
            raise EvolvXSIError(EvolvXSIErrorCode.UNAUTHENTICATED)
    credentials = json.dumps(
        [cookie_identity, authorization_identity], separators=(",", ":")
    )
    return hashlib.sha256(credentials.encode("utf-8")).hexdigest()


async def _authorization_session(request: Request, user: User) -> str:
    session_hash = _session_hash(request, user)
    if not has_global_permission(user, Permission.READ_SEARCH):
        raise EvolvXSIError(EvolvXSIErrorCode.INSUFFICIENT_PERMISSIONS)
    owner = oauth_provider_owner_snapshot(user)
    try:
        member = await run_in_threadpool(
            oauth_provider_owner_is_member,
            get_current_tenant_id(),
            owner.email,
            owner.oauth_identities,
        )
    except OAUTH_PROVIDER_STORAGE_ERRORS as error:
        raise EvolvXSIError(EvolvXSIErrorCode.SERVICE_UNAVAILABLE) from error
    if not member:
        raise EvolvXSIError(
            EvolvXSIErrorCode.UNAUTHORIZED, "Workspace membership is no longer active"
        )
    return session_hash


@router.get("/introspect")
def introspect(
    request: Request,
    response: Response,
    user: User = Depends(require_permission(Permission.READ_SEARCH)),
) -> OAuthProviderIntrospection:
    info = get_oauth_provider_token_info(request)
    if info is None:
        raise EvolvXSIError(EvolvXSIErrorCode.UNAUTHENTICATED)
    response.headers.update(NO_STORE_HEADERS)
    return OAuthProviderIntrospection(
        client_id=info.grant.client_id,
        scopes=list(info.grant.scopes),
        resource=info.grant.resource,
        expires_at=int(info.expires_at.timestamp()),
        subject=str(user.id),
        grant_id=info.grant.id,
    )


@router.get("/consent")
async def consent_details(
    request: Request,
    response: Response,
    authorization_request: str = Query(
        alias="request", pattern=rf"^{OAUTH_PROVIDER_SECRET_PATTERN}$"
    ),
    user: User = Depends(require_permission(Permission.CREATE_USER_API_KEYS)),
) -> OAuthConsentInfo:
    session_hash = await _authorization_session(request, user)
    pending = await run_in_threadpool(get_authorization_request, authorization_request)
    if pending is None:
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Authorization request expired")
    binding = await run_in_threadpool(
        bind_authorization_request,
        authorization_request,
        user_id=user.id,
        tenant_id=get_current_tenant_id(),
        session_hash=session_hash,
    )
    if binding is None:
        raise EvolvXSIError(
            EvolvXSIErrorCode.INVALID_INPUT,
            "Restart authorization after changing accounts or workspaces",
        )
    settings = await run_in_threadpool(load_settings)
    destination = urlsplit(str(pending.params.redirect_uri))
    response.headers.update(NO_STORE_HEADERS)
    return OAuthConsentInfo(
        client_name=pending.client_name,
        redirect_origin=f"{destination.scheme}://{destination.netloc}",
        account_email=user.email,
        workspace_name=settings.company_name
        or urlsplit(require_oauth_provider_settings().web_url).netloc,
        scopes=pending.params.scopes or [],
        csrf_token=binding.csrf_token,
    )


@router.post("/consent")
async def decide_consent(
    payload: OAuthConsentDecision,
    request: Request,
    response: Response,
    user: User = Depends(require_permission(Permission.CREATE_USER_API_KEYS)),
) -> OAuthConsentResult:
    settings = require_oauth_provider_settings()
    if request.headers.get("origin") != settings.web_origin:
        raise EvolvXSIError(EvolvXSIErrorCode.UNAUTHORIZED, "Invalid authorization origin")
    session_hash = await _authorization_session(request, user)
    pending = await run_in_threadpool(
        consume_authorization_request,
        payload.request_id,
        user_id=user.id,
        tenant_id=get_current_tenant_id(),
        session_hash=session_hash,
        csrf_token=payload.csrf_token,
    )
    if pending is None:
        raise EvolvXSIError(
            EvolvXSIErrorCode.INVALID_INPUT, "Invalid or expired authorization request"
        )
    response.headers.update(NO_STORE_HEADERS)
    if payload.decision == "deny":
        return OAuthConsentResult(
            redirect_url=construct_redirect_uri(
                str(pending.params.redirect_uri),
                error="access_denied",
                state=pending.params.state,
                iss=settings.issuer_url,
            )
        )
    client = await EvolvXSIOAuthProvider(settings).get_client(pending.client_id)
    if client is None or pending.params.resource != settings.mcp_resource_url:
        raise EvolvXSIError(
            EvolvXSIErrorCode.INVALID_INPUT, "Client authorization is no longer available"
        )
    try:
        client.validate_redirect_uri(pending.params.redirect_uri)
    except InvalidRedirectUriError as error:
        raise EvolvXSIError(
            EvolvXSIErrorCode.INVALID_INPUT,
            "Client redirect changed; restart authorization",
        ) from error
    code = await run_in_threadpool(
        store_authorization_code,
        StoredOAuthProviderCode(
            authorization=pending,
            user_id=user.id,
            tenant_id=get_current_tenant_id(),
            expires_at=time.time() + AUTHORIZATION_CODE_TTL_SECONDS,
        ),
    )
    return OAuthConsentResult(
        redirect_url=construct_redirect_uri(
            str(pending.params.redirect_uri),
            code=code,
            state=pending.params.state,
            iss=settings.issuer_url,
        )
    )


@router.get("/grants")
def connected_clients(
    request: Request,
    response: Response,
    user: User = Depends(current_limited_user),
) -> list[OAuthProviderGrantInfo]:
    _session_hash(request, user)
    response.headers.update(NO_STORE_HEADERS)
    with get_session_with_current_tenant() as session:
        return list_oauth_provider_grants(session, user.id)


@router.delete("/grants/{grant_id}")
def disconnect_client(
    grant_id: UUID,
    request: Request,
    response: Response,
    user: User = Depends(current_limited_user),
) -> dict[str, bool]:
    _session_hash(request, user)
    if request.headers.get("origin") != require_oauth_provider_settings().web_origin:
        raise EvolvXSIError(EvolvXSIErrorCode.UNAUTHORIZED, "Invalid authorization origin")
    with get_session_with_current_tenant() as session:
        revoked = revoke_oauth_provider_grant__no_commit(
            session, grant_id=grant_id, user_id=user.id
        )
        session.commit()
    if not revoked:
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND)
    response.headers.update(NO_STORE_HEADERS)
    return {"revoked": True}
