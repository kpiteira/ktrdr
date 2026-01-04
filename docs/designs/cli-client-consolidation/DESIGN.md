# CLI Client Consolidation: Design

## Problem Statement

The CLI has three separate HTTP clients (`AsyncCLIClient`, `KtrdrApiClient`, `AsyncOperationExecutor`) that each implement overlapping functionality — retry logic, URL resolution, timeout handling, error parsing — but with different patterns and capabilities. This creates ~500-700 lines of code duplication, inconsistent behavior across commands, and makes changes error-prone since any fix must be applied in multiple places.

## Goals

1. **Single source of truth** for HTTP client logic (retry, URL resolution, error handling, IB diagnostics)
2. **Consistent behavior** across all CLI commands regardless of sync/async pattern
3. **Reduced maintenance burden** — changes to client behavior happen in one place
4. **Preserve existing command patterns** — sync commands stay sync, async commands stay async

## Non-Goals

- Converting sync commands to async (or vice versa)
- Changing user-facing CLI behavior
- Performance optimization
- Adding new client features beyond what exists today

## Developer Experience

How command authors use the clients after consolidation:

### Sync Commands (indicators, checkpoints, strategies, etc.)

```python
# Before: KtrdrApiClient with inconsistent patterns
api_client = get_api_client()
result = api_client.get_request("/indicators")

# After: SyncCLIClient with consistent interface
from ktrdr.cli.client import SyncCLIClient

with SyncCLIClient() as client:
    result = client.get("/indicators")
```

### Async Commands (agent, data loading, etc.)

```python
# Before: AsyncCLIClient
async with AsyncCLIClient() as client:
    result = await client._make_request("GET", "/symbols")

# After: AsyncCLIClient with same interface as sync
from ktrdr.cli.client import AsyncCLIClient

async with AsyncCLIClient() as client:
    result = await client.get("/symbols")
```

### Long-Running Operations (training, backtest)

```python
# Before: Separate AsyncOperationExecutor
executor = AsyncOperationExecutor()
result = await executor.execute(adapter)

# After: Method on AsyncCLIClient
async with AsyncCLIClient() as client:
    result = await client.execute_operation(adapter, on_progress=callback)
```

## Key Decisions

### Decision 1: Shared Core, Two Facades

**Choice:** Extract all logic into a shared core module. Provide separate `AsyncCLIClient` and `SyncCLIClient` that use the core.

**Alternatives considered:**
- Single async client with sync wrapper — adds event loop complexity for no benefit
- Single sync client — can't support operation polling, loses connection reuse for async commands
- Keep three clients but share utilities — doesn't solve the duplication meaningfully

**Rationale:** Respects that some commands are naturally sync (simple lookups) and others naturally async (operation polling, connection reuse). Eliminates duplication without forcing pattern migration.

### Decision 2: Context Manager Pattern for Both Clients

**Choice:** Both clients use context manager pattern (`with`/`async with`) for resource management.

**Alternatives considered:**
- Implicit resource management — harder to reason about connection lifecycle
- Explicit open/close — more error-prone, easy to leak connections

**Rationale:** Context managers are idiomatic Python, make resource cleanup automatic, and both sync and async httpx support this pattern.

### Decision 3: Operation Execution Lives on AsyncCLIClient

**Choice:** The `execute_operation()` method is only on `AsyncCLIClient`, not `SyncCLIClient`.

**Alternatives considered:**
- Add sync version with internal event loop — complexity for no real use case
- Separate class — more fragmentation

**Rationale:** Operation polling is inherently async (needs to poll, handle signals, update progress). All commands that use it are already async. No sync command needs this.

## Open Questions

1. **IB diagnostics scope:** Currently only `KtrdrApiClient` has IB diagnostic enhancement. Should this be in the shared core (all commands get it) or optional?

2. **Error types:** Should we define custom exception hierarchy (`CLIClientError`, `ConnectionError`, `APIError`) or use httpx exceptions directly?

3. **Deprecation period:** How long do we keep old clients around during migration? Or do we migrate all at once?
