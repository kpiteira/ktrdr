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

---

## Task 2.4 Complete

**Implemented:** Configurable orphan detection settings via environment variables

### Settings Pattern

Configuration is in `ktrdr/config/settings.py` using Pydantic `BaseSettings`:

```python
class OrphanDetectorSettings(BaseSettings):
    timeout_seconds: int = Field(default=60, gt=0)
    check_interval_seconds: int = Field(default=15, gt=0)

    model_config = SettingsConfigDict(env_prefix="ORPHAN_")
```

Environment variables:

- `ORPHAN_TIMEOUT_SECONDS` — Time before orphan marked FAILED (default: 60)
- `ORPHAN_CHECK_INTERVAL_SECONDS` — Check interval (default: 15)

### Wiring in startup.py

```python
from ktrdr.config.settings import get_orphan_detector_settings

orphan_settings = get_orphan_detector_settings()
_orphan_detector = OrphanOperationDetector(
    operations_service=operations_service,
    worker_registry=registry,
    orphan_timeout_seconds=orphan_settings.timeout_seconds,
    check_interval_seconds=orphan_settings.check_interval_seconds,
)
```

### Gotchas (Task 2.4)

**Field naming for env var mapping:**
With `env_prefix="ORPHAN_"`, the field `timeout_seconds` maps to `ORPHAN_TIMEOUT_SECONDS`. If the field were named `orphan_timeout_seconds`, the env var would be `ORPHAN_ORPHAN_TIMEOUT_SECONDS`.

**Validation:**
Both values must be > 0 (Pydantic `gt=0` constraint). Invalid values raise `ValidationError` at startup, preventing misconfiguration.

---

## Next: Task 2.5 (Integration Test)

The integration test should:

1. Create operation with worker
2. Simulate worker disappearance (remove from registry)
3. Wait for orphan detection
4. Verify operation marked FAILED
