"""Reviewed-task endpoints. Each person sees and changes only their own tasks.

Every write names the task version it was based on; a stale version is refused
with a conflict, so a second click or an old tab cannot start a task twice or
overwrite newer edits.
"""

from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from evolvxsi.auth.permissions import require_permission
from evolvxsi.db.engine.sql_engine import get_session
from evolvxsi.db.enums import Permission
from evolvxsi.db.models import User
from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.route_policy.audit import record_audit
from evolvxsi.tasks.models import EvolvXSITask
from evolvxsi.tasks.drafter import draft_answer
from evolvxsi.tasks.evidence import gather_evidence
from evolvxsi.tasks.claims import (
    KEEP,
    REMOVE,
    carry_decisions,
    open_unsupported,
    split_claims,
    unknown_citations,
    visible_text,
)
from evolvxsi.tasks.export import draft_fingerprint, recheck_cited_sources, to_markdown
from evolvxsi.tasks.planner import PlanError, draft_plan
from evolvxsi.tasks.relevance import filter_relevant
from evolvxsi.tasks.untrusted import looks_like_instructions, neutralize_passage
from evolvxsi.tasks.states import EDITABLE, InvalidTransition, TaskAction, TaskState, next_state
from evolvxsi.utils.audit import AuditAction, AuditOutcome
from evolvxsi.utils.logger import setup_logger

logger = setup_logger()
router = APIRouter(prefix="/tasks")

MAX_TITLE = 200
MAX_TEXT = 8000


class TaskView(BaseModel):
    id: UUID
    title: str
    request: str
    desired_output: str
    state: TaskState
    version: int
    plan: list[str] | None
    plan_route: str | None
    plan_error: str | None
    revision_note: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    started_at: datetime.datetime | None
    draft_text: str | None = None
    draft_sources: list[dict] | None = None
    draft_route: str | None = None
    run_error: str | None = None
    drafted_at: datetime.datetime | None = None
    draft_hash: str | None = None
    draft_claims: list[dict] | None = None
    draft_version: int | None = None
    draft_versions: list[dict] | None = None
    approved_hash: str | None = None
    approved_at: datetime.datetime | None = None
    exported_at: datetime.datetime | None = None
    # True when the owner can no longer open a cited source: the draft text,
    # claims, sources and versions are then not returned until it is redrafted.
    withheld: bool = False
    withheld_message: str | None = None
    pack_id: str | None = None
    pack_version: str | None = None
    pack_template: str | None = None
    # Results of the pack's review rules on the current draft (empty without rules).
    rule_results: list[dict] = []


class TaskDraft(BaseModel):
    title: str
    request: str
    desired_output: str = ""

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("A task needs a title.")
        if len(v) > MAX_TITLE:
            raise ValueError(f"A title can be at most {MAX_TITLE} characters.")
        return v

    @field_validator("request")
    @classmethod
    def _request(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Describe what the task should do.")
        if len(v) > MAX_TEXT:
            raise ValueError(f"A request can be at most {MAX_TEXT} characters.")
        return v

    @field_validator("desired_output")
    @classmethod
    def _out(cls, v: str) -> str:
        if len(v) > MAX_TEXT:
            raise ValueError(f"The desired output can be at most {MAX_TEXT} characters.")
        return v.strip()


class TaskEdit(TaskDraft):
    version: int


class VersionOnly(BaseModel):
    version: int


class Revise(BaseModel):
    version: int
    note: str = ""


WITHHELD_FIELDS = ("draft_text", "draft_claims", "draft_sources", "draft_versions", "draft_hash")


def _withheld_count(t: EvolvXSITask) -> int:
    """How many cited sources the owner can no longer open (0 when none, or when
    the task has no draft). Checked from the database on every view."""
    from sqlalchemy.orm import object_session

    if TaskState(t.state) not in (TaskState.DRAFT_READY, TaskState.APPROVED) or not t.draft_sources:
        return 0
    db = object_session(t)
    owner = db.get(User, t.owner_id) if db is not None else None
    if db is None or owner is None:
        return 0
    return recheck_cited_sources(db, owner, t.draft_sources).withheld


def _view(t: EvolvXSITask) -> TaskView:
    data = t.as_dict()
    if (n := _withheld_count(t)):
        for f in WITHHELD_FIELDS:
            data[f] = None
        data["withheld"] = True
        data["withheld_message"] = (
            f"You can no longer open {n} source(s) this draft cites, so the draft is hidden. "
            "Ask for access again, or revise the task and run it again."
        )
    elif t.review_rules and t.state in (TaskState.DRAFT_READY.value, TaskState.APPROVED.value):
        from evolvxsi.packs.review_rules import evaluate

        data["rule_results"] = evaluate(t.review_rules, t.draft_text, t.draft_sources, t.draft_claims)
    data.pop("review_rules", None)
    return TaskView.model_validate(data)


def _refuse_if_withheld(t: EvolvXSITask) -> None:
    if _withheld_count(t):
        raise EvolvXSIError(
            EvolvXSIErrorCode.INSUFFICIENT_PERMISSIONS,
            "You can no longer open a source this draft cites, so it cannot be changed or approved.",
        )


def _own(db: Session, task_id: UUID, user: User) -> EvolvXSITask:
    task = db.scalar(select(EvolvXSITask).where(EvolvXSITask.id == task_id, EvolvXSITask.owner_id == user.id))
    if task is None:
        # Same answer for "missing" and "someone else's", so existence is not revealed.
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Task not found.")
    return task


def _move(db: Session, task_id: UUID, user: User, version: int, action: TaskAction, **values: object) -> EvolvXSITask:
    """Apply one state move as a single conditional update on (owner, state,
    version). Exactly one of two racing requests can win."""
    task = _own(db, task_id, user)
    try:
        new_state = next_state(TaskState(task.state), action)
    except InvalidTransition as e:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, str(e)) from e
    if task.version != version:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "This task changed since you opened it. Reload and try again.")
    result = db.execute(
        update(EvolvXSITask)
        .where(
            EvolvXSITask.id == task_id,
            EvolvXSITask.owner_id == user.id,
            EvolvXSITask.state == task.state,
            EvolvXSITask.version == version,
        )
        .values(state=new_state.value, version=EvolvXSITask.version + 1, updated_at=func.now(), **values)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "This task changed since you opened it. Reload and try again.")
    db.commit()
    db.expire_all()
    return _own(db, task_id, user)


def _audit(user: User, action: AuditAction, task: EvolvXSITask, summary: str, outcome: AuditOutcome = AuditOutcome.SUCCESS) -> None:
    # Title and request text stay out of the audit record.
    record_audit(action, outcome, actor=user, summary=summary, resource_type="task", resource_id=str(task.id))


@router.get("")
def list_tasks(
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[TaskView]:
    rows = db_session.scalars(
        select(EvolvXSITask).where(EvolvXSITask.owner_id == user.id).order_by(EvolvXSITask.updated_at.desc()).limit(200)
    )
    return [_view(t) for t in rows]


@router.get("/{task_id}")
def get_task(
    task_id: UUID,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    return _view(_own(db_session, task_id, user))


@router.post("")
def create_draft(
    body: TaskDraft,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    """Saving a draft creates no work."""
    task = EvolvXSITask(
        owner_id=user.id, title=body.title, request=body.request, desired_output=body.desired_output,
        state=TaskState.DRAFT.value, version=1,
    )
    db_session.add(task)
    db_session.commit()
    return _view(task)


@router.patch("/{task_id}")
def edit_draft(
    task_id: UUID,
    body: TaskEdit,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    task = _own(db_session, task_id, user)
    if TaskState(task.state) not in EDITABLE:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "Only a draft can be edited.")
    result = db_session.execute(
        update(EvolvXSITask)
        .where(EvolvXSITask.id == task_id, EvolvXSITask.owner_id == user.id,
               EvolvXSITask.state == TaskState.DRAFT.value, EvolvXSITask.version == body.version)
        .values(title=body.title, request=body.request, desired_output=body.desired_output,
                version=EvolvXSITask.version + 1, updated_at=func.now())
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db_session.rollback()
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "This task changed since you opened it. Reload and try again.")
    db_session.commit()
    db_session.expire_all()
    return _view(_own(db_session, task_id, user))


def _enforce_pack_requirements(db: Session, task: EvolvXSITask, user: User) -> None:
    """A task started from a pack runs only where that exact pack version says it
    may: the workspace's data class and the model route in use must both be
    listed. A pack from a signer revoked since is refused."""
    if not task.pack_id:
        return
    from evolvxsi.packs.models import EvolvXSIPackSigner, EvolvXSIPackVersion
    from evolvxsi.route_policy.enforce import default_route_kind
    from evolvxsi.route_policy.policy import load_policy

    v = db.scalar(select(EvolvXSIPackVersion).where(
        EvolvXSIPackVersion.pack_id == task.pack_id, EvolvXSIPackVersion.version == task.pack_version))
    signer = db.get(EvolvXSIPackSigner, v.signer_key_id) if v else None
    if v is None or signer is None or signer.revoked:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "The pack this task started from is no longer trusted, so it cannot run.")
    req = v.manifest["requires"]
    data_class = load_policy().default_data_class
    kind = default_route_kind(db)
    problem = None
    if data_class not in req["data_classes"]:
        problem = f"this workspace's data class ({data_class}) is not one the pack supports"
    elif kind is None or kind not in req["route_kinds"]:
        problem = f"the model route in use ({kind or 'none'}) is not one the pack supports ({', '.join(req['route_kinds'])})"
    if problem is None:
        from evolvxsi.packs.api import passed_on_current_model

        ok, why = passed_on_current_model(db, task.pack_id, task.pack_version or "", v.manifest)
        if not ok:
            problem = f"the pack has not passed its evaluation on the model in use ({why})"
    if problem:
        record_audit(AuditAction.ROUTE_BLOCKED, AuditOutcome.DENIED, actor=user,
                     summary=f"Pack {task.pack_id} {task.pack_version} cannot run: {problem}", resource_type="task", resource_id=str(task.id))
        raise EvolvXSIError(EvolvXSIErrorCode.POLICY_BLOCKED, f"This pack cannot run here: {problem}.")


@router.post("/{task_id}/start")
def start_task(
    task_id: UUID,
    body: VersionOnly,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    """The explicit start. Moves the draft to planning atomically (a duplicate
    start is refused), then drafts a plan through the route policy."""
    _enforce_pack_requirements(db_session, _own(db_session, task_id, user), user)
    task = _move(db_session, task_id, user, body.version, TaskAction.START,
                 started_at=func.now(), plan=None, plan_error=None, plan_route=None)
    _audit(user, AuditAction.TASK_START, task, "Started a task")
    try:
        from evolvxsi.packs.agents import agent_for
        from evolvxsi.packs.guidance import guides_for

        agent = agent_for(db_session, task.pack_id, task.pack_version, task.pack_template)
        if agent is not None:
            from evolvxsi.tasks.planner import draft_agent_plan

            result = draft_agent_plan(db_session, user, task.title, task.request, task.desired_output, agent)
        else:
            guides = guides_for(db_session, task.pack_id, task.pack_version, task.pack_template)
            result = draft_plan(db_session, user, task.title, task.request, task.desired_output, guides)
    except PlanError as e:
        return _view(_move(db_session, task_id, user, task.version, TaskAction.PLAN_FAILED, plan_error=str(e)))
    except EvolvXSIError as e:
        # A policy block keeps its own audit record; tell the owner plainly.
        return _view(_move(db_session, task_id, user, task.version, TaskAction.PLAN_FAILED, plan_error=e.detail))
    except Exception:
        logger.exception("task planning failed task_id=%s", task_id)
        return _view(_move(db_session, task_id, user, task.version, TaskAction.PLAN_FAILED,
                           plan_error="The plan could not be drafted. Try again in a moment."))
    return _view(_move(db_session, task_id, user, task.version, TaskAction.PLAN_READY,
                       plan=result.steps, plan_route=result.route_kind))


@router.post("/{task_id}/plan/accept")
def accept_plan(
    task_id: UUID, body: VersionOnly,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    task = _move(db_session, task_id, user, body.version, TaskAction.ACCEPT)
    _audit(user, AuditAction.TASK_PLAN_ACCEPT, task, f"Accepted a plan of {len(task.plan or [])} step(s)")
    return _view(task)


@router.post("/{task_id}/plan/revise")
def revise_plan(
    task_id: UUID, body: Revise,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    """Back to an editable draft; the owner edits and starts again."""
    return _view(_move(db_session, task_id, user, body.version, TaskAction.REVISE,
                       revision_note=body.note.strip()[:MAX_TEXT] or None))


@router.post("/{task_id}/cancel")
def cancel_task(
    task_id: UUID, body: VersionOnly,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    task = _move(db_session, task_id, user, body.version, TaskAction.CANCEL)
    _audit(user, AuditAction.TASK_CANCEL, task, "Cancelled a task")
    return _view(task)


@router.post("/{task_id}/run")
def run_task(
    task_id: UUID,
    body: VersionOnly,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    """Run an accepted plan (or retry a failed run): gather evidence as the
    owner, then draft a cited answer through the route policy. The move to
    running is atomic, so the same run cannot start twice."""
    _enforce_pack_requirements(db_session, _own(db_session, task_id, user), user)
    task = _move(db_session, task_id, user, body.version, TaskAction.RUN, run_error=None)
    _audit(user, AuditAction.TASK_RUN, task, "Started a task run")
    try:
        from evolvxsi.packs.agents import agent_for, planned_searches, run_searches
        from evolvxsi.packs.guidance import guides_for, style_for

        agent = agent_for(db_session, task.pack_id, task.pack_version, task.pack_template)
        if agent is not None:
            # Plan-then-execute: run exactly the accepted search steps, as the owner, in code. The model is not asked
            # what to do next; nothing it reads can add a step.
            queries = planned_searches(task.plan, agent)
            if not queries:
                raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "The accepted plan has no search the agent may run. Revise and start again.")
            found = run_searches(db_session, user, queries)
            evidence = filter_relevant(db_session, user, task.request, found)
            guides = list(agent.guides) + [(f"Agent instructions ({agent.name})", agent.instructions)]
            # Counts only: the queries come from the owner's request, so they stay out of the audit record.
            record_audit(AuditAction.AGENT_RUN, AuditOutcome.SUCCESS, actor=user,
                         summary=f"Agent {agent.name} ran {len(queries)} search(es) for the owner and found {len(found)} source(s)",
                         details={"agent": agent.id, "pack": agent.pack_id, "version": agent.version, "searches": len(queries),
                                  "sources_found": len(found), "sources_kept": len(evidence)},
                         resource_type="task", resource_id=str(task.id))
        else:
            question = f"{task.title}\n{task.request}"
            evidence = filter_relevant(db_session, user, task.request, gather_evidence(db_session, user, question))
            guides = guides_for(db_session, task.pack_id, task.pack_version, task.pack_template)
        style = style_for(db_session, task.pack_id, task.pack_version, task.pack_template)
        result = draft_answer(db_session, user, task.title, task.request, task.plan or [], evidence, style, guides)
    except EvolvXSIError as e:
        return _view(_move(db_session, task_id, user, task.version, TaskAction.RUN_FAILED, run_error=e.detail))
    except Exception:
        logger.exception("task run failed task_id=%s", task_id)
        return _view(_move(db_session, task_id, user, task.version, TaskAction.RUN_FAILED,
                           run_error="The run stopped before a draft was ready. Try again in a moment."))
    if not evidence:
        # The fixed "no source" message is the system's notice, not a claim the owner must rule on.
        claims = [{"i": 0, "text": result.text, "cites": [], "status": "notice", "decision": None}]
    else:
        claims = split_claims(result.text)
    by_n = {e.n: e for e in evidence}
    sources = [
        {"n": e.n, "doc_id": e.doc_id, "title": e.title, "link": e.link, "cited": e.n in result.cited,
         # The passage as the model saw it, so a reviewer can check a claim against it.
         "passage": neutralize_passage(e.passage, 1200),
         "flagged": looks_like_instructions(e.passage)}
        for e in by_n.values()
    ]
    if result.removed_citations:
        logger.info("task run removed %s citation(s) to sources not provided task_id=%s", result.removed_citations, task_id)
    return _view(_move(db_session, task_id, user, task.version, TaskAction.DRAFT_DONE,
                       draft_text=result.text, draft_sources=sources, draft_route=result.route_kind,
                       drafted_at=func.now(), draft_claims=claims,
                       draft_hash=draft_fingerprint(result.text, sources, claims),
                       draft_version=1,
                       draft_versions=[{"v": 1, "by": "model", "text": result.text,
                                        "hash": draft_fingerprint(result.text, sources, claims),
                                        "at": datetime.datetime.now(datetime.timezone.utc).isoformat()}],
                       approved_hash=None, approved_at=None))


class Approve(BaseModel):
    version: int
    # The fingerprint of the draft the owner looked at. A different draft is refused.
    draft_hash: str


class ExportResult(BaseModel):
    task: TaskView
    filename: str
    markdown: str


@router.post("/{task_id}/approve")
def approve_draft(
    task_id: UUID, body: Approve,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    """Approve one exact draft. The approval names the draft's fingerprint, so
    a draft that changed since the owner read it cannot be approved by mistake."""
    task = _own(db_session, task_id, user)
    _refuse_if_withheld(task)
    if (pending := open_unsupported(task.draft_claims)):
        raise EvolvXSIError(
            EvolvXSIErrorCode.CONFLICT,
            f"Decide on {pending} unsupported claim(s) first: keep each one as unsupported, or remove it.",
        )
    if not task.draft_hash or task.draft_hash != body.draft_hash:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "The draft changed since you read it. Reload and review it again.")
    if task.review_rules:
        from evolvxsi.packs.review_rules import blocking_failures, evaluate

        failed = blocking_failures(evaluate(task.review_rules, task.draft_text, task.draft_sources, task.draft_claims))
        if failed:
            _audit(user, AuditAction.TASK_APPROVE, task, f"Approval refused: {len(failed)} pack review rule(s) not met", AuditOutcome.DENIED)
            raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT,
                                "The pack's review rules are not met: " + "; ".join(f["message"] for f in failed))
    task = _move(db_session, task_id, user, body.version, TaskAction.APPROVE,
                 approved_hash=body.draft_hash, approved_at=func.now())
    _audit(user, AuditAction.TASK_APPROVE, task, f"Approved draft {body.draft_hash[:12]}")
    return _view(task)


@router.post("/{task_id}/export")
def export_draft(
    task_id: UUID, body: VersionOnly,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ExportResult:
    """Export the approved draft as Markdown, after re-checking access to every
    cited source. Withheld if any cited source is no longer open to the owner."""
    task = _own(db_session, task_id, user)
    if TaskState(task.state) is not TaskState.APPROVED or task.version != body.version:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "Only the approved draft you are looking at can be exported.")
    if task.approved_hash != draft_fingerprint(task.draft_text or "", task.draft_sources, task.draft_claims):
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "The draft no longer matches what was approved.")
    check = recheck_cited_sources(db_session, user, task.draft_sources)
    if check.withheld:
        _audit(user, AuditAction.TASK_EXPORT, task,
               f"Export withheld: {check.withheld} cited source(s) no longer open", AuditOutcome.DENIED)
        raise EvolvXSIError(
            EvolvXSIErrorCode.INSUFFICIENT_PERMISSIONS,
            f"Export withheld: you can no longer open {check.withheld} of the cited sources. "
            "Redraft the task or ask for access again.",
        )
    db_session.execute(
        update(EvolvXSITask).where(EvolvXSITask.id == task_id).values(exported_at=func.now())
        .execution_options(synchronize_session=False)
    )
    db_session.commit()
    db_session.expire_all()
    task = _own(db_session, task_id, user)
    _audit(user, AuditAction.TASK_EXPORT, task, "Exported an approved draft")
    safe = "".join(ch if ch.isalnum() or ch in "-_ " else "" for ch in task.title).strip().replace(" ", "-")[:60] or "task"
    return ExportResult(task=_view(task), filename=f"{safe}.md",
                        markdown=to_markdown(
                            task.title,
                            visible_text(task.draft_claims, label_unsupported=True) if task.draft_claims else (task.draft_text or ""),
                            task.draft_sources,
                        ))


class ClaimDecision(BaseModel):
    version: int
    decision: str

    @field_validator("decision")
    @classmethod
    def _d(cls, v: str) -> str:
        if v not in (KEEP, REMOVE):
            raise ValueError("Choose keep or remove.")
        return v


@router.post("/{task_id}/claims/{claim_index}")
def decide_claim(
    task_id: UUID, claim_index: int, body: ClaimDecision,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    """Keep an unsupported claim (it is labelled unsupported in the export) or
    remove it from the draft. Either way the draft's fingerprint changes."""
    task = _own(db_session, task_id, user)
    _refuse_if_withheld(task)
    if TaskState(task.state) is not TaskState.DRAFT_READY:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "Claims can only be reviewed on a draft that is ready.")
    claims = [dict(c) for c in (task.draft_claims or [])]
    target = next((c for c in claims if c["i"] == claim_index), None)
    if target is None:
        raise EvolvXSIError(EvolvXSIErrorCode.NOT_FOUND, "Claim not found.")
    if target["status"] != "unsupported":
        raise EvolvXSIError(EvolvXSIErrorCode.INVALID_INPUT, "Only unsupported claims need a decision.")
    target["decision"] = body.decision
    text_now = visible_text(claims)
    result = db_session.execute(
        update(EvolvXSITask)
        .where(EvolvXSITask.id == task_id, EvolvXSITask.owner_id == user.id,
               EvolvXSITask.state == TaskState.DRAFT_READY.value, EvolvXSITask.version == body.version)
        .values(draft_claims=claims, draft_text=text_now,
                draft_hash=draft_fingerprint(text_now, task.draft_sources, claims),
                version=EvolvXSITask.version + 1, updated_at=func.now())
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db_session.rollback()
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "This task changed since you opened it. Reload and try again.")
    db_session.commit()
    db_session.expire_all()
    return _view(_own(db_session, task_id, user))


MAX_DRAFT = 20000


class DraftEdit(BaseModel):
    version: int
    text: str

    @field_validator("text")
    @classmethod
    def _t(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("The draft cannot be empty.")
        if len(v) > MAX_DRAFT:
            raise ValueError(f"A draft can be at most {MAX_DRAFT} characters.")
        return v


@router.put("/{task_id}/draft")
def edit_ready_draft(
    task_id: UUID, body: DraftEdit,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TaskView:
    """Save an edited draft as a new version. Citations may name only sources
    this run had; claims are re-checked, and earlier decisions carry over only
    to unchanged sentences. Any earlier approval no longer applies, because the
    fingerprint changes."""
    task = _own(db_session, task_id, user)
    _refuse_if_withheld(task)
    if TaskState(task.state) is not TaskState.DRAFT_READY:
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "Only a draft that is ready can be edited.")
    sources = [dict(x) for x in (task.draft_sources or [])]
    valid = {int(x["n"]) for x in sources}
    if bad := unknown_citations(body.text, valid):
        raise EvolvXSIError(
            EvolvXSIErrorCode.INVALID_INPUT,
            "These citations do not match a source of this run: " + ", ".join(f"[{n}]" for n in bad),
        )
    claims = carry_decisions(split_claims(body.text), task.draft_claims)
    cited = {n for c in claims for n in c["cites"]}
    for x in sources:
        x["cited"] = int(x["n"]) in cited
    text_now = visible_text(claims)
    fp = draft_fingerprint(text_now, sources, claims)
    new_v = (task.draft_version or 1) + 1
    history = list(task.draft_versions or []) + [
        {"v": new_v, "by": "owner", "text": body.text, "hash": fp,
         "at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    ]
    result = db_session.execute(
        update(EvolvXSITask)
        .where(EvolvXSITask.id == task_id, EvolvXSITask.owner_id == user.id,
               EvolvXSITask.state == TaskState.DRAFT_READY.value, EvolvXSITask.version == body.version)
        .values(draft_text=text_now, draft_claims=claims, draft_sources=sources, draft_hash=fp,
                draft_version=new_v, draft_versions=history, version=EvolvXSITask.version + 1, updated_at=func.now())
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db_session.rollback()
        raise EvolvXSIError(EvolvXSIErrorCode.CONFLICT, "This task changed since you opened it. Reload and try again.")
    db_session.commit()
    db_session.expire_all()
    return _view(_own(db_session, task_id, user))
