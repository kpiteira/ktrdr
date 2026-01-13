"""CLI command implementations.

This package contains the new workflow-oriented CLI commands.
It also re-exports legacy utilities from _commands_base.py for
backward compatibility.
"""

# Re-export utilities from legacy commands module for backward compatibility
from ktrdr.cli._commands_base import (
    DEFAULT_API_PORT,
    cli_app,
    console,
    error_console,
    get_api_url_override,
    get_effective_api_url,
    normalize_api_url,
)

__all__ = [
    "DEFAULT_API_PORT",
    "cli_app",
    "console",
    "error_console",
    "get_api_url_override",
    "get_effective_api_url",
    "normalize_api_url",
]
