"""kinfra CLI main entry point.

Provides the main Typer app for infrastructure commands including
sandbox management, deployment, and worktree operations.
"""

import typer

from ktrdr.cli.kinfra.sandbox import sandbox_app

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


def main() -> None:
    """Entry point for the kinfra CLI."""
    app()
