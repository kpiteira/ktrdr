"""Operation runner for unified start/follow pattern.

Provides a simplified wrapper around AsyncCLIClient that supports both
fire-and-forget (return immediately with operation ID) and follow mode
(poll and display progress until completion).
"""

import asyncio

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from ktrdr.cli.client import AsyncCLIClient
from ktrdr.cli.client.operations import OperationAdapter
from ktrdr.cli.output import print_error, print_operation_started
from ktrdr.cli.state import CLIState


class OperationRunner:
    """Unified start/follow for all operation types.

    Provides a consistent interface for starting operations with either:
    - Fire-and-forget: Start operation, print ID, return immediately
    - Follow mode: Start operation, poll for status, show progress

    Usage:
        state = CLIState(json_mode=False, api_url="http://localhost:8000")
        runner = OperationRunner(state)

        # Fire-and-forget
        runner.start(adapter, follow=False)

        # Follow mode
        runner.start(adapter, follow=True)
    """

    def __init__(self, state: CLIState) -> None:
        """Initialize operation runner.

        Args:
            state: CLI state with json_mode, verbose, api_url settings.
        """
        self.state = state
        self.console = Console()

    def start(
        self,
        adapter: OperationAdapter,
        follow: bool = False,
    ) -> None:
        """Start operation via API.

        If follow=False: print operation ID and return immediately.
        If follow=True: poll and display progress until completion.

        Args:
            adapter: Operation adapter defining endpoint and payload.
            follow: If True, poll for status and show progress.

        Raises:
            SystemExit: With code 1 if operation fails in follow mode.
        """
        asyncio.run(self._start_async(adapter, follow))

    async def _start_async(
        self,
        adapter: OperationAdapter,
        follow: bool,
    ) -> None:
        """Async implementation of start.

        Args:
            adapter: Operation adapter defining endpoint and payload.
            follow: If True, poll for status and show progress.
        """
        async with AsyncCLIClient(base_url=self.state.api_url) as client:
            if follow:
                await self._execute_with_progress(client, adapter)
            else:
                await self._fire_and_forget(client, adapter)

    async def _fire_and_forget(
        self,
        client: AsyncCLIClient,
        adapter: OperationAdapter,
    ) -> None:
        """Start operation and return immediately with operation ID.

        Args:
            client: Async HTTP client.
            adapter: Operation adapter.
        """
        try:
            # POST to start endpoint
            endpoint = adapter.get_start_endpoint()
            payload = adapter.get_start_payload()
            response = await client.post(endpoint, json=payload)

            # Extract operation ID
            operation_id = adapter.parse_start_response(response)

            # Derive operation type from adapter class name
            operation_type = self._get_operation_type(adapter)

            # Print started message
            print_operation_started(
                operation_type=operation_type,
                operation_id=operation_id,
                state=self.state,
            )
        except Exception as e:
            print_error(str(e), self.state)
            raise SystemExit(1) from None

    async def _execute_with_progress(
        self,
        client: AsyncCLIClient,
        adapter: OperationAdapter,
    ) -> None:
        """Execute operation with progress display.

        Uses Rich Progress to show a progress bar during operation execution.

        Args:
            client: Async HTTP client.
            adapter: Operation adapter.

        Raises:
            SystemExit: With code 1 if operation fails.
        """
        progress_bar = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
        )
        task_id = None

        def on_progress(percentage: int, message: str) -> None:
            """Progress callback for Rich progress display."""
            nonlocal task_id
            if task_id is not None:
                progress_bar.update(task_id, completed=percentage, description=message)

        operation_type = self._get_operation_type(adapter)

        try:
            with progress_bar:
                task_id = progress_bar.add_task(
                    f"Running {operation_type}...", total=100
                )
                result = await client.execute_operation(
                    adapter,
                    on_progress=on_progress,
                    poll_interval=0.3,
                )
        except Exception as e:
            print_error(str(e), self.state)
            raise SystemExit(1) from None

        # Handle result based on final status
        status = result.get("status", "unknown")

        if status == "completed":
            self.console.print(
                f"✅ [green]{operation_type.capitalize()} completed successfully![/green]"
            )
        elif status == "failed":
            error_msg = result.get(
                "error_message", result.get("error", "Unknown error")
            )
            print_error(
                f"{operation_type.capitalize()} failed: {error_msg}", self.state
            )
            raise SystemExit(1)
        elif status == "cancelled":
            self.console.print(
                f"[yellow]{operation_type.capitalize()} was cancelled[/yellow]"
            )
        else:
            self.console.print(
                f"⚠️ [yellow]{operation_type.capitalize()} ended with status: {status}[/yellow]"
            )
            raise SystemExit(1)

    def _get_operation_type(self, adapter: OperationAdapter) -> str:
        """Derive operation type from adapter class name.

        Args:
            adapter: Operation adapter instance.

        Returns:
            Lowercase operation type (e.g., "training", "backtest").
        """
        class_name = adapter.__class__.__name__
        # Remove common suffixes
        for suffix in ("OperationAdapter", "Adapter"):
            if class_name.endswith(suffix):
                class_name = class_name[: -len(suffix)]
                break
        return class_name.lower()
