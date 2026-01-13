"""CLI app entry point.

Provides the main Typer app with global flags for output format,
verbosity, and API URL configuration. State is stored in Typer
context for commands to access.

This is the new CLI entry point that will eventually replace the
legacy entry point in __main__.py.
"""

from typing import Optional

import typer

from ktrdr.cli.commands import normalize_api_url
from ktrdr.cli.commands.train import train
from ktrdr.cli.sandbox_detect import resolve_api_url
from ktrdr.cli.state import CLIState

app = typer.Typer(
    name="ktrdr",
    help="KTRDR - Trading analysis and automation tool.",
    add_completion=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format for scripting",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show debug output and startup logs",
    ),
    url: Optional[str] = typer.Option(
        None,
        "--url",
        "-u",
        help="API URL (overrides auto-detection)",
        envvar="KTRDR_API_URL",
    ),
    port: Optional[int] = typer.Option(
        None,
        "--port",
        "-p",
        help="API port on localhost",
    ),
) -> None:
    """KTRDR CLI - workflow-oriented trading automation."""
    # Resolve URL using priority: explicit_url > explicit_port > .env.sandbox > default
    resolved_url = resolve_api_url(explicit_url=url, explicit_port=port)

    # Normalize URL (add protocol if missing, add default port if missing)
    normalized_url = normalize_api_url(resolved_url)

    # Create immutable state and store in context
    state = CLIState(
        json_mode=json_output,
        verbose=verbose,
        api_url=normalized_url,
    )
    ctx.obj = state


# Register commands
app.command()(train)


if __name__ == "__main__":
    app()
