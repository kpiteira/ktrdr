"""
Agent research system commands for the KTRDR CLI.

This module contains CLI commands for managing and monitoring the autonomous
research agent system:
- status: Show current agent state and session info
- trigger: Manually trigger an agent research cycle

Phase 0: Basic visibility commands for plumbing validation.
Future phases: history, budget, pause/resume, etc.
"""

import asyncio
import sys

import typer
from rich.console import Console
from rich.table import Table

from ktrdr.cli.telemetry import trace_cli_command
from ktrdr.logging import get_logger
from research_agents.database.queries import get_agent_db
from research_agents.services.trigger import TriggerConfig, TriggerService

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
    """Async implementation of status command."""
    try:
        db = await get_agent_db()

        console.print("\n[bold]Agent Research System Status[/bold]")
        console.print()

        # Get active session
        active_session = await db.get_active_session()

        if active_session is None:
            console.print("[dim]No active session[/dim]")
            console.print()
            console.print(
                "Use [cyan]ktrdr agent trigger[/cyan] to start a new research cycle."
            )
            return

        # Display active session info
        console.print(f"[green]Active Session: #{active_session.id}[/green]")

        # Create info table
        table = Table(show_header=False, box=None)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Phase", active_session.phase.value.upper())
        table.add_row(
            "Created", active_session.created_at.strftime("%Y-%m-%d %H:%M:%S")
        )

        if active_session.updated_at:
            table.add_row(
                "Updated", active_session.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            )

        if active_session.strategy_name:
            table.add_row("Strategy", active_session.strategy_name)

        if active_session.operation_id:
            table.add_row("Operation", active_session.operation_id)

        console.print(table)

        # Verbose mode: show recent actions
        if verbose:
            console.print()
            console.print("[bold]Recent Actions[/bold]")

            actions = await db.get_session_actions(active_session.id)

            if not actions:
                console.print("[dim]No actions recorded yet[/dim]")
            else:
                action_table = Table()
                action_table.add_column("Time", style="dim")
                action_table.add_column("Tool", style="cyan")
                action_table.add_column("Result", style="green")

                for action in actions[-5:]:  # Last 5 actions
                    time_str = action.created_at.strftime("%H:%M:%S")
                    result_status = "OK" if action.result.get("success") else "FAIL"
                    action_table.add_row(time_str, action.tool_name, result_status)

                console.print(action_table)

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
    """Async implementation of trigger command."""
    try:
        db = await get_agent_db()

        if verbose:
            console.print("[dim]Checking trigger conditions...[/dim]")

        # Check for active session first
        active_session = await db.get_active_session()

        if active_session is not None:
            console.print(
                f"\n[yellow]Cannot trigger:[/yellow] Active session exists (#{active_session.id})"
            )
            console.print(f"  Phase: {active_session.phase.value}")
            if active_session.strategy_name:
                console.print(f"  Strategy: {active_session.strategy_name}")
            console.print()
            console.print(
                "Wait for the current session to complete before triggering a new one."
            )
            return

        if dry_run:
            console.print("\n[cyan]DRY RUN:[/cyan] Would trigger a new research cycle")
            console.print("[dim]No active session found - conditions are met[/dim]")
            return

        # Create trigger service with a mock invoker for now
        # In production, this would use ClaudeCodeInvoker
        from research_agents.services.invoker import ClaudeCodeInvoker

        config = TriggerConfig.from_env()
        invoker = ClaudeCodeInvoker()

        # Check if service is enabled
        if not config.enabled:
            console.print("\n[yellow]Agent trigger is disabled[/yellow]")
            console.print("[dim]Set AGENT_ENABLED=true to enable[/dim]")
            return

        service = TriggerService(config=config, db=db, invoker=invoker)

        if verbose:
            console.print("[dim]Invoking agent...[/dim]")

        result = await service.check_and_trigger()

        if result.get("triggered"):
            console.print("\n[green]Agent triggered successfully![/green]")
            if result.get("session_id"):
                console.print(f"  Session ID: {result['session_id']}")
            console.print()
            console.print("Use [cyan]ktrdr agent status[/cyan] to monitor progress.")
        else:
            reason = result.get("reason", "unknown")
            console.print(f"\n[yellow]Agent not triggered:[/yellow] {reason}")
            if result.get("error"):
                console.print(f"[red]Error:[/red] {result['error']}")

    except Exception as e:
        logger.error(f"Failed to trigger agent: {e}")
        raise
