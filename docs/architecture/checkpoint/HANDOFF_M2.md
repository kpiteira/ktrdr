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

---

## Task 2.3 Complete

**Implemented:** Orphan detector status exposed via `/health` endpoint

### Health Endpoint Integration

The health endpoint in `ktrdr/api/endpoints/__init__.py` now includes orphan detector status:

```python
# Lazy import to avoid circular dependencies
def get_orphan_detector():
    from ktrdr.api.startup import get_orphan_detector as _get_orphan_detector
    return _get_orphan_detector()

def _get_orphan_detector_status() -> dict[str, Any] | None:
    try:
        detector = get_orphan_detector()
        return detector.get_status()
    except RuntimeError:
        return None  # Not initialized yet

@api_router.get("/health")
async def health_check(config: APIConfig = Depends(get_api_config)):
    return {
        "status": "ok",
        "version": config.version,
        "orphan_detector": _get_orphan_detector_status(),
    }
```

### Gotchas (Task 2.3)

**Lazy import pattern:**
The `get_orphan_detector()` is defined locally with a lazy import to avoid circular dependencies between `endpoints/__init__.py` and `startup.py`.

**Handling uninitialized detector:**
During tests or before startup completes, `get_orphan_detector()` raises RuntimeError. The helper `_get_orphan_detector_status()` catches this and returns `None`. Tests can verify this behavior.

**Response format:**

```json
{
  "status": "ok",
  "version": "1.0.x",
  "orphan_detector": {
    "running": true,
    "potential_orphans_count": 0,
    "last_check": "2024-12-21T10:30:00+00:00",
    "orphan_timeout_seconds": 60,
    "check_interval_seconds": 15
  }
}
```

When detector is not initialized, `orphan_detector` is `null`.

### For Task 2.4 (Configuration)

The timeout values are currently hardcoded in the `OrphanOperationDetector` constructor. Task 2.4 should:

1. Add environment variables: `ORPHAN_TIMEOUT_SECONDS`, `ORPHAN_CHECK_INTERVAL_SECONDS`
2. Read them in `startup.py` when creating the detector
3. Pass them to the constructor
