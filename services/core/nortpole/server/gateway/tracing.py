"""Traces for LLM gateway calls."""

from nortpole.server.gateway.craft_session import CRAFT_SESSION_ID_CONTEXTVAR
from nortpole.tracing.flows import LLMFlow
from nortpole.tracing.framework.create import trace
from nortpole.tracing.framework.traces import Trace


def llm_gateway_trace(flow: LLMFlow, model: str) -> Trace:
    """One trace per gateway call.

    Tagged with the calling Craft session when one is bound to the request,
    so a session's LLM calls can be found by filtering on ``craft_session_id``.
    """
    metadata: dict[str, str] = {"flow": flow.value, "model": model}
    craft_session_id = CRAFT_SESSION_ID_CONTEXTVAR.get()
    if craft_session_id is not None:
        metadata["craft_session_id"] = craft_session_id
    return trace("llm_gateway", metadata=metadata)
