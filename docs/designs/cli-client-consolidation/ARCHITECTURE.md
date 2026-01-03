# CLI Client Consolidation: Architecture

## Overview

The CLI client consolidation extracts shared HTTP client logic into a core module, with thin async and sync facades that use the core. This eliminates code duplication while preserving the natural sync/async patterns of existing commands.

The core handles: URL resolution, retry with backoff, error parsing, IB diagnostics, and timeout configuration. The facades handle: httpx client lifecycle and HTTP method dispatch.

## Components

### Core (`core.py`)

**Responsibility:** All shared client logic — URL resolution, retry policy, error handling, IB diagnostics enhancement.

**Location:** `ktrdr/cli/client/core.py`

**Dependencies:**
- `ktrdr.cli.commands` (URL override state)
- `ktrdr.config.host_services` (default URL)
- `ktrdr.cli.ib_diagnosis` (diagnostic enhancement)

```python
class ClientConfig:
    """Immutable configuration for client instances."""
    base_url: str
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0

def resolve_url(explicit_url: Optional[str] = None) -> str:
    """Resolve effective URL: explicit > --url flag > config default."""

def should_retry(status_code: int, attempt: int, max_retries: int) -> bool:
    """Determine if request should be retried."""

def calculate_backoff(attempt: int, base_delay: float) -> float:
    """Calculate exponential backoff delay."""

def parse_response(response: httpx.Response) -> dict:
    """Parse response, enhance errors with IB diagnostics if applicable."""

def enhance_with_ib_diagnostics(error_data: dict) -> dict:
    """Add IB diagnostic info to error responses when relevant."""
```

### AsyncCLIClient (`async_client.py`)

**Responsibility:** Async HTTP operations with connection pooling. Includes operation execution.

**Location:** `ktrdr/cli/client/async_client.py`

**Dependencies:** `core.py`, `operations.py`, `httpx` (async)

```python
class AsyncCLIClient:
    """Async HTTP client for CLI commands."""

    async def __aenter__(self) -> "AsyncCLIClient": ...
    async def __aexit__(self, *args) -> None: ...

    async def get(self, endpoint: str, **kwargs) -> dict: ...
    async def post(self, endpoint: str, **kwargs) -> dict: ...
    async def delete(self, endpoint: str, **kwargs) -> dict: ...

    async def execute_operation(
        self,
        adapter: OperationAdapter,
        on_progress: Optional[Callable] = None,
    ) -> dict: ...

    async def health_check(self) -> bool: ...
```

### SyncCLIClient (`sync_client.py`)

**Responsibility:** Sync HTTP operations for simple request/response commands.

**Location:** `ktrdr/cli/client/sync_client.py`

**Dependencies:** `core.py`, `httpx` (sync)

```python
class SyncCLIClient:
    """Sync HTTP client for CLI commands."""

    def __enter__(self) -> "SyncCLIClient": ...
    def __exit__(self, *args) -> None: ...

    def get(self, endpoint: str, **kwargs) -> dict: ...
    def post(self, endpoint: str, **kwargs) -> dict: ...
    def delete(self, endpoint: str, **kwargs) -> dict: ...

    def health_check(self) -> bool: ...
```

### Operations (`operations.py`)

**Responsibility:** Long-running operation execution with polling, progress callbacks, and cancellation.

**Location:** `ktrdr/cli/client/operations.py`

**Dependencies:** `core.py`, operation adapters

```python
async def execute_operation(
    client: AsyncCLIClient,
    adapter: OperationAdapter,
    on_progress: Optional[Callable[[int, str], None]] = None,
    poll_interval: float = 0.3,
) -> dict:
    """Execute operation with polling loop and cancellation support."""
```

### Errors (`errors.py`)

**Responsibility:** Exception hierarchy for client errors.

**Location:** `ktrdr/cli/client/errors.py`

```python
class CLIClientError(Exception):
    """Base exception for CLI client errors."""
    message: str
    status_code: Optional[int]
    details: dict

class ConnectionError(CLIClientError):
    """Failed to connect to API server."""

class TimeoutError(CLIClientError):
    """Request timed out."""

class APIError(CLIClientError):
    """API returned an error response."""
```

### Package Init (`__init__.py`)

**Responsibility:** Public exports.

**Location:** `ktrdr/cli/client/__init__.py`

```python
from .async_client import AsyncCLIClient
from .sync_client import SyncCLIClient
from .errors import CLIClientError, ConnectionError, TimeoutError, APIError

__all__ = [
    "AsyncCLIClient",
    "SyncCLIClient",
    "CLIClientError",
    "ConnectionError",
    "TimeoutError",
    "APIError",
]
```

## Directory Structure

```
ktrdr/cli/client/
├── __init__.py       # Public exports
├── core.py           # Shared logic (URL, retry, errors, diagnostics)
├── async_client.py   # AsyncCLIClient
├── sync_client.py    # SyncCLIClient
├── operations.py     # Operation execution (async only)
└── errors.py         # Exception hierarchy
```

## Data Flow

### Simple Request (Sync)

```
Command                  SyncCLIClient              Core                    httpx
   │                          │                       │                       │
   │── client.get("/ep") ────>│                       │                       │
   │                          │── resolve_url() ─────>│                       │
   │                          │<── base_url ──────────│                       │
   │                          │                       │                       │
   │                          │── httpx.get() ───────────────────────────────>│
   │                          │<── response ──────────────────────────────────│
   │                          │                       │                       │
   │                          │── parse_response() ──>│                       │
   │                          │   (retry if needed)   │                       │
   │                          │   (enhance IB diag)   │                       │
   │                          │<── result/error ──────│                       │
   │<── result ───────────────│                       │                       │
```

### Operation Execution (Async)

```
Command              AsyncCLIClient           Operations              API
   │                      │                       │                    │
   │── execute_op() ─────>│                       │                    │
   │                      │── execute_operation()>│                    │
   │                      │                       │── POST /start ────>│
   │                      │                       │<── operation_id ───│
   │                      │                       │                    │
   │                      │                       │   ┌─── poll loop ──┐
   │                      │                       │   │ GET /op/{id}   │
   │<── on_progress ──────│<── progress ──────────│<──│ update progress│
   │                      │                       │   │ check cancel   │
   │                      │                       │   └────────────────┘
   │                      │                       │                    │
   │<── result ───────────│<── final result ──────│<── COMPLETED ──────│
```

## State Management

### Client Configuration

**Where:** `ClientConfig` dataclass in core.py, instantiated per-client

**Shape:**
```python
@dataclass(frozen=True)
class ClientConfig:
    base_url: str
    timeout: float
    max_retries: int
    retry_delay: float
```

**Transitions:** Immutable — set at client creation, never changes.

### URL Override State

**Where:** `ktrdr.cli.commands._cli_state` (existing)

**Shape:** `{"api_url": Optional[str]}`

**Transitions:** Set by Click callback when `--url` flag is used. Read by `resolve_url()`.

### HTTP Client Lifecycle

**Where:** `_client` attribute on `AsyncCLIClient`/`SyncCLIClient`

**Transitions:**
- `None` → `httpx.Client` on context manager entry
- `httpx.Client` → `None` on context manager exit (closes connection)

## Error Handling

### Connection Failures

**When:** Cannot reach API server (network error, server down)

**Response:** Raise `ConnectionError` with helpful message including URL attempted

**User experience:**
```
Error: Could not connect to API at http://localhost:8000/api/v1
Is the server running? Try: docker compose up
```

### Timeout

**When:** Request exceeds configured timeout

**Response:** Raise `TimeoutError` after all retries exhausted

**User experience:**
```
Error: Request timed out after 30s (3 attempts)
The server may be overloaded. Try again or increase timeout.
```

### API Errors (4xx/5xx)

**When:** Server returns error response

**Response:** Raise `APIError` with status code, message, and details. Enhance with IB diagnostics if applicable.

**User experience:**
```
Error: IB Gateway connection failed (400)

Diagnosis: IB Gateway is not connected
- Check that IB Gateway is running
- Verify TWS/Gateway is logged in
- Run: ktrdr ib status
```

### Retry Policy

**Retryable:** 500, 502, 503, 504 (server errors)

**Not retryable:** 4xx (client errors), connection errors after initial failure

**Backoff:** Exponential with jitter: `base_delay * (2 ** attempt) + random(0, 1)`

## Integration Points

### URL Resolution Chain

```
resolve_url(explicit_url)
    │
    ├── explicit_url provided? → use it
    │
    ├── get_api_url_override() from ktrdr.cli.commands
    │   └── Returns --url flag value if set
    │
    └── get_api_base_url() from ktrdr.config.host_services
        └── Returns config default (http://localhost:8000/api/v1)
```

### IB Diagnostics Integration

```
parse_response(response)
    │
    ├── Response OK? → return data
    │
    └── Response error?
        ├── should_show_ib_diagnosis(error_data)?
        │   └── Check if error looks IB-related
        │
        └── detect_ib_issue_from_api_response(error_data)
            └── Returns (problem_type, message, details)
```

### Operation Adapters (Existing)

Operation execution uses existing adapter pattern:

```python
class OperationAdapter(Protocol):
    def get_start_endpoint(self) -> str: ...
    def get_start_payload(self) -> dict: ...
    def extract_operation_id(self, response: dict) -> str: ...
    def get_status_endpoint(self, operation_id: str) -> str: ...
    def process_result(self, status: dict) -> dict: ...
```

Existing adapters (`TrainingAdapter`, `BacktestAdapter`) work unchanged.

## Migration Strategy

### Phase 1: Create New Module

1. Create `ktrdr/cli/client/` with all components
2. Port logic from existing clients
3. Add tests
4. Old clients remain, unchanged

### Phase 2: Migrate Commands

Migrate command by command, starting with lowest-risk:

**Low risk (sync, simple):**
- `indicator_commands.py`
- `checkpoints_commands.py`
- `strategy_commands.py`

**Medium risk (sync, IB diagnostics):**
- `ib_commands.py`
- `fuzzy_commands.py`

**Medium risk (async):**
- `agent_commands.py`
- `async_data_commands.py`

**Higher risk (operations):**
- `model_commands.py`
- `backtest_commands.py`

### Phase 3: Cleanup

1. Delete `async_cli_client.py`
2. Delete `api_client.py`
3. Delete `operation_executor.py`
4. Remove `get_api_client()` helper

## Verification Strategy

### Core Module

**Type:** Pure logic (no I/O)

**Unit Test Focus:** URL resolution priority, retry decisions, backoff calculation, error parsing, IB diagnostic detection

**Integration Test:** N/A (no external dependencies)

**Smoke Test:** N/A

### AsyncCLIClient

**Type:** I/O with connection management

**Unit Test Focus:** Context manager lifecycle, method dispatch to core

**Integration Test:** Against running API — verify retry behavior, connection reuse, timeout handling

**Smoke Test:** `ktrdr agent status` (uses async client)

### SyncCLIClient

**Type:** I/O with connection management

**Unit Test Focus:** Context manager lifecycle, method dispatch to core

**Integration Test:** Against running API — verify retry behavior, timeout handling

**Smoke Test:** `ktrdr indicators list` (uses sync client)

### Operations Module

**Type:** Async polling with state machine

**Unit Test Focus:** Poll loop logic, cancellation handling, progress callback invocation

**Integration Test:** Start real operation, verify polling works, verify cancellation

**Smoke Test:** `ktrdr model train --dry-run` (if available) or actual short training
