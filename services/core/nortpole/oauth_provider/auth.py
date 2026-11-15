from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from nortpole.auth.constants import (
    OAUTH_PROVIDER_ACCESS_TOKEN_PREFIX,
    OAUTH_PROVIDER_REFRESH_TOKEN_PREFIX,
    OAUTH_PROVIDER_SCOPE,
)
from nortpole.auth.oauth_provider import OAuthProviderTokenKind, parse_oauth_provider_token
from nortpole.auth.permissions import has_global_permission
from nortpole.db.enums import Permission
from nortpole.db.models import User
from nortpole.db.oauth_provider import (
    OAUTH_PROVIDER_STORAGE_ERRORS,
    oauth_provider_owner_is_member,
    oauth_provider_owner_snapshot,
    oauth_provider_tenant_has_members,
    resolve_oauth_provider_access_token,
)
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.oauth_provider import config as oauth_provider_config
from nortpole.oauth_provider.models import OAuthProviderTokenInfo
from nortpole.server.middleware.api_prefix import strip_api_prefix
from shared_configs.contextvars import UsageCredentialIdentity, get_current_tenant_id
from shared_configs.enums import UsageCredentialType

_ACCESS_ROUTES = frozenset(
    {
        ("GET", "/oauth-provider/introspect"),
        ("POST", "/search"),
        ("POST", "/search/raw"),
        ("POST", "/web-search/search-lite"),
        ("POST", "/web-search/open-urls"),
        ("GET", "/manage/indexed-sources"),
        ("GET", "/manage/document-set"),
        ("GET", "/persona"),
    }
)
_TOKEN_INFO_SCOPE_KEY = "nortpole.mcp_oauth"


def _is_mcp_oauth_access_route(request: Request) -> bool:
    return (request.method, strip_api_prefix(request.url.path)) in _ACCESS_ROUTES


def extract_oauth_provider_bearer(request: Request) -> str | None:
    authorization = request.headers.getlist("authorization")
    alternate = request.headers.getlist("x-nortpole-authorization")
    values = authorization + alternate
    if not any(
        part.startswith(
            (OAUTH_PROVIDER_ACCESS_TOKEN_PREFIX, OAUTH_PROVIDER_REFRESH_TOKEN_PREFIX)
        )
        for value in values
        for part in value.split()
    ):
        return None
    if len(authorization) > 1 or len(alternate) > 1:
        raise NortPoleError(NortPoleErrorCode.UNAUTHENTICATED)
    credentials = [value.split() for value in values]
    if any(len(parts) != 2 or parts[0].lower() != "bearer" for parts in credentials):
        raise NortPoleError(NortPoleErrorCode.UNAUTHENTICATED)
    tokens = {parts[1] for parts in credentials}
    if len(tokens) != 1:
        raise NortPoleError(NortPoleErrorCode.UNAUTHENTICATED)
    return tokens.pop()


async def oauth_provider_tenant_from_request(request: Request) -> str | None:
    raw_token = extract_oauth_provider_bearer(request)
    if raw_token is None:
        return None
    parsed = parse_oauth_provider_token(raw_token)
    if (
        oauth_provider_config.OAUTH_PROVIDER_SETTINGS is None
        or parsed is None
        or parsed.kind != OAuthProviderTokenKind.ACCESS
    ):
        raise NortPoleError(NortPoleErrorCode.UNAUTHENTICATED)
    if not _is_mcp_oauth_access_route(request):
        raise NortPoleError(NortPoleErrorCode.INSUFFICIENT_PERMISSIONS)
    try:
        known = await run_in_threadpool(
            oauth_provider_tenant_has_members, parsed.tenant_id
        )
    except OAUTH_PROVIDER_STORAGE_ERRORS as error:
        raise NortPoleError(NortPoleErrorCode.SERVICE_UNAVAILABLE) from error
    if not known:
        raise NortPoleError(NortPoleErrorCode.UNAUTHENTICATED)
    return parsed.tenant_id


def get_oauth_provider_token_info(request: Request) -> OAuthProviderTokenInfo | None:
    info = request.scope.get(_TOKEN_INFO_SCOPE_KEY)
    return info if isinstance(info, OAuthProviderTokenInfo) else None


async def authenticate_oauth_provider_request(
    request: Request, session: AsyncSession, raw_token: str
) -> User:
    settings = oauth_provider_config.OAUTH_PROVIDER_SETTINGS
    if settings is None:
        raise NortPoleError(NortPoleErrorCode.UNAUTHENTICATED)
    if not _is_mcp_oauth_access_route(request):
        raise NortPoleError(NortPoleErrorCode.INSUFFICIENT_PERMISSIONS)
    try:
        result = await resolve_oauth_provider_access_token(
            session, raw_token, resource=settings.mcp_resource_url
        )
        if result is None:
            raise NortPoleError(NortPoleErrorCode.UNAUTHENTICATED)
        user, info = result
        owner = oauth_provider_owner_snapshot(user)
        await session.commit()
        is_member = await run_in_threadpool(
            oauth_provider_owner_is_member,
            get_current_tenant_id(),
            owner.email,
            owner.oauth_identities,
        )
    except OAUTH_PROVIDER_STORAGE_ERRORS as error:
        raise NortPoleError(NortPoleErrorCode.SERVICE_UNAVAILABLE) from error
    if not is_member:
        raise NortPoleError(NortPoleErrorCode.UNAUTHENTICATED)
    if set(info.grant.scopes) != {OAUTH_PROVIDER_SCOPE} or not has_global_permission(
        user, Permission.READ_SEARCH
    ):
        raise NortPoleError(NortPoleErrorCode.INSUFFICIENT_PERMISSIONS)
    request.state.token_scopes = [Permission.READ_SEARCH]
    request.state.usage_credential = UsageCredentialIdentity(
        UsageCredentialType.OAUTH_PROVIDER,
        str(info.grant.id),
        info.grant.client_name,
    )
    request.scope[_TOKEN_INFO_SCOPE_KEY] = info
    return user
