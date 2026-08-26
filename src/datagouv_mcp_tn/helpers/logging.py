"""Re-export logging utilities from the canonical module.

All project code should import from this module or directly from
``logging_config``. This file exists for backward compatibility.
"""

from datagouv_mcp_tn.helpers.logging_config import MAIN_LOGGER_NAME, log_tool, logger

__all__ = ["MAIN_LOGGER_NAME", "log_tool", "logger"]
