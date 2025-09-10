"""
Enhanced CLI progress display with rich formatting and context awareness.

This module provides enhanced progress display capabilities that work with
the ProgressManager's enhanced features including contextual information
and time estimation.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from ktrdr.async_infrastructure.progress import GenericProgressState

logger = logging.getLogger(__name__)


class EnhancedCLIProgressDisplay:
    """
    Enhanced CLI progress display with rich formatting and contextual information.

    This class provides:
    - Rich progress bars with contextual information
    - Time estimation display
    - Symbol and timeframe context in progress messages
    - Enhanced error reporting
    - Detailed operation summaries
    """

    def __init__(self, console: Optional[Console] = None, show_details: bool = True):
        """
        Initialize enhanced CLI progress display.

        Args:
            console: Optional Rich console instance
            show_details: Whether to show detailed progress information
        """
        self.console = console or Console()
        self.show_details = show_details
        self.progress: Optional[Progress] = None
        self.current_task: Optional[TaskID] = None
        self.live_display: Optional[Live] = None
        self.operation_start_time: Optional[datetime] = None
        self.last_update_time: Optional[datetime] = None

    def start_operation(
        self,
        operation_name: str,
        total_steps: int,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Start rich progress display for an operation.

        Args:
            operation_name: Name of the operation
            total_steps: Total number of steps
            context: Optional context information (symbol, timeframe, etc.)
        """
        self.operation_start_time = datetime.now()

        # Create enhanced operation title with context
        title = self._create_operation_title(operation_name, context)

        # Create progress bar with enhanced columns
        columns = [
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
        ]

        if self.show_details:
            columns.append(TimeRemainingColumn())
            columns.append(TextColumn("[dim]{task.fields[details]}"))

        self.progress = Progress(*columns, console=self.console, refresh_per_second=4)

        # Start live display
        self.live_display = Live(
            self._create_display_panel(), console=self.console, refresh_per_second=2
        )
        self.live_display.start()

        # Add the main task
        self.current_task = self.progress.add_task(
            description=title,
            total=100,
            details="",  # We'll work with percentages
        )

    def update_progress(self, progress_state: GenericProgressState) -> None:
        """
        Update progress display with enhanced state information.

        Args:
            progress_state: Current progress state from GenericProgressManager
        """
        if not self.progress or self.current_task is None:
            return

        self.last_update_time = datetime.now()

        # Create enhanced description with context
        description = self._create_step_description(progress_state)

        # Create details text
        details = self._create_details_text(progress_state)

        # Update the task
        self.progress.update(
            self.current_task,
            completed=progress_state.percentage,
            description=description,
            details=details,
        )

        # Update live display
        if self.live_display:
            self.live_display.update(self._create_display_panel())

    def complete_operation(
        self, success: bool = True, summary: Optional[str] = None
    ) -> None:
        """
        Complete and cleanup progress display.

        Args:
            success: Whether the operation completed successfully
            summary: Optional summary message
        """
        if self.live_display:
            self.live_display.stop()

        # Show completion message
        if success:
            completion_icon = "✅"
            completion_style = "bold green"
            completion_text = "Operation completed successfully"
        else:
            completion_icon = "❌"
            completion_style = "bold red"
            completion_text = "Operation failed"

        if summary:
            completion_text += f": {summary}"

        elapsed = (
            (datetime.now() - self.operation_start_time).total_seconds()
            if self.operation_start_time
            else 0
        )

        self.console.print(
            f"{completion_icon} {completion_text} ({elapsed:.1f}s)",
            style=completion_style,
        )

        # Cleanup
        self.progress = None
        self.current_task = None
        self.live_display = None
        self.operation_start_time = None

    def report_error(
        self, error_message: str, context: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Report an error with contextual information.

        Args:
            error_message: Error message to display
            context: Optional context information
        """
        error_text = f"❌ Error: {error_message}"

        if context:
            context_parts = []
            if "symbol" in context:
                context_parts.append(f"Symbol: {context['symbol']}")
            if "timeframe" in context:
                context_parts.append(f"Timeframe: {context['timeframe']}")
            if "current_item" in context:
                context_parts.append(f"Item: {context['current_item']}")

            if context_parts:
                error_text += f" ({', '.join(context_parts)})"

        self.console.print(error_text, style="bold red")

    def _create_operation_title(
        self, operation_name: str, context: Optional[dict[str, Any]]
    ) -> str:
        """Create enhanced operation title with context."""
        if not context:
            return operation_name

        title_parts = [operation_name]

        # Add symbol and timeframe if available
        if "symbol" in context and "timeframe" in context:
            title_parts.append(f"({context['symbol']} {context['timeframe']})")
        elif "symbol" in context:
            title_parts.append(f"({context['symbol']})")

        return " ".join(title_parts)

    def _create_step_description(self, progress_state: GenericProgressState) -> str:
        """Create enhanced step description with context."""
        base_description = progress_state.message

        # Add current step information if available
        if progress_state.context.get("current_step_name"):
            step_info = f"[{progress_state.current_step}/{progress_state.total_steps}] {progress_state.context['current_step_name']}"
            if progress_state.context.get("step_detail"):
                step_info += f": {progress_state.context['step_detail']}"
            return step_info

        return base_description

    def _create_details_text(self, progress_state: GenericProgressState) -> str:
        """Create details text with additional information."""
        details_parts = []

        # Add current item detail if available
        if progress_state.context.get("current_item_detail"):
            details_parts.append(progress_state.context["current_item_detail"])

        # Add items processed information
        if progress_state.items_processed > 0:
            if progress_state.total_items:
                details_parts.append(
                    f"{progress_state.items_processed}/{progress_state.total_items} items"
                )
            else:
                details_parts.append(f"{progress_state.items_processed} items")

        # Add time estimate if available
        if (
            progress_state.estimated_remaining
            and progress_state.estimated_remaining.total_seconds() > 1
        ):
            remaining = progress_state.estimated_remaining
            time_str = self._format_time_estimate(remaining)
            details_parts.append(f"ETA: {time_str}")

        return " | ".join(details_parts) if details_parts else ""

    def _format_time_estimate(self, remaining: timedelta) -> str:
        """Format time estimate in compact form."""
        total_seconds = int(remaining.total_seconds())
        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes}m"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h{minutes:02d}m"

    def _create_display_panel(self) -> Panel:
        """Create the main display panel."""
        if not self.progress:
            return Panel("No active progress", title="Operation Status")

        return Panel(
            self.progress,
            title="[bold blue]Progress Status[/bold blue]",
            border_style="blue",
            padding=(0, 1),
        )


def create_enhanced_progress_callback(
    console: Optional[Console] = None, show_details: bool = True
) -> tuple[Any, EnhancedCLIProgressDisplay]:
    """
    Create an enhanced progress callback function and display manager.

    Args:
        console: Optional Rich console instance
        show_details: Whether to show detailed progress information

    Returns:
        Tuple of (callback_function, display_manager)
    """
    display = EnhancedCLIProgressDisplay(console, show_details)
    operation_started = False

    def enhanced_progress_callback(progress_state: GenericProgressState) -> None:
        nonlocal operation_started

        # Start operation on first callback
        if not operation_started and progress_state.total_steps > 0:
            display.start_operation(
                progress_state.operation_id,
                progress_state.total_steps,
                progress_state.context.get("operation_context", progress_state.context),
            )
            operation_started = True

        # Update progress
        if operation_started:
            display.update_progress(progress_state)

            # Complete operation if at 100%
            if progress_state.percentage >= 100.0:
                display.complete_operation(success=True)
                operation_started = False

    return enhanced_progress_callback, display


def simple_enhanced_progress_callback(progress_state: GenericProgressState) -> None:
    """
    Simple enhanced progress callback that can be used directly.

    This creates a console instance and handles the display automatically.
    """
    # Use function attributes for singleton pattern
    if not hasattr(simple_enhanced_progress_callback, "_callback"):
        callback, display = create_enhanced_progress_callback()
        # Type: ignore because we're setting function attributes dynamically
        simple_enhanced_progress_callback._callback = callback  # type: ignore
        simple_enhanced_progress_callback._display_manager = display  # type: ignore

    # Delegate to the created callback
    simple_enhanced_progress_callback._callback(progress_state)  # type: ignore
