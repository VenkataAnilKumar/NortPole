from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

AgentPilotKind = Literal["research", "document-analysis", "reporting", "spreadsheet-analysis", "meeting-recap"]


class PackAgentSource(BaseModel, extra="forbid", frozen=True):
    pack_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    version: str = Field(pattern=r"^[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}$")
    agent_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class AgentPreviewDraft(BaseModel, extra="forbid"):
    name: str = Field(min_length=1, max_length=200)
    system_prompt: str = Field(max_length=100_000)
    task_prompt: str = Field(default="", max_length=100_000)
    replace_base_system_prompt: bool = False
    datetime_aware: bool = False
    document_set_ids: list[Annotated[int, Field(gt=0)]] = Field(
        default_factory=list, max_length=100
    )
    search_start_date: datetime | None = None
    model_configuration_id: int | None = Field(default=None, gt=0)
    pilot: AgentPilotKind | None = None
    pack_source: PackAgentSource | None = None

    @property
    def requires_knowledge(self) -> bool:
        return self.pilot in ("research", "document-analysis", "reporting")

    @field_validator("document_set_ids")
    @classmethod
    def order_library_ids(cls, ids: list[int]) -> list[int]:
        return sorted(set(ids))


class AgentPreview(AgentPreviewDraft, frozen=True):
    model_configuration_id: int = Field(gt=0)
