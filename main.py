"""Entry point for the CKAN open data MCP server.

Transport is selected with the FASTMCP_TRANSPORT environment variable:

- ``stdio`` (default): for local MCP clients such as opencode or Claude
  Desktop, which launch the server as a subprocess.
- ``http``: streamable HTTP on FASTMCP_HOST:FASTMCP_PORT (endpoint /mcp,
  health probe at /health). Recommended for production.
- ``sse``: legacy Server-Sent Events transport (endpoint /sse), kept for
  backward compatibility with older clients.

All logs are emitted as structured JSON (see helpers/logging_config.py).
"""

from __future__ import annotations

import logging
import os

from datagouv_mcp_tn.helpers.config import get_settings
from datagouv_mcp_tn.helpers.logging_config import (
    MAIN_LOGGER_NAME,
    configure_logging,
)
from datagouv_mcp_tn.server import mcp

SUPPORTED_TRANSPORTS = ("stdio", "http", "sse")

logger = logging.getLogger(MAIN_LOGGER_NAME)


def _get_run_kwargs(transport: str) -> dict:
    """Build kwargs for mcp.run() based on transport."""
    if transport == "stdio":
        return {"transport": "stdio"}

    host = os.getenv("FASTMCP_HOST", "127.0.0.1")
    port = int(os.getenv("FASTMCP_PORT", "8000"))
    return {
        "transport": transport,
        "host": host,
        "port": port,
    }


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    transport = os.getenv("FASTMCP_TRANSPORT", "stdio").strip().lower()

    if transport not in SUPPORTED_TRANSPORTS:
        raise ValueError(
            f"Unsupported FASTMCP_TRANSPORT {transport!r}. "
            f"Valid values: {', '.join(SUPPORTED_TRANSPORTS)}."
        )

    if transport != "stdio":
        logger.info(
            "Starting CKAN open data MCP server",
            extra={"transport": transport},
        )

    mcp.run(**_get_run_kwargs(transport))


if __name__ == "__main__":
    main()
