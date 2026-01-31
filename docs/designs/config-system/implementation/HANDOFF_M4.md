# M4 Handoff: Worker Settings

## Task 4.1 Complete: Create `WorkerSettings` Class

### Gotchas

**Port default is 5003 (not 5002 or 5004)**: The original bug had two different defaults — 5002 in `training_worker.py` and 5004 in `worker_registration.py`. The canonical default is now 5003, which matches the most common usage (first backtest worker port in docker-compose). All workers should use `get_worker_settings().port` as the single source of truth.

**No backend_url field**: Per design, `WorkerSettings` does NOT include a `backend_url` field. Workers should use `get_api_client_settings().base_url` from M5's `APIClientSettings` for backend connection. This ensures a single source of truth for the backend URL.

**worker_id defaults to None, not auto-generated**: Unlike the old code that generated worker IDs inline with `uuid.uuid4().hex[:8]`, the settings class defaults to `None`. The ID generation should happen at runtime in the worker startup code (Task 4.5 will handle this migration).

### Emergent Patterns

**Optional fields use `str | None` with `deprecated_field()`**: For fields like `endpoint_url` and `public_base_url` that are optional and auto-detected at runtime, use `str | None` type with `None` default.

### Next Task Notes (4.2: Align CheckpointSettings)

- `CheckpointSettings` already exists with `CHECKPOINT_*` prefix
- Need to change prefix to `KTRDR_CHECKPOINT_*`
- Add `deprecated_field()` for old names like `CHECKPOINT_EPOCH_INTERVAL` → `KTRDR_CHECKPOINT_EPOCH_INTERVAL`
- Keep all existing functionality

---

## Task 4.2 Complete: Align `CheckpointSettings` with KTRDR Prefix

### Gotchas

**Validation error messages change**: When using `deprecated_field()`, Pydantic's validation error messages show the env var name (via `validation_alias`) instead of the field name. Tests that checked for `"epoch_interval" in str(exc_info.value)` needed to be updated to check for `"greater than 0"` instead. This is expected behavior — the alias overrides the field name in error messages.

### Implementation Notes

Straightforward update following the M3 pattern:
- Changed `env_prefix` from `CHECKPOINT_` to `KTRDR_CHECKPOINT_`
- Used `deprecated_field()` for all 4 fields
- Added `env_file=".env.local"` and `extra="ignore"` for consistency

### Next Task Notes (4.3: Align OrphanDetectorSettings)

- `OrphanDetectorSettings` already exists with `ORPHAN_` prefix
- Same pattern as 4.2: change to `KTRDR_ORPHAN_*`, add `deprecated_field()`
- Fields: timeout_seconds, check_interval_seconds

---

## Task 4.3 Complete: Align `OrphanDetectorSettings` with KTRDR Prefix

### Implementation Notes

Identical pattern to Task 4.2:
- Changed `env_prefix` from `ORPHAN_` to `KTRDR_ORPHAN_`
- Used `deprecated_field()` for both fields
- Updated validation test assertions to check for `"greater than 0"` instead of field names

### Next Task Notes (4.4: Create OperationsSettings)

- New class — no existing implementation to migrate
- Prefix: `KTRDR_OPS_`
- Fields: max_operations, cleanup_interval, retention_days, etc.
- Check for any existing operation-related env vars in the codebase

---

## Task 4.4 Complete: Create `OperationsSettings` Class

### Implementation Notes

New class created with prefix `KTRDR_OPS_`:
- `cache_ttl` (float, default 1.0) — matches existing `OPERATIONS_CACHE_TTL` env var in operations_service.py
- `max_operations` (int, default 10000) — maximum operations to track in memory
- `cleanup_interval_seconds` (int, default 3600) — interval between cleanup runs
- `retention_days` (int, default 7) — days to retain completed operations

**Deprecated name support:** `OPERATIONS_CACHE_TTL` → `KTRDR_OPS_CACHE_TTL`

### Gotchas

**cache_ttl uses `ge=0` not `gt=0`**: Unlike other interval fields, cache_ttl of 0 is valid (means no caching). Used `ge=0` constraint instead of `gt=0`.

### Next Task Notes (4.5: Migrate Worker Consumers)

- Replace all `os.getenv("WORKER_*")` calls with `get_worker_settings().field`
- Files: `ktrdr/workers/*.py`, `ktrdr/training/training_worker.py`, `ktrdr/backtesting/backtest_worker.py`
- Watch for worker_id generation — settings returns None, runtime should generate if needed

---

## Task 4.5 Complete: Migrate Worker Consumers

### Gotchas

**Settings are cached via `lru_cache`**: Tests that patch environment variables via `monkeypatch.setenv()` or `patch.dict(os.environ, ...)` must call `clear_settings_cache()` before creating worker instances. Otherwise, the cached settings from a previous test will be used instead of the patched env vars.

**worker_id runtime generation**: When `worker_settings.worker_id` is None, the worker code generates an ID at runtime using either:
- `uuid.uuid4().hex[:8]` — for module-level worker_id (backtest_worker.py, training_worker.py)
- `f"{worker_type}-{socket.gethostname()}"` — for class __init__ (WorkerRegistration, WorkerAPIBase)
- `f"{worker_type}-worker-{os.urandom(4).hex()}"` — for WorkerAPIBase.__init__

**Keep `os` import when needed**: Files may still need `import os` for:
- `os.getenv("KTRDR_API_URL")` — backend URL (not a WORKER_* var)
- `os.path.exists()` — file system checks
- `os.cpu_count()` — capability detection
- `os.urandom()` — random ID generation

**Test default port expectations changed**: All workers now use canonical default port 5003 (not 5004 for training). Tests that expected `registration.port == 5004` for training workers needed to be updated to expect 5003.

### Files Migrated

| File | Changes |
|------|---------|
| `ktrdr/workers/base.py` | `WORKER_PUBLIC_BASE_URL` → `get_worker_settings().public_base_url`, `WORKER_ID` → settings in __init__ |
| `ktrdr/backtesting/backtest_worker.py` | `WORKER_ID` → settings, `WORKER_PORT` → settings |
| `ktrdr/backtesting/worker_registration.py` | `WORKER_ID`, `WORKER_PORT`, `WORKER_ENDPOINT_URL` → settings |
| `ktrdr/backtesting/remote_api.py` | `WORKER_ID` → settings |
| `ktrdr/training/training_worker.py` | `WORKER_ID` → settings, `WORKER_PORT` → settings |
| `ktrdr/training/worker_registration.py` | `WORKER_ID`, `WORKER_PORT`, `WORKER_ENDPOINT_URL` → settings |
| `ktrdr/training/training_worker_api.py` | `WORKER_ID` → settings |

### Added Tests

`tests/unit/config/test_worker_migration.py` — verifies no `os.getenv("WORKER_*")` calls remain in worker code.

### Next Task Notes (4.6: Add Worker Startup Validation)

- Add `warn_deprecated_env_vars()` and `validate_all("worker")` at worker entrypoints
- Files: `ktrdr/workers/base.py` (in `__init__` or lifespan), `ktrdr/backtesting/backtest_worker.py`, `ktrdr/training/training_worker.py`
- Workers should fail fast on invalid config

---
