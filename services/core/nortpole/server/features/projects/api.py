import json
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
)
from pydantic import BaseModel
from sqlalchemy import and_, exists, or_, select, update
from sqlalchemy.orm import Session

from nortpole.auth.permissions import require_permission
from nortpole.chat.incognito import incognito_allowed_for_user
from nortpole.chat.incognito_context import incognito_session_torn_down
from nortpole.configs.app_configs import DISABLE_VECTOR_DB
from nortpole.configs.constants import (
    PUBLIC_API_TAGS,
    USER_FILE_PROJECT_SYNC_MAX_QUEUE_DEPTH,
    NortPoleCeleryPriority,
    NortPoleCeleryQueues,
    NortPoleCeleryTask,
)
from nortpole.db.chat import get_owned_chat_session
from nortpole.db.engine.sql_engine import get_session
from nortpole.db.enums import ChatSessionSharedStatus, Permission, UserFileStatus
from nortpole.db.incognito import mark_incognito_user_files_deleting
from nortpole.db.models import ChatSession, Project__UserFile, ProjectMember, User, UserFile, UserProject
from nortpole.db.project_access import project_has_members, require_project
from nortpole.db.persona import get_personas_by_ids
from nortpole.db.projects import (
    get_project_token_count,
    upload_files_to_user_files_with_indexing,
)
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.server.features.projects.models import (
    CategorizedFilesSnapshot,
    ChatSessionRequest,
    TokenCountResponse,
    UserFileSnapshot,
    UserProjectSnapshot,
)
from nortpole.server.features.projects.collaboration import router as collaboration_router
from nortpole.server.features.projects.outputs import router as outputs_router
from nortpole.utils.logger import setup_logger
from shared_configs.contextvars import get_current_tenant_id

logger = setup_logger()


router = APIRouter(prefix="/user/projects")
router.include_router(outputs_router)
router.include_router(collaboration_router)

# `user_project.name` and `user_project.description` are both varchar(255). Longer
# values make Postgres reject the write, which surfaces as a 500.
_MAX_PROJECT_FIELD_LENGTH = 255


def _validate_project_field_length(value: str, field_name: str) -> None:
    if len(value) > _MAX_PROJECT_FIELD_LENGTH:
        raise NortPoleError(
            NortPoleErrorCode.INVALID_INPUT,
            f"Project {field_name} cannot be longer than "
            f"{_MAX_PROJECT_FIELD_LENGTH} characters",
        )


def _set_chat_project(
    db_session: Session, user_id: UUID, chat_session_id: str, project_id: int | None,
    *, private_only: bool = False,
) -> None:
    try:
        chat_id = UUID(chat_session_id)
    except ValueError as exc:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Chat session not found") from exc
    stmt = (
        update(ChatSession)
        .where(
            ChatSession.id == chat_id,
            ChatSession.user_id == user_id,
            ChatSession.spawned_by_message_id.is_(None),
            ChatSession.deleted.is_(False),
            ChatSession.incognito_record_mode.is_(None),
            ChatSession.agent_preview.is_(None),
        )
        .values(project_id=project_id)
    )
    if private_only:
        stmt = stmt.where(ChatSession.shared_status == ChatSessionSharedStatus.PRIVATE)
    if db_session.execute(stmt).rowcount != 1:
        raise NortPoleError(NortPoleErrorCode.NOT_FOUND, "Chat session not found")


class UserFileDeleteResult(BaseModel):
    has_associations: bool
    project_names: list[str] = []
    assistant_names: list[str] = []


def _claim_upload_if_session_ended(
    db_session: Session, incognito_session_id: UUID | None, user_id: UUID
) -> None:
    """Queue this session's uploads if a teardown landed during the upload.

    Never raises: it runs on the upload's failure path too, where masking the
    original error would cost more than the delay to the orphan sweep.
    """
    if incognito_session_id is None:
        return
    try:
        # The caller may be unwinding a failed statement, which would refuse
        # any further query on this session.
        db_session.rollback()
        if not incognito_session_torn_down(incognito_session_id):
            return
        mark_incognito_user_files_deleting(db_session, incognito_session_id, user_id)
        db_session.commit()
    except Exception:
        logger.exception(
            "Could not claim uploads for ended incognito session %s",
            incognito_session_id,
        )


def _trigger_user_file_project_sync(
    user_file_id: UUID,
    tenant_id: str,
    background_tasks: BackgroundTasks | None = None,
) -> None:
    if DISABLE_VECTOR_DB and background_tasks is not None:
        from nortpole.background.task_utils import drain_project_sync_loop

        background_tasks.add_task(drain_project_sync_loop, tenant_id)
        logger.info("Queued in-process project sync for user_file_id=%s", user_file_id)
        return

    from nortpole.background.celery.tasks.user_file_processing.tasks import (
        enqueue_user_file_project_sync_task,
        get_user_file_project_sync_queue_depth,
    )
    from nortpole.background.celery.versioned_apps.client import app as client_app
    from nortpole.redis.redis_pool import get_redis_client

    queue_depth = get_user_file_project_sync_queue_depth(client_app)
    if queue_depth > USER_FILE_PROJECT_SYNC_MAX_QUEUE_DEPTH:
        logger.warning(
            "Skipping immediate project sync for user_file_id=%s due to queue depth %s>%s. It will be picked up by beat later.",
            user_file_id,
            queue_depth,
            USER_FILE_PROJECT_SYNC_MAX_QUEUE_DEPTH,
        )
        return

    redis_client = get_redis_client(tenant_id=tenant_id)
    enqueued = enqueue_user_file_project_sync_task(
        celery_app=client_app,
        redis_client=redis_client,
        user_file_id=user_file_id,
        tenant_id=tenant_id,
        priority=NortPoleCeleryPriority.HIGHEST,
    )
    if not enqueued:
        logger.info(
            "Skipped duplicate project sync enqueue for user_file_id=%s", user_file_id
        )
        return

    logger.info("Triggered project sync for user_file_id=%s", user_file_id)


@router.get("", tags=PUBLIC_API_TAGS)
def get_projects(
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[UserProjectSnapshot]:
    user_id = user.id
    any_member = exists().where(ProjectMember.project_id == UserProject.id).correlate(UserProject)
    stmt = (
        select(UserProject, ProjectMember.role, any_member)
        .outerjoin(
            ProjectMember,
            and_(ProjectMember.project_id == UserProject.id, ProjectMember.user_id == user_id),
        )
        .where(or_(UserProject.user_id == user_id, ProjectMember.user_id == user_id))
    )
    return [
        UserProjectSnapshot.from_model(
            project, viewer_id=user_id, shared=shared,
            role="owner" if project.user_id == user_id else ("editor" if role == "editor" else "viewer"),
        )
        for project, role, shared in db_session.execute(stmt)
    ]

@router.post("/create", tags=PUBLIC_API_TAGS)
def create_project(
    name: str,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
    chat_session_id: str | None = None,
) -> UserProjectSnapshot:
    if name == "":
        raise HTTPException(status_code=400, detail="Project name cannot be empty")
    _validate_project_field_length(name, "name")
    user_id = user.id
    project = UserProject(name=name, user_id=user_id)
    db_session.add(project)
    if chat_session_id is not None:
        db_session.flush()
        try:
            _set_chat_project(db_session, user_id, chat_session_id, project.id)
        except NortPoleError:
            db_session.rollback()
            raise
    db_session.commit()
    return UserProjectSnapshot.from_model(project)


@router.post("/file/upload", tags=PUBLIC_API_TAGS)
def upload_user_files(
    bg_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    project_id: int | None = Form(None),
    temp_id_map: str | None = Form(None),  # JSON string mapping hashed key -> temp_id
    incognito_session_id: UUID | None = Form(None),
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> CategorizedFilesSnapshot:
    # The file names its session before that session exists, so it is private
    # from the moment it lands and the id is what teardown finds it by.
    if incognito_session_id is not None:
        if not incognito_allowed_for_user(user, db_session, cached=False):
            raise NortPoleError(
                NortPoleErrorCode.UNAUTHORIZED,
                "Incognito chat is not enabled for this user.",
            )
        # Teardown marks the rows that exist when it runs, so an upload landing
        # after it would otherwise sit until the orphan sweep.
        if incognito_session_torn_down(incognito_session_id):
            raise NortPoleError(
                NortPoleErrorCode.INVALID_INPUT,
                "This incognito chat has ended.",
            )
    try:
        parsed_temp_id_map: dict[str, str] | None = None
        if temp_id_map:
            try:
                parsed = json.loads(temp_id_map)
                if isinstance(parsed, dict):
                    # Ensure all keys/values are strings
                    parsed_temp_id_map = {str(k): str(v) for k, v in parsed.items()}
                else:
                    parsed_temp_id_map = None
            except json.JSONDecodeError:
                parsed_temp_id_map = None

        # Use our consolidated function that handles indexing properly
        categorized_files_result = upload_files_to_user_files_with_indexing(
            files=files,
            project_id=project_id,
            user=user,
            temp_id_map=parsed_temp_id_map,
            db_session=db_session,
            background_tasks=bg_tasks if DISABLE_VECTOR_DB else None,
            incognito_session_id=incognito_session_id,
        )

        return CategorizedFilesSnapshot.from_result(categorized_files_result)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error uploading files - %s: %s", type(e).__name__, str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to upload files. Please try again or contact support if the issue persists.",
        )
    finally:
        # Rows are committed before the indexing hand-off, which can still
        # fail, so this runs on every exit.
        _claim_upload_if_session_ended(db_session, incognito_session_id, user.id)


@router.get("/{project_id}", tags=PUBLIC_API_TAGS)
def get_project(
    project_id: int,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> UserProjectSnapshot:
    project, role = require_project(project_id, user.id, db_session)
    return UserProjectSnapshot.from_model(
        project, viewer_id=user.id, role=role, shared=project_has_members(project.id, db_session)
    )

@router.get("/files/{project_id}", tags=PUBLIC_API_TAGS)
def get_files_in_project(
    project_id: int,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[UserFileSnapshot]:
    require_project(project_id, user.id, db_session)
    user_files = (
        db_session.query(UserFile)
        .join(Project__UserFile, UserFile.id == Project__UserFile.user_file_id)
        .filter(
            Project__UserFile.project_id == project_id,
            UserFile.incognito.is_(False),
            UserFile.status.notin_((UserFileStatus.FAILED, UserFileStatus.DELETING)),
        )
        .order_by(Project__UserFile.created_at.desc())
        .all()
    )
    return [UserFileSnapshot.from_model(user_file) for user_file in user_files]


@router.delete("/{project_id}/files/{file_id}", tags=PUBLIC_API_TAGS)
def unlink_user_file_from_project(
    project_id: int,
    file_id: UUID,
    bg_tasks: BackgroundTasks,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> Response:
    """Unlink an existing user file from a specific project for the current user.

    Does not delete the underlying file; only removes the association.
    """
    project, _ = require_project(project_id, user.id, db_session, minimum="editor", lock=True)
    user_file = db_session.scalar(
        select(UserFile).join(Project__UserFile).where(
            Project__UserFile.project_id == project.id,
            UserFile.id == file_id,
            UserFile.incognito.is_(False),
        )
    )
    if user_file is None:
        return Response(status_code=204)

    # Remove the association if it exists
    if user_file in project.user_files:
        project.user_files.remove(user_file)
        user_file.needs_project_sync = True
        db_session.commit()

    tenant_id = get_current_tenant_id()
    _trigger_user_file_project_sync(user_file.id, tenant_id, bg_tasks)

    return Response(status_code=204)


@router.post(
    "/{project_id}/files/{file_id}",
    response_model=UserFileSnapshot,
    tags=PUBLIC_API_TAGS,
)
def link_user_file_to_project(
    project_id: int,
    file_id: UUID,
    bg_tasks: BackgroundTasks,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> UserFileSnapshot:
    """Link an existing user file to a specific project for the current user.

    Creates the association in the Project__UserFile join table if it does not exist.
    Returns the linked user file snapshot.
    """
    project, _ = require_project(project_id, user.id, db_session, minimum="editor", lock=True)
    user_file = (
        db_session.query(UserFile)
        .filter(UserFile.id == file_id, UserFile.user_id == user.id, UserFile.incognito.is_(False))
        .one_or_none()
    )
    if user_file is None:
        raise HTTPException(status_code=404, detail="File not found")

    if user_file not in project.user_files:
        user_file.needs_project_sync = True
        project.user_files.append(user_file)
        db_session.commit()

    tenant_id = get_current_tenant_id()
    _trigger_user_file_project_sync(user_file.id, tenant_id, bg_tasks)

    return UserFileSnapshot.from_model(user_file)


class ProjectInstructionsResponse(BaseModel):
    instructions: str | None


@router.get(
    "/{project_id}/instructions",
    response_model=ProjectInstructionsResponse,
    tags=PUBLIC_API_TAGS,
)
def get_project_instructions(
    project_id: int,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ProjectInstructionsResponse:
    project, _ = require_project(project_id, user.id, db_session, minimum="viewer")

    return ProjectInstructionsResponse(instructions=project.instructions)


class UpsertProjectInstructionsRequest(BaseModel):
    instructions: str


@router.post(
    "/{project_id}/instructions",
    response_model=ProjectInstructionsResponse,
    tags=PUBLIC_API_TAGS,
)
def upsert_project_instructions(
    project_id: int,
    body: UpsertProjectInstructionsRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ProjectInstructionsResponse:
    """Create or update this project's instructions stored on the project itself."""
    project, _ = require_project(project_id, user.id, db_session, minimum="editor", lock=True)
    project.instructions = body.instructions

    db_session.commit()
    db_session.refresh(project)
    return ProjectInstructionsResponse(instructions=project.instructions)


class ProjectPayload(BaseModel):
    project: UserProjectSnapshot
    files: list[UserFileSnapshot] | None = None
    persona_id_to_is_featured: dict[int, bool] | None = None


@router.get(
    "/{project_id}/details", response_model=ProjectPayload, tags=PUBLIC_API_TAGS
)
def get_project_details(
    project_id: int,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ProjectPayload:
    project = get_project(project_id, user, db_session)
    files = get_files_in_project(project_id, user, db_session)
    persona_ids = [
        session.persona_id
        for session in project.chat_sessions
        if session.persona_id is not None
    ]
    personas = get_personas_by_ids(persona_ids, db_session)
    persona_id_to_is_featured = {
        persona.id: persona.is_featured for persona in personas
    }
    return ProjectPayload(
        project=project,
        files=files,
        persona_id_to_is_featured=persona_id_to_is_featured,
    )


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    description: str | None = None


@router.patch("/{project_id}", response_model=UserProjectSnapshot, tags=PUBLIC_API_TAGS)
def update_project(
    project_id: int,
    body: UpdateProjectRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> UserProjectSnapshot:
    project, role = require_project(project_id, user.id, db_session, minimum="editor", lock=True)

    if body.name is not None:
        _validate_project_field_length(body.name, "name")
        project.name = body.name
    if body.description is not None:
        _validate_project_field_length(body.description, "description")
        project.description = body.description

    db_session.commit()
    db_session.refresh(project)
    return UserProjectSnapshot.from_model(
        project, viewer_id=user.id, role=role, shared=project_has_members(project.id, db_session)
    )


@router.delete("/{project_id}", tags=PUBLIC_API_TAGS)
def delete_project(
    project_id: int,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> Response:
    project, _ = require_project(project_id, user.id, db_session, minimum="owner", lock=True)

    # Unlink chat sessions from this project
    for chat in project.chat_sessions:
        chat.project_id = None

    # Unlink many-to-many user files association (Project__UserFile)
    for uf in list(project.user_files):
        project.user_files.remove(uf)

    db_session.delete(project)
    db_session.commit()
    return Response(status_code=204)


@router.delete("/file/{file_id}", tags=PUBLIC_API_TAGS)
def delete_user_file(
    file_id: UUID,
    bg_tasks: BackgroundTasks,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> UserFileDeleteResult:
    """Delete a user file belonging to the current user.

    This will also remove any project associations for the file.
    """
    user_id = user.id
    user_file = (
        db_session.query(UserFile)
        .filter(UserFile.id == file_id, UserFile.user_id == user_id)
        .one_or_none()
    )
    if user_file is None:
        raise HTTPException(status_code=404, detail="File not found")

    # Check associations with projects and assistants (personas)
    project_names = [project.name for project in user_file.projects]
    assistant_names = [assistant.name for assistant in user_file.assistants]

    if len(project_names) > 0 or len(assistant_names) > 0:
        return UserFileDeleteResult(
            has_associations=True,
            project_names=project_names,
            assistant_names=assistant_names,
        )

    # No associations found; mark as DELETING and enqueue delete task
    user_file.status = UserFileStatus.DELETING
    db_session.commit()

    tenant_id = get_current_tenant_id()
    if DISABLE_VECTOR_DB:
        from nortpole.background.task_utils import drain_delete_loop

        bg_tasks.add_task(drain_delete_loop, tenant_id)
        logger.info("Queued in-process delete for user_file_id=%s", user_file.id)
    else:
        from nortpole.background.celery.versioned_apps.client import app as client_app

        task = client_app.send_task(
            NortPoleCeleryTask.DELETE_SINGLE_USER_FILE,
            kwargs={"user_file_id": str(user_file.id), "tenant_id": tenant_id},
            queue=NortPoleCeleryQueues.USER_FILE_DELETE,
            priority=NortPoleCeleryPriority.HIGH,
        )
        logger.info(
            "Triggered delete for user_file_id=%s with task_id=%s",
            user_file.id,
            task.id,
        )

    return UserFileDeleteResult(
        has_associations=False, project_names=[], assistant_names=[]
    )


@router.get("/file/{file_id}", response_model=UserFileSnapshot, tags=PUBLIC_API_TAGS)
def get_user_file(
    file_id: UUID,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> UserFileSnapshot:
    """Fetch a single user file by ID for the current user.

    Includes files in any status (including FAILED) to allow status polling.
    """
    user_id = user.id
    user_file = (
        db_session.query(UserFile)
        .filter(UserFile.id == file_id, UserFile.user_id == user_id)
        .filter(UserFile.status != UserFileStatus.DELETING)
        .one_or_none()
    )
    if user_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    return UserFileSnapshot.from_model(user_file)


class UserFileIdsRequest(BaseModel):
    file_ids: list[UUID]


@router.post(
    "/file/statuses", response_model=list[UserFileSnapshot], tags=PUBLIC_API_TAGS
)
def get_user_file_statuses(
    body: UserFileIdsRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[UserFileSnapshot]:
    """Fetch statuses for a set of user file IDs owned by the current user.

    Includes files in any status so the client can detect transitions to FAILED.
    """
    if not body.file_ids:
        return []

    user_id = user.id
    user_files = (
        db_session.query(UserFile)
        .filter(UserFile.user_id == user_id)
        .filter(UserFile.id.in_(body.file_ids))
        .filter(UserFile.status != UserFileStatus.DELETING)
        .all()
    )

    return [UserFileSnapshot.from_model(user_file) for user_file in user_files]


@router.post("/{project_id}/move_chat_session")
def move_chat_session(
    project_id: int,
    body: ChatSessionRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> Response:
    _, role = require_project(project_id, user.id, db_session, minimum="editor", lock=True)
    _set_chat_project(
        db_session, user.id, body.chat_session_id, project_id,
        private_only=role != "owner" or project_has_members(project_id, db_session),
    )
    db_session.commit()
    return Response(status_code=204)


@router.post("/remove_chat_session")
def remove_chat_session(
    body: ChatSessionRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> Response:
    _set_chat_project(db_session, user.id, body.chat_session_id, None)
    db_session.commit()
    return Response(status_code=204)


@router.get("/session/{chat_session_id}/token-count", response_model=TokenCountResponse)
def get_chat_session_project_token_count(
    chat_session_id: str,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TokenCountResponse:
    """Return sum of token_count for all user files in the project linked to the given chat session.

    If the chat session has no project, returns 0.
    """
    user_id = user.id
    chat_session = get_owned_chat_session(chat_session_id, user_id, db_session)
    if chat_session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")

    total_tokens = get_project_token_count(
        project_id=chat_session.project_id,
        user_id=user_id,
        db_session=db_session,
    )

    return TokenCountResponse(total_tokens=total_tokens)


@router.get("/session/{chat_session_id}/files", tags=PUBLIC_API_TAGS)
def get_chat_session_project_files(
    chat_session_id: str,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[UserFileSnapshot]:
    chat_session = get_owned_chat_session(chat_session_id, user.id, db_session)
    if chat_session is None or chat_session.deleted:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if chat_session.project_id is None:
        return []
    return get_files_in_project(chat_session.project_id, user, db_session)

@router.get("/{project_id}/token-count", response_model=TokenCountResponse)
def get_project_total_token_count(
    project_id: int,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> TokenCountResponse:
    """Return sum of token_count for all user files in the given project for the current user."""

    total_tokens = get_project_token_count(
        project_id=project_id, user_id=user.id, db_session=db_session
    )

    return TokenCountResponse(total_tokens=total_tokens)
