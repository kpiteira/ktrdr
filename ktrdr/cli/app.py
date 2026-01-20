"""CLI app entry point.

Provides the main Typer app with global flags for output format,
verbosity, and API URL configuration. State is stored in Typer
context for commands to access.

PERFORMANCE NOTE: This module uses lazy imports for heavy command modules.
Subgroup apps (sandbox, ib, deploy, data, checkpoints) are imported lazily
using the __getattr__ pattern in their respective modules. This keeps CLI
startup fast (<100ms) while still providing all commands.
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


def _register_subgroups() -> None:
    """Register preserved subgroups (lazy loading to maintain fast startup).

    These subgroups contain heavy imports (pandas for data, ssh for deploy, etc).
    They are registered lazily when this function is called from __init__.py,
    after the fast app import path has been satisfied.
    """
    from ktrdr.cli.checkpoints_commands import checkpoints_app
    from ktrdr.cli.data_commands import data_app
    from ktrdr.cli.deploy_commands import deploy_app
    from ktrdr.cli.ib_commands import ib_app
    from ktrdr.cli.local_prod import local_prod_app
    from ktrdr.cli.sandbox import sandbox_app

    app.add_typer(
        checkpoints_app, name="checkpoints", help="Checkpoint management commands"
    )
    app.add_typer(data_app, name="data", help="Data management commands")
    app.add_typer(ib_app, name="ib", help="Interactive Brokers integration commands")
    app.add_typer(
        deploy_app, name="deploy", help="Deploy KTRDR services to pre-production"
    )
    app.add_typer(
        local_prod_app,
        name="local-prod",
        help="Manage local-prod production-like environment",
    )
    app.add_typer(
        sandbox_app,
        name="sandbox",
        help="Manage isolated development sandbox instances",
    )


# Track if subgroups have been registered
_subgroups_registered = False


def get_app_with_subgroups():
    """Get the app with all subgroups registered.

    This is called from __init__.py to ensure subgroups are registered
    when the CLI is actually run. For fast import tests, import app directly.
    """
    global _subgroups_registered
    if not _subgroups_registered:
        _register_subgroups()
        _subgroups_registered = True
    return app


if __name__ == "__main__":
    get_app_with_subgroups()()
