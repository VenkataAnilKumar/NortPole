from typing import Annotated, ClassVar

from evolvxsi.configs.app_configs import INDEX_BATCH_SIZE
from evolvxsi.connectors.connector_config import ConnectorConfig, CredentialBinding
from evolvxsi.connectors.field_policy import FieldClass, FieldPolicy


class ZulipCredentialBinding(CredentialBinding):
    site_url_fields: ClassVar[frozenset[str]] = frozenset({"realm_url"})

    # The connector stores it but does not use it.
    realm_name: Annotated[str, FieldPolicy(FieldClass.COSMETIC)]
    # Used only to build message links; the zuliprc credential picks the server.
    realm_url: Annotated[str, FieldPolicy(FieldClass.BEHAVIOR)]


class ZulipConnectorConfig(ZulipCredentialBinding, ConnectorConfig):
    batch_size: Annotated[int, FieldPolicy(FieldClass.COSMETIC)] = INDEX_BATCH_SIZE
