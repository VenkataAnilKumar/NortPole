from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from evolvxsi.context.search.models import SearchDoc
from evolvxsi.file_store.models import FileToolMetadata
from evolvxsi.llm.models import ReasoningEffort
from evolvxsi.tools.file_snapshot import SavedContextFiles
from evolvxsi.tools.tool_implementations.search.models import SearchContext


class ResearchConfiguration(BaseModel):
    """Settings needed to rebuild a research agent for another run."""

    language_section: str
    reasoning_effort: ReasoningEffort


class ResearchAgentCallResult(BaseModel):
    type: Literal["research_result"] = "research_result"
    intermediate_report: str
    citation_mapping: dict[int, SearchDoc]


class ResearchPhase(str, Enum):
    CLARIFICATION = "clarification"
    PLANNING = "planning"
    RESEARCH = "research"
    REPORT = "report"


class ResearchMessageMetadata(BaseModel):
    """Research phase and source references attached to a generated message."""

    phase: ResearchPhase
    is_intermediate: bool = False
    is_reasoning_model: bool
    sources: dict[int, SearchDoc] = Field(default_factory=dict)
    elapsed_seconds: float = 0


class ResearchTask(BaseModel):
    task: str


class DeepResearchFeatureState(BaseModel):
    kind: Literal["deep_research.state.v1"] = "deep_research.state.v1"
    language_section: str
    reasoning_effort: ReasoningEffort
    file_metadata: dict[str, FileToolMetadata] | None
    skip_clarification: bool
    request_context: str | None = None
    context_files: SavedContextFiles | None = None
    elapsed_seconds: float
    citation_mapping: dict[int, SearchDoc]


class ResearchFeatureState(BaseModel):
    kind: Literal["research.state.v1"] = "research.state.v1"
    elapsed_seconds: float = 0.0
    configuration: ResearchConfiguration
    citation_sources: dict[int, SearchDoc]
    citation_mapping: dict[int, str]
    search_context: SearchContext
