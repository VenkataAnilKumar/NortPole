from fastapi import APIRouter, Depends

from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import User
from evolvxsi.document_index.opensearch.models import ResourceHealth
from evolvxsi.document_index.opensearch.resource_health import get_resource_health
from evolvxsi.redis.redis_pool import get_redis_client
from evolvxsi.server.manage.opensearch_health.models import ResourcePopupResponse

router: APIRouter = APIRouter(prefix="/manage/admin/opensearch-health")
POPUP_INTERVAL_SECONDS = 24 * 60 * 60
POPUP_KEY_PREFIX = "opensearch_resource_popup"


@router.get("")
def read_resource_health(
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> ResourceHealth:
    return get_resource_health()


@router.post("/popup")
def claim_resource_popup(
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> ResourcePopupResponse:
    health: ResourceHealth = get_resource_health()
    show_popup: bool = bool(
        health.issues
        and not health.stale
        and get_redis_client().set(
            f"{POPUP_KEY_PREFIX}:{user.id}",
            "1",
            nx=True,
            ex=POPUP_INTERVAL_SECONDS,
        )
    )
    return ResourcePopupResponse(show_popup=show_popup, health=health)
