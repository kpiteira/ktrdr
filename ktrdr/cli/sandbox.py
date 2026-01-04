"""Sandbox management CLI commands.

This module provides commands for managing isolated development sandbox instances.
Each sandbox runs in its own git worktree with isolated Docker containers.

Commands will be implemented in subsequent tasks:
- create: Create a new sandbox instance
- init: Initialize current directory as sandbox
- up: Start the sandbox stack
- down: Stop the sandbox stack
- destroy: Remove sandbox instance completely
- list: List all sandbox instances
- status: Show detailed status (M3)
- logs: View container logs (future)
"""

import typer
from rich.console import Console

sandbox_app = typer.Typer(
    name="sandbox",
    help="Manage isolated development sandbox instances",
    no_args_is_help=True,
)

console = Console()
error_console = Console(stderr=True)
