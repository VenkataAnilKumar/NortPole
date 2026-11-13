"""One read-only summary for administrators. It shows counts, system error messages and reasons, never the
title or text of anyone's task: administering the product does not grant reading people's work."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.engine.sql_engine import get_session
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import User

router = APIRouter(prefix="/admin/overview")
WINDOW_DAYS = 7


def build(db: Session, now: datetime.datetime | None = None) -> dict:
    from evolvxsi.audit_log.chain import verify_quick
    from evolvxsi.configs.app_configs import DISABLE_VECTOR_DB
    from evolvxsi.extensions.policy import load as load_ext
    from evolvxsi.packs.api import _active_versions, current_model, passed_on_current_model
    from evolvxsi.packs.models import EvolvXSIPackSigner
    from evolvxsi.retention.settings import load as load_ret
    from evolvxsi.route_policy.audit import EvolvXSIAuditEvent as A
    from evolvxsi.route_policy.enforce import check_route
    from evolvxsi.route_policy.policy import load_policy
    from evolvxsi.tasks.models import EvolvXSITask as T

    now = now or datetime.datetime.now(datetime.timezone.utc)
    since = now - datetime.timedelta(days=WINDOW_DAYS)

    counts = dict(db.execute(select(T.state, func.count()).where(T.updated_at >= since).group_by(T.state)).all())
    errors = db.execute(
        select(T.state, func.coalesce(T.run_error, T.plan_error), T.updated_at)
        .where(T.updated_at >= since, T.state.in_(["run_failed", "plan_failed"])).order_by(T.updated_at.desc()).limit(5)
    ).all()
    runs = {
        "failed_plans": int(counts.get("plan_failed", 0)), "failed_runs": int(counts.get("run_failed", 0)),
        "drafts_ready": int(counts.get("draft_ready", 0)), "approved": int(counts.get("approved", 0)),
        "recent_errors": [{"state": s, "error": (e or "no message")[:200], "at": at.isoformat()} for s, e, at in errors],
    }

    by_action = db.execute(
        select(A.action, func.count()).where(A.created_at >= since, A.outcome == "denied").group_by(A.action).order_by(func.count().desc())
    ).all()
    recent = db.execute(
        select(A.action, A.summary, A.created_at).where(A.created_at >= since, A.outcome == "denied").order_by(A.id.desc()).limit(5)
    ).all()
    refusals = {
        "total": int(sum(n for _, n in by_action)),
        "by_action": [{"action": a, "count": int(n)} for a, n in by_action],
        "recent": [{"action": a, "summary": s[:200], "at": at.isoformat()} for a, s, at in recent],
    }

    active = _active_versions(db)
    unavailable = []
    for v in active:
        ok, why = passed_on_current_model(db, v.pack_id, v.version, v.manifest)
        if not ok:
            unavailable.append({"pack_id": v.pack_id, "name": v.manifest.get("name", v.pack_id), "version": v.version, "reason": why})
    packs = {"active": len(active), "unavailable": unavailable}

    chain = verify_quick(db)

    model = current_model(db)
    policy, ret, ext = load_policy(), load_ret(), load_ext()
    trusted = db.scalar(select(func.count()).select_from(EvolvXSIPackSigner).where(EvolvXSIPackSigner.revoked.is_(False))) or 0
    setup = [
        {"item": "Default model", "ok": model is not None, "href": "/admin/language-models",
         "note": f"{model.name} on a {check_route(db, model.id).kind} route" if model else "No default model: chats and tasks cannot run."},
        {"item": "Search index", "ok": not DISABLE_VECTOR_DB, "href": "/admin/index-settings",
         "note": "On." if not DISABLE_VECTOR_DB else "Off: drafts cannot cite indexed sources."},
        {"item": "Redaction", "ok": True, "href": "/admin/route-policy",
         "note": "Before sending to: " + (", ".join(policy.redact_route_kinds) or "no route type") + "."},
        {"item": "Retention", "ok": True, "href": "/admin/audit",
         "note": (f"Legal hold on ({ret.hold_reason}). " if ret.legal_hold else "")
                 + f"Audit kept {ret.audit_days or 'forever'} days. The default periods are placeholders until you set them."},
        {"item": "Pack signers", "ok": trusted > 0, "href": "/admin/packs",
         "note": f"{trusted} trusted." if trusted else "No trusted signer: no pack can be installed."},
        {"item": "MCP allowlist", "ok": True, "href": "/admin/inventory",
         "note": f"On, {len(ext.mcp_allowed_hosts)} hosts." if ext.mcp_allowlist_enabled else "Off: any host may be added by an administrator."},
    ]
    return {"generated_at": now.isoformat(), "window_days": WINDOW_DAYS, "runs": runs, "refusals": refusals,
            "packs": packs, "audit_chain": chain, "setup": setup}


@router.get("")
def get_overview(
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> dict:
    return build(db_session)
