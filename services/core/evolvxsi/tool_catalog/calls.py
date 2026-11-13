"""A log of every call to an outside tool (MCP or OpenAPI): which tool, which server host, for whom, how long, how big
the arguments were and whether it returned or raised. Never the arguments or the result: they can hold anyone's data."""

from __future__ import annotations

import json
import time
from typing import Any, Callable
from urllib.parse import urlparse

from evolvxsi.utils.logger import setup_logger

logger = setup_logger()
OUTSIDE_CLASSES = ("MCPTool", "CustomTool")


def is_outside(tool: Any) -> bool:
    return type(tool).__name__ in OUTSIDE_CLASSES


def logged(tool: Any, arguments: Any, call: Callable[[], Any]) -> Any:
    start = time.monotonic()
    outcome = "returned"
    try:
        return call()
    except BaseException:
        outcome = "raised"
        raise
    finally:
        try:
            from evolvxsi.route_policy.audit import record_audit
            from evolvxsi.utils.audit import AuditAction, AuditOutcome

            server = getattr(tool, "mcp_server", None)
            host = urlparse(server.server_url).hostname if server is not None else None
            try:
                size = len(json.dumps(arguments, default=str))
            except Exception:  # noqa: BLE001
                size = -1
            record_audit(
                AuditAction.TOOL_CALL, AuditOutcome.SUCCESS if outcome == "returned" else AuditOutcome.FAILURE, actor=None,
                summary=f"Outside tool {getattr(tool, 'name', type(tool).__name__)} {outcome}" + (f" ({host})" if host else ""),
                details={"tool_id": getattr(tool, "id", None), "host": host, "user_id": str(getattr(tool, "_user_id", "") or "") or None,
                         "argument_bytes": size, "ms": int((time.monotonic() - start) * 1000), "outcome": outcome},
                resource_type="tool", resource_id=getattr(tool, "id", None),
            )
        except Exception:  # noqa: BLE001 - logging must never change what the tool returned
            logger.warning("outside tool call was not logged", exc_info=True)
