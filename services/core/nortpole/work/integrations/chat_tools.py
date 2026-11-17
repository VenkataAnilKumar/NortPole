"""Installed integrations as chat tools (decision 0008).

A person's assistant in chat can use the integrations that person installed and connected, and only the **read** actions:
a write is never offered to the model here, because chat has no step where a person approves one call. Each read action
becomes one tool the model can call with the parameters meant for it; parameters only the person may set (their settings)
never appear in the tool. A call goes through `service.call`, so the order of checks is the same as everywhere else
(exists, not blocked by policy, installed, connected), it runs with the person's own account, and it leaves one audit row.
The tool carries no database row, so the administrator's tool catalog does not list it: the Integrations policy governs it.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy import select

from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.models import User
from nortpole.llm.models import ToolDefinition, ToolResult
from nortpole.tools.interface import Tool
from nortpole.tools.models import CodeModeExposure, ToolCallException, ToolContext
from nortpole.utils.logger import setup_logger
from nortpole.agents.tools import ToolInvocation, ToolOutcome
from nortpole.work.integrations import executor, policy, registry, service
from nortpole.work.integrations.manifest import Action, Integration, Param
from nortpole.work.integrations.models import NortPoleIntegrationUse

logger = setup_logger()

MAX_TOOLS = 40
MAX_RESULT_CHARS = 20_000
_NAME_UNSAFE = re.compile(r"[^a-zA-Z0-9_]")


def tool_name(integration: Integration, action: Action) -> str:
    return _NAME_UNSAFE.sub("_", f"{integration.id}_{action.id}")[:64]


def _property(param: Param) -> dict[str, Any]:
    prop: dict[str, Any] = {"description": param.description}
    if param.type == "object":
        prop["type"] = "object"
        prop["additionalProperties"] = True
        return prop
    prop["type"] = param.type
    if param.enum is not None:
        prop["enum"] = list(param.enum)
    if param.type == "integer":
        if param.minimum is not None:
            prop["minimum"] = param.minimum
        if param.maximum is not None:
            prop["maximum"] = param.maximum
    if param.type == "string":
        prop["maxLength"] = param.max_length
    if param.default is not None:
        prop["description"] = f"{param.description} (default {param.default})"
    return prop


def parameters_schema(action: Action) -> dict[str, Any]:
    """The JSON Schema of what the model may give: only parameters that are not the person's alone."""
    offered = {name: p for name, p in action.params.items() if p.fill != "user"}
    return {
        "type": "object",
        "properties": {name: _property(p) for name, p in offered.items()},
        "required": [name for name, p in offered.items() if p.required],
        "additionalProperties": False,
    }


class IntegrationChatTool(Tool):
    """One read action of one installed integration, offered to one person's chat."""

    def __init__(self, user_id: uuid.UUID, integration: Integration, action: Action, *, transport: executor.Transport | None = None) -> None:
        self._user_id = user_id
        self._integration = integration
        self._action = action
        self._transport = transport
        self._name = tool_name(integration, action)

    @property
    def id(self) -> None:
        return None

    @property
    def code_mode_exposure(self) -> CodeModeExposure:
        return CodeModeExposure.DEFERRED

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return (
            f"{self._integration.name}: {self._action.name}. {self._action.description} "
            f"Reads from {self._integration.name} with the person's own account; it never changes anything."
        )

    @property
    def display_name(self) -> str:
        return f"{self._integration.name}: {self._action.name}"

    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(name=self._name, description=self.description, parameters=parameters_schema(self._action))

    def _run(self, invocation: ToolInvocation, context: ToolContext) -> ToolOutcome:  # noqa: ARG002
        try:
            with get_session_with_current_tenant() as db:
                user = db.get(User, self._user_id)
                if user is None:
                    raise service.IntegrationAccessError("not_installed", "This person is not available.")
                out = service.call(db, user, self._integration.id, self._action.id, model_params=dict(invocation.arguments), transport=self._transport)
        except (service.IntegrationAccessError, executor.IntegrationCallError) as exc:
            # The message is written to be safe to show: it never holds a credential or the service's own text.
            raise ToolCallException(str(exc), f"{self._integration.name} could not be read: {exc}") from exc
        text = json.dumps(out, ensure_ascii=False, default=str)
        if len(text) > MAX_RESULT_CHARS:
            text = text[:MAX_RESULT_CHARS] + "\n[truncated: the result was longer than this tool returns]"
        return ToolResult(content=text)


def chat_tools_for(user: User, taken_names: set[str] | None = None, *, transport: executor.Transport | None = None) -> list[Tool]:
    """The tools for this person: read actions of integrations they installed, are not blocked, and (when an account is
    needed) connected. A fault here never stops a chat; it only means fewer tools."""
    if getattr(user, "is_anonymous", False):
        return []
    taken = set(taken_names or ())
    tools: list[Tool] = []
    try:
        config = policy.load()
        with get_session_with_current_tenant() as db:
            uses = db.scalars(select(NortPoleIntegrationUse).where(NortPoleIntegrationUse.user_id == user.id)).all()
            rows = [(u.integration_id, u.credential is not None) for u in uses]
        for integration_id, connected in sorted(rows):
            integration = registry.get(integration_id)
            if integration is None or policy.resolve(integration, config) == "blocked":
                continue
            if integration.auth.mode != "none" and not connected:
                continue
            for action in integration.actions:
                name = tool_name(integration, action)
                if action.effect != "read" or name in taken:
                    continue
                if len(tools) >= MAX_TOOLS:
                    logger.warning("Integration chat tools capped at %s for one person", MAX_TOOLS)
                    return tools
                taken.add(name)
                tools.append(IntegrationChatTool(user.id, integration, action, transport=transport))
    except Exception:  # noqa: BLE001 - chat must work without them
        logger.exception("Could not build the integration tools for chat")
        return []
    return tools
