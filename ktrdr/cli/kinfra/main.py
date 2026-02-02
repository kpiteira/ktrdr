"""kinfra CLI main entry point.

Provides the main Typer app for infrastructure commands including
sandbox management, deployment, and worktree operations.
"""

import typer

from ktrdr.cli.kinfra.deploy import deploy_app
from ktrdr.cli.kinfra.local_prod import local_prod_app
from ktrdr.cli.kinfra.sandbox import sandbox_app
from ktrdr.cli.kinfra.spec import spec_app
from ktrdr.cli.kinfra.worktrees import worktrees_app

app = typer.Typer(
    name="kinfra",
    help="KTRDR Infrastructure CLI - sandbox, deployment, and worktree management",
    no_args_is_help=True,
)


@app.callback()
def callback() -> None:
    """KTRDR Infrastructure CLI - sandbox, deployment, and worktree management."""
    pass


# Register subcommand groups
app.add_typer(
    sandbox_app, name="sandbox", help="Manage isolated development sandbox instances"
)
app.add_typer(
    local_prod_app,
    name="local-prod",
    help="Manage local-prod production-like environment",
)
app.add_typer(
    deploy_app,
    name="deploy",
    help="Deploy KTRDR services to pre-production environment",
)
app.add_typer(
    spec_app,
    name="spec",
    help="Create spec worktree for design work",
)
app.add_typer(
    worktrees_app,
    name="worktrees",
    help="List active worktrees with sandbox status",
)


def main() -> None:
    """Entry point for the kinfra CLI."""
    app()
