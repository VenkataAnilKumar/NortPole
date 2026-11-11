from typing import Annotated

from evolvxsi.connectors.connector_config import ConnectorConfig
from evolvxsi.connectors.field_policy import FieldClass, FieldPolicy, ScopeInclude


class BraintrustConnectorConfig(ConnectorConfig):
    project_name: Annotated[
        str | None,
        FieldPolicy(
            FieldClass.SCOPE,
            scope=ScopeInclude(empty_means_all=True, split_on_commas=False),
        ),
    ] = None
    # Decides whether an experiment document includes its per-case table.
    experiment_row_lookback_days: Annotated[
        int | None, FieldPolicy(FieldClass.BEHAVIOR)
    ] = None
