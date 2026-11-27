"""Deliver newly indexed Knowledge revisions to opt-in schedules."""

import datetime as dt

from sqlalchemy import Select, and_, delete, func, or_, select
from sqlalchemy.orm import Session, aliased

from nortpole.access.hierarchy_access import get_user_external_group_ids
from nortpole.auth.permissions import has_global_permission
from nortpole.configs.app_configs import DISABLE_VECTOR_DB
from nortpole.db.document_access import apply_document_access_filter
from nortpole.db.document_set import (
    construct_document_id_select_by_docset,
    get_document_set_by_id_for_user,
)
from nortpole.db.enums import Permission
from nortpole.db.models import Document, DocumentSet, User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.knowledge.knowledge_access.groups import group_names_for_user
from nortpole.work.tasks.models import NortPoleTask
from nortpole.work.tasks.states import TaskState
from nortpole.work.workflow_schedules import controls
from nortpole.work.workflow_schedules.models import (
    KnowledgeChange,
    KnowledgeTriggerInput,
    NortPoleWorkflowRun,
    NortPoleWorkflowSchedule,
)

EVENT_WINDOW = dt.timedelta(days=7)
MAX_PENDING_PLANS = 3


def allowed(config: controls.ScheduleControls, groups: set[str]) -> bool:
    return not DISABLE_VECTOR_DB and config.source_events_enabled and controls.allowed_for(config, groups)


def library_for(db: Session, owner: User, library_id: int) -> DocumentSet:
    library = None
    if owner.is_active and has_global_permission(owner, Permission.READ_SEARCH):
        library = get_document_set_by_id_for_user(db, library_id, owner, get_editable=False)
    if library is None:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "This Knowledge library is unavailable.")
    return library


def _visible_docs(db: Session, owner: User, library_id: int) -> Select:
    members = construct_document_id_select_by_docset(library_id).order_by(None)
    docs = select(Document.id).where(Document.id.in_(members), Document.hidden.is_(False))
    return apply_document_access_filter(
        db, docs, owner.email, get_user_external_group_ids(db, owner), user_id=owner.id,
    )


def require_current_source(db: Session, owner: User, source: KnowledgeTriggerInput) -> DocumentSet:
    library = library_for(db, owner, source.library_id)
    doc = db.scalar(_visible_docs(db, owner, source.library_id).where(
        Document.id == source.document_id, Document.content_hash == source.content_hash,
    ).limit(1))
    if doc is None:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "The triggering document changed or is unavailable.")
    return library


def next_change(db: Session, schedule: NortPoleWorkflowSchedule, owner: User, now: dt.datetime) -> KnowledgeChange | None:
    if schedule.source_library_id is None or schedule.source_since is None:
        return None
    library = library_for(db, owner, schedule.source_library_id)
    event = KnowledgeChange
    newer = aliased(event)
    prior = select(NortPoleWorkflowRun.id).where(
        NortPoleWorkflowRun.schedule_id == schedule.id,
        NortPoleWorkflowRun.source_event_id == event.id,
    )
    return db.scalar(select(event).join(Document, Document.id == event.document_id).where(
        event.created_at >= max(schedule.source_since, now - EVENT_WINDOW),
        event.content_hash == Document.content_hash,
        event.document_id.in_(_visible_docs(db, owner, library.id)),
        ~prior.exists(),
        ~select(newer.id).where(newer.document_id == event.document_id, newer.id > event.id).exists(),
    ).order_by(event.created_at, event.id).limit(1))


def claim_changes(db: Session, now: dt.datetime, limit: int) -> None:
    """Reserve at most one revision per subscription per tick."""
    config = controls.load()
    # Run even when delivery is disabled so the journal stays bounded.
    expired = select(KnowledgeChange.id).where(
        KnowledgeChange.created_at < now - EVENT_WINDOW,
    ).order_by(KnowledgeChange.created_at).limit(1000).with_for_update(skip_locked=True)
    db.execute(delete(KnowledgeChange).where(KnowledgeChange.id.in_(expired)))
    if not config.source_events_enabled or not config.enabled or DISABLE_VECTOR_DB:
        db.commit()
        return

    schedule = NortPoleWorkflowSchedule
    watches = db.scalars(select(schedule).where(
        schedule.cadence == "source", schedule.state == "active",
        schedule.source_library_id.is_not(None), schedule.source_since.is_not(None),
    ).order_by(schedule.source_scan_at.asc().nulls_first(), schedule.id).limit(limit).with_for_update(skip_locked=True))
    for watch in watches:
        watch.source_scan_at = now
        owner = db.get(User, watch.owner_id)
        if owner is None or not owner.is_active or not allowed(config, group_names_for_user(db, owner.id)):
            watch.source_since = now
            continue
        run = NortPoleWorkflowRun
        pending = db.scalar(select(func.count()).select_from(run).outerjoin(
            NortPoleTask, NortPoleTask.id == run.task_id,
        ).where(run.schedule_id == watch.id, or_(
            run.outcome == "queued",
            and_(run.outcome == "running", run.started_at > now - dt.timedelta(minutes=30)),
            NortPoleTask.state == TaskState.PLAN_REVIEW.value,
        )))
        if pending >= MAX_PENDING_PLANS:
            continue
        try:
            change = next_change(db, watch, owner, now)
        except NortPoleError:
            # Start from new revisions after access is restored.
            watch.source_since = now
            continue
        if change is None:
            continue
        db.add(NortPoleWorkflowRun(
            schedule_id=watch.id, schedule_version=watch.version, outcome="queued", trigger="source",
            source_event_id=change.id, source_library_id=watch.source_library_id,
            source_document_id=change.document_id, source_content_hash=change.content_hash,
        ))
        watch.last_fired_at = now
    db.commit()
