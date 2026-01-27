# Configuration System Redesign: Architecture

> **Status:** Architecture defined, ready for validation.
> **Dependency:** M6/M7 (sandbox → local-prod) landed on main. Blocker resolved.
> See `VALIDATION_NOTES.md` for session notes from 2026-01-18.

## Overview

The new configuration system consolidates all KTRDR settings into Pydantic BaseSettings classes organized by concern. Configuration flows from Python defaults, overridden by environment variables. Secrets are injected via 1Password at deploy time. The system validates all settings at import time, failing fast with clear error messages.

## Components

### Component 1: Settings Module

**Responsibility:** Define all configuration as Pydantic BaseSettings classes.

**Location:** `ktrdr/config/settings.py`

**Pattern:** Each concern gets its own Settings class with:
- Typed fields with defaults (or no default for required fields)
- `env_prefix` for namespacing (e.g., `KTRDR_DB_`)
- `AliasChoices` for deprecated env var names during migration
- Cached getter function (e.g., `get_db_settings()`)

**Settings Classes to Create:**

| Class | Prefix | Purpose |
|-------|--------|---------|
| `DatabaseSettings` | `KTRDR_DB_` | PostgreSQL connection |
| `APISettings` | `KTRDR_API_` | FastAPI server config |
| `AuthSettings` | `KTRDR_AUTH_` | JWT and security |
| `IBSettings` | `KTRDR_IB_` | Interactive Brokers connection |
| `IBHostServiceSettings` | `KTRDR_IB_HOST_SERVICE_` | IB proxy for Docker |
| `TrainingHostServiceSettings` | `KTRDR_TRAINING_HOST_` | GPU training proxy |
| `WorkerSettings` | `KTRDR_WORKER_` | Worker process config |
| `ObservabilitySettings` | `KTRDR_OTEL_` | OpenTelemetry/Jaeger |
| `LoggingSettings` | `KTRDR_LOG_` | Logging config |
| `CheckpointSettings` | `KTRDR_CHECKPOINT_` | Operation checkpoints |
| `OrphanDetectorSettings` | `KTRDR_ORPHAN_` | Orphan operation detection |
| `AgentSettings` | `KTRDR_AGENT_` | AI agent config |

**Key Pattern — Cached Getters:**
```python
@lru_cache
def get_db_settings() -> DatabaseSettings:
    return DatabaseSettings()
```

This ensures settings are loaded once and reused. Tests call `clear_settings_cache()` to reset.

---

### Component 2: Validation Module

**Responsibility:** Validate all required settings at startup, fail fast with clear errors.

**Location:** `ktrdr/config/validation.py`

**Behavior:**
1. Attempt to instantiate each required Settings class
2. Collect all validation errors (don't stop at first)
3. If any errors, print formatted error message and raise `ConfigurationError`
4. Called at app startup before serving requests

**Key Function:**
- `validate_all(component: str)` — Validates settings for "backend", "worker", or "all"

**Error Output Format:**
```
CONFIGURATION ERROR
====================
Missing required settings:
  - KTRDR_DB_PASSWORD: Database password (required)
  - KTRDR_AUTH_JWT_SECRET: JWT signing secret (required)

See: docs/configuration.md
====================
```

---

### Component 3: Deprecation Module

**Responsibility:** Warn about deprecated env var names during migration period.

**Location:** `ktrdr/config/deprecation.py`

**Behavior:**
1. Maintain mapping of old names → new names
2. At startup, check if any deprecated names are set
3. Emit `DeprecationWarning` for each
4. Old names still work (via `AliasChoices` in Settings fields)

**Deprecated Names to Support:**

| Old Name | New Name |
|----------|----------|
| `DB_HOST` | `KTRDR_DB_HOST` |
| `DB_PASSWORD` | `KTRDR_DB_PASSWORD` |
| `IB_HOST` | `KTRDR_IB_HOST` |
| `IB_PORT` | `KTRDR_IB_PORT` |
| `JWT_SECRET` | `KTRDR_AUTH_JWT_SECRET` |
| `USE_IB_HOST_SERVICE` | `KTRDR_IB_HOST_SERVICE_ENABLED` |
| `OTLP_ENDPOINT` | `KTRDR_OTEL_ENDPOINT` |
| `LOG_LEVEL` | `KTRDR_LOG_LEVEL` |
| `ANTHROPIC_API_KEY` | `KTRDR_AGENT_API_KEY` |
| (full list in implementation) | |

---

### Component 4: Public API

**Responsibility:** Export clean public interface from `ktrdr/config/`.

**Location:** `ktrdr/config/__init__.py`

**Exports:**
- All Settings classes (for type hints)
- All cached getters (for runtime use)
- `validate_all()` function
- `clear_settings_cache()` for testing
- `warn_deprecated_env_vars()` for startup

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        Application Startup                       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. warn_deprecated_env_vars()                                   │
│     - Check for old env var names                                │
│     - Emit DeprecationWarning for each                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. validate_all(component="backend")                            │
│     - Instantiate each Settings class                            │
│     - Collect validation errors                                  │
│     - If errors: print message, raise ConfigurationError         │
│     - If valid: continue                                         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Application runs                                             │
│     - Components call get_*_settings() as needed                 │
│     - Settings cached after first load                           │
└─────────────────────────────────────────────────────────────────┘
```

### Settings Resolution Order

For each field, Pydantic BaseSettings checks (in order):
1. Environment variable with prefix (e.g., `KTRDR_DB_HOST`)
2. Environment variable from `AliasChoices` (e.g., `DB_HOST` — deprecated)
3. `.env.local` file (if exists, gitignored)
4. Python default in field definition

---

## Integration Points

### Backend Startup (`ktrdr/api/main.py`)

Current code calls various config loaders. After migration:
1. Import `validate_all`, `warn_deprecated_env_vars`
2. Call both at startup before creating FastAPI app
3. Exit with code 1 if validation fails

### Worker Startup

Each worker entrypoint:
1. Call `validate_all(component="worker")`
2. Workers validate only the settings they need (DB, logging, worker, checkpoint)

### Database Connection (`ktrdr/api/database.py`)

Current code uses `os.getenv("DB_*")` directly. After migration:
1. Import `get_db_settings`
2. Use `get_db_settings().url` for connection string

### Existing Settings Usage

All existing code that reads config:
- `os.getenv("SOME_VAR")` → `get_*_settings().field`
- `metadata.get("path.to.value")` → `get_*_settings().field`
- Direct imports from old modules → imports from `ktrdr.config`

---

## File Changes

### Files to Create

| File | Purpose |
|------|---------|
| `ktrdr/config/settings.py` | All Settings classes |
| `ktrdr/config/validation.py` | Startup validation |
| `ktrdr/config/deprecation.py` | Deprecated name warnings |

### Files to Modify

| File | Change |
|------|--------|
| `ktrdr/config/__init__.py` | New public API |
| `ktrdr/api/main.py` | Add validation at startup |
| `ktrdr/api/database.py` | Use `get_db_settings()` |
| Worker entrypoints | Add validation at startup |
| Docker compose files | Update env var names |
| `.env.*` templates | Update env var names |

### Files to Delete (After Migration)

| File | Reason |
|------|--------|
| `ktrdr/metadata.py` | Replaced by settings + pyproject.toml |
| `ktrdr/config/loader.py` | No more YAML loading |
| `ktrdr/config/host_services.py` | Merged into settings.py |
| `ktrdr/config/ib_config.py` | Merged into settings.py |
| `ktrdr/api/config.py` | Merged into settings.py |
| `config/ktrdr_metadata.yaml` | Project info → pyproject.toml |
| `config/settings.yaml` | Merged into settings.py |
| `config/environment/*.yaml` | No more YAML layering |
| `config/indicators.yaml` | Unused |
| `config/ib_host_service.yaml` | Merged into settings.py |
| `config/training_host_service.yaml` | Merged into settings.py |

---

## Testing Strategy

### Unit Tests

**For each Settings class:**
- Test default values are correct
- Test env var override works
- Test deprecated alias works
- Test validation catches invalid values
- Test required fields fail without value

**For validation module:**
- Test `validate_all()` collects multiple errors
- Test error message format is readable
- Test component filtering works

**For deprecation module:**
- Test warnings emitted for deprecated names
- Test no warnings when using new names

### End-to-End Tests (CRITICAL)

These tests run real containers and verify the system actually works. They are NOT optional.

#### E2E Test Suite: Config System

| Test | What It Verifies | How |
|------|------------------|-----|
| **Backend starts with valid config** | New settings system works in production | Start backend container with all required env vars, verify `/health` returns 200 |
| **Backend fails with missing DB password** | Validation catches missing required settings | Start backend WITHOUT `KTRDR_DB_PASSWORD`, verify container exits with code 1 and stderr contains "KTRDR_DB_PASSWORD" |
| **Backend fails with missing JWT secret** | Validation catches missing auth settings | Start backend WITHOUT `KTRDR_AUTH_JWT_SECRET`, verify container exits with code 1 and stderr contains "KTRDR_AUTH_JWT_SECRET" |
| **Backend fails with invalid port** | Validation catches type errors | Start backend with `KTRDR_API_PORT=not_a_number`, verify container exits with code 1 and error message is clear |
| **Deprecated env vars work** | Backward compatibility during migration | Start backend with `DB_PASSWORD` (old name), verify it starts successfully |
| **Deprecated env vars emit warning** | Users know to update their config | Start backend with `DB_PASSWORD`, verify stderr contains deprecation warning |
| **Worker starts with valid config** | Worker settings work | Start worker container with required env vars, verify `/health` returns 200 |
| **Worker connects to backend** | Worker registration works with new settings | Start backend + worker, verify worker appears in `GET /api/v1/workers` |
| **Backend connects to database** | DatabaseSettings.url works correctly | Start full stack, run a query via API (e.g., `GET /api/v1/operations`), verify no DB connection errors |
| **API serves requests** | APISettings work correctly | Start backend, verify Swagger UI loads at `/api/v1/docs` |
| **CORS headers correct** | CORS settings applied | Start backend with `KTRDR_API_CORS_ORIGINS=https://example.com`, verify response headers |
| **Log level respected** | LoggingSettings work | Start backend with `KTRDR_LOG_LEVEL=DEBUG`, verify debug logs appear |
| **Full stack with new env vars only** | Can remove deprecated names | Start entire stack using ONLY new `KTRDR_*` names, verify everything works |

#### E2E Test: Error Message Quality

The error messages must be actionable. These tests verify humans can debug config issues:

| Scenario | Required in Error Output |
|----------|-------------------------|
| Missing `KTRDR_DB_PASSWORD` | "KTRDR_DB_PASSWORD", "required", "database" |
| Missing `KTRDR_AUTH_JWT_SECRET` | "KTRDR_AUTH_JWT_SECRET", "required", "JWT" |
| Invalid `KTRDR_API_PORT=abc` | "KTRDR_API_PORT", "integer", "abc" |
| Multiple missing settings | ALL missing settings listed (not just first) |
| Any config error | "See: docs/configuration.md" |

#### E2E Test: Migration Scenarios

These verify the migration path works:

| Scenario | Expected Behavior |
|----------|-------------------|
| Old names only (`DB_PASSWORD`, `IB_HOST`, etc.) | System starts, deprecation warnings in logs |
| Mix of old and new names | System starts, warnings only for old names used |
| New names only | System starts, no deprecation warnings |
| Old name AND new name for same setting | New name takes precedence, warning emitted |

### Test Implementation Notes

- E2E tests go in `tests/e2e/config/`
- Use `docker compose` to start real containers
- Capture stdout/stderr for assertion
- Tests must clean up containers after run
- Tests must be idempotent (can run multiple times)
- Timeout: 60 seconds per test (container startup)

### Sandbox Compatibility

Tests MUST work in sandbox environments where ports differ:

| Environment | API Port | DB Port |
|-------------|----------|---------|
| Main | 8000 | 5432 |
| Sandbox slot 1 | 8001 | 5433 |
| Sandbox slot 2 | 8002 | 5434 |

**Requirements:**
- Tests read ports from `.env.sandbox` if it exists
- Tests use `uv run ktrdr sandbox status` or equivalent to detect environment
- No hardcoded `localhost:8000` — always use detected/configured ports
- Use existing sandbox helpers from `ktrdr.cli.sandbox_ports` if available
- Docker compose commands must target the correct project (e.g., `ktrdr--feature-name-backend-1`)

### Test Fixtures (Unit Tests Only)

```python
@pytest.fixture(autouse=True)
def reset_settings():
    """Clear settings cache before/after each test."""
    clear_settings_cache()
    yield
    clear_settings_cache()
```

---

## Migration Plan

### Phase 1: Foundation (No Breaking Changes)

**Goal:** Create new settings module alongside existing code.

1. Create `ktrdr/config/settings.py` with all Settings classes
2. Create `ktrdr/config/validation.py`
3. Create `ktrdr/config/deprecation.py`
4. Update `ktrdr/config/__init__.py`
5. Write comprehensive tests
6. **Existing code unchanged** — both systems coexist

**Verification:**
- All new tests pass
- Existing tests still pass
- Can import from `ktrdr.config` and use new settings

### Phase 2: Incremental Migration

**Goal:** Migrate existing code to use new settings, one area at a time.

Order of migration (each is a separate PR):
1. Database settings (`ktrdr/api/database.py`)
2. API settings (`ktrdr/api/main.py`, `ktrdr/api/config.py`)
3. IB settings (`ktrdr/config/ib_config.py` usages)
4. Host service settings
5. Worker settings
6. Operational settings (checkpoint, orphan, observability)
7. Agent settings

**For each migration:**
- Update code to use new getter
- Update tests
- Verify deprecated names still work
- Delete old code only when fully migrated

### Phase 3: Cleanup

**Goal:** Remove all old config code and files.

1. Delete deprecated modules (see Files to Delete above)
2. Delete unused YAML files
3. Update documentation
4. Generate config reference from Pydantic models

### Phase 4: Deprecation Removal (Future Release)

**Goal:** Remove support for old env var names.

1. Remove `AliasChoices` for deprecated names
2. Update docker-compose to use only new names
3. Update all `.env` templates
4. Update documentation

---

## Verification Checklist

### Per-Component Verification

| Component | Unit Test | Integration Test | Smoke Test |
|-----------|-----------|------------------|------------|
| Settings classes | Field defaults, validation | N/A | N/A |
| Validation module | Error collection, formatting | Backend startup fails correctly | `docker compose up` with missing config |
| Deprecation module | Warning emission | Warnings appear in logs | `DB_PASSWORD=x docker compose up` shows warning |
| Database integration | N/A | Connection uses new settings | Backend connects to DB |
| API integration | N/A | Server uses new settings | Swagger UI loads |

### Migration Verification

Before deleting any old code:
- [ ] All usages migrated to new settings
- [ ] All tests pass
- [ ] Deprecated names still work
- [ ] No direct `os.getenv()` calls for migrated settings
- [ ] Docker compose works with both old and new names
