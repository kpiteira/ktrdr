# Configuration System Redesign: Architecture

> **Status:** Validated. Ready for implementation planning.
> **Dependency:** M6/M7 (sandbox → local-prod) landed on main. Blocker resolved.
> See `SCENARIOS.md` for validation results. See `VALIDATION_NOTES.md` for earlier session notes.

## Overview

The new configuration system consolidates all ~90 KTRDR environment variables and 14 YAML config files into 16 Pydantic BaseSettings classes organized by concern. Configuration flows from Python defaults, overridden by environment variables. Secrets are injected via 1Password at deploy time. The system validates all settings at explicit startup call, failing fast with clear error messages.

This is a full cleanup — every duplication resolved, every scattered `os.getenv()` replaced with a single cached getter, every inconsistent name standardized to `KTRDR_*`.

## Components

### Component 1: Settings Module

**Responsibility:** Define all configuration as Pydantic BaseSettings classes.

**Location:** `ktrdr/config/settings.py`

**Pattern:** Each concern gets its own Settings class with:
- Typed fields with defaults (or no default for required fields)
- `env_prefix` for namespacing (e.g., `KTRDR_DB_`)
- `AliasChoices` for deprecated env var names during migration
- Cached getter function (e.g., `get_db_settings()`)

**Settings Classes (16 total):**

| Class | Prefix | Fields | Purpose |
|-------|--------|--------|---------|
| `DatabaseSettings` | `KTRDR_DB_` | host, port, name, user, password, echo | PostgreSQL connection |
| `APISettings` | `KTRDR_API_` | title, description, version, host, port, reload, log_level, prefix, cors_* | FastAPI server (merges `APIConfig` + old `APISettings`) |
| `AuthSettings` | `KTRDR_AUTH_` | jwt_secret, anthropic_api_key | Secrets and authentication |
| `IBSettings` | `KTRDR_IB_` | host, port, client_id, timeout, readonly, rate_limit, rate_period, max_retries, retry_delay, retry_max_delay, pacing_delay, max_requests_10min, username, account_id, api_key | IB connection (merges `IbConfig` dataclass + credentials) |
| `IBHostServiceSettings` | `KTRDR_IB_HOST_` | enabled, url, timeout, health_interval, max_retries, retry_delay | IB host service proxy |
| `TrainingHostServiceSettings` | `KTRDR_TRAINING_HOST_` | enabled, url, timeout, health_interval, max_retries, retry_delay, poll_interval, session_timeout | Training host service proxy |
| `WorkerSettings` | `KTRDR_WORKER_` | id, port, type, public_url, backend_url, shutdown_timeout | Worker process config |
| `ObservabilitySettings` | `KTRDR_OTEL_` | endpoint, service_name | OpenTelemetry/Jaeger |
| `LoggingSettings` | `KTRDR_LOG_` | level, format | Logging config |
| `CheckpointSettings` | `KTRDR_CHECKPOINT_` | epoch_interval, time_interval, dir, max_age_days | Operation checkpoints |
| `OrphanDetectorSettings` | `KTRDR_ORPHAN_` | timeout, check_interval | Orphan operation detection |
| `AgentSettings` | `KTRDR_AGENT_` | enabled, model, max_tokens, timeout, max_iterations, max_input_tokens, daily_budget, budget_dir, poll_interval, trigger_interval, training_start/end, backtest_start/end, max_concurrent, concurrency_buffer, use_stubs, stub_fast, stub_delay | AI agent config |
| `AgentGateSettings` | `KTRDR_GATE_` | training_min_accuracy, training_max_loss, training_min_loss_decrease, backtest_min_win_rate, backtest_max_drawdown, backtest_min_sharpe | Quality gate thresholds |
| `DataSettings` | `KTRDR_DATA_` | dir, format, max_segment_size, save_interval, models_dir, strategies_dir | Data storage and acquisition |
| `OperationsSettings` | `KTRDR_OPS_` | cache_ttl | Operations service |
| `APIClientSettings` | `KTRDR_API_CLIENT_` | base_url, timeout, max_retries, retry_delay | API client for CLI/workers |

**Key Pattern — Cached Getters:**
```python
@lru_cache
def get_db_settings() -> DatabaseSettings:
    return DatabaseSettings()
```

This ensures settings are loaded once and reused. Tests call `clear_settings_cache()` to reset.

---

### Component 2: Validation Module

**Responsibility:** Validate all required settings at explicit startup call, detect insecure defaults, fail fast with clear errors.

**Location:** `ktrdr/config/validation.py` (existing file, to be rewritten)

**Critical Design Choice:** Validation is an **explicit startup call**, NOT import-time.
This is because CLI commands like `ktrdr --help` or `ktrdr data show` must work without a database password.
Only `ktrdr/api/main.py` and worker entrypoints call `validate_all()`.

**Behavior:**
1. Read `KTRDR_ENV` via `os.getenv()` (NOT from a Settings class — avoids circular dependency)
2. Attempt to instantiate each required Settings class for the given component
3. Collect all validation errors (don't stop at first)
4. Detect insecure defaults in use (secrets still at their dev default values)
5. **If `KTRDR_ENV=production`:** Insecure defaults are **hard failures** (local-prod IS production)
6. **If `KTRDR_ENV=development` or unset:** Insecure defaults emit BIG WARNING but don't fail
7. If any hard errors, print formatted error message and raise `ConfigurationError`

**Key Functions:**
- `validate_all(component: str)` — Validates settings for "backend", "worker", or "all"
- `detect_insecure_defaults()` — Checks if secrets are still at their default values

**Insecure Defaults Detection:**
```python
INSECURE_DEFAULTS = {
    "KTRDR_DB_PASSWORD": "localdev",
    "KTRDR_AUTH_JWT_SECRET": "local-dev-secret-do-not-use-in-production",
}
```

**Error Output Format (missing required settings):**
```
CONFIGURATION ERROR
====================
Missing required settings:
  - KTRDR_DB_PASSWORD: Database password (required)
  - KTRDR_AUTH_JWT_SECRET: JWT signing secret (required)

See: docs/configuration.md
====================
```

**Warning Output Format (insecure defaults in dev mode):**
```
========================================
WARNING: INSECURE DEFAULT CONFIGURATION
========================================
The following settings are using insecure defaults:
  - KTRDR_DB_PASSWORD: Using default "localdev"
  - KTRDR_AUTH_JWT_SECRET: Using default "local-dev-secret..."

This is fine for local development but MUST NOT be used in production.

To suppress this warning:
  - Set these values via 1Password (recommended)
  - Or create .env.local with secure values
  - Or set KTRDR_ACKNOWLEDGE_INSECURE_DEFAULTS=true
========================================
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

**Complete Deprecated Names Map (from codebase audit 2026-01-27):**

Database:

| Old Name | New Name |
|----------|----------|
| `DB_HOST` | `KTRDR_DB_HOST` |
| `DB_PORT` | `KTRDR_DB_PORT` |
| `DB_NAME` | `KTRDR_DB_NAME` |
| `DB_USER` | `KTRDR_DB_USER` |
| `DB_PASSWORD` | `KTRDR_DB_PASSWORD` |
| `DB_ECHO` | `KTRDR_DB_ECHO` |
| `DATABASE_URL` | Remove (compute from parts) |

Environment:

| Old Name | New Name |
|----------|----------|
| `ENVIRONMENT` | `KTRDR_ENV` |
| `KTRDR_ENVIRONMENT` | `KTRDR_ENV` |
| `KTRDR_API_ENVIRONMENT` | `KTRDR_ENV` |
| `APP_VERSION` | `KTRDR_VERSION` (or importlib.metadata) |

Auth/Secrets:

| Old Name | New Name |
|----------|----------|
| `JWT_SECRET` | `KTRDR_AUTH_JWT_SECRET` |
| `ANTHROPIC_API_KEY` | `KTRDR_AUTH_ANTHROPIC_KEY` |

Logging:

| Old Name | New Name |
|----------|----------|
| `LOG_LEVEL` | `KTRDR_LOG_LEVEL` |
| `KTRDR_LOGGING_LEVEL` | `KTRDR_LOG_LEVEL` |
| `KTRDR_LOGGING_FORMAT` | `KTRDR_LOG_FORMAT` |

Observability:

| Old Name | New Name |
|----------|----------|
| `OTLP_ENDPOINT` | `KTRDR_OTEL_ENDPOINT` |

IB Connection:

| Old Name | New Name |
|----------|----------|
| `IB_HOST` | `KTRDR_IB_HOST` |
| `IB_PORT` | `KTRDR_IB_PORT` |
| `IB_CLIENT_ID` | `KTRDR_IB_CLIENT_ID` |
| `IB_TIMEOUT` | `KTRDR_IB_TIMEOUT` |
| `IB_READONLY` | `KTRDR_IB_READONLY` |
| `IB_RATE_LIMIT` | `KTRDR_IB_RATE_LIMIT` |
| `IB_RATE_PERIOD` | `KTRDR_IB_RATE_PERIOD` |
| `IB_MAX_RETRIES` | `KTRDR_IB_MAX_RETRIES` |
| `IB_RETRY_DELAY` | `KTRDR_IB_RETRY_DELAY` |
| `IB_RETRY_MAX_DELAY` | `KTRDR_IB_RETRY_MAX_DELAY` |
| `IB_PACING_DELAY` | `KTRDR_IB_PACING_DELAY` |
| `IB_MAX_REQUESTS_10MIN` | `KTRDR_IB_MAX_REQUESTS_10MIN` |

IB Host Service:

| Old Name | New Name |
|----------|----------|
| `USE_IB_HOST_SERVICE` | `KTRDR_IB_HOST_ENABLED` |
| `IB_HOST_SERVICE_URL` | `KTRDR_IB_HOST_URL` |

Training Host Service:

| Old Name | New Name |
|----------|----------|
| `USE_TRAINING_HOST_SERVICE` | `KTRDR_TRAINING_HOST_ENABLED` |
| `TRAINING_HOST_SERVICE_URL` | `KTRDR_TRAINING_HOST_URL` |

Workers:

| Old Name | New Name |
|----------|----------|
| `WORKER_ID` | `KTRDR_WORKER_ID` |
| `WORKER_PORT` | `KTRDR_WORKER_PORT` |
| `WORKER_TYPE` | `KTRDR_WORKER_TYPE` |
| `WORKER_PUBLIC_BASE_URL` | `KTRDR_WORKER_PUBLIC_URL` |
| `WORKER_ENDPOINT_URL` | `KTRDR_WORKER_PUBLIC_URL` (merge) |

Orphan Detector:

| Old Name | New Name |
|----------|----------|
| `ORPHAN_TIMEOUT_SECONDS` | `KTRDR_ORPHAN_TIMEOUT` |
| `ORPHAN_CHECK_INTERVAL_SECONDS` | `KTRDR_ORPHAN_CHECK_INTERVAL` |

Checkpoint:

| Old Name | New Name |
|----------|----------|
| `CHECKPOINT_EPOCH_INTERVAL` | `KTRDR_CHECKPOINT_EPOCH_INTERVAL` |
| `CHECKPOINT_TIME_INTERVAL_SECONDS` | `KTRDR_CHECKPOINT_TIME_INTERVAL` |
| `CHECKPOINT_DIR` | `KTRDR_CHECKPOINT_DIR` |
| `CHECKPOINT_MAX_AGE_DAYS` | `KTRDR_CHECKPOINT_MAX_AGE_DAYS` |

Agent:

| Old Name | New Name |
|----------|----------|
| `AGENT_ENABLED` | `KTRDR_AGENT_ENABLED` |
| `AGENT_MODEL` | `KTRDR_AGENT_MODEL` |
| `AGENT_MAX_TOKENS` | `KTRDR_AGENT_MAX_TOKENS` |
| `AGENT_TIMEOUT_SECONDS` | `KTRDR_AGENT_TIMEOUT` |
| `AGENT_MAX_ITERATIONS` | `KTRDR_AGENT_MAX_ITERATIONS` |
| `AGENT_MAX_INPUT_TOKENS` | `KTRDR_AGENT_MAX_INPUT_TOKENS` |
| `AGENT_DAILY_BUDGET` | `KTRDR_AGENT_DAILY_BUDGET` |
| `AGENT_BUDGET_DIR` | `KTRDR_AGENT_BUDGET_DIR` |
| `AGENT_POLL_INTERVAL` | `KTRDR_AGENT_POLL_INTERVAL` |
| `AGENT_TRIGGER_INTERVAL_SECONDS` | `KTRDR_AGENT_TRIGGER_INTERVAL` |
| `AGENT_TRAINING_START_DATE` | `KTRDR_AGENT_TRAINING_START` |
| `AGENT_TRAINING_END_DATE` | `KTRDR_AGENT_TRAINING_END` |
| `AGENT_BACKTEST_START_DATE` | `KTRDR_AGENT_BACKTEST_START` |
| `AGENT_BACKTEST_END_DATE` | `KTRDR_AGENT_BACKTEST_END` |
| `AGENT_MAX_CONCURRENT_RESEARCHES` | `KTRDR_AGENT_MAX_CONCURRENT` |
| `AGENT_CONCURRENCY_BUFFER` | `KTRDR_AGENT_CONCURRENCY_BUFFER` |
| `USE_STUB_WORKERS` | `KTRDR_AGENT_USE_STUBS` |
| `STUB_WORKER_FAST` | `KTRDR_AGENT_STUB_FAST` |
| `STUB_WORKER_DELAY` | `KTRDR_AGENT_STUB_DELAY` |

Quality Gates:

| Old Name | New Name |
|----------|----------|
| `TRAINING_GATE_MIN_ACCURACY` | `KTRDR_GATE_TRAINING_MIN_ACCURACY` |
| `TRAINING_GATE_MAX_LOSS` | `KTRDR_GATE_TRAINING_MAX_LOSS` |
| `TRAINING_GATE_MIN_LOSS_DECREASE` | `KTRDR_GATE_TRAINING_MIN_LOSS_DECREASE` |
| `BACKTEST_GATE_MIN_WIN_RATE` | `KTRDR_GATE_BACKTEST_MIN_WIN_RATE` |
| `BACKTEST_GATE_MAX_DRAWDOWN` | `KTRDR_GATE_BACKTEST_MAX_DRAWDOWN` |
| `BACKTEST_GATE_MIN_SHARPE` | `KTRDR_GATE_BACKTEST_MIN_SHARPE` |

Data:

| Old Name | New Name |
|----------|----------|
| `DATA_DIR` | `KTRDR_DATA_DIR` |
| `DATA_MAX_SEGMENT_SIZE` | `KTRDR_DATA_MAX_SEGMENT_SIZE` |
| `DATA_PERIODIC_SAVE_MIN` | `KTRDR_DATA_SAVE_INTERVAL` |
| `MODELS_DIR` | `KTRDR_DATA_MODELS_DIR` |
| `STRATEGIES_DIR` | `KTRDR_DATA_STRATEGIES_DIR` |

Operations:

| Old Name | New Name |
|----------|----------|
| `OPERATIONS_CACHE_TTL` | `KTRDR_OPS_CACHE_TTL` |

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
| `ktrdr/config/deprecation.py` | Deprecated name warnings and mapping |

### Files to Modify (Significantly Rewrite)

| File | Change |
|------|--------|
| `ktrdr/config/settings.py` | Expand from 4 to 16 Settings classes (exists, has `APISettings`, `LoggingSettings`, `OrphanDetectorSettings`, `CheckpointSettings`) |
| `ktrdr/config/validation.py` | Rewrite for explicit startup validation with `KTRDR_ENV` awareness (exists, currently has different validation logic) |
| `ktrdr/config/__init__.py` | New public API exporting all Settings classes, getters, and utilities |
| `ktrdr/config/loader.py` | Remove system config loading, keep domain config loading (indicator specs, strategy YAML) |

### Files to Modify (Consumer Migration)

| File | Change |
|------|--------|
| `ktrdr/api/main.py` | Add `validate_all("backend")` + `warn_deprecated_env_vars()` at startup |
| `ktrdr/api/database.py` | Replace `os.getenv("DB_*")` with `get_db_settings()` |
| `ktrdr/api/dependencies.py` | Use settings getters instead of direct env reads |
| `ktrdr/api/services/*.py` | Replace scattered `os.getenv()` calls with settings getters |
| `ktrdr/workers/base.py` | Replace `os.getenv("WORKER_*")` with `get_worker_settings()` |
| `ktrdr/workers/backtest/backtest_worker.py` | Use settings getters |
| `ktrdr/workers/training/training_worker.py` | Use settings getters, fix WORKER_PORT inconsistency (bug) |
| `ktrdr/workers/training/worker_registration.py` | Use settings getters, fix WORKER_PORT inconsistency (bug) |
| `ktrdr/config/credentials.py` | Use `get_ib_settings()` instead of direct env reads |
| `ktrdr/data/ib_*.py` | Replace IB config reads with `get_ib_settings()` |
| `ktrdr/async_infrastructure/service_orchestrator.py` | Use settings getters for host service config |
| `ktrdr/models/training/*.py` | Use `get_checkpoint_settings()` and `get_training_host_settings()` |
| `ktrdr/agent/*.py` | Use `get_agent_settings()` and `get_agent_gate_settings()` |
| `ktrdr/cli/local_prod.py` | Set `KTRDR_ENV=production` in compose env |
| `ktrdr/cli/sandbox.py` | Set `KTRDR_ENV=development` in compose env |
| `deploy/environments/local/docker-compose.yml` | Update all env var names to `KTRDR_*` |
| `docker-compose.sandbox.yml` | Update all env var names to `KTRDR_*` |
| `.env.*` templates | Update env var names |
| Worker Dockerfiles / entrypoints | Add `validate_all("worker")` at startup |

### Files to Delete (After Migration)

| File | Reason |
|------|--------|
| `ktrdr/metadata.py` | Replaced by settings + `importlib.metadata` for version |
| `ktrdr/config/host_services.py` | Merged into `settings.py` (`IBHostServiceSettings`, `TrainingHostServiceSettings`) |
| `ktrdr/config/ib_config.py` | Merged into `settings.py` (`IBSettings`) |
| `ktrdr/api/config.py` | Merged into `settings.py` (`APISettings`) — resolves duplication |
| `config/ktrdr_metadata.yaml` | Project info → `pyproject.toml`, settings → Settings classes |
| `config/settings.yaml` | All values move to Settings class defaults |
| `config/environment/*.yaml` | No more YAML environment layering |
| `config/indicators.yaml` | Unused (domain indicator specs are separate) |
| `config/ib_host_service.yaml` | Merged into `IBHostServiceSettings` |
| `config/training_host_service.yaml` | Merged into `TrainingHostServiceSettings` |

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

**Goal:** Create new settings infrastructure alongside existing code.

1. Expand `ktrdr/config/settings.py` from 4 to 16 Settings classes with all ~90 env vars
2. Add `deprecated_field()` helper with `AliasChoices` (Decision 9)
3. Rewrite `ktrdr/config/validation.py` with `KTRDR_ENV`-aware explicit startup validation
4. Create `ktrdr/config/deprecation.py` with complete old→new name map
5. Update `ktrdr/config/__init__.py` public API
6. Write comprehensive unit tests for all Settings classes
7. **Existing code unchanged** — both systems coexist

**Verification:**
- All new tests pass
- Existing tests still pass
- Can import from `ktrdr.config` and use new settings
- `deprecated_field()` correctly handles `AliasChoices` + `env_prefix` interaction

### Phase 2: Incremental Migration

**Goal:** Migrate all existing code to use new settings, one domain at a time.

Each step is a separate PR. Order chosen to resolve duplications first, then move outward:

1. **Database** — `ktrdr/api/database.py`: Replace `os.getenv("DB_*")` → `get_db_settings()`
2. **API Server** — `ktrdr/api/main.py`, `ktrdr/api/dependencies.py`: Replace `APIConfig` usage → `get_api_settings()`, add startup validation. **Deletes `ktrdr/api/config.py`** (resolves duplication #1)
3. **Auth/Secrets** — Scattered `os.getenv("JWT_SECRET")`, `os.getenv("ANTHROPIC_API_KEY")` → `get_auth_settings()`
4. **Logging & Observability** — `ktrdr/utils/logging.py` and tracing setup: Replace `os.getenv("LOG_LEVEL")`, `os.getenv("OTLP_ENDPOINT")` → `get_logging_settings()`, `get_observability_settings()`
5. **IB Connection** — `ktrdr/config/ib_config.py` consumers, `ktrdr/data/ib_*.py`, `ktrdr/config/credentials.py`: Replace `IbConfig` dataclass → `get_ib_settings()`. **Deletes `ktrdr/config/ib_config.py`** (resolves duplication)
6. **Host Services** — `ktrdr/async_infrastructure/service_orchestrator.py`, data proxy, training proxy: Replace `os.getenv("USE_IB_HOST_SERVICE")` (read in 4 places) → `get_ib_host_settings().enabled`. **Deletes `ktrdr/config/host_services.py`** (resolves duplication)
7. **Workers** — `ktrdr/workers/base.py`, `ktrdr/workers/training/training_worker.py`, `ktrdr/workers/training/worker_registration.py`: Replace `os.getenv("WORKER_*")` → `get_worker_settings()`. **Fixes WORKER_PORT bug** (inconsistent defaults 5002 vs 5004)
8. **Operational** — Checkpoint, orphan detector, operations service: Already partially migrated (existing Settings classes), align with new naming
9. **Agent** — `ktrdr/agent/*.py`: Replace ~20 `os.getenv("AGENT_*")` calls → `get_agent_settings()`, `get_agent_gate_settings()`
10. **Data** — `ktrdr/data/*.py`: Replace `os.getenv("DATA_DIR")` etc → `get_data_settings()`
11. **Docker Compose** — Update both `docker-compose.yml` and `docker-compose.sandbox.yml` env var names to `KTRDR_*`
12. **CLI** — `ktrdr/cli/local_prod.py` sets `KTRDR_ENV=production`, `ktrdr/cli/sandbox.py` sets `KTRDR_ENV=development`

**For each migration step:**
- Update code to use new getter
- Update tests
- Verify deprecated names still work via `AliasChoices`
- Delete old config module only when ALL its consumers are migrated

### Phase 3: Cleanup

**Goal:** Remove all old config code, YAML files, and metadata system.

1. Delete deprecated Python modules (see Files to Delete): `metadata.py`, `ib_config.py`, `host_services.py`, `api/config.py`
2. Delete unused YAML files: `config/settings.yaml`, `config/ktrdr_metadata.yaml`, `config/environment/*.yaml`, `config/indicators.yaml`, `config/ib_host_service.yaml`, `config/training_host_service.yaml`
3. Simplify `ktrdr/config/loader.py` — remove system config loading, keep only domain config (indicator/strategy YAML)
4. Remove all `metadata.get()` calls and `from ktrdr.metadata import metadata` imports
5. Move project version to `importlib.metadata.version("ktrdr")`
6. Update documentation
7. Generate config reference from Pydantic model schemas

**Verification:**
- `grep -r "os.getenv" ktrdr/` returns zero hits for any migrated env var
- `grep -r "metadata.get" ktrdr/` returns zero hits
- `grep -r "from ktrdr.metadata" ktrdr/` returns zero hits
- All tests pass
- Full E2E stack starts cleanly

### Phase 4: Deprecation Removal (Future Release)

**Goal:** Remove support for old env var names after migration period.

1. Remove `AliasChoices` from all `deprecated_field()` calls
2. Convert `deprecated_field()` back to standard `Field()`
3. Update docker-compose to use only new `KTRDR_*` names
4. Update all `.env` templates
5. Delete `ktrdr/config/deprecation.py`
6. Update documentation

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
