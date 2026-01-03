# Handoff: M1 — Create Client Module

## Completed Tasks

- [x] Task 1.1: Create errors module
- [x] Task 1.2: Create core module
- [x] Task 1.3: Create sync client
- [x] Task 1.4: Create async client

## Emergent Patterns

### Exception Class Structure

All error classes follow this pattern:

```python
class SomeError(CLIClientError):
    """Docstring explaining when this is raised."""
    pass  # Inherits __init__ from base
```

Only override `__str__` if the string representation needs special formatting (e.g., `APIError` includes status code).

### Core Module Design

The core module is pure functions + frozen dataclass — no I/O, no state:

```python
from ktrdr.cli.client.core import (
    ClientConfig,      # Frozen dataclass
    resolve_url,       # URL priority resolution
    should_retry,      # Retry decision (5xx only)
    calculate_backoff, # Exponential + jitter
    parse_response,    # JSON extraction, raises APIError
    enhance_with_ib_diagnostics,  # IB error enhancement
)
```

### Client Pattern (Sync & Async)

Both clients follow the same structure. The async version mirrors sync:

```python
# Sync
class SyncCLIClient:
    def __init__(...): ...
    def __enter__(self): self._client = httpx.Client(...); return self
    def __exit__(...): self._client.close(); self._client = None

# Async
class AsyncCLIClient:
    def __init__(...): ...  # Identical
    async def __aenter__(self): self._client = httpx.AsyncClient(...); return self
    async def __aexit__(...): await self._client.aclose(); self._client = None
```

Key differences:

- `httpx.Client` vs `httpx.AsyncClient`
- `close()` vs `await aclose()`
- `time.sleep()` vs `await asyncio.sleep()`
- Method calls: `self._client.request()` vs `await self._client.request()`

### Retry Loop Pattern

The `_make_request` method uses a while-True loop with explicit break points:

```python
while True:
    try:
        response = self._client.request(...)  # or await for async
        if should_retry(response.status_code, attempt, retries):
            time.sleep(calculate_backoff(...))  # or await asyncio.sleep for async
            attempt += 1
            continue
        return parse_response(response)
    except httpx.ConnectError:
        if attempt < retries:
            ...
            continue
        raise ConnectionError(...)
```

This pattern handles both HTTP-level retries (5xx) and connection-level retries uniformly.

### Test Organization

Tests organized by class/function with `TestClassName` pattern:

- `Test{Sync|Async}CLIClientContextManager`
- `Test{Sync|Async}CLIClientHTTPMethods`
- `Test{Sync|Async}CLIClientRetryBehavior`
- `Test{Sync|Async}CLIClientErrorHandling`
- `Test{Sync|Async}CLIClientHealthCheck`
- `Test{Sync|Async}CLIClientConfiguration`

## Gotchas

### Name Shadowing

`ConnectionError` and `TimeoutError` shadow Python builtins. This is intentional. Catch via base class:

```python
from ktrdr.cli.client import CLIClientError

try:
    ...
except CLIClientError as e:
    ...
```

### Backoff Implementation

The architecture doc specifies exponential backoff with jitter:

```python
base_delay * (2 ** attempt) + random(0, 1)
```

This differs from the existing `async_cli_client.py` which uses constant delay. The new implementation follows the architecture doc.

### IB Diagnostics Integration

`enhance_with_ib_diagnostics()` wraps existing functions from `ktrdr.cli.ib_diagnosis`:

- `should_show_ib_diagnosis()` — checks if IB-related
- `detect_ib_issue_from_api_response()` — returns problem_type, message, details

The enhanced dict gets an `ib_diagnosis` key with structured data.

### health_check() Design

`health_check()` is designed to never raise — it catches all exceptions and returns `bool`. Uses:

- Short timeout (5s)
- No retries (`max_retries=0`)
- Calls `/health` endpoint

### execute_operation() Placeholder

`AsyncCLIClient.execute_operation()` exists with correct signature but raises `NotImplementedError`. It will be implemented in Task 1.5.

## Next Up

Task 1.5: Create operations module (`ktrdr/cli/client/operations.py`) with:

- Port operation execution from `AsyncOperationExecutor`
- Start operation via adapter
- Poll loop with progress callbacks
- Cancellation handling
- Return final result

Reference: `ktrdr/cli/operation_executor.py`
