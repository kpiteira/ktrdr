---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 3: IB & Host Services Settings

**Goal:** Backend proxies to host services (IB and Training) using new `IBSettings`, `IBHostServiceSettings`, and `TrainingHostServiceSettings`.

**Why M3:** Host services are external dependencies. After M2 completes core backend config, M3 handles the external integrations.

**Branch:** `feature/config-m3-ib-host-services`

**Depends on:** M2 (API, Auth & Logging)

---

## Task 3.1: Create `IBSettings` Class

**Files:** `ktrdr/config/settings.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Add `IBSettings` class to replace the existing `IbConfig` dataclass in `ktrdr/config/ib_config.py`. This consolidates IB configuration into the unified settings system.

**Implementation Notes:**
- Audit `ktrdr/config/ib_config.py` for all fields
- Include: gateway_host, gateway_port, client_id, account, etc.
- Use `deprecated_field()` for fields with old env var names

**Key signatures:**
```python
class IBSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KTRDR_IB_", env_file=".env.local")
    # Fields: gateway_host, gateway_port, client_id, account, ...

@lru_cache
def get_ib_settings() -> IBSettings: ...
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `IBSettings` loads defaults correctly
- [ ] All IB-related env vars work
- [ ] Deprecated names supported

**Acceptance Criteria:**
- [ ] `IBSettings` class exists with all IB fields
- [ ] `get_ib_settings()` cached getter exists
- [ ] Fields match `IbConfig` plus any additional needs

---

## Task 3.2: Create `IBHostServiceSettings` Class

**Files:** `ktrdr/config/settings.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Add `IBHostServiceSettings` class to replace the existing dataclass in `ktrdr/config/host_services.py` for IB host service connection.

**Implementation Notes:**
- Include: host, port, enabled, timeout, etc.
- Use `deprecated_field()` for `USE_IB_HOST_SERVICE` → `KTRDR_IB_HOST_SERVICE_ENABLED` (this fixes duplication #3 from audit — inconsistent defaults across 4 places)

**Key signatures:**
```python
class IBHostServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KTRDR_IB_HOST_", env_file=".env.local")
    # Fields: host, port, enabled, timeout, ...

@lru_cache
def get_ib_host_service_settings() -> IBHostServiceSettings: ...
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `IBHostServiceSettings` loads defaults correctly
- [ ] `KTRDR_IB_HOST_ENABLED` works
- [ ] Deprecated `USE_IB_HOST_SERVICE` works with warning

**Acceptance Criteria:**
- [ ] `IBHostServiceSettings` class exists
- [ ] Single source of truth for enabled flag (fixes duplication #3)
- [ ] All unit tests pass

---

## Task 3.3: Create `TrainingHostServiceSettings` Class

**Files:** `ktrdr/config/settings.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Add `TrainingHostServiceSettings` class to replace the existing dataclass in `ktrdr/config/host_services.py` for training host service connection.

**Implementation Notes:**
- Include: host, port, enabled, timeout, etc.
- Similar structure to `IBHostServiceSettings`

**Key signatures:**
```python
class TrainingHostServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KTRDR_TRAINING_HOST_", env_file=".env.local")
    # Fields: host, port, enabled, timeout, ...

@lru_cache
def get_training_host_service_settings() -> TrainingHostServiceSettings: ...
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `TrainingHostServiceSettings` loads defaults correctly
- [ ] All fields work via env vars

**Acceptance Criteria:**
- [ ] `TrainingHostServiceSettings` class exists
- [ ] `get_training_host_service_settings()` cached getter exists

---

## Task 3.4: Migrate IB Consumers and Delete `ktrdr/config/ib_config.py`

**Files:** `ktrdr/services/ib/*.py`, `ktrdr/config/ib_config.py` (delete)
**Type:** CODING

**Task Categories:** Wiring/DI

**Description:**
Replace all `IbConfig` usages with `get_ib_settings()`. Delete the old `ib_config.py` file.

**Implementation Notes:**
- Find all `IbConfig()` instantiations
- Replace with `get_ib_settings()`
- Find direct `os.getenv("IB_*")` calls and replace
- Delete `ktrdr/config/ib_config.py` after migration

**Testing Requirements:**

*Integration Tests:*
- [ ] IB service initializes with new settings

**Acceptance Criteria:**
- [ ] Zero `IbConfig` usages
- [ ] `ktrdr/config/ib_config.py` deleted
- [ ] IB functionality unchanged

---

## Task 3.5: Migrate Host Service Consumers and Delete `ktrdr/config/host_services.py`

**Files:** `ktrdr/services/*.py`, `ktrdr/config/host_services.py` (delete)
**Type:** CODING

**Task Categories:** Wiring/DI

**Description:**
Replace all `HostServiceSettings` usages (for both IB and Training) with the new getters. Delete the old `host_services.py` file.

**Implementation Notes:**
- Find all `HostServiceSettings` usages for IB → replace with `get_ib_host_service_settings()`
- Find all `HostServiceSettings` usages for Training → replace with `get_training_host_service_settings()`
- Delete `ktrdr/config/host_services.py` after migration

**Testing Requirements:**

*Integration Tests:*
- [ ] Host service proxying works for IB
- [ ] Host service proxying works for Training

**Acceptance Criteria:**
- [ ] Zero `HostServiceSettings` usages
- [ ] `ktrdr/config/host_services.py` deleted
- [ ] Host service functionality unchanged

---

## Task 3.6: Update Validation Module for M3 Settings

**Files:** `ktrdr/config/validation.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Update `validate_all()` to include M3 Settings classes in `BACKEND_SETTINGS`.

**Acceptance Criteria:**
- [ ] `IBSettings`, `IBHostServiceSettings`, `TrainingHostServiceSettings` validated at startup

---

## Task 3.7: Update Deprecation Module for M3 Names

**Files:** `ktrdr/config/deprecation.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Add deprecated name mappings for IB and host service env vars.

**Implementation Notes:**
- Add mappings like `IB_GATEWAY_HOST` → `KTRDR_IB_GATEWAY_HOST`
- Add `USE_IB_HOST_SERVICE` → `KTRDR_IB_HOST_ENABLED`

**Acceptance Criteria:**
- [ ] All M3 deprecated names in `DEPRECATED_NAMES` dict

---

## Task 3.8: Write Unit Tests

**Files:** `tests/unit/config/test_ib_settings.py`, `tests/unit/config/test_host_service_settings.py`
**Type:** CODING

**Description:**
Write unit tests for all M3 Settings classes.

**Acceptance Criteria:**
- [ ] All M3 Settings classes have unit tests
- [ ] `make test-unit` passes

---

## Task 3.9: Execute E2E Test

**Type:** VALIDATION

**Description:**
Validate M3 is complete with E2E scenarios.

**E2E Test Scenarios:**

### Scenario 1: Backend proxies to IB host service
```bash
# Start full stack including host services
docker compose up -d

# Make request that goes through IB host service
curl http://localhost:8000/api/v1/ib/status
# Expected: response from IB host service (or graceful "not connected" if IB not running)

docker compose down
```

### Scenario 2: USE_IB_HOST_SERVICE (deprecated) works with warning
```bash
USE_IB_HOST_SERVICE=true docker compose up -d backend
docker compose logs backend 2>&1 | grep "USE_IB_HOST_SERVICE.*deprecated"
# Expected: deprecation warning
docker compose down
```

### Scenario 3: Training host service settings work
```bash
docker compose up -d
# Verify training host service is reachable
curl http://localhost:8000/api/v1/training/status
# Expected: response (or graceful error if no GPU)
docker compose down
```

**Success Criteria:**
- [ ] All scenarios pass
- [ ] Host service proxying works
- [ ] Deprecated env vars work with warnings

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E tests pass
- [ ] Quality gates pass: `make quality`
- [ ] `ktrdr/config/ib_config.py` deleted
- [ ] `ktrdr/config/host_services.py` deleted
- [ ] Duplication #3 (inconsistent USE_IB_HOST_SERVICE defaults) resolved
- [ ] Branch merged to main
