"""
Agent research system commands for the KTRDR CLI.

This module contains CLI commands for managing and monitoring the autonomous
research agent system:
- status: Show current agent state and session info
- trigger: Manually trigger an agent research cycle

Phase 1: Commands now use API endpoints instead of direct service calls.
"""

import asyncio
import sys

import typer
from rich.console import Console
from rich.table import Table

from ktrdr.cli.async_cli_client import AsyncCLIClient, AsyncCLIClientError
from ktrdr.cli.telemetry import trace_cli_command
from ktrdr.logging import get_logger

# Setup logging and console
logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)

# Create the CLI app for agent commands
agent_app = typer.Typer(
    name="agent",
    help="Research agent management commands",
    no_args_is_help=True,
)


@agent_app.command("status")
@trace_cli_command("agent_status")
def show_status(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    ),
):
    """
    Show current agent research system status.

    Displays information about active sessions, current phase,
    and recent activity.

    Examples:
        ktrdr agent status
        ktrdr agent status --verbose
    """
    try:
        asyncio.run(_show_status_async(verbose))
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


async def _show_status_async(verbose: bool):
    """Async implementation of status command using API."""
    try:
        async with AsyncCLIClient() as client:
            result = await client._make_request(
                "GET", "/agent/status", params={"verbose": verbose}
            )

        console.print("\n[bold]Agent Research System Status[/bold]")
        console.print()

        if not result.get("has_active_session"):
            console.print("[dim]No active session[/dim]")
            console.print()
            console.print(
                "Use [cyan]ktrdr agent trigger[/cyan] to start a new research cycle."
            )
            return

        session = result.get("session", {})
        session_id = session.get("id")

        console.print(f"[green]Active Session: #{session_id}[/green]")

        # Create info table
        table = Table(show_header=False, box=None)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Phase", session.get("phase", "unknown").upper())
        if session.get("created_at"):
            table.add_row("Created", session["created_at"])
        if session.get("updated_at"):
            table.add_row("Updated", session["updated_at"])
        if session.get("strategy_name"):
            table.add_row("Strategy", session["strategy_name"])
        if session.get("operation_id"):
            table.add_row("Operation", session["operation_id"])

        console.print(table)

        # Verbose mode: show recent actions
        if verbose and result.get("recent_actions"):
            console.print()
            console.print("[bold]Recent Actions[/bold]")

            actions = result["recent_actions"]
            if not actions:
                console.print("[dim]No actions recorded yet[/dim]")
            else:
                action_table = Table()
                action_table.add_column("Time", style="dim")
                action_table.add_column("Tool", style="cyan")
                action_table.add_column("Result", style="green")

                for action in actions[-5:]:
                    time_str = action.get("created_at", "")
                    tool = action.get("tool_name", "unknown")
                    result_status = action.get("result", "unknown")
                    action_table.add_row(time_str, tool, result_status)

                console.print(action_table)

    except AsyncCLIClientError as e:
        logger.error(f"API error: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to get agent status: {e}")
        raise


@agent_app.command("trigger")
@trace_cli_command("agent_trigger")
def trigger_agent(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would happen without actually triggering",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    ),
):
    """
    Manually trigger an agent research cycle.

    Checks if conditions are met and invokes the agent to start
    a new research cycle. Useful for testing and debugging.

    Examples:
        ktrdr agent trigger
        ktrdr agent trigger --dry-run
        ktrdr agent trigger --verbose
    """
    try:
        asyncio.run(_trigger_agent_async(dry_run, verbose))
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


async def _trigger_agent_async(dry_run: bool, verbose: bool):
    """Async implementation of trigger command using API."""
    try:
        if verbose:
            console.print("[dim]Sending trigger request to API...[/dim]")

        async with AsyncCLIClient() as client:
            result = await client._make_request(
                "POST", "/agent/trigger", params={"dry_run": dry_run}
            )

        if dry_run:
            if result.get("would_trigger"):
                console.print(
                    "\n[cyan]DRY RUN:[/cyan] Would trigger a new research cycle"
                )
                console.print("[dim]No active session found - conditions are met[/dim]")
            else:
                console.print("\n[cyan]DRY RUN:[/cyan] Would NOT trigger")
                reason = result.get("reason", "unknown")
                console.print(f"[dim]Reason: {reason}[/dim]")
            return

        if result.get("triggered"):
            console.print("\n[green]Agent triggered successfully![/green]")
            if result.get("session_id"):
                console.print(f"  Session ID: {result['session_id']}")
            console.print()
            console.print("Use [cyan]ktrdr agent status[/cyan] to monitor progress.")
        else:
            reason = result.get("reason", "unknown")
            message = result.get("message", f"Agent not triggered: {reason}")

            if reason == "active_session_exists":
                active_id = result.get("active_session_id", "unknown")
                console.print(
                    f"\n[yellow]Cannot trigger:[/yellow] Active session exists (#{active_id})"
                )
                console.print()
                console.print(
                    "Wait for the current session to complete before triggering a new one."
                )
            elif reason == "disabled":
                console.print("\n[yellow]Agent trigger is disabled[/yellow]")
                console.print("[dim]Set AGENT_ENABLED=true to enable[/dim]")
            else:
                console.print(f"\n[yellow]Agent not triggered:[/yellow] {message}")

            if result.get("error"):
                console.print(f"[red]Error:[/red] {result['error']}")

    except AsyncCLIClientError as e:
        logger.error(f"API error: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to trigger agent: {e}")
        raise
