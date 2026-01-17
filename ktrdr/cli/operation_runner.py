"""Operation runner for unified start/follow pattern.

Provides a simplified wrapper around AsyncCLIClient that supports both
fire-and-forget (return immediately with operation ID) and follow mode
(poll and display progress until completion).
"""

import asyncio
import signal

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
        operation_type = self._get_operation_type(adapter)

        try:
            # POST to start endpoint
            endpoint = adapter.get_start_endpoint()
            payload = adapter.get_start_payload()
            response = await client.post(endpoint, json=payload)

            # Extract operation ID
            operation_id = adapter.parse_start_response(response)

            # Print started message
            print_operation_started(
                operation_type=operation_type,
                operation_id=operation_id,
                state=self.state,
            )
        except Exception as e:
            # Enhance exception with operation context if not already present
            if hasattr(e, "operation_type") and not e.operation_type:
                e.operation_type = operation_type
            elif not hasattr(e, "operation_type"):
                # For exceptions that don't support operation context, wrap the message
                from ktrdr.errors.exceptions import KtrdrError

                enhanced_error = KtrdrError(
                    message=str(e),
                    operation_type=operation_type,
                    stage="initialization",
                    suggestion="Check API connectivity and request parameters",
                )
                print_error(str(e), self.state, enhanced_error)
                raise SystemExit(1) from None

            print_error(str(e), self.state, e)
            raise SystemExit(1) from None

    async def _execute_with_progress(
        self,
        client: AsyncCLIClient,
        adapter: OperationAdapter,
    ) -> None:
        """Execute operation with progress display and Ctrl+C cancellation.

        Uses Rich Progress to show a progress bar during operation execution.
        Handles Ctrl+C by sending DELETE to cancel the operation.

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
        cancelled = False
        operation_id = None
        loop = asyncio.get_running_loop()

        def signal_handler() -> None:
            """Handle Ctrl+C by setting cancelled flag."""
            nonlocal cancelled
            cancelled = True

        # Setup signal handler for Ctrl+C
        signal_handler_registered = False
        try:
            loop.add_signal_handler(signal.SIGINT, signal_handler)
            signal_handler_registered = True
        except (ValueError, OSError):
            # Signal handlers not supported (e.g., Windows or not main thread)
            pass

        def on_progress(percentage: int, message: str) -> None:
            """Progress callback for Rich progress display."""
            nonlocal task_id
            if task_id is not None:
                progress_bar.update(task_id, completed=percentage, description=message)

        operation_type = self._get_operation_type(adapter)
        operation_id = None

        try:
            # Start the operation
            endpoint = adapter.get_start_endpoint()
            payload = adapter.get_start_payload()
            response = await client.post(endpoint, json=payload)
            operation_id = adapter.parse_start_response(response)

            with progress_bar:
                task_id = progress_bar.add_task(
                    f"Running {operation_type}...", total=100
                )

                # Initialize status and op_data before loop (in case Ctrl+C arrives early)
                status = "pending"
                op_data = {}

                # Poll until terminal state or cancelled
                while not cancelled:
                    result = await client.get(f"/operations/{operation_id}")
                    op_data = result.get("data", {})
                    status = op_data.get("status")

                    # Update progress
                    prog = op_data.get("progress", {})
                    pct = prog.get("percentage", 0)
                    step = prog.get("current_step", f"Running {operation_type}...")
                    progress_bar.update(task_id, completed=pct, description=step)

                    if status in ("completed", "failed", "cancelled"):
                        break

                    await asyncio.sleep(0.3)

                # Handle cancellation request
                if cancelled and status not in ("completed", "failed", "cancelled"):
                    self.console.print(
                        f"\n[yellow]Cancelling {operation_type}...[/yellow]"
                    )
                    try:
                        await client.delete(f"/operations/{operation_id}")
                        # Wait briefly for cancellation to process
                        await asyncio.sleep(0.5)
                        result = await client.get(f"/operations/{operation_id}")
                        op_data = result.get("data", {})
                        status = op_data.get("status")
                    except Exception:
                        pass  # Continue with last known status

        except Exception as e:
            # Enhance exception with operation context
            if hasattr(e, "operation_type") and not e.operation_type:
                e.operation_type = operation_type
            if hasattr(e, "operation_id") and not e.operation_id and operation_id:
                e.operation_id = operation_id
            elif not hasattr(e, "operation_type"):
                # For exceptions that don't support operation context, wrap the message
                from ktrdr.errors.exceptions import KtrdrError

                enhanced_error = KtrdrError(
                    message=str(e),
                    operation_type=operation_type,
                    operation_id=operation_id,
                    stage="execution",
                    suggestion="Check operation logs with: ktrdr operations status <operation_id>",
                )
                print_error(str(e), self.state, enhanced_error)
                raise SystemExit(1) from None

            print_error(str(e), self.state, e)
            raise SystemExit(1) from None
        finally:
            # Cleanup signal handler
            if signal_handler_registered:
                try:
                    loop.remove_signal_handler(signal.SIGINT)
                except Exception:
                    # Best-effort cleanup: ignore errors when removing signal handler
                    # during shutdown, since failure here is non-critical.
                    pass

        # Handle result based on final status
        status = op_data.get("status", "unknown")

        if status == "completed":
            self.console.print(
                f"✅ [green]{operation_type.capitalize()} completed successfully![/green]"
            )
            # Display results if available
            self._display_results(op_data, operation_type)
        elif status == "failed":
            error_msg = str(
                op_data.get("error_message", op_data.get("error", "Unknown error"))
            )
            # Create error with context
            from ktrdr.errors.exceptions import KtrdrError

            error_with_context = KtrdrError(
                message=error_msg,
                operation_type=operation_type,
                operation_id=operation_id,
                stage="completion",
                suggestion=f"Check full operation details with: ktrdr operations status {operation_id}",
            )
            print_error(
                f"{operation_type.capitalize()} failed: {error_msg}",
                self.state,
                error_with_context,
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

    def _display_results(self, op_data: dict, operation_type: str) -> None:
        """Display operation results based on type.

        Args:
            op_data: Operation data from API including result_summary.
            operation_type: Type of operation (training, backtest, etc.)
        """
        result_summary = op_data.get("result_summary", {})
        if not result_summary:
            return

        if operation_type == "training":
            self._display_training_results(result_summary)
        elif operation_type in ("backtest", "backtesting"):
            self._display_backtest_results(result_summary)

    def _display_training_results(self, result_summary: dict) -> None:
        """Display training-specific results.

        Args:
            result_summary: Training result summary from API.
        """
        training_metrics = result_summary.get("training_metrics", {})
        if not training_metrics:
            self.console.print(
                "[yellow]No training metrics were returned for this operation.[/yellow]"
            )
            return

        self.console.print("📊 [bold green]Training Results:[/bold green]")

        epochs_trained = training_metrics.get("epochs_trained")
        if epochs_trained:
            self.console.print(f"   Epochs Trained: {epochs_trained}")

        final_loss = training_metrics.get("final_loss")
        if final_loss is not None:
            self.console.print(f"   Final Loss: {final_loss:.6f}")

        final_val_loss = training_metrics.get("final_val_loss")
        if final_val_loss is not None:
            self.console.print(f"   Final Validation Loss: {final_val_loss:.6f}")

        model_path = result_summary.get("model_path")
        if model_path:
            self.console.print(f"   Model saved to: {model_path}")

    def _display_backtest_results(self, result_summary: dict) -> None:
        """Display backtest-specific results.

        Args:
            result_summary: Backtest result summary from API.
        """
        metrics = result_summary.get("metrics", {})
        if not metrics:
            self.console.print(
                "[yellow]No performance metrics were returned for this backtest.[/yellow]"
            )
            return

        self.console.print("📊 [bold green]Backtest Results:[/bold green]")

        total_return_pct = metrics.get("total_return_pct")
        if total_return_pct is not None:
            self.console.print(f"   Total Return: {total_return_pct:.2%}")

        sharpe_ratio = metrics.get("sharpe_ratio")
        if sharpe_ratio is not None:
            self.console.print(f"   Sharpe Ratio: {sharpe_ratio:.2f}")

        max_drawdown_pct = metrics.get("max_drawdown_pct")
        if max_drawdown_pct is not None:
            self.console.print(f"   Max Drawdown: {max_drawdown_pct:.2%}")

        total_trades = metrics.get("total_trades")
        if total_trades is not None:
            self.console.print(f"   Total Trades: {total_trades}")

        win_rate = metrics.get("win_rate")
        if win_rate is not None:
            self.console.print(f"   Win Rate: {win_rate:.2%}")
