"""
Progress display utilities for CLI operations.

This module provides progress bars and status reporting for long-running
IB data operations and other CLI tasks.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from ktrdr import get_logger

logger = get_logger(__name__)


@dataclass
class ProgressStats:
    """Statistics for progress tracking."""

    total_items: int
    completed_items: int
    failed_items: int
    start_time: datetime
    current_item: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def completion_percentage(self) -> float:
        """Get completion percentage (0-100)."""
        if self.total_items == 0:
            return 100.0
        return (self.completed_items / self.total_items) * 100

    @property
    def elapsed_time(self) -> timedelta:
        """Get elapsed time since start."""
        return datetime.now() - self.start_time

    @property
    def estimated_remaining(self) -> Optional[timedelta]:
        """Estimate remaining time based on current progress."""
        if self.completed_items == 0:
            return None

        elapsed = self.elapsed_time
        rate = self.completed_items / elapsed.total_seconds()
        remaining_items = self.total_items - self.completed_items

        if rate > 0:
            return timedelta(seconds=remaining_items / rate)
        return None


class ProgressDisplayManager:
    """
    Manager for displaying progress bars and status updates for CLI operations.

    Provides rich progress bars, status tables, and real-time updates for
    long-running operations like IB data fetching.
    """

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize progress display manager.

        Args:
            console: Optional Rich console instance
        """
        self.console = console or Console()
        self.stats: Optional[ProgressStats] = None
        self._active_progress: Optional[Any] = None
        self._active_task = None

    @contextmanager
    def progress_context(
        self,
        title: str,
        total_items: int,
        show_eta: bool = True,
        show_speed: bool = False,
    ):
        """
        Context manager for progress tracking.

        Args:
            title: Title for the progress bar
            total_items: Total number of items to process
            show_eta: Whether to show estimated time remaining
            show_speed: Whether to show processing speed
        """
        # Initialize statistics
        self.stats = ProgressStats(
            total_items=total_items,
            completed_items=0,
            failed_items=0,
            start_time=datetime.now(),
        )

        # Create progress bar columns
        columns = [
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        ]

        if show_eta:
            columns.append(TimeRemainingColumn())

        if show_speed:
            columns.append(TextColumn("[yellow]{task.speed:.2f} items/sec[/yellow]"))

        columns.append(TimeElapsedColumn())

        # Create and start progress
        self._active_progress = Progress(*columns, console=self.console)

        with self._active_progress:
            self._active_task = self._active_progress.add_task(title, total=total_items)

            try:
                yield self
            finally:
                self._active_progress = None
                self._active_task = None
                self.stats = None

    def update_progress(
        self,
        advance: int = 1,
        current_item: Optional[str] = None,
        status_message: Optional[str] = None,
    ):
        """
        Update progress bar.

        Args:
            advance: Number of items to advance
            current_item: Current item being processed
            status_message: Optional status message
        """
        if not self._active_progress or not self._active_task:
            return

        if self.stats:
            self.stats.completed_items += advance
            self.stats.current_item = current_item

        # Update task description if provided
        if status_message:
            self._active_progress.update(
                self._active_task, advance=advance, description=status_message
            )
        else:
            self._active_progress.update(self._active_task, advance=advance)

    def report_error(self, error_message: str, current_item: Optional[str] = None):
        """
        Report an error during progress.

        Args:
            error_message: Error message to display
            current_item: Item that caused the error
        """
        if self.stats:
            self.stats.failed_items += 1
            self.stats.error_message = error_message

        self.console.print(f"[red]❌ Error: {error_message}[/red]")
        if current_item:
            self.console.print(f"   Item: {current_item}")

    def print_summary(self):
        """Print a summary of the operation."""
        if not self.stats:
            return

        # Create summary table
        table = Table(
            title="Operation Summary", show_header=True, header_style="bold blue"
        )
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Items", str(self.stats.total_items))
        table.add_row("Completed", str(self.stats.completed_items))
        table.add_row("Failed", str(self.stats.failed_items))
        table.add_row(
            "Success Rate",
            f"{((self.stats.completed_items / self.stats.total_items) * 100):.1f}%",
        )
        table.add_row("Elapsed Time", str(self.stats.elapsed_time).split(".")[0])

        if self.stats.completed_items > 0:
            rate = self.stats.completed_items / self.stats.elapsed_time.total_seconds()
            table.add_row("Processing Rate", f"{rate:.2f} items/sec")

        self.console.print(table)


class IbProgressTracker:
    """
    Specialized progress tracker for IB operations.

    Provides progress tracking for:
    - Data fetching from IB
    - Symbol validation
    - Range discovery
    - Connection status
    """

    def __init__(self, console: Optional[Console] = None):
        """Initialize IB progress tracker."""
        self.console = console or Console()
        self.display_manager = ProgressDisplayManager(console)

    @contextmanager
    def data_fetch_progress(self, symbols: list, timeframes: list):
        """
        Progress context for IB data fetching.

        Args:
            symbols: List of symbols to fetch
            timeframes: List of timeframes to fetch
        """
        total_combinations = len(symbols) * len(timeframes)

        with self.display_manager.progress_context(
            "Fetching IB data", total_combinations, show_eta=True, show_speed=True
        ) as progress:
            yield progress

    @contextmanager
    def symbol_validation_progress(self, symbols: list):
        """
        Progress context for symbol validation.

        Args:
            symbols: List of symbols to validate
        """
        with self.display_manager.progress_context(
            "Validating symbols", len(symbols), show_eta=True
        ) as progress:
            yield progress

    @contextmanager
    def range_discovery_progress(self, symbols: list, timeframes: list):
        """
        Progress context for range discovery.

        Args:
            symbols: List of symbols for range discovery
            timeframes: List of timeframes for range discovery
        """
        total_combinations = len(symbols) * len(timeframes)

        with self.display_manager.progress_context(
            "Discovering data ranges",
            total_combinations,
            show_eta=True,
            show_speed=False,  # Range discovery can be slow
        ) as progress:
            yield progress

    def print_connection_status(self, connection_info: dict[str, Any]):
        """
        Print IB connection status in a formatted table.

        Args:
            connection_info: Connection information dictionary
        """
        # Create status panel
        if connection_info.get("connected", False):
            status_text = "[green]✅ Connected[/green]"
            panel_style = "green"
        else:
            status_text = "[red]❌ Disconnected[/red]"
            panel_style = "red"

        # Create connection details table
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Status", status_text)
        table.add_row("Host", connection_info.get("host", "N/A"))
        table.add_row("Port", str(connection_info.get("port", "N/A")))
        table.add_row("Client ID", str(connection_info.get("client_id", "N/A")))

        if "metrics" in connection_info:
            metrics = connection_info["metrics"]
            table.add_row("Total Connections", str(metrics.get("total_connections", 0)))
            table.add_row(
                "Failed Connections", str(metrics.get("failed_connections", 0))
            )

            if metrics.get("last_connect_time"):
                last_connect = datetime.fromtimestamp(metrics["last_connect_time"])
                table.add_row(
                    "Last Connected", last_connect.strftime("%Y-%m-%d %H:%M:%S")
                )

        # Display in a panel
        panel = Panel(table, title="IB Connection Status", border_style=panel_style)

        self.console.print(panel)

    def print_metrics_summary(self, metrics: dict[str, Any]):
        """
        Print IB metrics summary.

        Args:
            metrics: Metrics dictionary
        """
        table = Table(
            title="IB Performance Metrics", show_header=True, header_style="bold blue"
        )
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Requests", str(metrics.get("total_requests", 0)))
        table.add_row("Successful Requests", str(metrics.get("successful_requests", 0)))
        table.add_row("Failed Requests", str(metrics.get("failed_requests", 0)))
        table.add_row("Total Bars Fetched", str(metrics.get("total_bars_fetched", 0)))

        success_rate = metrics.get("success_rate", 0) * 100
        table.add_row("Success Rate", f"{success_rate:.1f}%")

        self.console.print(table)


# Convenience function for simple progress tracking
def simple_progress(
    items: list,
    process_func: Callable,
    title: str = "Processing",
    console: Optional[Console] = None,
):
    """
    Simple progress tracking for a list of items.

    Args:
        items: List of items to process
        process_func: Function to call for each item
        title: Progress bar title
        console: Optional console instance

    Returns:
        List of results from process_func
    """
    progress_manager = ProgressDisplayManager(console)
    results = []

    with progress_manager.progress_context(title, len(items)) as progress:
        for i, item in enumerate(items):
            try:
                result = process_func(item)
                results.append(result)
                progress.update_progress(
                    advance=1,
                    current_item=str(item),
                    status_message=f"{title} ({i+1}/{len(items)})",
                )
            except Exception as e:
                progress.report_error(str(e), str(item))
                results.append(None)

    progress_manager.print_summary()
    return results
