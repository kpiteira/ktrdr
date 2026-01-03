# Handoff: M1 — Create Client Module

## Completed Tasks

- [x] Task 1.1: Create errors module
- [x] Task 1.2: Create core module

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

### Test Organization

Tests organized by class/function with `TestClassName` pattern.

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

## Next Up

Task 1.3: Create sync client (`ktrdr/cli/client/sync_client.py`) with:

- `SyncCLIClient` class
- `__enter__` / `__exit__` — httpx.Client lifecycle
- `get/post/delete` methods using core functions
- `health_check()` method

Key integration points:

- Use `ClientConfig` from core
- Use `resolve_url()` for base URL
- Use `parse_response()` for all responses
- Use `should_retry()` + `calculate_backoff()` for retry logic
- Raise errors from `errors.py`
