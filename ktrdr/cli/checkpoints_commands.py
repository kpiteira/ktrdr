"""
Checkpoint management commands for the KTRDR CLI.

This module contains CLI commands for viewing checkpoint information:
- show: View checkpoint details before resuming
- delete: Delete a checkpoint (Task 8.6)
"""

import asyncio
import sys
from datetime import datetime, timezone
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ktrdr.cli.api_client import check_api_connection, get_api_client
from ktrdr.cli.telemetry import trace_cli_command
from ktrdr.config.validation import InputValidator
from ktrdr.errors import DataError, ValidationError
from ktrdr.logging import get_logger

# Setup logging and console
logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)


def _format_size(size_bytes: Optional[int]) -> str:
    """Format byte size as human-readable string."""
    if size_bytes is None:
        return "N/A"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def _format_age(created_at_str: str) -> str:
    """Format checkpoint age as human-readable string."""
    try:
        created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - created_at

        if delta.days > 0:
            return f"{delta.days}d"
        elif delta.seconds >= 3600:
            return f"{delta.seconds // 3600}h"
        elif delta.seconds >= 60:
            return f"{delta.seconds // 60}m"
        else:
            return "just now"
    except Exception:
        return "N/A"


# Create the CLI app for checkpoints commands
checkpoints_app = typer.Typer(
    name="checkpoints",
    help="Checkpoint management commands",
    no_args_is_help=True,
)


@checkpoints_app.command("show")
@trace_cli_command("checkpoints_show")
def show_checkpoint(
    operation_id: str = typer.Argument(..., help="Operation ID of the checkpoint"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show additional details"
    ),
):
    """
    View checkpoint details for an operation.

    Shows checkpoint state, artifacts, and resume information.
    Useful for inspecting a checkpoint before resuming.

    Examples:
        ktrdr checkpoints show op_training_20241213_143022_abc123
        ktrdr checkpoints show op_training_20241213_143022_abc123 --verbose
    """
    try:
        # Input validation
        operation_id = InputValidator.validate_string(
            operation_id, min_length=1, max_length=100
        )

        # Run async operation
        asyncio.run(_show_checkpoint_async(operation_id, verbose))

    except ValidationError as e:
        error_console.print(f"[bold red]Validation error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Validation error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        error_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


async def _show_checkpoint_async(operation_id: str, verbose: bool):
    """Async implementation of show checkpoint command."""
    try:
        # Check API connection
        if not await check_api_connection():
            error_console.print(
                "[bold red]Error:[/bold red] Could not connect to KTRDR API server"
            )
            error_console.print(
                "Make sure the API server is running at http://localhost:8000"
            )
            sys.exit(1)

        api_client = get_api_client()

        if verbose:
            console.print(f"Fetching checkpoint for: {operation_id}")

        # Fetch checkpoint details
        try:
            response = await api_client.get(f"/checkpoints/{operation_id}")
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                error_console.print(f"No checkpoint found for: {operation_id}")
                sys.exit(1)
                return  # Needed for tests that mock sys.exit
            raise

        if not response.get("success"):
            error_console.print(f"No checkpoint found for: {operation_id}")
            sys.exit(1)
            return  # Needed for tests that mock sys.exit

        checkpoint = response.get("data", {})

        # Display checkpoint details
        console.print("\n[bold]Checkpoint Details[/bold]")
        console.print("=" * 40)

        # Basic info table
        info_table = Table(show_header=False, box=None)
        info_table.add_column("Property", style="cyan", width=18)
        info_table.add_column("Value", style="white")

        info_table.add_row("Operation ID:", checkpoint.get("operation_id", "N/A"))
        info_table.add_row("Checkpoint Type:", checkpoint.get("checkpoint_type", "N/A"))

        created_at = checkpoint.get("created_at", "")
        if created_at:
            created_display = created_at.replace("T", " ").replace("Z", " UTC")
            age = _format_age(created_at)
            info_table.add_row("Created At:", created_display)
            info_table.add_row("Age:", age)

        console.print(info_table)

        # State information
        state = checkpoint.get("state", {})
        if state:
            console.print("\n[bold]State:[/bold]")
            state_table = Table(show_header=False, box=None)
            state_table.add_column("Property", style="cyan", width=18)
            state_table.add_column("Value", style="green")

            # Training-specific fields
            if "epoch" in state:
                total = state.get("total_epochs", state.get("epochs", "?"))
                state_table.add_row("Epoch:", f"{state['epoch']} / {total}")
            if "train_loss" in state:
                state_table.add_row("Train Loss:", f"{state['train_loss']:.4f}")
            if "val_loss" in state:
                state_table.add_row("Val Loss:", f"{state['val_loss']:.4f}")
            if "best_val_loss" in state:
                state_table.add_row("Best Val Loss:", f"{state['best_val_loss']:.4f}")
            if "learning_rate" in state:
                state_table.add_row("Learning Rate:", f"{state['learning_rate']}")

            # Backtesting-specific fields
            if "bar_index" in state:
                total = state.get("total_bars", "?")
                state_table.add_row("Bar Index:", f"{state['bar_index']} / {total}")

            # Agent-specific fields
            if "step" in state:
                state_table.add_row("Step:", str(state["step"]))

            # Show additional state in verbose mode
            if verbose:
                for key, value in state.items():
                    if key not in [
                        "epoch",
                        "total_epochs",
                        "epochs",
                        "train_loss",
                        "val_loss",
                        "best_val_loss",
                        "learning_rate",
                        "bar_index",
                        "total_bars",
                        "step",
                    ]:
                        if not key.startswith("_"):
                            state_table.add_row(
                                f"{key.replace('_', ' ').title()}:", str(value)
                            )

            console.print(state_table)

        # Artifacts path
        artifacts_path = checkpoint.get("artifacts_path")
        if artifacts_path:
            console.print(f"\n[bold]Artifacts:[/bold] {artifacts_path}")

        # Resume command hint
        console.print(f"\n[dim]To resume:[/dim] ktrdr operations resume {operation_id}")

        if verbose:
            console.print("\nCheckpoint details retrieved successfully")

    except Exception as e:
        raise DataError(
            message=f"Failed to show checkpoint for {operation_id}",
            error_code="CLI-ShowCheckpointError",
            details={"operation_id": operation_id, "error": str(e)},
        ) from e
