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
from ktrdr.cli.commands.backtest import backtest
from ktrdr.cli.commands.cancel import cancel
from ktrdr.cli.commands.follow import follow
from ktrdr.cli.commands.list_cmd import list_app
from ktrdr.cli.commands.migrate import migrate_cmd
from ktrdr.cli.commands.ops import ops
from ktrdr.cli.commands.research import research
from ktrdr.cli.commands.resume import resume
from ktrdr.cli.commands.show import show_app
from ktrdr.cli.commands.status import status
from ktrdr.cli.commands.train import train
from ktrdr.cli.commands.validate import validate_cmd
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


# Register M2 top-level commands
app.command()(train)
app.command()(backtest)
app.command()(research)
app.command()(status)
app.command()(follow)
app.command()(ops)
app.command()(cancel)
app.command()(resume)

# Register M3 commands
app.add_typer(list_app)  # ktrdr list strategies/models/checkpoints
app.add_typer(show_app)  # ktrdr show data/features
app.command("validate")(validate_cmd)  # ktrdr validate <name|path>
app.command("migrate")(migrate_cmd)  # ktrdr migrate <path>


if __name__ == "__main__":
    app()
