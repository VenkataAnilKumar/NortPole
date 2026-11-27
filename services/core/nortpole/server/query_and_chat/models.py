from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from nortpole.agents.models import RunStatus
from nortpole.configs.constants import DocumentSource, MessageType, SessionType
from nortpole.context.search.models import BaseFilters, SavedSearchDoc, SearchDoc, Tag
from nortpole.db.enums import ChatSessionSharedStatus
from nortpole.db.models import ChatSession
from nortpole.file_store.models import FileDescriptor
from nortpole.llm.models import GenerationRequestParams
from nortpole.llm.override_models import LLMOverride
from nortpole.server.query_and_chat.streaming_models import Packet, StreamingError

AUTO_PLACE_AFTER_LATEST_MESSAGE = -1


class MessageOrigin(str, Enum):
    """Origin of a chat message for telemetry tracking."""

    WEBAPP = "webapp"
    CHROME_EXTENSION = "chrome_extension"
    API = "api"
    SLACKBOT = "slackbot"
    WIDGET = "widget"
    DISCORDBOT = "discordbot"
    MOBILE = "mobile"
    UNKNOWN = "unknown"
    UNSET = "unset"


class MessageResponseIDInfo(BaseModel):
    model_display_name: str | None = None
    user_message_id: int | None
    reserved_assistant_message_id: int


class ResponseModelInfo(BaseModel):
    """The concrete model identified by the provider during generation."""

    response_model_name: str
    response_model_index: int


class ModelResponseSlot(BaseModel):
    """Pairs a reserved assistant message ID with its model display name."""

    message_id: int
    model_name: str


class MultiModelMessageResponseIDInfo(BaseModel):
    """Sent at the start of a multi-model streaming response.
    Contains the user message ID and one slot per model being run in parallel."""

    user_message_id: int | None
    responses: list[ModelResponseSlot]


class SourceTag(Tag):
    source: DocumentSource


class TagResponse(BaseModel):
    tags: list[SourceTag]


class UpdateChatSessionThreadRequest(BaseModel):
    # If not specified, use NortPole default persona
    chat_session_id: UUID
    new_alternate_model: str


class UpdateChatSessionTemperatureRequest(BaseModel):
    chat_session_id: UUID
    temperature_override: float


class UpdateChatSessionReasoningRequest(BaseModel):
    chat_session_id: UUID
    reasoning_effort_override: str | None = None


class ChatSessionCreationRequest(BaseModel):
    # If not specified, use NortPole default persona
    persona_id: int = 0
    description: str | None = None
    project_id: int | None = None
    # Start the session incognito. Refused with an error when incognito is
    # unavailable, never silently downgraded to an ordinary chat.
    incognito: bool = False
    # The id the client already used when uploading, so this session owns those
    # files. Ignored unless incognito.
    incognito_session_id: UUID | None = None


class ChatFeedbackRequest(BaseModel):
    chat_message_id: int
    is_positive: bool | None = None
    feedback_text: str | None = None
    predefined_feedback: str | None = None

    @model_validator(mode="after")
    def check_is_positive_or_feedback_text(self) -> "ChatFeedbackRequest":
        if self.is_positive is None and self.feedback_text is None:
            raise ValueError("Empty feedback received.")
        return self


# NOTE: This model is used for the core flow of the NortPole application, any changes to it should be reviewed and approved by an
# experienced team member. It is very important to 1. avoid bloat and 2. that this remains backwards compatible across versions.
class SearchEvidenceReference(BaseModel):
    document_id: str = Field(min_length=1, max_length=2048)
    chunk_id: int = Field(ge=0, le=2147483647)


class SearchEvidenceSelection(BaseModel):
    documents: list[SearchEvidenceReference] = Field(default_factory=list, max_length=5)
    library_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def check_selection(self) -> "SearchEvidenceSelection":
        if bool(self.documents) == (self.library_id is not None):
            raise ValueError("Select documents or one Knowledge library.")
        if len({item.document_id for item in self.documents}) != len(self.documents):
            raise ValueError("Select one result per document.")
        return self


class SendMessageRequest(BaseModel):
    message: str
    model_selection: Literal["auto", "manual"] | None = None
    skill_ids: list[UUID] | None = None

    llm_override: LLMOverride | None = None
    # For multi-model mode: up to 3 LLM overrides to run in parallel.
    # When provided with >1 entry, triggers multi-model streaming.
    llm_overrides: list[LLMOverride] | None = None

    allowed_tool_ids: list[int] | None = None
    preferred_tool_id: int | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_forced_action(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("forced_tool_id") is not None:
            raise ValueError(
                "forced_tool_id is no longer supported. Use preferred_tool_id for "
                "an optional Action preference; invocation is not guaranteed."
            )
        return data

    file_descriptors: list[FileDescriptor] = []

    internal_search_filters: BaseFilters | None = None
    ground_selected_knowledge: bool = False
    search_evidence: SearchEvidenceSelection | None = None
    # An empty title reviews the single unambiguous policy in the library.
    receipt_review_policy_title: str | None = Field(default=None, max_length=300)
    document_review: bool = False
    document_review_pack: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    document_review_previous_id: int | None = Field(default=None, ge=1)

    deep_research: bool = False

    # Headers to forward to MCP tool calls (e.g., user JWT token, user ID)
    # Example: {"Authorization": "Bearer <user_jwt>", "X-User-ID": "user123"}
    mcp_headers: dict[str, str] | None = None

    # Origin of the message for telemetry tracking
    origin: MessageOrigin = MessageOrigin.UNSET

    # Placement information for the message in the conversation tree:
    # - -1: auto-place after latest message in chain
    # - null: regeneration from root (first message)
    # - positive int: place after that specific parent message
    # NOTE: for regeneration, this is the only case currently where there is branching on the user message.
    # If the message of parent_message_id is a user message, the message will be ignored and it will use the
    # original user message for regeneration.
    parent_message_id: int | None = AUTO_PLACE_AFTER_LATEST_MESSAGE
    chat_session_id: UUID | None = None
    chat_session_info: ChatSessionCreationRequest | None = None

    # When True (default), returns StreamingResponse with SSE
    # When False, returns ChatFullResponse with complete data
    stream: bool = True

    # When False, disables citation generation:
    # - Citation markers like [1], [2] are removed from response text
    # - No CitationInfo packets are emitted during streaming
    include_citations: bool = True

    # Additional context injected into the LLM call but NOT stored in the DB
    # (not shown in chat history). Used e.g. by the Chrome extension to pass
    # the current tab URL when "Read this tab" is enabled.
    additional_context: str | None = None

    @model_validator(mode="after")
    def check_preference_supported(self) -> "SendMessageRequest":
        if self.deep_research and self.preferred_tool_id is not None:
            raise ValueError("preferred_tool_id is not supported with deep_research")
        return self

    @model_validator(mode="after")
    def check_search_evidence_inputs(self) -> "SendMessageRequest":
        if self.search_evidence and (
            self.deep_research or self.ground_selected_knowledge or self.document_review
        ):
            raise ValueError("Use the selected Search evidence in a standard Chat turn.")
        return self

    @model_validator(mode="after")
    def check_receipt_review_inputs(self) -> "SendMessageRequest":
        if self.receipt_review_policy_title is None:
            return self
        libraries = self.internal_search_filters.document_set if self.internal_search_filters else None
        if not self.ground_selected_knowledge or len(libraries or []) != 1:
            raise ValueError("Expense Review requires one Knowledge library.")
        if len(self.file_descriptors) != 1 or not (
            self.file_descriptors[0].get("name") or ""
        ).lower().endswith(".csv"):
            raise ValueError("Expense Review requires one CSV attachment.")
        if self.deep_research or self.llm_overrides:
            raise ValueError("Expense Review requires a single chat response.")
        return self

    @model_validator(mode="after")
    def check_document_review_inputs(self) -> "SendMessageRequest":
        if not self.document_review:
            if self.document_review_pack or self.document_review_previous_id is not None:
                raise ValueError("Select Document Review to use a pack or review a revision.")
            return self
        from nortpole.chat.document_review import DOCUMENT_EXTENSIONS

        if self.receipt_review_policy_title is not None or self.deep_research or self.llm_overrides or self.preferred_tool_id is not None:
            raise ValueError("Document Review requires a single chat response.")
        libraries = self.internal_search_filters.document_set if self.internal_search_filters else None
        if not self.ground_selected_knowledge or len(libraries or []) != 1:
            raise ValueError("Document Review requires one Knowledge library.")
        if len(self.file_descriptors) != 1 or not (
            self.file_descriptors[0].get("name") or ""
        ).lower().endswith(DOCUMENT_EXTENSIONS):
            raise ValueError("Document Review requires one PDF, DOCX, Markdown, or text attachment.")
        if self.document_review_previous_id is not None and (
            self.chat_session_id is None or self.parent_message_id != self.document_review_previous_id
        ):
            raise ValueError("A revised review must continue from the original review.")
        return self

    @model_validator(mode="after")
    def check_chat_session_id_or_info(self) -> "SendMessageRequest":
        # If neither is provided, default to creating a new chat session using the
        # default ChatSessionCreationRequest values.
        if self.chat_session_id is None and self.chat_session_info is None:
            return self.model_copy(
                update={"chat_session_info": ChatSessionCreationRequest()}
            )
        if self.chat_session_id is not None and self.chat_session_info is not None:
            raise ValueError(
                "Only one of chat_session_id or chat_session_info should be provided, not both."
            )
        return self


class ChatMessageIdentifier(BaseModel):
    message_id: int


class ChatRenameRequest(BaseModel):
    chat_session_id: UUID
    name: str | None = None


class ChatSessionUpdateRequest(BaseModel):
    sharing_status: ChatSessionSharedStatus


class DeleteAllSessionsRequest(BaseModel):
    session_type: SessionType


class RenameChatSessionResponse(BaseModel):
    new_name: str  # This is only really useful if the name is generated


class StopChatResponse(BaseModel):
    message: str


class ChatSessionDetails(BaseModel):
    id: UUID
    name: str | None
    persona_id: int | None = None
    time_created: str
    time_updated: str
    shared_status: ChatSessionSharedStatus
    current_alternate_model: str | None = None
    current_temperature_override: float | None = None
    current_reasoning_effort_override: str | None = None
    agent_preview_name: str | None = None

    @classmethod
    def from_model(cls, model: ChatSession) -> "ChatSessionDetails":
        return cls(
            id=model.id,
            name=model.description,
            persona_id=model.persona_id,
            time_created=model.time_created.isoformat(),
            time_updated=model.time_updated.isoformat(),
            shared_status=model.shared_status,
            current_alternate_model=model.current_alternate_model,
            current_temperature_override=model.temperature_override,
            current_reasoning_effort_override=model.reasoning_effort_override,
            agent_preview_name=model.agent_preview.name if model.agent_preview else None,
        )


class ChatSessionsResponse(BaseModel):
    sessions: list[ChatSessionDetails]
    has_more: bool = False


class ChatMessageDetail(BaseModel):
    chat_session_id: UUID | None = None
    message_id: int
    parent_message: int | None = None
    latest_child_message: int | None = None
    message: str
    reasoning_tokens: str | None = None
    message_type: MessageType
    context_docs: list[SavedSearchDoc] | None = None
    # Dict mapping citation number to document_id
    citations: dict[int, str] | None = None
    time_sent: datetime
    files: list[FileDescriptor]
    error: str | None = None
    error_info: StreamingError | None = None
    response_status: RunStatus | None = None
    current_feedback: str | None = None  # "like" | "dislike" | null
    processing_duration_seconds: float | None = None
    preferred_response_id: int | None = None
    model_display_name: str | None = None
    # Absent on messages written before this was captured.
    request_params: GenerationRequestParams | None = None

    def model_dump(  # ty: ignore[invalid-method-override]
        self, *args: list, **kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        initial_dict = super().model_dump(
            *args,
            mode="json",
            **kwargs,  # ty: ignore[invalid-argument-type]
        )
        initial_dict["time_sent"] = self.time_sent.isoformat()
        return initial_dict


class SetPreferredResponseRequest(BaseModel):
    user_message_id: int
    preferred_response_id: int


class CurrentStreamInfo(BaseModel):
    """Unfinished response available for stream reconnection."""

    stream_id: int


class ChatSessionProcessingStatus(BaseModel):
    is_processing: bool


class ChatSessionDetailResponse(BaseModel):
    chat_session_id: UUID
    description: str | None
    persona_id: int | None = None
    persona_name: str | None
    personal_icon_name: str | None
    messages: list[ChatMessageDetail]
    time_created: datetime
    shared_status: ChatSessionSharedStatus
    current_alternate_model: str | None
    current_temperature_override: float | None
    current_reasoning_effort_override: str | None
    deleted: bool = False
    owner_name: str | None = None
    packets: list[list[Packet]]
    # The buffer also retains interrupted work until its cache TTL expires.
    current_stream: CurrentStreamInfo | None = None
    # Readiness is independent of whether a stream can be replayed.
    is_processing: bool = False
    # True for sessions pinned to an incognito record mode, so a reload can
    # restore the incognito UI state.
    incognito: bool = False
    agent_preview_name: str | None = None
    agent_release_version: int | None = None
    # Set on a paged load when the current branch has messages before the page.
    has_older_messages: bool = False


class AdminSearchRequest(BaseModel):
    query: str
    filters: BaseFilters


class AdminSearchResponse(BaseModel):
    documents: list[SearchDoc]


class ChatSessionSummary(BaseModel):
    id: UUID
    name: str | None = None
    persona_id: int | None = None
    time_created: datetime
    shared_status: ChatSessionSharedStatus
    current_alternate_model: str | None = None
    current_temperature_override: float | None = None
    current_reasoning_effort_override: str | None = None


class ChatSessionGroup(BaseModel):
    title: str
    chats: list[ChatSessionSummary]


class ChatSearchResponse(BaseModel):
    groups: list[ChatSessionGroup]
    has_more: bool
    next_page: int | None = None
