from typing import Annotated

from evolvxsi.connectors.connector_config import ConnectorConfig
from evolvxsi.connectors.field_policy import FieldClass, FieldPolicy, ScopeInclude


class GongConnectorConfig(ConnectorConfig):
    workspaces: Annotated[
        list[str] | None,
        FieldPolicy(FieldClass.SCOPE, scope=ScopeInclude(empty_means_all=True)),
    ] = None
    # Replaces speaker names in transcripts.
    hide_user_info: Annotated[bool, FieldPolicy(FieldClass.BEHAVIOR)] = False
