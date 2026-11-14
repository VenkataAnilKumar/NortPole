"""Entry point for MCP server - HTTP POST transport with API key auth."""

import uvicorn

from nortpole.configs.app_configs import (
    MCP_SERVER_ENABLED,
    MCP_SERVER_HOST,
    MCP_SERVER_PORT,
)
from nortpole.tracing.setup import setup_tracing
from nortpole.utils.logger import setup_logger
from nortpole.utils.variable_functionality import set_is_ee_if_available

logger = setup_logger()


def main() -> None:
    """Run the MCP server."""
    if not MCP_SERVER_ENABLED:
        logger.info("MCP server is disabled (MCP_SERVER_ENABLED=false)")
        return

    set_is_ee_if_available()
    setup_tracing()
    logger.info("Starting MCP server on %s:%s", MCP_SERVER_HOST, MCP_SERVER_PORT)

    from nortpole.mcp_server.api import mcp_app

    uvicorn.run(
        mcp_app,
        host=MCP_SERVER_HOST,
        port=MCP_SERVER_PORT,
        log_config=None,
    )


if __name__ == "__main__":
    main()
