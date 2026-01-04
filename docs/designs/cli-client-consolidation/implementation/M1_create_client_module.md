---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 1: Create Client Module

**Branch:** `feature/cli-client-consolidation-m1`
**Builds on:** -
**Goal:** New `ktrdr/cli/client/` module exists and passes tests. No commands use it yet.

## E2E Test Scenario

```bash
# Verify module exists and tests pass
pytest tests/unit/cli/client/ -v

# Verify imports work
python -c "from ktrdr.cli.client import SyncCLIClient, AsyncCLIClient"
```

**Success Criteria:**
- [ ] All unit tests pass
- [ ] Both clients can be imported
- [ ] No existing code modified

---

## Task 1.1: Create errors module

**File(s):** `ktrdr/cli/client/errors.py`
**Type:** CODING
**Estimated time:** 1 hour
**Task Categories:** Wiring/DI

**Description:**
Define exception hierarchy for client errors:
- `CLIClientError` — base exception with message, status_code, details
- `ConnectionError` — failed to connect
- `TimeoutError` — request timed out
- `APIError` — API returned error response

**Acceptance Criteria:**
- [ ] All exception classes defined
- [ ] Each has appropriate attributes (message, status_code, details)

---

## Task 1.2: Create core module

**File(s):** `ktrdr/cli/client/core.py`
**Type:** CODING
**Estimated time:** 2-3 hours
**Task Categories:** Configuration

**Description:**
Port shared logic from existing clients:

1. `ClientConfig` dataclass (base_url, timeout, max_retries, retry_delay)
2. `resolve_url(explicit_url)` — URL priority: explicit > --url flag > config default
3. `should_retry(status_code, attempt, max_retries)` — retry on 5xx only
4. `calculate_backoff(attempt, base_delay)` — exponential with jitter
5. `parse_response(response)` — extract JSON, handle errors
6. `enhance_with_ib_diagnostics(error_data)` — add IB diagnosis if applicable

**Reference:**
- URL resolution: `ktrdr/cli/api_client.py`
- Retry logic: `ktrdr/cli/async_cli_client.py`
- IB diagnostics: `ktrdr/cli/api_client.py`

**Testing Requirements:**

*Unit Tests:* `tests/unit/cli/client/test_core.py`
- [ ] URL resolution priority (explicit > flag > config)
- [ ] Retry decisions (5xx yes, 4xx no)
- [ ] Backoff calculation
- [ ] IB diagnostic detection

**Acceptance Criteria:**
- [ ] All functions implemented
- [ ] Unit tests pass
- [ ] Logic matches existing behavior

---

## Task 1.3: Create sync client

**File(s):** `ktrdr/cli/client/sync_client.py`
**Type:** CODING
**Estimated time:** 2 hours
**Task Categories:** Wiring/DI, Cross-Component

**Description:**
Create `SyncCLIClient` class:
- `__init__(base_url, timeout, max_retries, retry_delay)`
- `__enter__` / `__exit__` — manage httpx.Client lifecycle
- `get(endpoint, **kwargs)` / `post(...)` / `delete(...)`
- `health_check()`

**Testing Requirements:**

*Unit Tests:* `tests/unit/cli/client/test_sync_client.py`
- [ ] Context manager opens/closes client
- [ ] Methods call correct HTTP verbs
- [ ] Retry behavior works
- [ ] Errors raised correctly

*Smoke Test:*
```bash
python -c "from ktrdr.cli.client import SyncCLIClient; print('OK')"
```

**Acceptance Criteria:**
- [ ] Class implemented with all methods
- [ ] Uses core module for shared logic
- [ ] Unit tests pass with mocked httpx

---

## Task 1.4: Create async client

**File(s):** `ktrdr/cli/client/async_client.py`
**Type:** CODING
**Estimated time:** 2 hours
**Task Categories:** Wiring/DI, Cross-Component, Background/Async

**Description:**
Create `AsyncCLIClient` class (mirrors sync but async):
- `__aenter__` / `__aexit__`
- `async get/post/delete`
- `async health_check()`
- `async execute_operation(adapter, on_progress, poll_interval)`

**Testing Requirements:**

*Unit Tests:* `tests/unit/cli/client/test_async_client.py`
- [ ] Async context manager works
- [ ] Methods call correct HTTP verbs
- [ ] Retry behavior works

*Smoke Test:*
```bash
python -c "from ktrdr.cli.client import AsyncCLIClient; print('OK')"
```

**Acceptance Criteria:**
- [ ] Class implemented with all methods
- [ ] Uses core module for shared logic
- [ ] Unit tests pass

---

## Task 1.5: Create operations module

**File(s):** `ktrdr/cli/client/operations.py`
**Type:** CODING
**Estimated time:** 2 hours
**Task Categories:** Background/Async, State Machine

**Description:**
Port operation execution from `AsyncOperationExecutor`:
- Start operation via adapter
- Poll loop with progress callbacks
- Cancellation handling
- Return final result

**Reference:** `ktrdr/cli/operation_executor.py`

**Testing Requirements:**

*Unit Tests:*
- [ ] Operation starts and polls
- [ ] Progress callback invoked
- [ ] Cancellation works
- [ ] Final result returned

**Acceptance Criteria:**
- [ ] Function ported from existing executor
- [ ] Integrated into AsyncCLIClient.execute_operation()

---

## Task 1.6: Create package init

**File(s):** `ktrdr/cli/client/__init__.py`
**Type:** CODING
**Estimated time:** 30 minutes
**Task Categories:** Wiring/DI

**Description:**
Export public API:
```python
from .async_client import AsyncCLIClient
from .sync_client import SyncCLIClient
from .errors import CLIClientError, ConnectionError, TimeoutError, APIError
```

**Acceptance Criteria:**
- [ ] All public classes exported
- [ ] `from ktrdr.cli.client import SyncCLIClient` works

---

## Completion Checklist

- [ ] All tasks complete
- [ ] `pytest tests/unit/cli/client/` passes
- [ ] `make quality` passes
- [ ] No existing commands modified
