"""A source that registers and then fails to import, for the loader test."""

from evolvxsi.configs.constants import DocumentSource
from evolvxsi.connectors.event_inbox.models import WebhookRequest, WebhookSourceSpec
from evolvxsi.connectors.event_inbox.source_registry import register_webhook_source
from evolvxsi.connectors.event_models import EventParseResult


def _parse(request: WebhookRequest) -> EventParseResult:  # noqa: ARG001
    return EventParseResult()


register_webhook_source(
    WebhookSourceSpec(
        source=DocumentSource.WEB,
        slug="half-registered",
        parser=_parse,
        verifier=None,
        allow_unsigned=True,
    )
)

raise RuntimeError("this source fails after registering")
