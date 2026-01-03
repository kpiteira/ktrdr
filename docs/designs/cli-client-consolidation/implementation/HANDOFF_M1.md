# Handoff: M1 — Create Client Module

## Completed Tasks

- [x] Task 1.1: Create errors module
- [x] Task 1.2: Create core module
- [x] Task 1.3: Create sync client

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

### SyncCLIClient Pattern

The sync client follows this structure:

```python
class SyncCLIClient:
    def __init__(self, base_url=None, timeout=30.0, max_retries=3, retry_delay=1.0):
        effective_url = resolve_url(base_url)
        self.config = ClientConfig(base_url=effective_url, ...)
        self._client: Optional[httpx.Client] = None

    def __enter__(self):
        self._client = httpx.Client(timeout=self.config.timeout)
        return self

    def __exit__(self, ...):
        if self._client:
            self._client.close()
            self._client = None
```

Key points:
- `_client` is `None` outside context manager
- URL resolution happens at `__init__`, not `__enter__`
- Config is immutable (`ClientConfig` is frozen dataclass)

### Retry Loop Pattern

The `_make_request` method uses a while-True loop with explicit break points:

```python
while True:
    try:
        response = self._client.request(...)
        if should_retry(response.status_code, attempt, retries):
            time.sleep(calculate_backoff(attempt, self.config.retry_delay))
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
- `TestSyncCLIClientContextManager`
- `TestSyncCLIClientHTTPMethods`
- `TestSyncCLIClientRetryBehavior`
- `TestSyncCLIClientErrorHandling`
- `TestSyncCLIClientHealthCheck`
- `TestSyncCLIClientConfiguration`

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

## Next Up

Task 1.4: Create async client (`ktrdr/cli/client/async_client.py`) with:

- `AsyncCLIClient` class
- `__aenter__` / `__aexit__` — httpx.AsyncClient lifecycle
- `async get/post/delete` methods using core functions
- `async health_check()` method
- `async execute_operation()` method (may be added in Task 1.5)

Mirror the sync client pattern but async:
- Use `httpx.AsyncClient` instead of `httpx.Client`
- Use `await` for all HTTP calls
- Use `asyncio.sleep()` instead of `time.sleep()`
