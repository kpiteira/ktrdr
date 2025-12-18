"""Agent research system commands for the KTRDR CLI.

Simplified commands:
- status: Show current agent state
- trigger: Start a new research cycle
- cancel: Cancel active research cycle (M6 Task 6.3)
"""

import asyncio
import sys

import typer
from rich.console import Console
from rich.table import Table

from ktrdr.cli.async_cli_client import AsyncCLIClient, AsyncCLIClientError
from ktrdr.cli.telemetry import trace_cli_command
from ktrdr.logging import get_logger

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
def show_status():
    """Show current agent research system status.

    Displays whether a cycle is active and its current phase,
    or information about the last completed cycle.

    Examples:
        ktrdr agent status
    """
    try:
        asyncio.run(_show_status_async())
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


async def _show_status_async():
    """Async implementation of status command using API."""
    try:
        async with AsyncCLIClient() as client:
            result = await client._make_request("GET", "/agent/status")

        console.print("\n[bold]Agent Research System Status[/bold]")
        console.print()

        if result.get("status") == "active":
            console.print("[green]Status: ACTIVE[/green]")

            # Create info table
            table = Table(show_header=False, box=None)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="white")

            table.add_row("Operation", result.get("operation_id", "unknown"))
            table.add_row("Phase", result.get("phase", "unknown").upper())
            if result.get("strategy_name"):
                table.add_row("Strategy", result["strategy_name"])
            if result.get("started_at"):
                table.add_row("Started", result["started_at"])

            console.print(table)
        else:
            console.print("[dim]Status: IDLE[/dim]")

            last_cycle = result.get("last_cycle")
            if last_cycle:
                console.print("\n[bold]Last Cycle[/bold]")

                table = Table(show_header=False, box=None)
                table.add_column("Property", style="cyan")
                table.add_column("Value", style="white")

                table.add_row("Operation", last_cycle.get("operation_id", "unknown"))
                table.add_row("Outcome", last_cycle.get("outcome", "unknown").upper())
                if last_cycle.get("strategy_name"):
                    table.add_row("Strategy", last_cycle["strategy_name"])
                if last_cycle.get("completed_at"):
                    table.add_row("Completed", last_cycle["completed_at"])

                console.print(table)
            else:
                console.print("[dim]No previous cycles.[/dim]")
                console.print()
                console.print(
                    "Use [cyan]ktrdr agent trigger[/cyan] to start a new research cycle."
                )

    except AsyncCLIClientError as e:
        logger.error(f"API error: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to get agent status: {e}")
        raise


@agent_app.command("trigger")
@trace_cli_command("agent_trigger")
def trigger_agent():
    """Start a new research cycle.

    Triggers the agent to begin a new research cycle. If a cycle
    is already running, the command will fail with a conflict message.

    Examples:
        ktrdr agent trigger
    """
    try:
        asyncio.run(_trigger_agent_async())
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


async def _trigger_agent_async():
    """Async implementation of trigger command using API."""
    try:
        async with AsyncCLIClient() as client:
            result = await client._make_request("POST", "/agent/trigger")

        if result.get("triggered"):
            console.print("\n[green]Research cycle started![/green]")
            console.print(f"  Operation ID: {result['operation_id']}")
            console.print()
            console.print("Use [cyan]ktrdr agent status[/cyan] to monitor progress.")
        else:
            reason = result.get("reason", "unknown")
            message = result.get("message", f"Could not start cycle: {reason}")

            if reason == "active_cycle_exists":
                console.print("\n[yellow]Cannot trigger:[/yellow] Active cycle exists")
                if result.get("operation_id"):
                    console.print(f"  Operation ID: {result['operation_id']}")
                console.print()
                console.print("Wait for the current cycle to complete, or cancel it:")
                console.print(
                    f"  [cyan]ktrdr operations cancel {result.get('operation_id', '<op_id>')}[/cyan]"
                )
            else:
                console.print(f"\n[yellow]Could not trigger:[/yellow] {message}")

    except AsyncCLIClientError as e:
        logger.error(f"API error: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to trigger agent: {e}")
        raise


@agent_app.command("cancel")
@trace_cli_command("agent_cancel")
def cancel_agent():
    """Cancel the active research cycle.

    Cancels the currently running research cycle if one exists.
    Both the parent operation and any active child operation
    will be cancelled.

    Examples:
        ktrdr agent cancel
    """
    try:
        asyncio.run(_cancel_agent_async())
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


async def _cancel_agent_async():
    """Async implementation of cancel command using API."""
    try:
        async with AsyncCLIClient() as client:
            result = await client._make_request("DELETE", "/agent/cancel")

        if result.get("success"):
            console.print("\n[green]Research cycle cancelled![/green]")
            console.print(f"  Operation: {result['operation_id']}")
            if result.get("child_cancelled"):
                console.print(f"  Child operation: {result['child_cancelled']}")
            console.print()
        else:
            reason = result.get("reason", "unknown")
            message = result.get("message", f"Could not cancel: {reason}")

            if reason == "no_active_cycle":
                console.print("\n[dim]No active research cycle to cancel.[/dim]")
                console.print()
                console.print(
                    "Use [cyan]ktrdr agent trigger[/cyan] to start a new research cycle."
                )
            else:
                console.print(f"\n[yellow]Could not cancel:[/yellow] {message}")

    except AsyncCLIClientError as e:
        # Handle 404 "no active cycle" gracefully
        if "no_active_cycle" in str(e).lower() or "no active" in str(e).lower():
            console.print("\n[dim]No active research cycle to cancel.[/dim]")
            console.print()
            console.print(
                "Use [cyan]ktrdr agent trigger[/cyan] to start a new research cycle."
            )
        else:
            logger.error(f"API error: {e}")
            raise
    except Exception as e:
        logger.error(f"Failed to cancel agent: {e}")
        raise
