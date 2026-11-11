from collections.abc import Callable
from typing import cast

from evolvxsi.access.models import ExternalAccess
from evolvxsi.connectors.models import BasicExpertInfo
from evolvxsi.connectors.slack.models import ChannelType
from evolvxsi.connectors.slack.source_operations import SlackSourceOperations
from evolvxsi.utils.variable_functionality import (
    fetch_versioned_implementation,
    global_version,
)


def get_channel_access(
    slack_client: SlackSourceOperations,
    channel: ChannelType,
    user_cache: dict[str, BasicExpertInfo | None],
    team_id_to_user_emails: dict[str, set[str]] | None = None,
) -> ExternalAccess | None:
    """Get channel access permissions for a Slack channel. EE only.

    ``team_id_to_user_emails`` (Grid only): when provided, public channels
    are scoped to the union of the workspaces they're shared into instead of
    being marked org-public.
    """
    if not global_version.is_ee_version():
        return None

    ee_get_channel_access = cast(
        Callable[
            [
                SlackSourceOperations,
                ChannelType,
                dict[str, BasicExpertInfo | None],
                dict[str, set[str]] | None,
            ],
            ExternalAccess,
        ],
        fetch_versioned_implementation(
            "evolvxsi.external_permissions.slack.channel_access", "get_channel_access"
        ),
    )

    return ee_get_channel_access(
        slack_client, channel, user_cache, team_id_to_user_emails
    )
