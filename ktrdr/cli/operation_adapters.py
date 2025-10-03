"""
Operation adapter interface for unified CLI async operations.

This module defines the contract between the generic AsyncOperationExecutor
and domain-specific operation logic. Adapters are lightweight translators
that provide operation-specific knowledge while the executor handles all
infrastructure concerns.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from httpx import AsyncClient
from rich.console import Console
from rich.table import Table

from ktrdr.logging import get_logger

logger = get_logger(__name__)


class OperationAdapter(ABC):
    """
    Abstract interface for operation-specific logic.

    Separates generic async operation infrastructure from domain knowledge.
    Adapters are lightweight translators (~50-100 lines each) that tell the
    executor:
    - Which endpoint to call to start the operation
    - What payload to send
    - How to extract the operation_id from the response
    - How to display final results

    Example:
        class MyOperationAdapter(OperationAdapter):
            def __init__(self, param1: str, param2: int):
                self.param1 = param1
                self.param2 = param2

            def get_start_endpoint(self) -> str:
                return "/api/v1/my-operation/start"

            def get_start_payload(self) -> dict[str, Any]:
                return {"param1": self.param1, "param2": self.param2}

            def parse_start_response(self, response: dict) -> str:
                return response["data"]["operation_id"]

            async def display_results(
                self,
                final_status: dict,
                console: Console,
                http_client: AsyncClient,
            ) -> None:
                console.print(f"[green]Operation completed: {final_status}[/green]")
    """

    @abstractmethod
    def get_start_endpoint(self) -> str:
        """
        Return HTTP endpoint to start this operation.

        This should be the full path relative to the API base URL,
        e.g., "/api/v1/trainings/start" or "/api/v1/data/load"

        Returns:
            Endpoint path string
        """
        pass

    @abstractmethod
    def get_start_payload(self) -> dict[str, Any]:
        """
        Return JSON payload for the start request.

        The adapter constructs this from parameters passed to its constructor.
        It should match what the backend API expects for this operation.

        Returns:
            Dictionary containing the request payload
        """
        pass

    @abstractmethod
    def parse_start_response(self, response: dict) -> str:
        """
        Extract operation_id from the start response.

        The executor calls this to get the operation_id that will be used
        for polling the operations API.

        Args:
            response: Full response dictionary from the start endpoint

        Returns:
            The operation_id string to use for polling

        Raises:
            KeyError: If operation_id cannot be extracted from response
        """
        pass

    @abstractmethod
    async def display_results(
        self,
        final_status: dict,
        console: Console,
        http_client: AsyncClient,
    ) -> None:
        """
        Display final results after operation completes successfully.

        This is called when the operation reaches 'completed' status.
        The adapter can:
        - Fetch additional data using the http_client
        - Format and print results using the Rich console
        - Display domain-specific metrics and summaries

        Args:
            final_status: Final operation status from /operations/{id}
            console: Rich console for formatted output
            http_client: Async HTTP client for additional requests
        """
        pass


class TrainingOperationAdapter(OperationAdapter):
    """
    Adapter for neural network training operations.

    Knows how to:
    - Start training via /api/v1/trainings/start
    - Parse training response to extract operation_id
    - Fetch and display training performance metrics
    """

    def __init__(
        self,
        strategy_name: str,
        symbols: list[str],
        timeframes: list[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        validation_split: float = 0.2,
        detailed_analytics: bool = False,
    ):
        """
        Initialize training operation adapter.

        Args:
            strategy_name: Name of the strategy to train
            symbols: List of trading symbols
            timeframes: List of timeframes
            start_date: Training start date (YYYY-MM-DD)
            end_date: Training end date (YYYY-MM-DD)
            validation_split: Validation data split ratio
            detailed_analytics: Whether to enable detailed analytics
        """
        self.strategy_name = strategy_name
        self.symbols = symbols
        self.timeframes = timeframes
        self.start_date = start_date
        self.end_date = end_date
        self.validation_split = validation_split
        self.detailed_analytics = detailed_analytics

    def get_start_endpoint(self) -> str:
        """Return the training start endpoint."""
        return "/trainings/start"

    def get_start_payload(self) -> dict[str, Any]:
        """Construct training request payload."""
        payload: dict[str, Any] = {
            "strategy_name": self.strategy_name,
            "symbols": self.symbols,
            "timeframes": self.timeframes,
            "detailed_analytics": self.detailed_analytics,
        }

        # Add optional date range if provided
        if self.start_date:
            payload["start_date"] = self.start_date
        if self.end_date:
            payload["end_date"] = self.end_date

        return payload

    def parse_start_response(self, response: dict) -> str:
        """
        Extract operation_id from training start response.

        Training API returns task_id which is the operation_id.
        """
        # The training endpoint returns task_id directly in the response
        if "task_id" in response:
            return response["task_id"]
        # Fallback to data.operation_id if using standard format
        return response["data"]["operation_id"]

    async def display_results(
        self,
        final_status: dict,
        console: Console,
        http_client: AsyncClient,
    ) -> None:
        """
        Display training results with performance metrics.

        Fetches detailed training metrics from /trainings/{id}/performance
        and displays them in a formatted table.
        """
        operation_id = final_status.get("operation_id")
        console.print(
            "\n✅ [green bold]Training completed successfully![/green bold]\n"
        )

        # Fetch detailed performance metrics
        try:
            # Get performance data from training endpoint
            response = await http_client.get(
                f"/api/v1/trainings/{operation_id}/performance"
            )
            response.raise_for_status()
            perf_data = response.json()

            if not perf_data.get("success"):
                console.print("[yellow]⚠️  Could not fetch training metrics[/yellow]")
                return

            # Display training metrics in a nice table
            table = Table(title="Training Results", show_header=True)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            # Training metrics
            training_metrics = perf_data.get("training_metrics", {})
            if training_metrics:
                table.add_row(
                    "Final Training Accuracy",
                    f"{training_metrics.get('final_train_accuracy', 0):.2%}",
                )
                table.add_row(
                    "Final Validation Accuracy",
                    f"{training_metrics.get('final_val_accuracy', 0):.2%}",
                )
                table.add_row(
                    "Epochs Completed",
                    str(training_metrics.get("epochs_completed", "N/A")),
                )
                table.add_row(
                    "Training Time",
                    f"{training_metrics.get('training_time_minutes', 0):.2f} min",
                )

            # Test metrics
            test_metrics = perf_data.get("test_metrics", {})
            if test_metrics:
                table.add_row("", "")  # Separator
                table.add_row(
                    "Test Accuracy", f"{test_metrics.get('test_accuracy', 0):.2%}"
                )
                table.add_row("Precision", f"{test_metrics.get('precision', 0):.2%}")
                table.add_row("Recall", f"{test_metrics.get('recall', 0):.2%}")
                table.add_row("F1 Score", f"{test_metrics.get('f1_score', 0):.2%}")

            # Model info
            model_info = perf_data.get("model_info", {})
            if model_info:
                table.add_row("", "")  # Separator
                params = model_info.get("parameters_count", 0)
                table.add_row("Model Parameters", f"{params:,}")
                size_bytes = model_info.get("model_size_bytes", 0)
                size_mb = size_bytes / (1024 * 1024)
                table.add_row("Model Size", f"{size_mb:.2f} MB")

            console.print(table)

        except Exception as e:
            logger.warning(f"Failed to fetch training metrics: {e}")
            console.print(
                f"[yellow]⚠️  Training completed but could not fetch metrics: {e}[/yellow]"
            )


class DummyOperationAdapter(OperationAdapter):
    """
    Adapter for dummy test operations.

    Simple reference implementation showing the minimal adapter pattern.
    Used for testing and as an example for developers.
    """

    def __init__(self, duration: int = 200, iterations: int = 100):
        """
        Initialize dummy operation adapter.

        Args:
            duration: Total duration in seconds
            iterations: Number of iterations
        """
        self.duration = duration
        self.iterations = iterations

    def get_start_endpoint(self) -> str:
        """Return the dummy start endpoint."""
        return "/dummy/start"

    def get_start_payload(self) -> dict[str, Any]:
        """
        Dummy operation doesn't require payload parameters.

        The backend handles duration/iterations internally.
        """
        return {}

    def parse_start_response(self, response: dict) -> str:
        """Extract operation_id from dummy start response."""
        # Dummy endpoint returns data.operation_id
        return response["data"]["operation_id"]

    async def display_results(
        self,
        final_status: dict,
        console: Console,
        http_client: AsyncClient,
    ) -> None:
        """Display dummy operation results."""
        console.print("\n✅ [green bold]Dummy operation completed![/green bold]")
        console.print(
            f"Total iterations: {final_status.get('progress', {}).get('total_steps', 'N/A')}"
        )
        console.print(
            f"Duration: {final_status.get('metadata', {}).get('duration', 'N/A')}s"
        )

    async def display_cancellation_results(
        self,
        final_status: dict,
        console: Console,
        http_client: AsyncClient,
    ) -> None:
        """
        Display cancellation results for dummy operation.

        Optional method - if not implemented, executor shows generic cancellation message.
        This demonstrates how to display domain-specific cancellation details.
        """
        metadata = final_status.get("metadata", {})
        iterations_completed = metadata.get("iterations_completed", 0)
        total_iterations = metadata.get("total_iterations", self.iterations)

        console.print(
            f"\n[yellow]✓ Cancellation confirmed - "
            f"Completed {iterations_completed}/{total_iterations} iterations[/yellow]"
        )
