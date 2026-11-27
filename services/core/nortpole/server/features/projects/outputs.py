import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nortpole.auth.permissions import require_permission
from nortpole.db.engine.sql_engine import get_session
from nortpole.db.enums import Permission
from nortpole.db.models import ProjectOutput, User
from nortpole.db.project_access import require_project

router = APIRouter()
OutputKind = Literal["document", "presentation", "spreadsheet"]
OutputName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
]
Cell = Annotated[str, StringConstraints(max_length=32767)]
Row = Annotated[list[Cell], Field(min_length=1, max_length=100)]


class OutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DocumentPayload(OutputModel):
    body: str = Field(max_length=100_000)


class ChartImage(OutputModel):
    data: str = Field(
        pattern=r"^data:image/png;base64,[A-Za-z0-9+/]+={0,2}$", max_length=14_000_000
    )
    name: str = Field(max_length=255)
    width: int = Field(gt=0, le=16384)
    height: int = Field(gt=0, le=16384)


class Slide(OutputModel):
    kind: Literal["title", "points", "chart"]
    title: str = Field(max_length=150)
    text: str = Field(max_length=2_000)
    image: ChartImage | None = None


class PresentationPayload(OutputModel):
    slides: list[Slide] = Field(min_length=1, max_length=24)


class SpreadsheetPayload(OutputModel):
    rows: list[Row] = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def check_grid(self) -> "SpreadsheetPayload":
        width = len(self.rows[0])
        if len(self.rows) * width > 5_000 or any(
            len(row) != width for row in self.rows
        ):
            raise ValueError("The sheet must be rectangular with up to 5,000 cells")
        return self


class Document(OutputModel):
    kind: Literal["document"]
    payload: DocumentPayload


class Presentation(OutputModel):
    kind: Literal["presentation"]
    payload: PresentationPayload


class Spreadsheet(OutputModel):
    kind: Literal["spreadsheet"]
    payload: SpreadsheetPayload


Artifact = Annotated[Document | Presentation | Spreadsheet, Field(discriminator="kind")]


class SaveOutput(OutputModel):
    name: OutputName
    version: int = Field(ge=0)
    artifact: Artifact


class OutputSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    kind: OutputKind
    version: int
    updated_at: datetime.datetime


class OutputDetail(OutputSummary):
    artifact: Artifact


def _output(db: Session, project_id: int, output_id: UUID) -> ProjectOutput | None:
    return db.scalar(
        select(ProjectOutput).where(
            ProjectOutput.project_id == project_id, ProjectOutput.id == output_id
        )
    )


@router.get("/{project_id}/outputs")
def list_outputs(
    project_id: int,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db: Session = Depends(get_session),
) -> list[OutputSummary]:
    require_project(project_id, user.id, db)
    fields = [
        ProjectOutput.id,
        ProjectOutput.name,
        ProjectOutput.kind,
        ProjectOutput.version,
        ProjectOutput.updated_at,
    ]
    stmt = (
        select(*fields)
        .where(ProjectOutput.project_id == project_id)
        .order_by(ProjectOutput.updated_at.desc())
    )
    return [OutputSummary.model_validate(row) for row in db.execute(stmt)]


@router.get("/{project_id}/outputs/{output_id}")
def get_output(
    project_id: int,
    output_id: UUID,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db: Session = Depends(get_session),
) -> OutputDetail:
    require_project(project_id, user.id, db)
    item = _output(db, project_id, output_id)
    if item is None:
        raise HTTPException(404, "Output not found")
    return OutputDetail(
        **OutputSummary.model_validate(item).model_dump(),
        artifact={"kind": item.kind, "payload": item.payload},
    )


@router.put("/{project_id}/outputs/{output_id}")
def save_output(
    project_id: int,
    output_id: UUID,
    body: SaveOutput,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db: Session = Depends(get_session),
) -> OutputSummary:
    encoded = body.model_dump_json()
    if len(encoded.encode()) > 16_000_000:
        raise HTTPException(413, "Output is too large to save")
    # JSONB cannot store U+0000. Check actual string values before writing.
    if "\x00" in body.name or any(
        "\x00" in text for text in _text_values(body.artifact)
    ):
        raise HTTPException(422, "Output contains an unsupported character")
    require_project(project_id, user.id, db, minimum="editor", lock=True)
    item = _output(db, project_id, output_id)
    kind = body.artifact.kind
    payload = body.artifact.payload.model_dump(exclude_none=True)
    if item is None:
        if body.version != 0:
            raise HTTPException(409, "Output has changed")
        count = db.scalar(
            select(func.count())
            .select_from(ProjectOutput)
            .where(ProjectOutput.project_id == project_id)
        )
        if count is not None and count >= 200:
            raise HTTPException(409, "This project already has 200 outputs")
        item = ProjectOutput(id=output_id, project_id=project_id, kind=kind, version=0)
        db.add(item)
    elif item.kind == kind and item.name == body.name and item.payload == payload:
        return OutputSummary.model_validate(item)
    elif item.kind != kind or item.version != body.version:
        raise HTTPException(409, "Output has changed")
    item.name = body.name
    item.payload = payload
    item.version += 1
    item.updated_at = datetime.datetime.now(datetime.timezone.utc)
    result = OutputSummary.model_validate(item)
    db.commit()
    return result


def _text_values(artifact: Artifact):
    if isinstance(artifact, Document):
        yield artifact.payload.body
    elif isinstance(artifact, Presentation):
        for slide in artifact.payload.slides:
            yield slide.title
            yield slide.text
            if slide.image:
                yield slide.image.name
    else:
        for row in artifact.payload.rows:
            yield from row
