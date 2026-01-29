---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 1: Database Settings

**Goal:** Backend starts using new `DatabaseSettings`, validates at startup, accepts deprecated `DB_*` names with warnings.

**Why M1:** Database is the first thing the backend needs. This milestone proves the full pattern works end-to-end before we scale to 15 more Settings classes.

**Branch:** `feature/config-m1-database-settings`

---

## Task 1.1: Create `deprecated_field()` Helper and `DatabaseSettings` Class

**Files:** `ktrdr/config/settings.py`
**Type:** CODING

**Task Categories:** Configuration, Wiring/DI

**Description:**
Add the `deprecated_field()` helper function that creates Pydantic Fields with `AliasChoices` for backward compatibility. Then create `DatabaseSettings` class with all DB-related fields, using the helper for fields that have deprecated names.

**Implementation Notes:**
- `deprecated_field()` MUST list the new name first in `AliasChoices` (see Decision 9 in DESIGN.md)
- `DatabaseSettings` needs computed `url` and `sync_url` properties for connection strings
- Use `env_file=".env.local"` in `model_config` (file is optional)
- Existing `settings.py` has 4 classes — add to it, don't replace
- Reference existing Settings classes in the file for patterns

**Key signatures:**
```python
def deprecated_field(default, new_env: str, old_env: str, **kwargs) -> FieldInfo: ...

class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KTRDR_DB_", env_file=".env.local")
    # Fields: host, port, name, user, password, echo
    # Computed: url, sync_url

@lru_cache
def get_db_settings() -> DatabaseSettings: ...

def clear_settings_cache() -> None: ...
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `DatabaseSettings` loads defaults correctly when no env vars set
- [ ] `KTRDR_DB_HOST` overrides default
- [ ] `DB_HOST` (deprecated) overrides default
- [ ] `KTRDR_DB_HOST` takes precedence when both old and new are set
- [ ] `url` computed field produces correct connection string
- [ ] `sync_url` computed field produces correct connection string
- [ ] Invalid `KTRDR_DB_PORT=abc` raises `ValidationError`
- [ ] `get_db_settings()` returns same instance on repeated calls
- [ ] `clear_settings_cache()` causes new instance on next call

*Integration Tests:*
- [ ] Wiring test: `get_db_settings()` returns a `DatabaseSettings` instance

*Smoke Test:*
```bash
uv run python -c "from ktrdr.config import get_db_settings; print(get_db_settings().url)"
```

**Acceptance Criteria:**
- [ ] `deprecated_field()` helper exists and is documented
- [ ] `DatabaseSettings` class exists with all 6 fields
- [ ] `get_db_settings()` cached getter exists
- [ ] `clear_settings_cache()` exists
- [ ] All unit tests pass
- [ ] Code follows existing patterns in `ktrdr/config/settings.py`

---

## Task 1.2: Create Validation Module

**Files:** `ktrdr/config/validation.py`
**Type:** CODING

**Task Categories:** Configuration, State Machine (validation states)

**Description:**
Rewrite `validation.py` to implement explicit startup validation with `KTRDR_ENV`-aware insecure default detection. The existing file has different validation logic — this is a rewrite, not an extension.

**Implementation Notes:**
- `KTRDR_ENV` is read via `os.getenv()`, NOT from a Settings class (avoids circular dependency)
- `validate_all(component)` accepts "backend", "worker", or "all"
- For M1, only `DatabaseSettings` is validated — we'll add more in later milestones
- Collect ALL errors before raising (don't stop at first)
- `detect_insecure_defaults()` checks if secrets match known insecure values
- Use the project's logging system (`from ktrdr.logging import get_logger`) — NOT print()
- Warning/error formatting should match ARCHITECTURE.md spec

**Key signatures:**
```python
INSECURE_DEFAULTS: dict[str, str] = {"KTRDR_DB_PASSWORD": "localdev", ...}
BACKEND_SETTINGS: list[type] = [DatabaseSettings]
WORKER_SETTINGS: list[type] = [DatabaseSettings]

def validate_all(component: Literal["backend", "worker", "all"] = "all") -> None:
    """Raises ConfigurationError if invalid or insecure defaults in production."""
    ...

def detect_insecure_defaults() -> dict[str, str]:
    """Returns {env_var: value} for secrets at insecure defaults."""
    ...
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `validate_all("backend")` succeeds with valid settings
- [ ] `validate_all("backend")` collects multiple errors (not just first)
- [ ] `validate_all("backend")` with `KTRDR_ENV=production` and insecure default raises
- [ ] `validate_all("backend")` with `KTRDR_ENV=development` and insecure default warns but doesn't raise
- [ ] `detect_insecure_defaults()` returns empty dict when secrets are set
- [ ] `detect_insecure_defaults()` returns dict with insecure values when defaults are used
- [ ] Error message format includes env var name and is human-readable

*Integration Tests:*
- [ ] `validate_all()` actually loads settings from environment

*Smoke Test:*
```bash
KTRDR_ENV=development uv run python -c "from ktrdr.config.validation import validate_all; validate_all('backend')"
# Should print warning about insecure defaults, not raise
```

**Acceptance Criteria:**
- [ ] `validate_all(component)` exists and works
- [ ] `detect_insecure_defaults()` exists and works
- [ ] Error messages are clear and actionable
- [ ] Warning format matches ARCHITECTURE.md spec
- [ ] `KTRDR_ACKNOWLEDGE_INSECURE_DEFAULTS=true` suppresses warning
- [ ] All unit tests pass

---

## Task 1.3: Create Deprecation Module

**Files:** `ktrdr/config/deprecation.py` (new file)
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Create the deprecation module that warns about deprecated env var names at startup. For M1, only include DB_* mappings — we'll add more in later milestones.

**Implementation Notes:**
- Check `os.environ` for deprecated names
- Emit `warnings.warn()` with `DeprecationWarning` category
- Return list of deprecated names found (for logging/testing)

**Key signatures:**
```python
DEPRECATED_NAMES: dict[str, str] = {
    "DB_HOST": "KTRDR_DB_HOST",
    "DB_PORT": "KTRDR_DB_PORT",
    # ... other DB_* mappings
}

def warn_deprecated_env_vars() -> list[str]:
    """Check os.environ for deprecated names, emit DeprecationWarning for each."""
    ...
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `warn_deprecated_env_vars()` returns empty list when no deprecated vars set
- [ ] `warn_deprecated_env_vars()` returns list of found deprecated vars
- [ ] `warn_deprecated_env_vars()` emits `DeprecationWarning` for each found var
- [ ] Warning message includes both old and new name

*Smoke Test:*
```bash
DB_PASSWORD=test uv run python -c "from ktrdr.config.deprecation import warn_deprecated_env_vars; print(warn_deprecated_env_vars())"
# Should print ['DB_PASSWORD'] and emit warning
```

**Acceptance Criteria:**
- [ ] `DEPRECATED_NAMES` dict exists with DB_* mappings
- [ ] `warn_deprecated_env_vars()` exists and works
- [ ] Warnings include clear migration guidance
- [ ] All unit tests pass

---

## Task 1.4: Update `__init__.py` Public API

**Files:** `ktrdr/config/__init__.py`
**Type:** CODING

**Task Categories:** Wiring/DI

**Description:**
Update the config module's public API to export the new settings infrastructure. Keep existing exports for backward compatibility during migration.

**Implementation Notes:**
- Export `DatabaseSettings` class (for type hints)
- Export `get_db_settings` getter (for runtime use)
- Export `validate_all`, `detect_insecure_defaults` from validation
- Export `warn_deprecated_env_vars`, `DEPRECATED_NAMES` from deprecation
- Export `clear_settings_cache` for testing
- Keep existing exports (`metadata`, `ConfigLoader`, etc.) until M7 cleanup

**New exports to add:**
- `DatabaseSettings`, `get_db_settings`, `clear_settings_cache`, `deprecated_field` from settings
- `validate_all`, `detect_insecure_defaults` from validation
- `warn_deprecated_env_vars`, `DEPRECATED_NAMES` from deprecation

**Testing Requirements:**

*Unit Tests:*
- [ ] Can import `DatabaseSettings` from `ktrdr.config`
- [ ] Can import `get_db_settings` from `ktrdr.config`
- [ ] Can import `validate_all` from `ktrdr.config`
- [ ] Can import `warn_deprecated_env_vars` from `ktrdr.config`
- [ ] Existing imports still work (backward compatibility)

*Smoke Test:*
```bash
uv run python -c "from ktrdr.config import DatabaseSettings, get_db_settings, validate_all, warn_deprecated_env_vars; print('OK')"
```

**Acceptance Criteria:**
- [ ] All new APIs exported from `ktrdr.config`
- [ ] Existing imports still work
- [ ] All unit tests pass

---

## Task 1.5: Migrate `database.py` to Use `get_db_settings()`

**Files:** `ktrdr/api/database.py`
**Type:** CODING

**Task Categories:** Persistence, Wiring/DI

**Description:**
Replace direct `os.getenv()` calls in `database.py` with the new `get_db_settings()` getter. This is the first consumer migration — proves the pattern works.

**Implementation Notes:**
- Find all `os.getenv("DB_*")` calls and replace with `get_db_settings().field`
- Use `get_db_settings().url` for the async connection string
- Use `get_db_settings().sync_url` if sync URL is needed
- Remove any inline DATABASE_URL construction
- Don't change the database engine/session logic, just the config source

**Testing Requirements:**

*Unit Tests:*
- [ ] Database module uses `get_db_settings()` (mock test)

*Integration Tests:*
- [ ] Wiring test: database actually connects using new settings
- [ ] DB queries work after migration

*Smoke Test:*
```bash
# After backend starts
curl http://localhost:8000/api/v1/operations | head -1
# Should return JSON (proves DB connection works)
```

**Acceptance Criteria:**
- [ ] Zero `os.getenv("DB_*")` calls in `database.py`
- [ ] Database connection works with new settings
- [ ] Existing tests still pass
- [ ] Code review shows clean migration

---

## Task 1.6: Add Startup Validation to `main.py`

**Files:** `ktrdr/api/main.py`
**Type:** CODING

**Task Categories:** Wiring/DI, Configuration

**Description:**
Add `warn_deprecated_env_vars()` and `validate_all("backend")` calls at the very start of `main.py`, before creating the FastAPI app.

**Implementation Notes:**
- Call `warn_deprecated_env_vars()` first (emit deprecation warnings)
- Call `validate_all("backend")` second (fail fast if invalid)
- These must run BEFORE `app = FastAPI(...)` creation
- If validation fails, the process should exit with code 1

**Code sketch:**
```python
# At the very top of main.py, after imports
from ktrdr.config import warn_deprecated_env_vars, validate_all

# Before any other initialization
warn_deprecated_env_vars()
validate_all("backend")

# Then continue with FastAPI app creation...
```

**Testing Requirements:**

*Integration Tests:*
- [ ] Backend fails to start with invalid config
- [ ] Backend starts with valid config
- [ ] Deprecation warnings appear in logs when using old names

*Smoke Test:*
```bash
# Invalid config should fail
KTRDR_DB_PORT=abc docker compose up backend
# Should exit with code 1

# Valid config should start
docker compose up backend
curl http://localhost:8000/health
# Should return 200
```

**Acceptance Criteria:**
- [ ] `warn_deprecated_env_vars()` called at startup
- [ ] `validate_all("backend")` called at startup
- [ ] Backend fails fast with invalid config
- [ ] Backend starts successfully with valid config
- [ ] Startup time not noticeably impacted

---

## Task 1.7: Write Unit Tests

**Files:** `tests/unit/config/test_database_settings.py`, `tests/unit/config/test_validation.py`, `tests/unit/config/test_deprecation.py`
**Type:** CODING

**Task Categories:** N/A (testing)

**Description:**
Write comprehensive unit tests for all the new code. Tests should cover happy paths, error paths, and edge cases.

**Implementation Notes:**
- Use `monkeypatch.setenv()` to set env vars in tests
- Call `clear_settings_cache()` in fixtures to ensure isolation
- Test the `deprecated_field()` helper with both old and new names
- Test validation with various `KTRDR_ENV` values
- Test deprecation warnings are emitted correctly

**Test file structure:**
```
tests/unit/config/
  test_database_settings.py   # DatabaseSettings class tests
  test_validation.py          # validate_all(), detect_insecure_defaults()
  test_deprecation.py         # warn_deprecated_env_vars()
```

**Acceptance Criteria:**
- [ ] All test cases from Tasks 1.1-1.4 implemented
- [ ] Tests are isolated (use fixtures to clear cache)
- [ ] Tests cover happy paths, error paths, and edge cases
- [ ] `make test-unit` passes
- [ ] Coverage for new code >90%

---

## Task 1.8: Execute E2E Test

**Type:** VALIDATION

**Description:**
Run the E2E tests to validate the milestone is complete. This is the final verification that everything works together.

**E2E Test Scenarios:**

### Scenario 1: New name works

```bash
# Start backend with new env var names
KTRDR_DB_PASSWORD=testpass docker compose up -d backend

# Wait for startup
sleep 5

# Verify backend is healthy
curl -f http://localhost:8000/health
# Expected: 200 OK

# Verify no deprecation warnings
docker compose logs backend 2>&1 | grep -i "deprecated"
# Expected: no output (no deprecated vars used)

# Cleanup
docker compose down
```

### Scenario 2: Old name works with warning

```bash
# Start backend with old env var name
DB_PASSWORD=testpass docker compose up -d backend

# Wait for startup
sleep 5

# Verify backend is healthy (old name should work)
curl -f http://localhost:8000/health
# Expected: 200 OK

# Verify deprecation warning was emitted
docker compose logs backend 2>&1 | grep "DB_PASSWORD.*deprecated"
# Expected: warning about DB_PASSWORD being deprecated

# Cleanup
docker compose down
```

### Scenario 3: Invalid type fails at startup

```bash
# Start backend with invalid port type
KTRDR_DB_PORT=abc docker compose up backend
# Expected: container exits with code 1

# Check error message
docker compose logs backend 2>&1 | grep -i "KTRDR_DB_PORT"
# Expected: error message mentioning KTRDR_DB_PORT

# Cleanup
docker compose down
```

### Scenario 4: Insecure default in production fails

```bash
# Start backend in production mode with default password
KTRDR_ENV=production docker compose up backend
# Expected: container exits with code 1

# Check error message
docker compose logs backend 2>&1 | grep -i "KTRDR_DB_PASSWORD.*insecure\|production"
# Expected: error about insecure defaults in production

# Cleanup
docker compose down
```

### Scenario 5: Insecure default in development warns

```bash
# Start backend in development mode with default password
KTRDR_ENV=development docker compose up -d backend

# Wait for startup
sleep 5

# Verify backend is healthy (should start despite insecure defaults)
curl -f http://localhost:8000/health
# Expected: 200 OK

# Verify insecure warning was emitted
docker compose logs backend 2>&1 | grep -i "INSECURE DEFAULT"
# Expected: warning about insecure defaults

# Cleanup
docker compose down
```

**Success Criteria:**
- [ ] All 5 scenarios pass
- [ ] Backend connects to database successfully
- [ ] Deprecation warnings work correctly
- [ ] Production mode rejects insecure defaults
- [ ] Development mode warns about insecure defaults

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E tests pass (all 5 scenarios above)
- [ ] Quality gates pass: `make quality`
- [ ] No regressions introduced
- [ ] Code reviewed
- [ ] Branch merged to main
