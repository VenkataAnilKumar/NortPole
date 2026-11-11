from typing import Annotated

from evolvxsi.connectors.connector_config import ConnectorConfig
from evolvxsi.connectors.field_policy import FieldClass, FieldPolicy


class MockConnectorConfig(ConnectorConfig):
    # The mock server returns the documents.
    mock_server_host: Annotated[str, FieldPolicy(FieldClass.IDENTITY)]
    mock_server_port: Annotated[int, FieldPolicy(FieldClass.IDENTITY)]
