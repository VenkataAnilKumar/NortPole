"""Let a Chat agent propose scheduling without granting execution authority."""

from uuid import UUID

from nortpole.agents.tools import ToolInvocation, ToolOutcome
from nortpole.auth.permissions import has_global_permission
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.enums import Permission
from nortpole.db.models import User
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.llm.models import ToolDefinition, ToolResult
from nortpole.tools.interface import Tool, parse_tool_arguments
from nortpole.tools.models import CodeModeExposure, ToolCallException, ToolContext
from nortpole.utils.logger import setup_logger
from nortpole.work.workflow_schedules import api, proposals

logger = setup_logger()

CREATE_DESCRIPTION = (
    "Propose a recurring or one-time schedule for a task only when the user explicitly asks to schedule it. "
    "Ask first if the task, local time, cadence, or IANA time zone is missing or ambiguous. "
    "Time is 24-hour HH:MM. For weekly recurrence provide weekday (0 Monday to 6 Sunday). "
    "For monthly recurrence provide month_day (1 to 28). For once provide run_on as YYYY-MM-DD. "
    "For a workflow with specialized setup such as Expense Review, direct the user to the New schedule editor "
    "to choose its sources. The proposal requires the user to confirm it in Chat."
)
RUN_DESCRIPTION = (
    "Propose running one of the user's existing active schedules now, only on the user's explicit request. "
    "Provide the exact schedule name. It requires the user to confirm it in Chat and preserves its recurrence."
)


class ScheduleProposalTool(Tool):
    def __init__(self, user_id: UUID, chat_id: UUID, message_id: int, *, create: bool) -> None:
        self._user_id = user_id
        self._chat_id = chat_id
        self._message_id = message_id
        self._create = create

    @property
    def id(self) -> None:
        return None

    @property
    def name(self) -> str:
        return "propose_schedule" if self._create else "propose_schedule_run"

    @property
    def display_name(self) -> str:
        return "Propose schedule" if self._create else "Propose schedule run"

    @property
    def description(self) -> str:
        return CREATE_DESCRIPTION if self._create else RUN_DESCRIPTION

    @property
    def code_mode_exposure(self) -> CodeModeExposure:
        return CodeModeExposure.DIRECT

    def tool_definition(self) -> ToolDefinition:
        model = proposals.CreateScheduleArguments if self._create else proposals.RunScheduleArguments
        return ToolDefinition(name=self.name, description=self.description, parameters=model.model_json_schema())

    def _run(self, invocation: ToolInvocation, context: ToolContext) -> ToolOutcome:  # noqa: ARG002
        args = (
            parse_tool_arguments(proposals.CreateScheduleArguments, invocation.arguments)
            if self._create
            else parse_tool_arguments(proposals.RunScheduleArguments, invocation.arguments)
        )
        try:
            with get_session_with_current_tenant() as db:
                proposals.propose(db, db.get(User, self._user_id), self._chat_id, self._message_id, args)
        except NortPoleError as exc:
            raise ToolCallException(exc.detail, exc.detail) from exc
        return ToolResult(content="Schedule proposal ready in this Chat. Ask the user to review and confirm the proposal card. It has not been executed.")


def tools_for(user: User, chat_id: UUID, message_id: int, taken_names: set[str]) -> list[Tool]:
    if user.is_anonymous or not has_global_permission(user, Permission.BASIC_ACCESS):
        return []
    try:
        with get_session_with_current_tenant() as db:
            if not api._allowed(db, user):
                return []
    except Exception:
        logger.exception("Could not load scheduling access for Chat")
        return []
    available = [ScheduleProposalTool(user.id, chat_id, message_id, create=create) for create in (True, False)]
    return [tool for tool in available if tool.name not in taken_names]
