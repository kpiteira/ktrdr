# Adding New Async Operations to the CLI

This guide explains how to add new async operations (like training, data loading, etc.) to the KTRDR CLI using the unified operations pattern.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Step-by-Step Guide](#step-by-step-guide)
- [Adapter Interface Reference](#adapter-interface-reference)
- [Examples](#examples)
- [Testing Your Operation](#testing-your-operation)
- [Best Practices](#best-practices)

## Overview

The KTRDR CLI uses a unified pattern for all async operations. This pattern separates:

- **Generic infrastructure** (HTTP, polling, cancellation, progress) - handled by `AsyncOperationExecutor`
- **Domain-specific logic** (endpoints, payloads, result display) - handled by `OperationAdapter`

This separation means you can add new async operations by writing a simple adapter (~50-100 lines) without duplicating infrastructure code.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              CLI Command Layer                       │
│           (your_command.py)                          │
│                                                      │
│  Responsibility:                                     │
│  • Parse command-line arguments                      │
│  • Create adapter with parameters                    │
│  • Invoke AsyncOperationExecutor                     │
└────────────────────┬────────────────────────────────┘
                     │
                     │ Creates and passes
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│          AsyncOperationExecutor                      │
│              (Generic Infrastructure)                │
│                                                      │
│  • Manages HTTP client lifecycle                     │
│  • Polls operations API until completion             │
│  • Displays progress bar                             │
│  • Handles Ctrl+C cancellation                       │
│  • Invokes adapter for domain logic                  │
└────────────────────┬────────────────────────────────┘
                     │
                     │ Delegates via interface
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│         YourOperationAdapter                         │
│          (Domain-Specific Logic)                     │
│                                                      │
│  • Knows operation endpoint                          │
│  • Constructs request payload                        │
│  • Displays operation results                        │
└─────────────────────────────────────────────────────┘
```

## Step-by-Step Guide

### Step 1: Create Your Adapter

Create a new adapter class in `ktrdr/cli/operation_adapters.py`:

```python
from ktrdr.cli.operation_adapters import OperationAdapter

class MyOperationAdapter(OperationAdapter):
    """Adapter for my custom operation."""

    def __init__(self, param1: str, param2: int):
        """
        Initialize adapter with operation parameters.

        Args:
            param1: Description of param1
            param2: Description of param2
        """
        self.param1 = param1
        self.param2 = param2

    def get_start_endpoint(self) -> str:
        """Return endpoint to start this operation."""
        return "/api/v1/my-operation/start"

    def get_start_payload(self) -> dict[str, Any]:
        """Construct request payload from parameters."""
        return {
            "param1": self.param1,
            "param2": self.param2,
        }

    def parse_start_response(self, response: dict) -> str:
        """Extract operation_id from start response."""
        return response["data"]["operation_id"]

    async def display_results(
        self,
        final_status: dict,
        console: Console,
        http_client: AsyncClient,
    ) -> None:
        """Display operation results after completion."""
        # Extract results from final_status
        result_data = final_status.get("result", {})

        # Display using Rich console
        console.print("[green]✓[/green] Operation completed successfully!")
        console.print(f"Result: {result_data}")
```

### Step 2: Create Your Command Function

Add your command in a new or existing CLI module (e.g., `ktrdr/cli/my_commands.py`):

```python
import typer
import asyncio
from rich.console import Console

from ktrdr.cli.operation_executor import AsyncOperationExecutor
from ktrdr.cli.operation_adapters import MyOperationAdapter

app = typer.Typer()
console = Console()


@app.command()
def my_operation(
    param1: str = typer.Argument(..., help="First parameter"),
    param2: int = typer.Option(10, help="Second parameter"),
    api_url: str = typer.Option(
        "http://localhost:8000",
        envvar="KTRDR_API_URL",
        help="API server URL"
    ),
):
    """
    Execute my custom async operation.

    This command demonstrates how to add a new async operation
    using the unified operations pattern.
    """
    asyncio.run(_my_operation_async(param1, param2, api_url))


async def _my_operation_async(param1: str, param2: int, api_url: str):
    """Async wrapper for my_operation command."""
    # Print operation header
    console.print(f"[bold]Starting My Operation[/bold]")
    console.print(f"Param1: {param1}")
    console.print(f"Param2: {param2}")
    console.print()

    # Create adapter with parameters
    adapter = MyOperationAdapter(param1=param1, param2=param2)

    # Create executor
    executor = AsyncOperationExecutor(base_url=api_url)

    # Execute operation
    success = await executor.execute_operation(
        adapter=adapter,
        console=console,
        options={"show_progress": True},
    )

    # Exit with appropriate code
    import sys
    sys.exit(0 if success else 1)
```

### Step 3: Register Your Command

Add your command to the main CLI in `ktrdr/cli/main.py`:

```python
from ktrdr.cli.my_commands import app as my_app

# Add to main CLI
main_app.add_typer(my_app, name="my")
```

### Step 4: Test Your Operation

```bash
# Test your new command
ktrdr my my-operation "test-value" --param2 42

# Test cancellation (press Ctrl+C during execution)
ktrdr my my-operation "test-value" --param2 100
```

## Adapter Interface Reference

### Required Methods

All adapters must implement these four methods:

#### `get_start_endpoint() -> str`

Returns the HTTP endpoint to start this operation.

**Example:**
```python
def get_start_endpoint(self) -> str:
    return "/api/v1/trainings/start"
```

#### `get_start_payload() -> dict[str, Any]`

Returns the JSON payload for the start request.

**Example:**
```python
def get_start_payload(self) -> dict[str, Any]:
    return {
        "strategy_name": self.strategy_name,
        "symbols": self.symbols,
        "timeframes": self.timeframes,
    }
```

#### `parse_start_response(response: dict) -> str`

Extracts the operation_id from the start response.

**Example:**
```python
def parse_start_response(self, response: dict) -> str:
    # Most operations use this format
    return response["data"]["operation_id"]

    # Or handle custom response format
    return response.get("session_id") or response["data"]["operation_id"]
```

#### `async display_results(final_status: dict, console: Console, http_client: AsyncClient) -> None`

Displays final results after operation completes successfully.

**Example:**
```python
async def display_results(
    self,
    final_status: dict,
    console: Console,
    http_client: AsyncClient,
) -> None:
    # Option 1: Display data from final_status directly
    result = final_status.get("result", {})
    console.print(f"[green]✓[/green] Success! Result: {result}")

    # Option 2: Fetch additional data from API
    response = await http_client.get(f"/api/v1/my-operation/{operation_id}/details")
    details = response.json()

    # Display with Rich formatting
    from rich.table import Table
    table = Table(title="Operation Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    for key, value in details.items():
        table.add_row(key, str(value))
    console.print(table)
```

### Optional Methods

#### `display_cancellation_results(final_status: dict, console: Console, http_client: AsyncClient) -> None`

Called when operation is cancelled. If not implemented, executor shows default message.

**Example:**
```python
async def display_cancellation_results(
    self,
    final_status: dict,
    console: Console,
    http_client: AsyncClient,
) -> None:
    iterations = final_status.get("metadata", {}).get("iterations_completed", 0)
    total = final_status.get("metadata", {}).get("total_iterations", 0)
    console.print(f"[yellow]Cancelled after {iterations}/{total} iterations[/yellow]")
```

## Examples

### Example 1: Simple Adapter (Dummy Operation)

The simplest possible adapter:

```python
class DummyOperationAdapter(OperationAdapter):
    """Reference implementation - simplest adapter."""

    def __init__(self, duration: int, iterations: int):
        self.duration = duration
        self.iterations = iterations

    def get_start_endpoint(self) -> str:
        return "/api/v1/dummy/start"

    def get_start_payload(self) -> dict[str, Any]:
        return {"duration": self.duration, "iterations": self.iterations}

    def parse_start_response(self, response: dict) -> str:
        return response["data"]["operation_id"]

    async def display_results(
        self,
        final_status: dict,
        console: Console,
        http_client: AsyncClient,
    ) -> None:
        iterations = final_status.get("metadata", {}).get("iterations_completed", 0)
        console.print(f"[green]✓[/green] Completed {iterations} iterations")
```

### Example 2: Complex Adapter (Training Operation)

A more complex adapter that fetches additional data:

```python
class TrainingOperationAdapter(OperationAdapter):
    """Adapter for training operations."""

    def __init__(
        self,
        strategy_name: str,
        symbols: list[str],
        timeframes: list[str],
        start_date: str | None,
        end_date: str | None,
    ):
        self.strategy_name = strategy_name
        self.symbols = symbols
        self.timeframes = timeframes
        self.start_date = start_date
        self.end_date = end_date

    def get_start_endpoint(self) -> str:
        return "/api/v1/trainings/start"

    def get_start_payload(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "symbols": self.symbols,
            "timeframes": self.timeframes,
            "start_date": self.start_date,
            "end_date": self.end_date,
        }

    def parse_start_response(self, response: dict) -> str:
        return response["data"]["operation_id"]

    async def display_results(
        self,
        final_status: dict,
        console: Console,
        http_client: AsyncClient,
    ) -> None:
        # Extract training_id from final status
        training_id = final_status.get("result", {}).get("training_id")

        # Fetch detailed metrics
        response = await http_client.get(
            f"/api/v1/trainings/{training_id}/performance"
        )
        metrics = response.json()["data"]

        # Display results
        console.print("[green]✓[/green] Training completed successfully!")
        console.print(f"\nAccuracy: {metrics['accuracy']:.2%}")
        console.print(f"Precision: {metrics['precision']:.2%}")
        console.print(f"Recall: {metrics['recall']:.2%}")
        console.print(f"F1 Score: {metrics['f1']:.2%}")
```

## Testing Your Operation

### Unit Tests

Create unit tests for your adapter in `tests/unit/cli/test_my_adapter.py`:

```python
import pytest
from ktrdr.cli.operation_adapters import MyOperationAdapter


class TestMyOperationAdapter:
    def test_get_start_endpoint(self):
        adapter = MyOperationAdapter(param1="test", param2=42)
        assert adapter.get_start_endpoint() == "/api/v1/my-operation/start"

    def test_get_start_payload(self):
        adapter = MyOperationAdapter(param1="test", param2=42)
        payload = adapter.get_start_payload()
        assert payload["param1"] == "test"
        assert payload["param2"] == 42

    def test_parse_start_response(self):
        adapter = MyOperationAdapter(param1="test", param2=42)
        response = {"data": {"operation_id": "op-123"}}
        operation_id = adapter.parse_start_response(response)
        assert operation_id == "op-123"
```

### Integration Tests

Test the full command flow in `tests/integration/cli/test_my_operation.py`:

```python
import pytest
from click.testing import CliRunner
from ktrdr.cli.my_commands import app


class TestMyOperationIntegration:
    def test_my_operation_success(self, mock_api_server):
        """Test successful operation execution."""
        runner = CliRunner()
        result = runner.invoke(app, ["my-operation", "test", "--param2", "42"])
        assert result.exit_code == 0
        assert "completed successfully" in result.output.lower()

    def test_my_operation_cancellation(self, mock_api_server):
        """Test operation cancellation."""
        # Test Ctrl+C handling
        # (implementation depends on your test setup)
        pass
```

### Manual Testing

```bash
# Start your API server
ktrdr api start

# Test your command
ktrdr my my-operation "test-value" --param2 42

# Test with different parameters
ktrdr my my-operation "another-test" --param2 100

# Test cancellation (press Ctrl+C during execution)
ktrdr my my-operation "long-running" --param2 1000
```

## Best Practices

### 1. Keep Adapters Simple

✅ **DO**: Keep adapters focused on data transformation
```python
def get_start_payload(self) -> dict[str, Any]:
    return {"symbols": self.symbols, "timeframe": self.timeframe}
```

❌ **DON'T**: Put complex logic in adapters
```python
def get_start_payload(self) -> dict[str, Any]:
    # Too much logic - move to service layer
    processed_symbols = self._validate_and_process_symbols()
    optimized_config = self._optimize_configuration()
    return {"symbols": processed_symbols, "config": optimized_config}
```

### 2. Use Type Hints

✅ **DO**: Add type hints for clarity
```python
def __init__(self, symbols: list[str], timeframe: str):
    self.symbols = symbols
    self.timeframe = timeframe
```

❌ **DON'T**: Omit type information
```python
def __init__(self, symbols, timeframe):
    self.symbols = symbols
    self.timeframe = timeframe
```

### 3. Document Your Adapter

✅ **DO**: Add clear docstrings
```python
class MyOperationAdapter(OperationAdapter):
    """
    Adapter for my custom operation.

    This adapter handles communication with the my-operation API endpoint,
    constructing requests and displaying results.
    """

    def __init__(self, param1: str, param2: int):
        """
        Initialize adapter with operation parameters.

        Args:
            param1: Description of what param1 does
            param2: Description of what param2 does
        """
```

### 4. Handle Errors Gracefully

✅ **DO**: Provide helpful error messages
```python
async def display_results(self, final_status: dict, console: Console, http_client: AsyncClient) -> None:
    result = final_status.get("result")
    if not result:
        console.print("[red]Error: No result data available[/red]")
        return

    # Display results...
```

### 5. Use Rich Console Features

✅ **DO**: Leverage Rich for better output
```python
from rich.table import Table
from rich.panel import Panel

async def display_results(self, final_status: dict, console: Console, http_client: AsyncClient) -> None:
    # Use tables for structured data
    table = Table(title="Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    # ...

    # Use panels for emphasis
    console.print(Panel("[green]Operation completed successfully![/green]"))
```

### 6. Test Thoroughly

✅ **DO**: Test all code paths
- Happy path (success)
- Error cases
- Cancellation
- Edge cases (empty data, missing fields, etc.)

### 7. Follow Existing Patterns

✅ **DO**: Study existing adapters for consistency
- `TrainingOperationAdapter` - Complex adapter with additional API calls
- `DummyOperationAdapter` - Simple reference implementation

## Related Documentation

- [CLI Architecture](../architecture/cli/unified_cli_operations_design.md) - Detailed architecture documentation
- [Operations API](../api/ENDPOINT_REFERENCE.md) - Operations API reference
- [Testing Guide](../developer/testing-guide.md) - Testing guidelines

## Questions or Issues?

If you encounter issues or have questions:
1. Check the [existing adapters](../../ktrdr/cli/operation_adapters.py) for examples
2. Review the [design document](../architecture/cli/unified_cli_operations_design.md)
3. Open an issue on GitHub with the `cli` label
