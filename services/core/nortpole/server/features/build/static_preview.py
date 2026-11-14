"""Read-only, short-lived capabilities for isolated static output previews."""

import hashlib
import json
import mimetypes
import secrets
from pathlib import PurePosixPath
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from nortpole.auth.permissions import has_global_permission, require_permission
from nortpole.cache.factory import get_shared_cache_backend
from nortpole.db.engine.sql_engine import get_session, get_session_with_tenant
from nortpole.db.enums import Permission
from nortpole.db.models import User
from nortpole.db.users import fetch_user_by_id
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.server.features.build.db.build_session import get_build_session
from nortpole.server.features.build.models import StaticPreviewGrant, StaticPreviewResponse
from nortpole.server.features.build.session.manager import SessionManager
from nortpole.server.features.build.utils import is_craft_enabled_for_user
from shared_configs.contextvars import (
    CURRENT_TENANT_ID_CONTEXTVAR,
    get_current_tenant_id,
)

router = APIRouter(prefix="/sessions")
public_router = APIRouter(prefix="/build/static-preview")
PREVIEW_TTL_SECONDS = 3600
MAX_ASSET_BYTES = 20 * 1024 * 1024
MAX_PREVIEW_FILES = 1000
MAX_PREVIEW_BYTES = 50 * 1024 * 1024
STATIC_EXTENSIONS = frozenset(
    ".html .htm .css .js .mjs .json .svg .png .jpg .jpeg .gif .webp .avif .ico "
    ".woff .woff2 .ttf .otf .mp3 .wav .ogg .mp4 .webm".split()
)
# Keep these restrictions on responses too: opening a preview URL directly must be safe.
PREVIEW_HEADERS = {
    "Content-Security-Policy": (
        "sandbox allow-scripts; default-src 'none'; "
        "script-src 'unsafe-inline' https: http:; style-src 'unsafe-inline' https: http:; "
        "img-src data: blob: https: http:; font-src data: https: http:; "
        "media-src blob: https: http:; "
        "connect-src http://{authority}/api/build/static-preview/{token}/ "
        "https://{authority}/api/build/static-preview/{token}/; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
    ),
    "Cache-Control": "private, no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Access-Control-Allow-Origin": "*",
    "Cross-Origin-Resource-Policy": "cross-origin",
}


@router.post("/{session_id}/static-preview/{path:path}")
def create_static_preview(
    session_id: UUID,
    path: str,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
    renew_token: Annotated[str | None, Query(min_length=43, max_length=43)] = None,
) -> StaticPreviewResponse:
    target = PurePosixPath(path)
    if (
        target.parts[:1] != ("outputs",)
        or any(part.startswith(".") for part in target.parts)
        or "\\" in path
        or target.suffix.lower() not in {".html", ".htm"}
    ):
        raise NortPoleError(NortPoleErrorCode.BAD_REQUEST, "Invalid HTML output path")
    manager = SessionManager(db_session)
    inventory = manager.get_output_inventory(session_id, user.id)
    root = target.parent.as_posix() + "/"
    files = {
        file.path[len(root) :]: file.size
        for file in inventory.files
        if file.path.startswith(root)
        and file.size <= MAX_ASSET_BYTES
        and PurePosixPath(file.path).suffix.lower() in STATIC_EXTENSIONS
        and not any(part.startswith(".") for part in PurePosixPath(file.path).parts)
    }
    if target.name not in files:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "HTML output not found or too large")
    if len(files) > MAX_PREVIEW_FILES or sum(files.values()) > MAX_PREVIEW_BYTES:
        raise NortPoleError(
            NortPoleErrorCode.BAD_REQUEST, "Preview folder exceeds the size limit"
        )
    cache = get_shared_cache_backend()
    if renew_token is not None:
        raw = cache.get(f"craft:static-preview:{renew_token}")
        try:
            previous = StaticPreviewGrant.model_validate_json(raw or b"")
        except ValidationError as error:
            raise NortPoleError(
                NortPoleErrorCode.NOT_FOUND, "Preview expired; reload the file"
            ) from error
        if (
            previous.tenant_id != get_current_tenant_id()
            or previous.session_id != session_id
            or previous.user_id != user.id
            or previous.root != root
            or target.name not in previous.files
        ):
            raise NortPoleError(NortPoleErrorCode.NOT_FOUND)
        cache.set(
            f"craft:static-preview:{renew_token}",
            previous.model_dump_json(),
            ex=PREVIEW_TTL_SECONDS,
        )
        return StaticPreviewResponse(
            path=f"{renew_token}/{quote(target.name, safe='')}",
            expires_in=PREVIEW_TTL_SECONDS,
        )
    token = secrets.token_urlsafe(32)
    grant = StaticPreviewGrant(
        tenant_id=get_current_tenant_id(),
        session_id=session_id,
        user_id=user.id,
        root=root,
        files=files,
        revisions={
            file.path[len(root) :]: file.revision
            for file in inventory.files
            if file.path[len(root) :] in files and file.path.startswith(root)
        },
    )
    cache.set(
        f"craft:static-preview:{token}", grant.model_dump_json(), ex=PREVIEW_TTL_SECONDS
    )
    return StaticPreviewResponse(
        path=f"{token}/{quote(target.name, safe='')}", expires_in=PREVIEW_TTL_SECONDS
    )


@public_router.get("/{token}/{path:path}")
def read_static_preview(
    token: str,
    path: str,
    request: Request,
) -> Response:
    # The capability selects its issuing tenant; cookies grant no access here.
    cache = get_shared_cache_backend()
    raw = cache.get(f"craft:static-preview:{token}")
    if raw is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Preview expired; reload the file")
    try:
        grant = StaticPreviewGrant.model_validate_json(raw)
    except ValidationError as error:
        raise NortPoleError(
            NortPoleErrorCode.NOT_FOUND, "Preview expired; reload the file"
        ) from error
    if path not in grant.files:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND)
    context_token = CURRENT_TENANT_ID_CONTEXTVAR.set(grant.tenant_id)
    try:
        with get_session_with_tenant(tenant_id=grant.tenant_id) as db_session:
            owner = fetch_user_by_id(db_session, grant.user_id)
            if (
                owner is None
                or not owner.is_active
                or not has_global_permission(owner, Permission.BASIC_ACCESS)
                or not is_craft_enabled_for_user(owner)
            ):
                raise NortPoleError(NortPoleErrorCode.NOT_FOUND)
            if get_build_session(grant.session_id, grant.user_id, db_session) is None:
                raise NortPoleError(NortPoleErrorCode.NOT_FOUND)
            # Authorization remains grant-scoped; identical revisions share bytes.
            full_path = grant.root + path
            identity = json.dumps(
                [
                    grant.tenant_id,
                    str(grant.session_id),
                    full_path,
                    grant.revisions[path],
                ]
            )
            asset_key = (
                f"craft:static-asset:{hashlib.sha256(identity.encode()).hexdigest()}"
            )
            content = cache.get(asset_key)
            mime_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
            if content is None:
                manager = SessionManager(db_session)
                inventory = manager.get_output_inventory(
                    grant.session_id, grant.user_id
                )
                if not any(
                    file.path == full_path
                    and file.size <= grant.files[path]
                    and file.revision == grant.revisions[path]
                    for file in inventory.files
                ):
                    raise NortPoleError(NortPoleErrorCode.NOT_FOUND)
                result = manager.download_artifact(
                    grant.session_id, grant.user_id, full_path
                )
                if result is None or len(result[0]) > grant.files[path]:
                    raise NortPoleError(NortPoleErrorCode.NOT_FOUND)
                content, mime_type, _ = result
                cache.set(asset_key, content, ex=PREVIEW_TTL_SECONDS)
            if PurePosixPath(path).suffix.lower() in {".js", ".mjs"}:
                mime_type = "text/javascript"
            return Response(
                content,
                media_type=mime_type,
                headers={
                    key: value.format(token=token, authority=request.url.netloc)
                    for key, value in PREVIEW_HEADERS.items()
                },
            )
    finally:
        CURRENT_TENANT_ID_CONTEXTVAR.reset(context_token)
