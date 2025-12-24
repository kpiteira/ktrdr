# Handoff: Milestone 2 (Orphan Detection)

## Task 2.1 Complete

**Implemented:** `OrphanOperationDetector` service

### Gotchas

**Backend-local detection pattern:**
The `_is_backend_local()` method checks `operation.metadata.parameters.get("is_backend_local", False)`. This is the same pattern used by `StartupReconciliation`. If the flag isn't set, operations default to worker-based.

**list_operations signature:**
`OperationsService.list_operations()` returns a tuple: `(operations, total_count, active_count)`. The orphan detector only uses the first element. Example:
```python
running_ops, _, _ = await self._operations_service.list_operations(status=OperationStatus.RUNNING)
```

**fail_operation signature:**
`OperationsService.fail_operation(operation_id, error_message, fail_parent=False)`. The orphan detector does not cascade to parent operations.

### Patterns Established

**Health status pattern:**
The `get_status()` method returns a dict suitable for inclusion in health check responses:
```python
{
    "running": bool,
    "potential_orphans_count": int,
    "last_check": Optional[str],  # ISO timestamp
    "orphan_timeout_seconds": int,
    "check_interval_seconds": int,
}
```

---

## Task 2.2 Complete

**Implemented:** OrphanDetector integrated with backend startup via `startup.py`

### Integration Pattern

The orphan detector is managed in `ktrdr/api/startup.py` using the `lifespan` context manager pattern (not deprecated `@app.on_event` decorators):

```python
# Module-level singleton
_orphan_detector: OrphanOperationDetector | None = None

def get_orphan_detector() -> OrphanOperationDetector:
    """Get the global OrphanOperationDetector instance."""
    if _orphan_detector is None:
        raise RuntimeError("OrphanOperationDetector not initialized.")
    return _orphan_detector

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _orphan_detector

    # M1: Startup reconciliation first
    await _run_startup_reconciliation()

    # M2: Start orphan detector
    _orphan_detector = OrphanOperationDetector(
        operations_service=get_operations_service(),
        worker_registry=get_worker_registry(),
    )
    await _orphan_detector.start()

    yield  # App runs here

    # Shutdown
    if _orphan_detector:
        await _orphan_detector.stop()
```

### Gotchas (Task 2.2)

**Lifespan vs on_event:**
The codebase uses the modern `lifespan` context manager pattern, not the deprecated `@app.on_event("startup")` and `@app.on_event("shutdown")` decorators. Always use `lifespan` for new lifecycle management.

**Import at module level:**
`OrphanOperationDetector` is imported at module level in `startup.py`, not inside the lifespan function. This is consistent with how it's used in tests (patching `ktrdr.api.startup.OrphanOperationDetector`).

### For Task 2.3 (Health Check)

Use `get_orphan_detector().get_status()` in the health endpoint. The status dict can be directly included in the response. Import from `ktrdr.api.startup`:

```python
from ktrdr.api.startup import get_orphan_detector

@router.get("/health")
async def health():
    detector = get_orphan_detector()
    return {"orphan_detector": detector.get_status()}
```
