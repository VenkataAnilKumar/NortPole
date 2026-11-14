from typing import Annotated

from nortpole.configs.app_configs import INDEX_BATCH_SIZE
from nortpole.connectors.connector_config import ConnectorConfig
from nortpole.connectors.field_policy import FieldClass, FieldPolicy, ScopeInclude


class HighspotConnectorConfig(ConnectorConfig):
    spot_names: Annotated[
        list[str] | None,
        FieldPolicy(FieldClass.SCOPE, scope=ScopeInclude(empty_means_all=True)),
    ] = None
    batch_size: Annotated[int, FieldPolicy(FieldClass.COSMETIC)] = INDEX_BATCH_SIZE
