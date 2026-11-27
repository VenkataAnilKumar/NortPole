from threading import Lock
from uuid import UUID

from cachetools import TTLCache
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from nortpole.auth.permissions import require_permission
from nortpole.configs.constants import NotificationType
from nortpole.db.engine.sql_engine import get_session
from nortpole.db.enums import NotificationSeverity, Permission
from nortpole.db.models import User
from nortpole.db.notification import (
    InboxTab,
    count_inbox_notifications,
    count_notifications,
    dismiss_notification,
    dismiss_user_notifications,
    get_notification_by_id,
    get_notifications,
)
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.server.features.notifications.models import (
    InboxNotificationSummary,
    NotificationResponse,
    NotificationSummary,
    PaginatedNotifications,
)
from nortpole.server.features.notifications.utils import (
    ensure_system_announcement_notification,
)
from nortpole.utils.logger import setup_logger
from nortpole.utils.variable_functionality import fetch_ee_implementation_or_noop

logger = setup_logger()
router = APIRouter(prefix="/notifications")

DEFAULT_NOTIFICATIONS_PAGE_SIZE = 10
MAX_NOTIFICATIONS_PAGE_SIZE = 50

# The banner queue polls severity-only requests every minute per open tab, so
# run its lazy-materialization ensures at most once per user per window.
# Per-replica and best-effort: a miss only repeats an idempotent ensure.
ENSURE_THROTTLE_SECONDS = 300
_polled_ensure_cache: TTLCache[UUID, bool] = TTLCache(
    maxsize=5000, ttl=ENSURE_THROTTLE_SECONDS
)
_polled_ensure_lock = Lock()


def _polled_ensures_due(user_id: UUID) -> bool:
    with _polled_ensure_lock:
        return user_id not in _polled_ensure_cache


def _mark_polled_ensures_done(user_id: UUID) -> None:
    with _polled_ensure_lock:
        _polled_ensure_cache[user_id] = True


def _check_for_notifications_to_create(
    user: User,  # noqa: ARG001
    db_session: Session,  # noqa: ARG001
) -> None:
    """NortPole creates no upstream-seeded notifications.

    The upstream build-mode intro, the permissions-migration announcement and the
    release-notes poll are disabled here: the last one fetched the upstream
    project's changelog from the network on every poll. Admin-authored system
    announcements still work (see ``_ensure_system_announcement_notification``),
    and NortPole's own events (approvals, updates) are added by later phases.
    """
    return


def _ensure_system_announcement_notification(user: User, db_session: Session) -> bool:
    """Materialize the current admin-authored site-wide announcement on read so
    it appears without waiting for a background pass. No-op when none is set."""
    try:
        ensure_system_announcement_notification(user, db_session)
        return True
    except Exception:
        logger.exception("Failed to ensure system announcement notification on read")
        return False


def _ensure_license_expiry_notification(user: User, db_session: Session) -> bool:
    """Self-hosted EE only: create the admin's current-stage license-expiry
    notification on read so the banner appears without waiting for the daily
    task. No-op on non-EE builds (and for non-admins / no active warning)."""
    try:
        fetch_ee_implementation_or_noop(
            "nortpole.utils.license_notifications",
            "ensure_license_expiry_notification_for_user",
        )(user, db_session)
        return True
    except Exception:
        logger.exception("Failed to ensure license expiry notification on read")
        return False


@router.get("")
def get_notifications_api(
    page_num: int = Query(0, ge=0),
    page_size: int = Query(
        DEFAULT_NOTIFICATIONS_PAGE_SIZE, ge=1, le=MAX_NOTIFICATIONS_PAGE_SIZE
    ),
    notif_type: NotificationType | None = None,
    min_severity: NotificationSeverity | None = None,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
    inbox_tab: InboxTab | None = None,
) -> PaginatedNotifications:
    """
    Get a page of notifications for the current user, optionally filtered to a
    single notif_type and/or a minimum severity (min_severity returns rows at
    that severity or louder — the banner queue asks for WARNING and up).

    Note: the first unfiltered page runs the generic create-checks. A filtered
    request skips them, except that SYSTEM_ANNOUNCEMENT and
    LICENSE_EXPIRY_WARNING are ensured whenever they could appear in the
    response: always on their type filter, and throttled per user on
    severity-only requests (the banner queue's polled fetch).

    Examples of checks that create new notifications:
    - Checking for new release notes the user hasn't seen
    - Checking for misconfigurations due to version changes
    - Explicitly announcing breaking changes
    """
    if page_num == 0 and inbox_tab in (None, InboxTab.UPDATES):
        if notif_type is None and min_severity is None:
            _check_for_notifications_to_create(user, db_session)
        # A severity-only request is the banner queue's polled fetch: its
        # ensures are throttled, and a user is only marked done once both
        # succeed so a transient failure retries on the next poll. Other
        # requests keep the always-run behavior.
        polled = min_severity is not None and notif_type is None
        if not polled or _polled_ensures_due(user.id):
            succeeded: list[bool] = []
            for banner_type, ensure in (
                (
                    NotificationType.SYSTEM_ANNOUNCEMENT,
                    _ensure_system_announcement_notification,
                ),
                (
                    NotificationType.LICENSE_EXPIRY_WARNING,
                    _ensure_license_expiry_notification,
                ),
            ):
                if polled or notif_type in (None, banner_type):
                    succeeded.append(ensure(user, db_session))
            if polled and all(succeeded):
                _mark_polled_ensures_done(user.id)

    total_items, undismissed_count = count_notifications(
        user=user,
        db_session=db_session,
        notif_type=notif_type,
        min_severity=min_severity,
        inbox_tab=inbox_tab,
    )
    offset = page_num * page_size
    notifications = [
        NotificationResponse.model_validate(notif)
        for notif in get_notifications(
            user=user,
            db_session=db_session,
            notif_type=notif_type,
            include_dismissed=True,
            limit=page_size,
            offset=offset,
            min_severity=min_severity,
            inbox_tab=inbox_tab,
        )
    ]
    return PaginatedNotifications(
        notifications=notifications,
        total_items=total_items,
        undismissed_count=undismissed_count,
        page_num=page_num,
        page_size=page_size,
        has_more=offset + page_size < total_items,
    )


@router.get("/summary")
def get_notifications_summary_api(
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> NotificationSummary:
    # Preserve app-load notification bootstrap behavior: notifications that are
    # lazily created on read should exist before we compute badge counts.
    _check_for_notifications_to_create(user=user, db_session=db_session)
    _ensure_system_announcement_notification(user=user, db_session=db_session)
    total_items, undismissed_count = count_notifications(
        user=user,
        db_session=db_session,
    )
    return NotificationSummary(
        total_items=total_items,
        undismissed_count=undismissed_count,
    )


@router.get("/inbox-summary")
def get_inbox_summary_api(
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> InboxNotificationSummary:
    if _polled_ensures_due(user.id):
        announcement_ok = _ensure_system_announcement_notification(user, db_session)
        license_ok = _ensure_license_expiry_notification(user, db_session)
        if announcement_ok and license_ok:
            _mark_polled_ensures_done(user.id)
    return InboxNotificationSummary.model_validate(
        count_inbox_notifications(user, db_session)
    )


@router.post("/dismiss-all")
def dismiss_all_notifications_endpoint(
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> None:
    dismiss_user_notifications(user=user, db_session=db_session)


@router.post("/{notification_id}/dismiss")
def dismiss_notification_endpoint(
    notification_id: int,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> None:
    try:
        notification = get_notification_by_id(notification_id, user, db_session)
    except PermissionError as e:
        raise NortPoleError(
            NortPoleErrorCode.UNAUTHORIZED,
            "Not authorized to dismiss this notification",
        ) from e
    except ValueError as e:
        raise NortPoleError(
            NortPoleErrorCode.NOT_FOUND,
            "Notification not found",
        ) from e

    dismiss_notification(notification, db_session)
