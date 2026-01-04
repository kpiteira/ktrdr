"""
CLI commands for KTRDR application.

This module defines the main CLI application entry point.
All specific commands have been migrated to dedicated subcommand modules:
- data_commands.py - Data management commands
- operations_commands.py - Operation management commands
- indicator_commands.py - Technical indicator commands
- ib_commands.py - Interactive Brokers integration commands
- model_commands.py - Neural network model management commands
- strategy_commands.py - Trading strategy management commands
- fuzzy_commands.py - Fuzzy logic operations commands
"""

from typing import Optional
from urllib.parse import urlparse

import typer
from rich.console import Console

from ktrdr import get_logger
from ktrdr.cli.sandbox_detect import resolve_api_url

# Default API port
DEFAULT_API_PORT = 8000

# Global CLI state for URL override
# This allows --url at root level to affect all subcommands
_cli_state: dict[str, Optional[str]] = {"api_url": None}


def normalize_api_url(url: str) -> str:
    """
    Normalize an API URL by adding protocol and port if missing.

    Args:
        url: Raw URL (e.g., "backend.example.com" or "http://backend.example.com:8000")

    Returns:
        Normalized URL with protocol and port (e.g., "http://backend.example.com:8000")
    """
    if not url:
        return url

    # Add http:// if no protocol specified
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"

    # Parse and add default port if missing
    parsed = urlparse(url)
    if parsed.port is None:
        # Reconstruct with default port
        netloc = f"{parsed.hostname}:{DEFAULT_API_PORT}"
        url = f"{parsed.scheme}://{netloc}{parsed.path}"

    return url.rstrip("/")


def get_api_url_override() -> Optional[str]:
    """Get the global API URL override if set via --url (already normalized)."""
    return _cli_state["api_url"]


def get_effective_api_url() -> str:
    """
    Get the effective API URL for display in error messages.

    Returns the --url override if set, otherwise the default localhost URL.
    """
    from ktrdr.config.host_services import get_api_base_url

    return _cli_state["api_url"] or get_api_base_url()


# Create a Typer application with help text
cli_app = typer.Typer(
    name="ktrdr",
    help="KTRDR - Trading analysis and automation tool",
    add_completion=False,
)

# Get module logger
logger = get_logger(__name__)

# Create a rich console for formatted output
console = Console()
error_console = Console(stderr=True)


@cli_app.callback()
def main(
    url: Optional[str] = typer.Option(
        None,
        "--url",
        "-u",
        help="API URL (e.g., http://backend.example.com:8000). Overrides auto-detection.",
        envvar="KTRDR_API_URL",
    ),
    port: Optional[int] = typer.Option(
        None,
        "--port",
        "-p",
        help="API port on localhost. Overrides auto-detection. (e.g., -p 8001)",
    ),
):
    """KTRDR - Trading analysis and automation tool."""
    # Use resolve_api_url for priority-based resolution:
    # 1. --url flag (explicit full URL)
    # 2. --port flag (localhost with specified port)
    # 3. .env.sandbox file (auto-detect from current directory tree)
    # 4. Default: http://localhost:8000
    resolved_url = resolve_api_url(
        explicit_url=url,
        explicit_port=port,
    )

    # Only set state if different from default (to avoid unnecessary reconfiguration)
    if resolved_url != "http://localhost:8000":
        normalized_url = normalize_api_url(resolved_url)
        _cli_state["api_url"] = normalized_url

        # Reconfigure telemetry to send traces to the same host as the API
        # This enables distributed tracing when targeting remote servers
        from ktrdr.cli import reconfigure_telemetry_for_url

        reconfigure_telemetry_for_url(normalized_url)


# All commands have been migrated to subcommand modules
# This file now only contains the main CLI app definition
# Individual commands are registered in __init__.py via add_typer()
