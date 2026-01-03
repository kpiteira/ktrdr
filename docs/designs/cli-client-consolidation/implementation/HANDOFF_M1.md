# Handoff: M1 — Create Client Module

## Completed Tasks

- [x] Task 1.1: Create errors module

## Emergent Patterns

### Exception Class Structure

All error classes follow this pattern:

```python
class SomeError(CLIClientError):
    """Docstring explaining when this is raised."""
    pass  # Inherits __init__ from base
```

Only override `__str__` if the string representation needs special formatting (e.g., `APIError` includes status code).

### Test Organization

Tests are organized by class with `TestClassName` pattern:
- `TestCLIClientError` — base class tests
- `TestConnectionError`, `TestTimeoutError`, `TestAPIError` — subclass tests
- `TestErrorHierarchy` — cross-cutting inheritance tests

### Import Pattern

The `__init__.py` exports errors for now. Later tasks will add clients:

```python
from ktrdr.cli.client.errors import (
    APIError,
    CLIClientError,
    ConnectionError,
    TimeoutError,
)
```

## Gotchas

### Name Shadowing

`ConnectionError` and `TimeoutError` shadow Python builtins. This is intentional per the architecture doc. When catching these in CLI code, import explicitly:

```python
from ktrdr.cli.client.errors import ConnectionError as CLIConnectionError
```

Or catch via base class:

```python
from ktrdr.cli.client import CLIClientError

try:
    ...
except CLIClientError as e:
    ...
```

## Next Up

Task 1.2: Create core module (`ktrdr/cli/client/core.py`) with:
- `ClientConfig` dataclass
- `resolve_url()` — URL priority logic
- `should_retry()` — retry decisions
- `calculate_backoff()` — exponential backoff
- `parse_response()` — response handling
- `enhance_with_ib_diagnostics()` — IB error enhancement

Reference existing implementations in:
- `ktrdr/cli/api_client.py` — URL resolution, IB diagnostics
- `ktrdr/cli/async_cli_client.py` — retry logic
