---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 4: Worker Settings

**Goal:** Workers start, register, and validate their config subset using new `WorkerSettings`, `CheckpointSettings`, `OrphanDetectorSettings`, and `OperationsSettings`.

**Why M4:** Workers are separate processes that need their own config validation. After M3 handles host services, M4 completes the distributed system configuration.

**Branch:** `feature/config-m4-workers`

**Depends on:** M3 (IB & Host Services)

---

## Task 4.1: Create `WorkerSettings` Class

**Files:** `ktrdr/config/settings.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Add `WorkerSettings` class for worker process configuration.

**Implementation Notes:**
- Include: worker_id, backend_url, port, heartbeat_interval, etc.
- Fix duplication #4 from audit: `WORKER_PORT` defaults to 5002 in one place, 5004 in another — use single authoritative default
- Note: `backend_url` should reference `APIClientSettings.base_url` (M5) for consistency — for now, keep as standalone field

**Key signatures:**
```python
class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KTRDR_WORKER_", env_file=".env.local")
    # Fields: worker_id, port, heartbeat_interval, backend_url, ...

@lru_cache
def get_worker_settings() -> WorkerSettings: ...
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `WorkerSettings` loads defaults correctly
- [ ] `KTRDR_WORKER_PORT` overrides default
- [ ] Single authoritative default for port (fixes bug)

**Acceptance Criteria:**
- [ ] `WorkerSettings` class exists
- [ ] Port default is consistent (fixes duplication #4)
- [ ] All unit tests pass

---

## Task 4.2: Align `CheckpointSettings` with KTRDR Prefix

**Files:** `ktrdr/config/settings.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
`CheckpointSettings` already exists — align it with `KTRDR_*` prefix convention. Add deprecated name support for any existing env var names.

**Implementation Notes:**
- Existing class may use different prefix
- Update `env_prefix` to `KTRDR_CHECKPOINT_`
- Use `deprecated_field()` for fields with old names
- Keep all existing functionality

**Key signatures:**
```python
class CheckpointSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KTRDR_CHECKPOINT_", env_file=".env.local")
    # Existing fields with deprecated_field() for old names

@lru_cache
def get_checkpoint_settings() -> CheckpointSettings: ...
```

**Acceptance Criteria:**
- [ ] `CheckpointSettings` uses `KTRDR_CHECKPOINT_` prefix
- [ ] Old env var names still work with deprecation warnings
- [ ] Existing functionality unchanged

---

## Task 4.3: Align `OrphanDetectorSettings` with KTRDR Prefix

**Files:** `ktrdr/config/settings.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
`OrphanDetectorSettings` already exists — align it with `KTRDR_*` prefix convention.

**Implementation Notes:**
- Same pattern as Task 4.2
- Update prefix, add deprecated field support

**Key signatures:**
```python
class OrphanDetectorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KTRDR_ORPHAN_", env_file=".env.local")
    # Existing fields with deprecated_field() for old names

@lru_cache
def get_orphan_detector_settings() -> OrphanDetectorSettings: ...
```

**Acceptance Criteria:**
- [ ] `OrphanDetectorSettings` uses `KTRDR_ORPHAN_` prefix
- [ ] Old env var names still work with deprecation warnings

---

## Task 4.4: Create `OperationsSettings` Class

**Files:** `ktrdr/config/settings.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Add `OperationsSettings` class for operation tracking configuration.

**Implementation Notes:**
- Include: max_operations, cleanup_interval, retention_days, etc.
- Reference any existing operation-related env vars

**Key signatures:**
```python
class OperationsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KTRDR_OPS_", env_file=".env.local")
    # Fields: max_operations, cleanup_interval, retention_days, ...

@lru_cache
def get_operations_settings() -> OperationsSettings: ...
```

**Acceptance Criteria:**
- [ ] `OperationsSettings` class exists
- [ ] `get_operations_settings()` cached getter exists

---

## Task 4.5: Migrate Worker Consumers

**Files:** `ktrdr/workers/*.py`
**Type:** CODING

**Task Categories:** Wiring/DI

**Description:**
Replace all worker-related `os.getenv()` calls with settings getters.

**Implementation Notes:**
- Find all `os.getenv("WORKER_*")` calls in worker code
- Replace with `get_worker_settings().field`
- This includes `training_worker.py`, `backtest_worker.py`, etc.

**Testing Requirements:**

*Integration Tests:*
- [ ] Worker starts with new settings
- [ ] Worker registers with backend

**Acceptance Criteria:**
- [ ] Zero direct `os.getenv("WORKER_*")` calls in worker code
- [ ] Workers start and register correctly

---

## Task 4.6: Add Worker Startup Validation

**Files:** `ktrdr/workers/training_worker.py`, `ktrdr/workers/backtest_worker.py`, etc.
**Type:** CODING

**Task Categories:** Wiring/DI, Configuration

**Description:**
Add `validate_all("worker")` call at worker entrypoints, similar to what M1 added to backend's `main.py`.

**Implementation Notes:**
- Find each worker's entrypoint (main function or startup code)
- Add `warn_deprecated_env_vars()` and `validate_all("worker")` calls
- Workers should fail fast on invalid config

**Acceptance Criteria:**
- [ ] All worker entrypoints call `validate_all("worker")`
- [ ] Workers fail fast with invalid config
- [ ] Deprecation warnings emitted for old names

---

## Task 4.7: Update Validation Module for M4 Settings

**Files:** `ktrdr/config/validation.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Update `WORKER_SETTINGS` list to include all M4 Settings classes.

**Implementation Notes:**
- Add `WorkerSettings`, `CheckpointSettings`, `OrphanDetectorSettings`, `OperationsSettings` to `WORKER_SETTINGS`
- Workers may also need some backend settings (DB, logging) — ensure those are included

**Acceptance Criteria:**
- [ ] `validate_all("worker")` validates all worker-relevant settings

---

## Task 4.8: Update Deprecation Module for M4 Names

**Files:** `ktrdr/config/deprecation.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Add deprecated name mappings for worker-related env vars.

**Acceptance Criteria:**
- [ ] All M4 deprecated names in `DEPRECATED_NAMES` dict

---

## Task 4.9: Write Unit Tests

**Files:** `tests/unit/config/test_worker_settings.py`, etc.
**Type:** CODING

**Description:**
Write unit tests for all M4 Settings classes.

**Acceptance Criteria:**
- [ ] All M4 Settings classes have unit tests
- [ ] `make test-unit` passes

---

## Task 4.10: Execute E2E Test

**Type:** VALIDATION

**Description:**
Validate M4 is complete with E2E scenarios.

**E2E Test Scenarios:**

### Scenario 1: Worker starts and registers
```bash
docker compose up -d backend
# Start a worker
docker compose up -d training-worker
sleep 5
# Check worker registered
curl http://localhost:8000/api/v1/workers | jq '.[] | select(.worker_type == "training")'
# Expected: worker appears in list
docker compose down
```

### Scenario 2: Worker validates config at startup
```bash
# Invalid worker config
KTRDR_WORKER_PORT=abc docker compose up training-worker
# Expected: exit code 1
docker compose down
```

### Scenario 3: Worker uses consistent port default
```bash
# Start worker without explicit port
docker compose up -d training-worker
# Check it uses the expected default port (not the buggy one)
docker compose logs training-worker | grep -E "port|PORT"
# Expected: consistent default port used
docker compose down
```

### Scenario 4: Deprecated WORKER_* names work with warnings
```bash
WORKER_PORT=5010 docker compose up -d training-worker
docker compose logs training-worker 2>&1 | grep "WORKER_PORT.*deprecated"
# Expected: deprecation warning
docker compose down
```

**Success Criteria:**
- [ ] All scenarios pass
- [ ] Workers start and register
- [ ] Workers validate config at startup
- [ ] Port default bug fixed (duplication #4)
- [ ] Deprecated names work with warnings

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E tests pass
- [ ] Quality gates pass: `make quality`
- [ ] Duplication #4 (WORKER_PORT inconsistent defaults) fixed
- [ ] All existing Settings classes aligned with KTRDR prefix
- [ ] Branch merged to main
