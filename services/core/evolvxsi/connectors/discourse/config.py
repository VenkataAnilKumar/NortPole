from typing import Annotated

from evolvxsi.configs.app_configs import INDEX_BATCH_SIZE
from evolvxsi.connectors.connector_config import BaseUrlCredentialBinding, ConnectorConfig
from evolvxsi.connectors.field_policy import FieldClass, FieldPolicy, ScopeInclude


class DiscourseConnectorConfig(BaseUrlCredentialBinding, ConnectorConfig):
    categories: Annotated[
        list[str] | None,
        FieldPolicy(FieldClass.SCOPE, scope=ScopeInclude(empty_means_all=True)),
    ] = None
    batch_size: Annotated[int, FieldPolicy(FieldClass.COSMETIC)] = INDEX_BATCH_SIZE
