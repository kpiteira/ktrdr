# ServiceOrchestrator Pattern - Developer Guide

**Quick Reference**: How to build async services using the Service Orchestrator pattern

---

## When to Use ServiceOrchestrator

Use the ServiceOrchestrator pattern when building services that:
- ✅ Have long-running async operations (>5 seconds)
- ✅ Need progress reporting to users
- ✅ Should support cancellation
- ✅ Route between local and host service execution
- ✅ Integrate with OperationsService for tracking

## Quick Start

### 1. Inherit from ServiceOrchestrator

```python
from ktrdr.async_infrastructure.service_orchestrator import ServiceOrchestrator
from ktrdr.my_domain.my_adapter import MyAdapter

class MyService(ServiceOrchestrator[MyAdapter]):
    """My service with ServiceOrchestrator integration."""

    def __init__(self):
        super().__init__()
        self._progress_renderer = MyProgressRenderer()

    def _initialize_adapter(self) -> MyAdapter:
        """Initialize domain-specific adapter."""
        use_host = os.getenv("USE_MY_HOST_SERVICE", "false").lower() == "true"
        return MyAdapter(use_host_service=use_host)

    def _get_service_name(self) -> str:
        return "MyService"
```

### 2. Create Progress Renderer

```python
from ktrdr.async_infrastructure.progress import (
    ProgressRenderer,
    GenericProgressState
)

class MyProgressRenderer(ProgressRenderer):
    """Domain-specific progress message formatting."""

    def render_message(self, state: GenericProgressState) -> str:
        """Render rich progress message with domain context."""
        # Extract domain-specific context
        item_name = state.context.get("item_name", "Unknown")
        operation_mode = state.context.get("mode", "")

        # Build enhanced message
        if operation_mode:
            return f"{state.message} ({item_name}, {operation_mode} mode)"
        return f"{state.message} ({item_name})"

    def enhance_state(self, state: GenericProgressState) -> GenericProgressState:
        """Optionally enhance state (usually return unchanged)."""
        return state
```

### 3. Use start_managed_operation()

```python
class MyService(ServiceOrchestrator[MyAdapter]):

    async def perform_operation(
        self,
        item_name: str,
        parameters: dict,
        **kwargs
    ) -> dict:
        """Public API method that users call."""

        # Build operation context
        context = self._build_context(item_name, parameters)

        # Start managed operation through ServiceOrchestrator
        return await self.start_managed_operation(
            operation_type=OperationType.MY_OPERATION,
            operation_name=f"process_{item_name}",
            total_steps=context.estimated_steps,
            metadata=context.metadata,
            operation_func=self._execute_operation,
            context=context,
        )

    async def _execute_operation(
        self,
        context: MyOperationContext,
        progress_manager: GenericProgressManager,
        cancellation_token: CancellationToken,
    ) -> dict:
        """
        Private execution method.

        This is where your actual work happens. ServiceOrchestrator
        provides progress_manager and cancellation_token for you.
        """

        # Update progress
        progress_manager.update_progress(
            current_step=1,
            total_steps=context.estimated_steps,
            percentage=10.0,
            message="Starting operation",
            context={"item_name": context.item_name, "mode": "processing"}
        )

        # Check cancellation
        if cancellation_token.is_cancelled():
            raise CancellationError("Operation cancelled")

        # Perform work
        result = await self.adapter.do_work(
            item_name=context.item_name,
            cancellation_token=cancellation_token
        )

        # Final progress update
        progress_manager.update_progress(
            current_step=context.estimated_steps,
            total_steps=context.estimated_steps,
            percentage=100.0,
            message="Operation complete"
        )

        return result
```

---

## Common Patterns

### Simple Delegation Pattern (Training Style)

**When to use**: Single-block operations that delegate to an adapter

```python
class TrainingService(ServiceOrchestrator[TrainingAdapter]):
    """Simple delegation: one call to adapter."""

    async def _execute_operation(
        self,
        context: TrainingContext,
        progress_manager: GenericProgressManager,
        cancellation_token: CancellationToken,
    ) -> dict:
        # Single delegation to adapter or runner
        if context.use_host_service:
            runner = HostSessionManager(...)
        else:
            runner = LocalTrainingRunner(...)

        return await runner.run()
```

**Characteristics**:
- Minimal orchestration logic
- Complexity handled by adapter or runner
- Progress forwarded from underlying execution
- Clean separation of concerns

### Complex Orchestration Pattern (Data Style)

**When to use**: Multi-step operations requiring job coordination

```python
class DataManager(ServiceOrchestrator[IbDataAdapter]):
    """Complex orchestration: multi-step job management."""

    async def _execute_operation(
        self,
        context: DataContext,
        progress_manager: GenericProgressManager,
        cancellation_token: CancellationToken,
    ) -> pd.DataFrame:
        # Step 1: Gap analysis
        progress_manager.update_progress(
            current_step=1,
            message="Analyzing data gaps",
            context={"phase": "gap_analysis"}
        )
        gaps = await self._analyze_gaps(context)

        # Step 2: Create jobs
        progress_manager.update_progress(
            current_step=2,
            message="Creating load jobs",
            context={"phase": "job_creation"}
        )
        jobs = self._create_jobs(gaps)

        # Step 3: Execute jobs with job manager
        progress_manager.update_progress(
            current_step=3,
            message="Loading data segments",
            context={"phase": "data_loading"}
        )
        results = await self.job_manager.execute_jobs(
            jobs,
            cancellation_token=cancellation_token
        )

        # Step 4: Combine results
        return self._combine_results(results)
```

**Characteristics**:
- Multiple orchestration steps
- Job coordination and management
- Complex progress tracking
- Detailed phase reporting

---

## Progress Management

### Updating Progress

```python
# Simple progress update
progress_manager.update_progress(
    current_step=5,
    total_steps=10,
    percentage=50.0,
    message="Processing items",
)

# Progress with rich context
progress_manager.update_progress(
    current_step=5,
    total_steps=10,
    percentage=50.0,
    message="Processing items",
    items_processed=250,
    total_items=500,
    context={
        "item_name": "AAPL",
        "timeframe": "1h",
        "mode": "backfill",
        "current_segment": 3,
        "total_segments": 5,
    }
)
```

### Progress Context Guidelines

**DO** include:
- Domain-specific identifiers (symbol, strategy_name, etc.)
- Operation modes (backfill, live, training, etc.)
- Current item being processed
- Granular progress (segments, epochs, batches)
- Performance metrics (bars_fetched, gpu_utilization, etc.)

**DON'T** include:
- Large data structures
- Sensitive information
- Implementation details users don't care about

---

## Cancellation Handling

### Checking Cancellation

```python
# Simple check
if cancellation_token.is_cancelled():
    raise CancellationError("Operation cancelled by user")

# Check in loops (frequent operations)
for item in items:
    if cancellation_token.is_cancelled():
        raise CancellationError(f"Operation cancelled at item {item}")

    process_item(item)

# Check in loops (infrequent - with stride)
for i, item in enumerate(items):
    if i % 10 == 0 and cancellation_token.is_cancelled():
        raise CancellationError(f"Operation cancelled at item {i}")

    process_expensive_item(item)
```

### Passing Cancellation Tokens

```python
# Always pass cancellation token to underlying operations
class MyService(ServiceOrchestrator[MyAdapter]):

    async def _execute_operation(
        self,
        context: MyContext,
        progress_manager: GenericProgressManager,
        cancellation_token: CancellationToken,  # Provided by ServiceOrchestrator
    ) -> dict:

        # Pass to adapter
        result = await self.adapter.do_work(
            item=context.item,
            cancellation_token=cancellation_token,  # Pass through
        )

        # Pass to job manager
        await self.job_manager.execute_jobs(
            jobs,
            cancellation_token=cancellation_token,  # Pass through
        )

        return result
```

### Cancellation Best Practices

**Performance vs Responsiveness**:
- Epoch/segment boundaries: Low overhead, moderate responsiveness
- Every N iterations: Balanced (recommended)
- Every iteration: High overhead, maximum responsiveness

**Cleanup on Cancellation**:
```python
try:
    await self._execute_operation(...)
except CancellationError:
    # Clean up resources
    await self._cleanup_resources()
    raise  # Re-raise for ServiceOrchestrator to handle
```

---

## Common Patterns & Recipes

### Pattern 1: Local vs Host Service Routing

```python
class MyService(ServiceOrchestrator[MyAdapter]):

    def _should_use_host_service(self) -> bool:
        """Determine execution mode from environment."""
        return os.getenv("USE_MY_HOST_SERVICE", "false").lower() == "true"

    async def _execute_operation(
        self,
        context: MyContext,
        progress_manager: GenericProgressManager,
        cancellation_token: CancellationToken,
    ) -> dict:
        if self._should_use_host_service():
            return await self._execute_on_host(context, progress_manager, cancellation_token)
        else:
            return await self._execute_locally(context, progress_manager, cancellation_token)
```

### Pattern 2: Progress Bridging

For operations that have their own progress callbacks:

```python
class MyProgressBridge:
    """Translate domain callbacks to GenericProgressManager updates."""

    def __init__(
        self,
        progress_manager: GenericProgressManager,
        cancellation_token: CancellationToken,
    ):
        self._manager = progress_manager
        self._token = cancellation_token

    def on_item_processed(self, item_index: int, total: int, metrics: dict):
        """Called by underlying operation."""
        if self._token.is_cancelled():
            raise CancellationError("Operation cancelled")

        percentage = (item_index / max(1, total)) * 100.0

        self._manager.update_progress(
            current_step=item_index,
            total_steps=total,
            percentage=percentage,
            message=f"Processing item {item_index}/{total}",
            context={
                "item_index": item_index,
                "metrics": metrics,
            }
        )

# Usage
bridge = MyProgressBridge(progress_manager, cancellation_token)
await underlying_operation(callback=bridge.on_item_processed)
```

### Pattern 3: Polling Remote Operations

For host services that require polling:

```python
async def _poll_remote_operation(
    self,
    session_id: str,
    progress_manager: GenericProgressManager,
    cancellation_token: CancellationToken,
    poll_interval: float = 2.0,
) -> dict:
    """Poll remote operation until complete."""

    while True:
        # Check cancellation
        if cancellation_token.is_cancelled():
            await self._cancel_remote_operation(session_id)
            raise CancellationError("Operation cancelled")

        # Get status
        snapshot = await self.adapter.get_status(session_id)

        # Update progress
        progress_manager.update_progress(
            percentage=snapshot.get("progress_percent", 0.0),
            message=snapshot.get("message", "Processing"),
            context={"remote_status": snapshot}
        )

        # Check terminal states
        status = snapshot.get("status")
        if status == "completed":
            return snapshot
        elif status == "failed":
            raise RuntimeError(f"Remote operation failed: {snapshot.get('error')}")

        # Wait before next poll
        await asyncio.sleep(poll_interval)
```

---

## Do's and Don'ts

### ✅ DO

- Inherit from `ServiceOrchestrator[YourAdapter]`
- Use `start_managed_operation()` for all async operations
- Implement domain-specific `ProgressRenderer`
- Check cancellation at appropriate boundaries
- Pass `cancellation_token` to all underlying operations
- Provide rich context in progress updates
- Use immutable context objects (dataclasses with `frozen=True`)
- Handle errors gracefully and let ServiceOrchestrator manage final state

### ❌ DON'T

- Create manual `asyncio.create_task()` wrappers
- Bypass `OperationsService` integration
- Implement custom progress tracking
- Ignore cancellation tokens
- Put large data in progress context
- Modify context objects after creation
- Swallow `CancellationError` exceptions
- Mix sync and async code without proper `asyncio.to_thread()`

---

## Testing Your ServiceOrchestrator

### Unit Test Example

```python
import pytest
from unittest.mock import Mock, AsyncMock

async def test_my_service_operation():
    # Arrange
    service = MyService()
    service.adapter = AsyncMock()
    service.adapter.do_work.return_value = {"result": "success"}

    # Act
    result = await service.perform_operation(
        item_name="test_item",
        parameters={"param1": "value1"}
    )

    # Assert
    assert result["operation_id"]
    assert result["status"] == "completed"
    service.adapter.do_work.assert_called_once()

async def test_my_service_cancellation():
    # Arrange
    service = MyService()
    service.adapter = AsyncMock()
    service.adapter.do_work.side_effect = asyncio.CancelledError()

    # Act & Assert
    with pytest.raises(asyncio.CancelledError):
        await service.perform_operation(
            item_name="test_item",
            parameters={}
        )
```

---

## Complete Example

See [TrainingService](../../../ktrdr/api/services/training_service.py) for a complete reference implementation using the simple delegation pattern.

See [DataManager](../../../ktrdr/data/data_manager.py) for a complete reference implementation using the complex orchestration pattern.

---

## Further Reading

- [ARCHITECTURE.md](../ARCHITECTURE.md) - Complete async architecture specification
- [IMPLEMENTATION-STATUS.md](../IMPLEMENTATION-STATUS.md) - Current implementation status
- [ServiceOrchestrator source code](../../../ktrdr/async_infrastructure/service_orchestrator.py)
