---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 2: API, Auth & Logging Settings

**Goal:** Backend serves requests with new `APISettings`, `AuthSettings`, `LoggingSettings`, and `ObservabilitySettings`. Logs correctly. Traces to Jaeger.

**Why M2:** API, auth, and logging are core backend infrastructure. After M1 proves database works, M2 completes the backend's core configuration needs.

**Branch:** `feature/config-m2-api-auth-logging`

**Depends on:** M1 (Database Settings)

---

## Task 2.1: Create `APISettings` Class

**Files:** `ktrdr/config/settings.py`
**Type:** CODING

**Task Categories:** Configuration, Wiring/DI

**Description:**
Add `APISettings` class with all API-related fields. Merge fields from the existing `ktrdr/api/config.py` `APIConfig` class — this resolves duplication #1 from the audit.

**Implementation Notes:**
- Merge fields from `ktrdr/api/config.py::APIConfig` (this class will be deleted in Task 2.5)
- Use `deprecated_field()` for any fields with old env var names
- Include: host, port, debug, environment, cors_origins, etc.
- Reference existing patterns in `settings.py`

**Key signatures:**
```python
class APISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KTRDR_API_", env_file=".env.local")
    # Fields: host, port, debug, environment, cors_origins, ...

@lru_cache
def get_api_settings() -> APISettings: ...
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `APISettings` loads defaults correctly
- [ ] `KTRDR_API_PORT` overrides default
- [ ] Deprecated names (if any) work with warnings
- [ ] `get_api_settings()` caching works

**Acceptance Criteria:**
- [ ] `APISettings` class exists with all API fields
- [ ] `get_api_settings()` cached getter exists
- [ ] Fields match combined set from `APIConfig` + existing needs
- [ ] All unit tests pass

---

## Task 2.2: Create `AuthSettings` Class

**Files:** `ktrdr/config/settings.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Add `AuthSettings` class for JWT and authentication configuration.

**Implementation Notes:**
- `jwt_secret` is a secret field — use `deprecated_field()` if old name exists
- Include: jwt_secret, jwt_algorithm, token_expire_minutes, etc.
- Mark `jwt_secret` for insecure default detection in validation module

**Key signatures:**
```python
class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KTRDR_AUTH_", env_file=".env.local")
    # Fields: jwt_secret, jwt_algorithm, token_expire_minutes, ...

@lru_cache
def get_auth_settings() -> AuthSettings: ...
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `AuthSettings` loads defaults correctly
- [ ] `jwt_secret` can be overridden via env var
- [ ] Deprecated name support (if applicable)

**Acceptance Criteria:**
- [ ] `AuthSettings` class exists
- [ ] `get_auth_settings()` cached getter exists
- [ ] All unit tests pass

---

## Task 2.3: Create `LoggingSettings` Class

**Files:** `ktrdr/config/settings.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Add `LoggingSettings` class for logging configuration.

**Implementation Notes:**
- Include: level, format, json_output, etc.
- Some logging settings may come from existing `LOG_LEVEL` env var

**Key signatures:**
```python
class LoggingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KTRDR_LOG_", env_file=".env.local")
    # Fields: level, format, json_output, ...

@lru_cache
def get_logging_settings() -> LoggingSettings: ...
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `LoggingSettings` loads defaults correctly
- [ ] `KTRDR_LOG_LEVEL` overrides default

**Acceptance Criteria:**
- [ ] `LoggingSettings` class exists
- [ ] `get_logging_settings()` cached getter exists
- [ ] All unit tests pass

---

## Task 2.4: Create `ObservabilitySettings` Class

**Files:** `ktrdr/config/settings.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Add `ObservabilitySettings` class for Jaeger/tracing configuration.

**Implementation Notes:**
- Include: jaeger_host, jaeger_port, service_name, enabled, etc.
- Reference existing Jaeger env vars in codebase

**Key signatures:**
```python
class ObservabilitySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KTRDR_OTEL_", env_file=".env.local")
    # Fields: jaeger_host, jaeger_port, service_name, enabled, ...

@lru_cache
def get_observability_settings() -> ObservabilitySettings: ...
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `ObservabilitySettings` loads defaults correctly
- [ ] Jaeger connection settings work

**Acceptance Criteria:**
- [ ] `ObservabilitySettings` class exists
- [ ] `get_observability_settings()` cached getter exists
- [ ] All unit tests pass

---

## Task 2.5: Migrate API Consumers and Delete `ktrdr/api/config.py`

**Files:** `ktrdr/api/*.py`, `ktrdr/api/config.py` (delete)
**Type:** CODING

**Task Categories:** Wiring/DI, Persistence

**Description:**
Replace all `os.getenv()` calls and `APIConfig` usage in `ktrdr/api/` with the new settings getters. Then delete `ktrdr/api/config.py` to resolve duplication #1.

**Implementation Notes:**
- Find all `os.getenv("KTRDR_API_*")` and `os.getenv("API_*")` calls
- Replace with `get_api_settings().field`
- Find all `APIConfig()` usages and replace with `get_api_settings()`
- Delete `ktrdr/api/config.py` after all usages migrated

**Testing Requirements:**

*Integration Tests:*
- [ ] API starts and responds to requests
- [ ] CORS settings work correctly

**Acceptance Criteria:**
- [ ] Zero `os.getenv("API_*")` calls in `ktrdr/api/`
- [ ] `ktrdr/api/config.py` deleted
- [ ] Existing tests still pass

---

## Task 2.6: Migrate Auth Consumers

**Files:** `ktrdr/api/auth/*.py`
**Type:** CODING

**Task Categories:** Wiring/DI

**Description:**
Replace all auth-related `os.getenv()` calls with `get_auth_settings()`.

**Implementation Notes:**
- Find all `os.getenv("JWT_*")` and similar calls
- Replace with `get_auth_settings().field`

**Testing Requirements:**

*Integration Tests:*
- [ ] JWT token generation works
- [ ] Token validation works

**Acceptance Criteria:**
- [ ] Zero direct auth env var reads
- [ ] Auth functionality unchanged

---

## Task 2.7: Migrate Logging Consumers

**Files:** `ktrdr/logging/*.py`
**Type:** CODING

**Task Categories:** Wiring/DI

**Description:**
Replace logging-related `os.getenv()` calls with `get_logging_settings()`.

**Implementation Notes:**
- Find `LOG_LEVEL` and similar reads
- Replace with `get_logging_settings().field`

**Testing Requirements:**

*Integration Tests:*
- [ ] Log level changes based on settings
- [ ] Log format correct

**Acceptance Criteria:**
- [ ] Zero direct logging env var reads in logging module
- [ ] Logging behavior unchanged

---

## Task 2.8: Migrate Observability/Tracing Consumers

**Files:** `ktrdr/observability/*.py`
**Type:** CODING

**Task Categories:** Wiring/DI

**Description:**
Replace Jaeger/tracing `os.getenv()` calls with `get_observability_settings()`.

**Implementation Notes:**
- Find all `JAEGER_*`, `OTEL_*` env var reads
- Replace with `get_observability_settings().field`

**Testing Requirements:**

*Integration Tests:*
- [ ] Traces appear in Jaeger

**Acceptance Criteria:**
- [ ] Zero direct observability env var reads
- [ ] Tracing still works

---

## Task 2.9: Update Validation Module for M2 Settings

**Files:** `ktrdr/config/validation.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Update `validate_all()` to include the new M2 Settings classes. Add any new secrets to `INSECURE_DEFAULTS`.

**Implementation Notes:**
- Add `APISettings`, `AuthSettings`, `LoggingSettings`, `ObservabilitySettings` to `BACKEND_SETTINGS`
- Add `AuthSettings.jwt_secret` to `INSECURE_DEFAULTS` if it has an insecure default

**Acceptance Criteria:**
- [ ] All M2 settings classes validated at startup
- [ ] Insecure jwt_secret detected in production mode

---

## Task 2.10: Update Deprecation Module for M2 Names

**Files:** `ktrdr/config/deprecation.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Add deprecated name mappings for API, auth, logging, and observability env vars.

**Implementation Notes:**
- Add mappings like `API_PORT` → `KTRDR_API_PORT`
- Add mappings for any auth, logging, observability deprecated names

**Acceptance Criteria:**
- [ ] All M2 deprecated names in `DEPRECATED_NAMES` dict
- [ ] Deprecation warnings emitted for old names

---

## Task 2.11: Write Unit Tests

**Files:** `tests/unit/config/test_api_settings.py`, `tests/unit/config/test_auth_settings.py`, etc.
**Type:** CODING

**Description:**
Write comprehensive unit tests for all M2 Settings classes.

**Acceptance Criteria:**
- [ ] All M2 Settings classes have unit tests
- [ ] Tests cover happy paths, error paths, and edge cases
- [ ] `make test-unit` passes

---

## Task 2.12: Execute E2E Test

**Type:** VALIDATION

**Description:**
Validate M2 is complete with E2E scenarios.

**E2E Test Scenarios:**

### Scenario 1: Backend serves requests
```bash
docker compose up -d backend
curl -f http://localhost:8000/api/v1/operations
# Expected: 200 OK with JSON response
docker compose down
```

### Scenario 2: Logs appear with correct format
```bash
docker compose up -d backend
docker compose logs backend 2>&1 | grep -E "INFO|DEBUG"
# Expected: log lines present with expected format
docker compose down
```

### Scenario 3: Traces appear in Jaeger
```bash
docker compose up -d
# Make some API requests
curl http://localhost:8000/api/v1/operations
# Check Jaeger
curl "http://localhost:16686/api/traces?service=ktrdr-backend&limit=1"
# Expected: traces found
docker compose down
```

### Scenario 4: Invalid JWT secret in production fails
```bash
KTRDR_ENV=production docker compose up backend
# Expected: exit code 1, error about insecure jwt_secret
docker compose down
```

**Success Criteria:**
- [ ] All scenarios pass
- [ ] Backend serves requests correctly
- [ ] Logging works
- [ ] Tracing works
- [ ] Production mode rejects insecure auth defaults

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E tests pass
- [ ] Quality gates pass: `make quality`
- [ ] No regressions introduced
- [ ] `ktrdr/api/config.py` deleted (resolves duplication #1)
- [ ] Branch merged to main
