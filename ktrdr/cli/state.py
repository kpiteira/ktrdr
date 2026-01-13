"""CLI state management.

Provides a typed, immutable state object that holds CLI-wide configuration.
This replaces the global `_cli_state` dict with a more explicit pattern where
state is passed through Typer context to commands.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CLIState:
    """Immutable state object for CLI-wide configuration.

    Populated by the root Typer callback and stored in `ctx.obj` for
    commands to access. Using a frozen dataclass ensures state cannot
    be accidentally modified during command execution.

    Attributes:
        json_mode: If True, output JSON for scripting. If False, human-readable output.
        verbose: If True, show debug output and startup logs.
        api_url: Target API URL (e.g., "http://localhost:8000").
    """

    json_mode: bool = False
    verbose: bool = False
    api_url: str = "http://localhost:8000"
