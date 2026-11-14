"""A source that registers at import, for the loader test.

Also the smallest complete example of the contract: one spec, registered
when the module is imported.
"""

from nortpole.configs.constants import DocumentSource
from nortpole.connectors.event_inbox.models import WebhookRequest, WebhookSourceSpec
from nortpole.connectors.event_inbox.source_registry import register_webhook_source
from nortpole.connectors.event_models import EventParseResult


def _parse(request: WebhookRequest) -> EventParseResult:  # noqa: ARG001
    return EventParseResult()


register_webhook_source(
    WebhookSourceSpec(
        source=DocumentSource.MOCK_CONNECTOR,
        slug="registering-source",
        parser=_parse,
        verifier=None,
        allow_unsigned=True,
    )
)
