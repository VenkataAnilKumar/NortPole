from typing import Annotated

from nortpole.configs.app_configs import INDEX_BATCH_SIZE
from nortpole.connectors.connector_config import ConnectorConfig
from nortpole.connectors.field_policy import FieldClass, FieldPolicy


class GitbookConnectorConfig(ConnectorConfig):
    # Document ids contain the space id.
    space_id: Annotated[str, FieldPolicy(FieldClass.IDENTITY)]
    batch_size: Annotated[int, FieldPolicy(FieldClass.COSMETIC)] = INDEX_BATCH_SIZE
