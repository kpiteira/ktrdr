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

## Task 4.6 Complete: Add Worker Startup Validation

### Implementation Notes

Added startup validation calls at module level in both worker files, following the exact pattern from `ktrdr/api/main.py`:

```python
# =============================================================================
# Startup Validation (M4: Config System)
# =============================================================================
# These MUST run before any other initialization to fail fast on invalid config.
# 1. warn_deprecated_env_vars() emits DeprecationWarning for old env var names
# 2. validate_all("worker") raises ConfigurationError if config is invalid
warn_deprecated_env_vars()
validate_all("worker")
```

**Files modified:**
- `ktrdr/backtesting/backtest_worker.py` — validation added before `get_worker_settings()` call
- `ktrdr/training/training_worker.py` — validation added before `get_worker_settings()` call

**Not modified:**
- `ktrdr/workers/base.py` — validation is NOT added here because `WorkerAPIBase` is a class that gets instantiated, not a module entrypoint. The validation must happen at module level in the actual worker entry scripts.

### Gotchas

**Validation happens at module level, not in classes**: The validation calls must be at module level (before any class definitions or settings access) so they run on import. Adding them to `WorkerAPIBase.__init__` would be too late — the module-level `get_worker_settings()` calls happen first.

**WORKER_SETTINGS list is minimal**: Currently `WORKER_SETTINGS` only contains `DatabaseSettings`. Task 4.7 will add the M4 settings classes to this list.

### Next Task Notes (4.7: Update Validation Module for M4 Settings)

- Add `WorkerSettings`, `CheckpointSettings`, `OrphanDetectorSettings`, `OperationsSettings` to `WORKER_SETTINGS` in `ktrdr/config/validation.py`
- May also need to add some backend settings workers depend on (logging, observability)

---

## Task 4.7 Complete: Update Validation Module for M4 Settings

### Implementation Notes

Added 6 new settings classes to `WORKER_SETTINGS` in `_init_settings_lists()`:
- `LoggingSettings` — workers need logging configuration
- `ObservabilitySettings` — workers need tracing/metrics configuration
- `WorkerSettings` — core worker configuration
- `CheckpointSettings` — checkpoint persistence configuration
- `OrphanDetectorSettings` — orphan detection configuration
- `OperationsSettings` — operations tracking configuration

`WORKER_SETTINGS` now contains 7 classes total (including the existing `DatabaseSettings`).

### Gotchas

**Workers need shared infrastructure settings too**: Not just the M4 worker-specific classes, but also `LoggingSettings` and `ObservabilitySettings` since workers need proper logging and observability configuration to function correctly.

### Next Task Notes (4.8: Update Deprecation Module for M4 Names)

- Add deprecated name mappings for worker-related env vars in `ktrdr/config/deprecation.py`
- Check what's already there from Tasks 4.1-4.6
- M4 deprecated names: `WORKER_*`, `CHECKPOINT_*`, `ORPHAN_*`, `OPERATIONS_*`

---

## Task 4.8 Complete: Update Deprecation Module for M4 Names

### Implementation Notes

Added 11 M4 deprecated name mappings to `DEPRECATED_NAMES` in `ktrdr/config/deprecation.py`:

**WorkerSettings (4):**
- `WORKER_ID` → `KTRDR_WORKER_ID`
- `WORKER_PORT` → `KTRDR_WORKER_PORT`
- `WORKER_ENDPOINT_URL` → `KTRDR_WORKER_ENDPOINT_URL`
- `WORKER_PUBLIC_BASE_URL` → `KTRDR_WORKER_PUBLIC_BASE_URL`

**CheckpointSettings (4):**
- `CHECKPOINT_EPOCH_INTERVAL` → `KTRDR_CHECKPOINT_EPOCH_INTERVAL`
- `CHECKPOINT_TIME_INTERVAL_SECONDS` → `KTRDR_CHECKPOINT_TIME_INTERVAL_SECONDS`
- `CHECKPOINT_DIR` → `KTRDR_CHECKPOINT_DIR`
- `CHECKPOINT_MAX_AGE_DAYS` → `KTRDR_CHECKPOINT_MAX_AGE_DAYS`

**OrphanDetectorSettings (2):**
- `ORPHAN_TIMEOUT_SECONDS` → `KTRDR_ORPHAN_TIMEOUT_SECONDS`
- `ORPHAN_CHECK_INTERVAL_SECONDS` → `KTRDR_ORPHAN_CHECK_INTERVAL_SECONDS`

**OperationsSettings (1):**
- `OPERATIONS_CACHE_TTL` → `KTRDR_OPS_CACHE_TTL`

### Next Task Notes (4.9: Write Unit Tests)

- Unit tests for M4 Settings classes may already exist from Tasks 4.1-4.4
- Review existing tests in `tests/unit/config/` for coverage
- Check `test_worker_settings.py`, `test_checkpoint_settings.py`, etc.

---

## Task 4.9 Complete: Write Unit Tests

### Implementation Notes

Unit tests for all M4 Settings classes were already written during Tasks 4.1-4.4:
- `test_worker_settings.py` — 27 tests (defaults, env vars, deprecated names, precedence, validation, getter)
- `test_checkpoint_settings.py` — 27 tests (same categories)
- `test_orphan_detector_settings.py` — 16 tests (same categories)
- `test_operations_settings.py` — 18 tests (same categories)

**Total: 88 tests** covering:
1. Default values
2. Environment variable configuration (new KTRDR_* names)
3. Deprecated env var names still work
4. New names take precedence over deprecated
5. Validation constraints (gt=0, ge=0, port range)
6. Cached getter returns same instance
7. Cache clear returns new instance

All 4676 unit tests pass.

### Next Task Notes (4.10: Execute E2E Test)

- This is a VALIDATION task — run E2E scenarios from the milestone
- Scenarios: worker starts/registers, invalid config fails, port default consistent, deprecated names warn

---

## Task 4.10 Complete: Execute E2E Test

### E2E Test Results

All 4 scenarios passed:

| Scenario | Result | Notes |
|----------|--------|-------|
| 1. Worker starts and registers | ✅ PASSED | Both training and backtest workers registered with backend |
| 2. Worker validates config at startup | ✅ PASSED | Invalid KTRDR_WORKER_PORT=abc exits with code 1 |
| 3. Worker uses consistent port default | ✅ PASSED | After fixing remaining hardcoded defaults |
| 4. Deprecated names work with warnings | ✅ PASSED | WORKER_PORT triggers warning, value is used |

### Gotchas

**Remaining hardcoded port defaults found during E2E**: The initial run of Scenario 3 found two remaining hardcoded port values:
- `ktrdr/training/training_worker.py:104` — default `worker_port: int = 5002` (changed to 5003)
- `ktrdr/training/training_worker_api.py:16` — documentation showed port 5004 (changed to 5003)

These were fixed and committed before re-running the scenario.

### E2E Test Catalog

4 new E2E test specifications were created in `.claude/skills/e2e-testing/tests/workers/`:
- `startup-registration.md` — Worker starts and registers with backend
- `config-validation.md` — Invalid config causes exit code 1
- `port-defaults.md` — Consistent port default (bug #4 fix)
- `deprecated-names.md` — Deprecated env var names work with warnings

A new preflight file was also created: `.claude/skills/e2e-testing/preflight/workers.md`

---

## M4 Milestone Complete

All tasks 4.1-4.10 are complete:
- [x] Task 4.1: WorkerSettings class created
- [x] Task 4.2: CheckpointSettings aligned with KTRDR prefix
- [x] Task 4.3: OrphanDetectorSettings aligned with KTRDR prefix
- [x] Task 4.4: OperationsSettings class created
- [x] Task 4.5: Worker consumers migrated to settings
- [x] Task 4.6: Worker startup validation added
- [x] Task 4.7: WORKER_SETTINGS list updated
- [x] Task 4.8: M4 deprecated names added
- [x] Task 4.9: Unit tests verified (88 tests, all pass)
- [x] Task 4.10: E2E tests pass (4 scenarios)

---
