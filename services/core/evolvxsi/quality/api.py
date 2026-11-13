"""Run quality for administrators: how reviewed work is going, whether packs still pass on the current model,
how reviewers and chat users respond, and how it changes day by day.

Everything here is counts, rates, durations and ids. It never returns the title, request, draft text, claim
text or feedback text of anyone's work or chat: administering the product does not grant reading people's work."""

from __future__ import annotations

import datetime
import statistics

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.orm import Session

from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.engine.sql_engine import get_session
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import User

router = APIRouter(prefix="/admin/quality")
DEFAULT_DAYS = 30
MAX_DAYS = 90
FAILED = ("plan_failed", "run_failed")


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 3) if whole else None


def _runs(db: Session, since: datetime.datetime) -> dict:
    from evolvxsi.tasks.models import EvolvXSITask as T

    started = db.execute(
        select(T.pack_id, T.state, T.started_at, T.drafted_at, T.approved_at, T.draft_claims)
        .where(T.started_at >= since)
    ).all()
    totals = {"started": len(started), "drafted": 0, "failed": 0, "approved": 0}
    by_pack: dict[str, dict] = {}
    seconds: list[float] = []
    claims = {"supported": 0, "unsupported": 0, "notice": 0, "kept": 0, "removed": 0, "undecided": 0}
    for pack_id, state, started_at, drafted_at, approved_at, draft_claims in started:
        key = pack_id or "(own request)"
        row = by_pack.setdefault(key, {"pack_id": pack_id, "started": 0, "drafted": 0, "failed": 0, "approved": 0})
        row["started"] += 1
        if drafted_at is not None:
            totals["drafted"] += 1
            row["drafted"] += 1
            seconds.append((drafted_at - started_at).total_seconds())
        if state in FAILED:
            totals["failed"] += 1
            row["failed"] += 1
        if approved_at is not None:
            totals["approved"] += 1
            row["approved"] += 1
        for c in draft_claims or []:
            status = c.get("status")
            if status in ("supported", "unsupported", "notice"):
                claims[status] += 1
            if status == "unsupported":
                decision = c.get("decision")
                claims["kept" if decision == "keep" else "removed" if decision == "remove" else "undecided"] += 1
    finished = totals["drafted"] + totals["failed"]
    return {
        "totals": totals,
        "draft_rate": _rate(totals["drafted"], finished),
        "approval_rate": _rate(totals["approved"], totals["drafted"]),
        "median_seconds_to_draft": round(statistics.median(seconds), 1) if seconds else None,
        "by_pack": sorted(by_pack.values(), key=lambda r: (-r["started"], r["pack_id"] or "")),
        "claims": claims,
        "unsupported_share": _rate(claims["unsupported"], claims["supported"] + claims["unsupported"]),
    }


def _evals(db: Session) -> list[dict]:
    from evolvxsi.packs.models import EvolvXSIPackEvaluation as E

    latest = (
        select(E.pack_id, E.version, E.model_configuration_id, func.max(E.row_id).label("row_id"))
        .group_by(E.pack_id, E.version, E.model_configuration_id)
        .subquery()
    )
    rows = db.execute(
        select(E).join(latest, E.row_id == latest.c.row_id).order_by(E.pack_id, E.version.desc(), E.model_name)
    ).scalars().all()
    out = []
    for e in rows:
        # The questions come from the signed pack, not from anyone's work, so they may be shown.
        failed = [str(d.get("question", ""))[:120] for d in (e.details or []) if isinstance(d, dict) and d.get("passed") is False]
        out.append({
            "pack_id": e.pack_id, "version": e.version, "model": e.model_name, "route_kind": e.route_kind,
            "passed": bool(e.passed), "cases_passed": e.cases_passed, "cases_total": e.cases_total,
            "failed_questions": failed[:5], "run_at": e.run_at.isoformat(),
        })
    return out


def _feedback(db: Session, since: datetime.datetime) -> dict:
    from evolvxsi.db.models import ChatMessage, ChatMessageFeedback as F

    pos, neg, followup = db.execute(
        select(
            func.coalesce(func.sum(case((F.is_positive.is_(True), 1), else_=0)), 0),
            func.coalesce(func.sum(case((F.is_positive.is_(False), 1), else_=0)), 0),
            func.coalesce(func.sum(case((F.required_followup.is_(True), 1), else_=0)), 0),
        ).join(ChatMessage, ChatMessage.id == F.chat_message_id).where(ChatMessage.time_sent >= since)
    ).one()
    return {"chat": {"positive": int(pos), "negative": int(neg), "needed_followup": int(followup),
                     "positive_share": _rate(int(pos), int(pos) + int(neg))}}


def _trends(db: Session, since: datetime.datetime, now: datetime.datetime, days: int) -> list[dict]:
    from evolvxsi.route_policy.audit import EvolvXSIAuditEvent as A
    from evolvxsi.tasks.models import EvolvXSITask as T

    def per_day(column, *where) -> dict[datetime.date, int]:
        day = cast(func.timezone("UTC", column), Date)
        return {d: int(n) for d, n in db.execute(select(day, func.count()).where(column >= since, *where).group_by(day)).all()}

    started = per_day(T.started_at)
    drafted = per_day(T.drafted_at)
    approved = per_day(T.approved_at)
    failed = per_day(T.updated_at, T.state.in_(FAILED))
    refused = per_day(A.created_at, A.outcome == "denied")
    today = now.astimezone(datetime.timezone.utc).date()
    out = []
    for back in range(days - 1, -1, -1):
        d = today - datetime.timedelta(days=back)
        out.append({"date": d.isoformat(), "started": started.get(d, 0), "drafted": drafted.get(d, 0),
                    "approved": approved.get(d, 0), "failed": failed.get(d, 0), "refused": refused.get(d, 0)})
    return out


def build(db: Session, days: int = DEFAULT_DAYS, now: datetime.datetime | None = None) -> dict:
    days = max(1, min(int(days), MAX_DAYS))
    now = now or datetime.datetime.now(datetime.timezone.utc)
    since = now - datetime.timedelta(days=days)
    return {"generated_at": now.isoformat(), "window_days": days, "runs": _runs(db, since), "evals": _evals(db),
            "feedback": _feedback(db, since), "trends": _trends(db, since, now, days)}


@router.get("")
def get_quality(
    days: int = Query(DEFAULT_DAYS, ge=1, le=MAX_DAYS),
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> dict:
    return build(db_session, days)
