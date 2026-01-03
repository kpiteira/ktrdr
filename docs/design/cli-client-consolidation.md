# CLI Client Consolidation Design

## Overview

This document outlines a complete refactor to consolidate the three CLI API clients (`AsyncCLIClient`, `KtrdrApiClient`, `AsyncOperationExecutor`) into a single unified client.

## Current State Analysis

### Existing Clients

| Client | Location | Pattern | Used By |
|--------|----------|---------|---------|
| `AsyncCLIClient` | `async_cli_client.py` | Async context manager | agent_commands, data_commands (partial), model_commands (partial), async_data_commands |
| `KtrdrApiClient` | `api_client.py` | Sync wrapper over async | indicator_commands, checkpoints_commands, fuzzy_commands, ib_commands, operations_commands, strategy_commands, data_commands (partial), model_commands (partial) |
| `AsyncOperationExecutor` | `operation_executor.py` | Async with polling loop | Training/backtest execution via adapters |

### Feature Matrix

| Feature | AsyncCLIClient | KtrdrApiClient | AsyncOperationExecutor |
|---------|----------------|----------------|------------------------|
| Async native | ✅ | ❌ (sync wrapper) | ✅ |
| Connection reuse | ✅ | ❌ | ✅ |
| Retry logic | ✅ | ✅ | ❌ |
| IB diagnostics | ❌ | ✅ | ❌ |
| Progress polling | ❌ | ❌ | ✅ |
| Signal handling (Ctrl+C) | ❌ | ❌ | ✅ |
| URL override (`--url`) | ✅ | ✅ (added) | ✅ (added) |
| Timeout config | ✅ | ✅ | ✅ |

### Code Duplication

Both `AsyncCLIClient` and `KtrdrApiClient` implement:
- URL resolution logic (now in 3 places)
- Retry with exponential backoff
- Error response parsing
- Timeout handling
- HTTP client lifecycle

`AsyncOperationExecutor` adds:
- Operation polling loop
- Progress display integration
- Cancellation handling

## Target Architecture

### Single Unified Client: `CLIClient`

```
ktrdr/cli/
├── client/
│   ├── __init__.py          # Public exports
│   ├── base.py              # CLIClient class
│   ├── operations.py        # OperationMixin for long-running ops
│   ├── diagnostics.py       # IB diagnostics mixin
│   └── errors.py            # CLIClientError exceptions
├── commands.py              # URL state (unchanged)
└── [command modules]        # Use CLIClient
```

### CLIClient Design

```python
# ktrdr/cli/client/base.py

class CLIClient:
    """
    Unified async HTTP client for all CLI commands.

    Features:
    - Async context manager with connection pooling
    - Automatic retry with configurable backoff
    - URL normalization and --url flag support
    - IB diagnostic enhancement for error responses
    - Operation polling for long-running tasks
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        # URL resolution: explicit > --url flag > config default
        self.base_url = self._resolve_url(base_url)
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "CLIClient":
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
        return self

    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.aclose()

    # Core HTTP methods
    async def get(self, endpoint: str, **kwargs) -> dict:
        return await self._request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs) -> dict:
        return await self._request("POST", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> dict:
        return await self._request("DELETE", endpoint, **kwargs)

    # Operation support (from AsyncOperationExecutor)
    async def execute_operation(
        self,
        adapter: OperationAdapter,
        on_progress: Optional[Callable] = None,
        poll_interval: float = 0.3,
    ) -> dict:
        """Execute a long-running operation with polling and cancellation support."""
        ...

    # Health check
    async def health_check(self) -> bool:
        ...

    # Private methods
    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make HTTP request with retry, error handling, and IB diagnostics."""
        ...

    def _resolve_url(self, explicit_url: Optional[str]) -> str:
        """Resolve effective URL from explicit > --url flag > config."""
        ...

    def _enhance_error_with_diagnostics(self, response: dict) -> dict:
        """Add IB diagnostic info if applicable."""
        ...
```

### Sync Wrapper (for gradual migration)

```python
# ktrdr/cli/client/sync.py

def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run async code from sync context."""
    return asyncio.get_event_loop().run_until_complete(coro)


class SyncCLIClient:
    """
    Sync wrapper for gradual migration.

    Usage:
        client = SyncCLIClient()
        result = client.get("/symbols")

    Deprecated: Migrate to async CLIClient.
    """

    def get(self, endpoint: str, **kwargs) -> dict:
        async def _get():
            async with CLIClient() as client:
                return await client.get(endpoint, **kwargs)
        return run_async(_get())

    # ... other methods
```

## Migration Strategy

### Phase 1: Create New Client (Non-Breaking)

1. Create `ktrdr/cli/client/` module with `CLIClient`
2. Port all features from existing clients
3. Add comprehensive tests
4. Keep existing clients unchanged

**Deliverable**: New client exists alongside old ones

### Phase 2: Migrate AsyncCLIClient Commands

Commands currently using `AsyncCLIClient`:
- `agent_commands.py`
- `async_data_commands.py`
- `data_commands.py` (partial)
- `model_commands.py` (partial)

Migration pattern:
```python
# Before
async with AsyncCLIClient() as client:
    result = await client._make_request("GET", "/symbols")

# After
async with CLIClient() as client:
    result = await client.get("/symbols")
```

**Deliverable**: All async commands use new client

### Phase 3: Migrate KtrdrApiClient Commands

Commands currently using `KtrdrApiClient`:
- `indicator_commands.py`
- `checkpoints_commands.py`
- `fuzzy_commands.py`
- `ib_commands.py`
- `operations_commands.py`
- `strategy_commands.py`

Two options per command:

**Option A: Convert to async (preferred)**
```python
# Before
def list_indicators():
    api_client = get_api_client()
    result = api_client.get_request("/indicators")

# After
def list_indicators():
    asyncio.run(_list_indicators_async())

async def _list_indicators_async():
    async with CLIClient() as client:
        result = await client.get("/indicators")
```

**Option B: Use sync wrapper (temporary)**
```python
# Before
api_client = get_api_client()
result = api_client.get_request("/indicators")

# After
client = SyncCLIClient()
result = client.get("/indicators")
```

**Deliverable**: All sync commands migrated

### Phase 4: Migrate Operation Executor

The `AsyncOperationExecutor` becomes a method on `CLIClient`:

```python
# Before
executor = AsyncOperationExecutor()
result = await executor.execute(adapter)

# After
async with CLIClient() as client:
    result = await client.execute_operation(adapter)
```

Commands affected:
- `backtest_commands.py`
- `model_commands.py` (training)

**Deliverable**: Operation execution integrated into client

### Phase 5: Cleanup

1. Delete `async_cli_client.py`
2. Delete `api_client.py`
3. Delete `operation_executor.py`
4. Update all imports
5. Remove `get_api_client()` function

**Deliverable**: Single client, no legacy code

## Implementation Details

### URL Resolution (Centralized)

```python
# ktrdr/cli/client/base.py

def _resolve_url(self, explicit_url: Optional[str]) -> str:
    """
    Resolve the effective API URL.

    Priority:
    1. Explicit parameter (for testing/overrides)
    2. Global --url flag
    3. Config default
    """
    from ktrdr.cli.commands import get_api_url_override
    from ktrdr.config.host_services import get_api_base_url

    url = explicit_url or get_api_url_override() or get_api_base_url()
    url = url.rstrip("/")

    # Auto-append /api/v1 if using --url flag without API path
    if get_api_url_override() and "/api/" not in url:
        url = f"{url}/api/v1"

    return url
```

### Error Handling (Unified)

```python
# ktrdr/cli/client/errors.py

class CLIClientError(Exception):
    """Base exception for CLI client errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "CLI-Error",
        status_code: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ConnectionError(CLIClientError):
    """Failed to connect to API server."""
    pass


class TimeoutError(CLIClientError):
    """Request timed out."""
    pass


class APIError(CLIClientError):
    """API returned an error response."""
    pass
```

### IB Diagnostics Integration

```python
# ktrdr/cli/client/diagnostics.py

def enhance_error_with_ib_diagnostics(response_data: dict) -> dict:
    """
    Enhance API error response with IB-specific diagnostics.

    If the error appears to be IB Gateway related, adds:
    - Clear problem description
    - Recovery suggestions
    - Diagnostic commands
    """
    from ktrdr.cli.ib_diagnosis import (
        detect_ib_issue_from_api_response,
        should_show_ib_diagnosis,
    )

    if not should_show_ib_diagnosis(response_data):
        return response_data

    problem_type, message, details = detect_ib_issue_from_api_response(response_data)
    if problem_type:
        response_data["ib_diagnosis"] = {
            "problem_type": problem_type,
            "message": message,
            "details": details,
        }

    return response_data
```

### Operation Polling

```python
# ktrdr/cli/client/operations.py

async def execute_operation(
    self,
    adapter: OperationAdapter,
    on_progress: Optional[Callable[[int, str], None]] = None,
    poll_interval: float = 0.3,
    cancellation_check: Optional[Callable[[], bool]] = None,
) -> dict:
    """
    Execute a long-running operation with progress polling.

    Args:
        adapter: Operation-specific adapter (training, backtest, etc.)
        on_progress: Callback for progress updates (percent, message)
        poll_interval: Seconds between status polls
        cancellation_check: Returns True if operation should be cancelled

    Returns:
        Final operation result

    Raises:
        CLIClientError: On operation failure
        OperationCancelled: If cancelled by user
    """
    # Start operation
    start_response = await self.post(
        adapter.get_start_endpoint(),
        json=adapter.get_start_payload(),
    )
    operation_id = adapter.extract_operation_id(start_response)

    # Poll until complete
    while True:
        if cancellation_check and cancellation_check():
            await self.delete(f"/operations/{operation_id}")
            raise OperationCancelled(operation_id)

        status = await self.get(f"/operations/{operation_id}")

        if on_progress:
            on_progress(
                status.get("progress_percent", 0),
                status.get("progress_message", ""),
            )

        if status["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            return adapter.process_result(status)

        await asyncio.sleep(poll_interval)
```

## Testing Strategy

### Unit Tests

```python
# tests/unit/cli/client/test_cli_client.py

@pytest.mark.asyncio
async def test_url_resolution_explicit():
    async with CLIClient(base_url="http://custom:9000/api/v1") as client:
        assert client.base_url == "http://custom:9000/api/v1"


@pytest.mark.asyncio
async def test_url_resolution_flag(monkeypatch):
    monkeypatch.setattr("ktrdr.cli.commands._cli_state", {"api_url": "http://flag:8000"})
    async with CLIClient() as client:
        assert client.base_url == "http://flag:8000/api/v1"


@pytest.mark.asyncio
async def test_retry_on_server_error(httpx_mock):
    httpx_mock.add_response(status_code=500)
    httpx_mock.add_response(status_code=500)
    httpx_mock.add_response(json={"success": True})

    async with CLIClient(max_retries=3) as client:
        result = await client.get("/test")
        assert result["success"] is True
        assert len(httpx_mock.get_requests()) == 3


@pytest.mark.asyncio
async def test_ib_diagnostics_enhancement(httpx_mock):
    httpx_mock.add_response(
        status_code=400,
        json={"detail": "IB Gateway connection failed: timeout"}
    )

    async with CLIClient() as client:
        with pytest.raises(APIError) as exc:
            await client.get("/data")

        assert "ib_diagnosis" in exc.value.details
```

### Integration Tests

```python
# tests/integration/cli/test_cli_client_integration.py

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_operation_lifecycle():
    """Test starting, polling, and completing an operation."""
    async with CLIClient() as client:
        # Start dummy operation
        result = await client.execute_operation(
            DummyOperationAdapter(duration=2),
            on_progress=lambda p, m: print(f"{p}%: {m}"),
        )
        assert result["status"] == "COMPLETED"
```

## Risk Assessment

### Low Risk
- New client is additive (no breaking changes initially)
- Gradual migration allows rollback per-command
- Comprehensive test coverage before migration

### Medium Risk
- Sync wrapper may have edge cases with event loops
- IB diagnostics integration needs careful testing
- Operation cancellation signal handling

### Mitigations
1. Feature flags to switch between old/new client
2. Shadow mode: run both clients, compare results
3. Canary rollout: migrate least-used commands first

## Timeline Estimate

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1: Create new client | 2-3 days | Low |
| Phase 2: Migrate async commands | 1-2 days | Low |
| Phase 3: Migrate sync commands | 2-3 days | Medium |
| Phase 4: Migrate operation executor | 1-2 days | Medium |
| Phase 5: Cleanup | 1 day | Low |

**Total: ~8-11 days of focused work**

## Success Criteria

1. Single `CLIClient` class handles all CLI HTTP needs
2. All existing tests pass
3. No user-facing behavior changes
4. Code reduction: ~500-700 lines removed
5. URL handling in exactly one place
6. All commands work with `--url` flag
