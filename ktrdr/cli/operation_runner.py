"""Operation runner for unified start/follow pattern.

Provides a simplified wrapper around AsyncCLIClient that supports both
fire-and-forget (return immediately with operation ID) and follow mode
(poll and display progress until completion).
"""

import asyncio
import json
import signal
from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

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
                    suggestion="Check operation logs with: ktrdr status <operation_id>",
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
                suggestion=f"Check full operation details with: ktrdr status {operation_id}",
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

        Provides consistent result formatting across all operation types.
        In JSON mode, outputs structured JSON. In human mode, uses Rich tables.

        Args:
            op_data: Operation data from API including result_summary.
            operation_type: Type of operation (training, backtest, etc.)
        """
        result_summary = op_data.get("result_summary") or {}

        # Extract results based on operation type
        results = self._extract_results(result_summary, operation_type)

        if self.state.json_mode:
            self._display_results_json(operation_type, results)
        else:
            self._display_results_human(operation_type, results)

    def _extract_results(
        self, result_summary: dict[str, Any], operation_type: str
    ) -> dict[str, Any]:
        """Extract normalized results from result_summary based on operation type.

        Args:
            result_summary: Raw result summary from API.
            operation_type: Type of operation.

        Returns:
            Normalized results dictionary.
        """
        if operation_type == "training":
            training_metrics = result_summary.get("training_metrics", {})
            results = {
                "epochs_trained": training_metrics.get("epochs_trained"),
                "final_loss": training_metrics.get("final_loss"),
                "final_val_loss": training_metrics.get("final_val_loss"),
            }
            if result_summary.get("model_path"):
                results["model_path"] = result_summary.get("model_path")
            # Remove None values
            return {k: v for k, v in results.items() if v is not None}

        elif operation_type in ("backtest", "backtesting"):
            metrics = result_summary.get("metrics", {})
            if metrics:
                return {
                    k: v
                    for k, v in {
                        "total_return_pct": metrics.get("total_return_pct"),
                        "sharpe_ratio": metrics.get("sharpe_ratio"),
                        "max_drawdown_pct": metrics.get("max_drawdown_pct"),
                        "total_trades": metrics.get("total_trades"),
                        "win_rate": metrics.get("win_rate"),
                    }.items()
                    if v is not None
                }
            return {}

        else:
            # For unknown operation types, return the full result_summary
            return result_summary

    def _display_results_json(
        self, operation_type: str, results: dict[str, Any]
    ) -> None:
        """Display results in JSON format.

        Args:
            operation_type: Type of operation.
            results: Extracted results dictionary.
        """
        output = {
            "operation_type": operation_type,
            "results": results,
        }
        print(json.dumps(output, indent=2, default=str))

    def _display_results_human(
        self,
        operation_type: str,
        results: dict[str, Any],
    ) -> None:
        """Display results in human-readable format.

        Args:
            operation_type: Type of operation.
            results: Extracted results dictionary.
        """
        if not results:
            self.console.print(
                f"[yellow]No results were returned for this {operation_type}.[/yellow]"
            )
            return

        # Use operation-specific display methods for better formatting
        if operation_type == "training":
            self._display_training_results_human(results)
        elif operation_type in ("backtest", "backtesting"):
            self._display_backtest_results_human(results)
        else:
            self._display_generic_results_human(operation_type, results)

    def _display_training_results_human(self, results: dict[str, Any]) -> None:
        """Display training-specific results in human-readable format.

        Args:
            results: Extracted training results.
        """
        self.console.print("📊 [bold green]Training Results:[/bold green]")

        if "epochs_trained" in results:
            self.console.print(f"   Epochs Trained: {results['epochs_trained']}")

        if "final_loss" in results:
            self.console.print(f"   Final Loss: {results['final_loss']:.6f}")

        if "final_val_loss" in results:
            self.console.print(
                f"   Final Validation Loss: {results['final_val_loss']:.6f}"
            )

        if "model_path" in results:
            self.console.print(f"   Model saved to: {results['model_path']}")

    def _display_backtest_results_human(self, results: dict[str, Any]) -> None:
        """Display backtest-specific results in human-readable format.

        Args:
            results: Extracted backtest results.
        """
        self.console.print("📊 [bold green]Backtest Results:[/bold green]")

        if "total_return_pct" in results:
            self.console.print(f"   Total Return: {results['total_return_pct']:.2%}")

        if "sharpe_ratio" in results:
            self.console.print(f"   Sharpe Ratio: {results['sharpe_ratio']:.2f}")

        if "max_drawdown_pct" in results:
            self.console.print(f"   Max Drawdown: {results['max_drawdown_pct']:.2%}")

        if "total_trades" in results:
            self.console.print(f"   Total Trades: {results['total_trades']}")

        if "win_rate" in results:
            self.console.print(f"   Win Rate: {results['win_rate']:.2%}")

    def _display_generic_results_human(
        self, operation_type: str, results: dict[str, Any]
    ) -> None:
        """Display generic results for unknown operation types.

        Uses a Rich table for consistent presentation of any result structure.

        Args:
            operation_type: Type of operation.
            results: Results dictionary.
        """
        title = f"{operation_type.replace('_', ' ').title()} Results"
        self.console.print(f"📊 [bold green]{title}:[/bold green]")

        table = Table(show_header=False, box=None, padding=(0, 2, 0, 3))
        table.add_column("Key", style="cyan")
        table.add_column("Value")

        for key, value in results.items():
            display_key = key.replace("_", " ").title()
            if isinstance(value, float):
                key_lower = key.lower()
                if "pct" in key_lower or "rate" in key_lower:
                    display_value = f"{value:.2%}"
                else:
                    display_value = f"{value:.4g}"
            elif isinstance(value, dict):
                display_value = json.dumps(value, default=str)
            else:
                display_value = str(value)
            table.add_row(display_key, display_value)

        self.console.print(table)
