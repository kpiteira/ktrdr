# M5 Handoff: Agent & Data Settings

## Task 5.1 Complete: Create `AgentSettings` Class

### Implementation Notes

Created `AgentSettings` class with prefix `KTRDR_AGENT_` in `ktrdr/config/settings.py`:

**Fields:**
- `poll_interval` (float, default 5.0) — Poll interval for agent loops
- `model` (str, default "claude-sonnet-4-20250514") — LLM model identifier
- `max_tokens` (int, default 4096) — Maximum output tokens per request
- `timeout_seconds` (int, default 300) — Request timeout
- `max_iterations` (int, default 10) — Maximum agentic iterations per task
- `max_input_tokens` (int, default 50000) — Maximum input context tokens
- `daily_budget` (float, default 5.0) — Daily cost budget in USD (0 = disabled)
- `budget_dir` (str, default "data/budget") — Directory for budget tracking
- `max_concurrent_researches` (int, default 0) — Max concurrent (0 = unlimited)
- `concurrency_buffer` (int, default 1) — Concurrency buffer
- `training_start_date` (str | None) — Default training start date
- `training_end_date` (str | None) — Default training end date
- `backtest_start_date` (str | None) — Default backtest start date
- `backtest_end_date` (str | None) — Default backtest end date

**Deprecated name support** for all existing `AGENT_*` env vars:
- `AGENT_POLL_INTERVAL` → `KTRDR_AGENT_POLL_INTERVAL`
- `AGENT_MODEL` → `KTRDR_AGENT_MODEL`
- `AGENT_MAX_TOKENS` → `KTRDR_AGENT_MAX_TOKENS`
- `AGENT_TIMEOUT_SECONDS` → `KTRDR_AGENT_TIMEOUT_SECONDS`
- `AGENT_MAX_ITERATIONS` → `KTRDR_AGENT_MAX_ITERATIONS`
- `AGENT_MAX_INPUT_TOKENS` → `KTRDR_AGENT_MAX_INPUT_TOKENS`
- `AGENT_DAILY_BUDGET` → `KTRDR_AGENT_DAILY_BUDGET`
- `AGENT_BUDGET_DIR` → `KTRDR_AGENT_BUDGET_DIR`
- `AGENT_MAX_CONCURRENT_RESEARCHES` → `KTRDR_AGENT_MAX_CONCURRENT_RESEARCHES`
- `AGENT_CONCURRENCY_BUFFER` → `KTRDR_AGENT_CONCURRENCY_BUFFER`
- `AGENT_TRAINING_START_DATE` → `KTRDR_AGENT_TRAINING_START_DATE`
- `AGENT_TRAINING_END_DATE` → `KTRDR_AGENT_TRAINING_END_DATE`
- `AGENT_BACKTEST_START_DATE` → `KTRDR_AGENT_BACKTEST_START_DATE`
- `AGENT_BACKTEST_END_DATE` → `KTRDR_AGENT_BACKTEST_END_DATE`

### Gotchas

**conftest.py sets AGENT_MODEL=haiku globally**: The test `conftest.py` sets `AGENT_MODEL=haiku` to avoid burning API budget during tests. Tests checking the default model value must call `monkeypatch.delenv("AGENT_MODEL")` first.

**poll_interval is float, not int**: The existing `AGENT_POLL_INTERVAL` is used as `float(os.getenv("AGENT_POLL_INTERVAL", "5"))`, so the settings class uses `float` type to match.

**daily_budget uses `ge=0` not `gt=0`**: A budget of 0 means "disabled", which is a valid configuration.

**max_concurrent_researches uses `ge=0`**: A value of 0 means "unlimited", which is the default behavior.

### Tests

26 unit tests in `tests/unit/config/test_agent_settings.py`:
- Default values (12 tests)
- New env var names (4 tests)
- Deprecated env var names (3 tests)
- Precedence (1 test)
- Validation (4 tests)
- Getter caching (2 tests)

### Next Task Notes (5.2: Create AgentGateSettings)

- Prefix: `KTRDR_GATE_`
- Fields: mode (simulation/live), dry_run, confirmation_required
- Controls whether agent can actually execute trades
- Check for existing `GATE_*` or trade execution control env vars

---

## Task 5.2 Complete: Create `AgentGateSettings` Class

### Implementation Notes

Created `AgentGateSettings` class with prefix `KTRDR_GATE_` in `ktrdr/config/settings.py`:

**Fields:**
- `mode` (str, default "simulation") — Execution mode: simulation or live
- `dry_run` (bool, default True) — If True, log trades but don't execute
- `confirmation_required` (bool, default True) — Require confirmation before trades
- `max_position_size` (int, default 0) — Maximum position size in dollars (0 = no limit)
- `max_daily_trades` (int, default 0) — Maximum trades per day (0 = no limit)

**Helper methods:**
- `is_live_mode()` — Returns True if mode is "live"
- `can_execute_trade()` — Returns True only if mode is "live" AND dry_run is False

### Gotchas

**Safe defaults**: All defaults are set to the safest option (simulation, dry_run=True, confirmation_required=True). This ensures accidental production runs cannot execute real trades.

**No deprecated names**: This is a new settings class with no existing env vars to deprecate.

**Zero means no limit**: For `max_position_size` and `max_daily_trades`, a value of 0 means no limit, following the pattern from `AgentSettings.max_concurrent_researches`.

### Tests

20 unit tests in `tests/unit/config/test_agent_gate_settings.py`:
- Default values (5 tests)
- New env var names (6 tests)
- Validation (3 tests)
- Helper methods (4 tests)
- Getter caching (2 tests)

### Next Task Notes (5.3: Create DataSettings)

- Prefix: `KTRDR_DATA_`
- Fields: data_dir, cache_dir, models_dir, etc.
- Check for existing `DATA_*` or `CACHE_*` env vars in the codebase

---

## Task 5.3 Complete: Create `DataSettings` Class

### Implementation Notes

Created `DataSettings` class with prefix `KTRDR_DATA_` in `ktrdr/config/settings.py`:

**Fields:**
- `data_dir` (str, default "data") — Base data directory for OHLCV data
- `models_dir` (str, default "models") — Directory for trained model storage
- `cache_dir` (str, default "data/cache") — Directory for cached data
- `max_segment_size` (int, default 5000) — Maximum data segment size for acquisition
- `periodic_save_interval` (float, default 0.5) — Periodic save interval in minutes

**Deprecated name support:**
- `DATA_DIR` → `KTRDR_DATA_DIR`
- `MODELS_DIR` → `KTRDR_DATA_MODELS_DIR`
- `DATA_MAX_SEGMENT_SIZE` → `KTRDR_DATA_MAX_SEGMENT_SIZE`
- `DATA_PERIODIC_SAVE_MIN` → `KTRDR_DATA_PERIODIC_SAVE_INTERVAL`

### Gotchas

**cache_dir has no deprecated name**: This is a new field with no existing env var to deprecate.

**Default for data_dir is "data" not "./data"**: The existing code uses `os.getenv("DATA_DIR", "./data")` but we use "data" without the "./" prefix for cleaner path handling.

### Tests

19 unit tests in `tests/unit/config/test_data_settings.py`:
- Default values (5 tests)
- New env var names (5 tests)
- Deprecated env var names (4 tests)
- Precedence (1 test)
- Validation (2 tests)
- Getter caching (2 tests)

### Next Task Notes (5.4: Create APIClientSettings)

- Prefix: `KTRDR_API_CLIENT_`
- Fields: base_url, timeout, retry_count
- Note: `ApiServiceSettings` already exists — may need to update or extend it
- Check for existing `KTRDR_API_URL` or similar env vars

---

## Task 5.4 Complete: Add APIClientSettings (Update to ApiServiceSettings)

### Implementation Notes

Updated existing `ApiServiceSettings` class in `ktrdr/config/settings.py` to:
1. Add deprecated name support for `KTRDR_API_URL` → `KTRDR_API_CLIENT_BASE_URL`
2. Add validation constraints (timeout gt=0, max_retries ge=0, retry_delay ge=0)
3. Changed `extra="forbid"` to `extra="ignore"` for consistency with other settings classes

**This resolves duplication #5 from the config audit**: Multiple env vars for backend URL now consolidated through `ApiServiceSettings` as the single source of truth.

### Gotchas

**`ApiServiceSettings` already existed**: Rather than creating a new class, we enhanced the existing one with deprecated name support.

**extra="forbid" changed to extra="ignore"**: The original class used `extra="forbid"` which would reject unknown env vars. Changed to `extra="ignore"` for consistency and to avoid issues with the deprecated name alias.

### Tests

18 unit tests in `tests/unit/config/test_api_client_settings.py`:
- Default values (4 tests)
- New env var names (4 tests)
- Deprecated env var names (1 test)
- Precedence (1 test)
- Validation (3 tests)
- Getter caching (3 tests)
- Helper methods (2 tests)

### Next Task Notes (5.5: Migrate Agent Consumers)

- Replace all `os.getenv("AGENT_*")` calls with `get_agent_settings().field`
- Files: `ktrdr/agents/*.py`
- Watch for the conftest.py AGENT_MODEL=haiku override in tests

---

## Task 5.5 Complete: Migrate Agent Consumers

### Implementation Notes

Replaced all `os.getenv("AGENT_*")` calls with `get_agent_settings().field`:

**Files modified:**
- `ktrdr/agents/invoker.py` — `resolve_model()` and `AnthropicInvokerConfig.from_env()`
- `ktrdr/agents/budget.py` — `BudgetTracker.__init__()`
- `ktrdr/agents/workers/research_worker.py` — `_get_poll_interval()`, training dates, backtest dates, pricing model
- `ktrdr/api/services/agent_service.py` — `_get_max_concurrent_researches()`

**Test fix:**
- `tests/unit/config/test_api_service_settings.py` — Fixed env var name in test (was using old alias `api_base_url`, now uses `KTRDR_API_CLIENT_BASE_URL`)

### Gotchas

**Import inside function**: To avoid circular imports, the settings import is done inside the function body rather than at module level.

**Removed unused `os` imports**: After migration, the `os` module was no longer needed in some files.

### Tests

All 708 config tests pass.

### Next Task Notes (5.6: Migrate Data/Path Consumers)

- Replace `os.getenv("DATA_DIR")`, `os.getenv("MODELS_DIR")` etc.
- Files: `ktrdr/training/model_storage.py`, `ktrdr/data/repository/data_repository.py`, `ktrdr/data/acquisition/acquisition_service.py`

---

## Task 5.6 Complete: Migrate Data/Path Consumers

### Implementation Notes

Replaced all `os.getenv("DATA_*")` and `os.getenv("MODELS_*")` calls with `get_data_settings()`:

**Files modified:**
- `ktrdr/training/model_storage.py` — `_get_default_models_dir()`
- `ktrdr/data/repository/data_repository.py` — `DataRepository.__init__()`
- `ktrdr/data/acquisition/acquisition_service.py` — `MAX_SEGMENT_SIZE` and `PERIODIC_SAVE_INTERVAL` as properties

### Gotchas

**Class-level constants changed to properties**: `MAX_SEGMENT_SIZE` and `PERIODIC_SAVE_INTERVAL` were class-level constants computed at import time. Changed them to properties so they read from settings dynamically.

**IB_HOST_SERVICE_URL not migrated**: This env var in `acquisition_service.py` is IB-related (not DATA-related) and should be handled in M3 (IB Host Services migration), not M5.

### Next Task Notes (5.7: Migrate CLI/API Client Consumers)

- Replace `os.getenv("KTRDR_API_URL")` with `get_api_service_settings().base_url`
- Files: `ktrdr/cli/*.py`, worker registration files

---

## Task 5.7 Complete: Migrate CLI/API Client Consumers

### Implementation Notes

Replaced all `os.getenv("KTRDR_API_URL")` calls with `get_api_service_settings().base_url`:

**Files modified:**
- `ktrdr/agents/executor.py` — Added `_get_api_base_url()` helper
- `ktrdr/training/worker_registration.py` — `WorkerRegistration.__init__()`
- `ktrdr/backtesting/worker_registration.py` — `WorkerRegistration.__init__()`
- `ktrdr/training/training_worker.py` — Worker instance creation
- `ktrdr/backtesting/backtest_worker.py` — Worker instance creation
- `ktrdr/cli/__init__.py` — Telemetry setup

### Gotchas

**base_url includes /api/v1 suffix**: The `get_api_service_settings().base_url` includes `/api/v1` suffix, but many call sites just need the base host:port. Created helper functions that strip this suffix.

**Worker registration no longer throws RuntimeError**: Previously, workers would fail if `KTRDR_API_URL` wasn't set. Now they use settings with the default value, which is `http://localhost:8000/api/v1`.

### Next Task Notes (5.8: Update Validation and Deprecation Modules)

- The `deprecated_field()` helper already exists and was used throughout
- May need to update the deprecation warning system if not already in place
- Check if we need to add startup warnings for deprecated env vars

---

## Task 5.8 Complete: Update Validation and Deprecation Modules

### Implementation Notes

Updated `ktrdr/config/deprecation.py` with M5 deprecated name mappings:

**Agent settings (AGENT_* → KTRDR_AGENT_*):**
- AGENT_POLL_INTERVAL
- AGENT_MODEL, AGENT_MAX_TOKENS, AGENT_TIMEOUT_SECONDS
- AGENT_MAX_ITERATIONS, AGENT_MAX_INPUT_TOKENS
- AGENT_DAILY_BUDGET, AGENT_BUDGET_DIR
- AGENT_MAX_CONCURRENT_RESEARCHES, AGENT_CONCURRENCY_BUFFER
- AGENT_TRAINING_START_DATE, AGENT_TRAINING_END_DATE
- AGENT_BACKTEST_START_DATE, AGENT_BACKTEST_END_DATE

**Data settings:**
- DATA_DIR → KTRDR_DATA_DIR
- MODELS_DIR → KTRDR_DATA_MODELS_DIR
- DATA_MAX_SEGMENT_SIZE → KTRDR_DATA_MAX_SEGMENT_SIZE
- DATA_PERIODIC_SAVE_MIN → KTRDR_DATA_PERIODIC_SAVE_INTERVAL

**API client settings:**
- KTRDR_API_URL → KTRDR_API_CLIENT_BASE_URL

### Gotchas

**The deprecation module uses `warn_deprecated_env_vars()`**: This function is already called at startup and will emit DeprecationWarning for any deprecated env vars found in the environment.

### Next Task Notes (5.9: Write Unit Tests)

- Tests already written for each settings class
- Need to run full test suite to verify everything works together
- May need to add tests for the deprecation module updates

---

## Task 5.9 Complete: Write Unit Tests

### Implementation Notes

All unit tests pass (4983 passed, 5 skipped). Key fixes made:

**Created autouse fixtures** for clearing settings cache in test directories:
- `tests/unit/workers/conftest.py` — clears cache before/after each test
- `tests/unit/agents/conftest.py` — clears cache before/after each test
- `tests/unit/agent_tests/conftest.py` — already existed (updated)

**Updated test behaviors:**
- `test_default_poll_interval` — Now uses `monkeypatch.delenv("AGENT_POLL_INTERVAL")` since conftest sets it to 0.01
- `test_invalid_override_raises_validation_error` — Renamed and updated to expect ValidationError instead of silent fallback (Pydantic validates on instantiation)
- `test_cost_estimation_typical_design_phase` — Added `clear_settings_cache()` inside `patch.dict` blocks

**Removed unused imports:**
- `tests/unit/workers/test_network_config.py` — Removed unused `pytest` import

### Gotchas

**`conftest.py` sets environment variables globally**: The `tests/unit/agent_tests/conftest.py` sets `AGENT_POLL_INTERVAL=0.01` and `AGENT_MODEL=haiku`. Tests verifying defaults must explicitly unset these.

**Pydantic validation is stricter than `os.getenv`**: Invalid env var values (like "invalid" for an int field) now cause ValidationError at settings instantiation, rather than silently falling back. This is better behavior (fail-fast).

**`patch.dict(os.environ)` doesn't clear settings cache**: When using `patch.dict` to change env vars, you must also call `clear_settings_cache()` inside the `with` block for changes to take effect.

### Tests

All 4983 unit tests pass in 62 seconds. Quality checks pass.

### Next Task Notes (5.10: Execute E2E Test)

- Start Docker environment and run E2E tests
- Verify workers can register with backend using new settings
- Check deprecation warnings are emitted for old env vars

---

## Task 5.10 Complete: Execute E2E Test

### Implementation Notes

All E2E scenarios pass in sandbox environment (`ktrdr--indicator-std`):

**Scenario 1: Agent reads config** ✅
```bash
KTRDR_GATE_DRY_RUN=true → Mode: simulation, Dry run: True, Can execute: False
```

**Scenario 2: Data paths work** ✅
```bash
KTRDR_DATA_DIR=/tmp/ktrdr-test → Data dir: /tmp/ktrdr-test
```

**Scenario 3: CLI uses correct API URL** ✅
```bash
ktrdr ops → Connected to http://localhost:8001 (sandbox backend)
```

**Scenario 4: Deprecated KTRDR_API_URL works** ✅
```bash
KTRDR_API_URL=http://localhost:8001 → Emits deprecation warning, value is used
```

**Additional fix:**
- Exported new M5 settings classes and getters from `ktrdr/config/__init__.py`

### All Tests Pass

- Unit tests: 4983 passed
- Quality checks: All pass
- E2E scenarios: All 4 pass

---

## M5 Milestone Complete

All 10 tasks completed:
- ✅ Tasks 5.1-5.4: Created AgentSettings, AgentGateSettings, DataSettings, updated ApiServiceSettings
- ✅ Tasks 5.5-5.7: Migrated all consumers from `os.getenv()` to settings
- ✅ Task 5.8: Updated deprecation module with M5 mappings
- ✅ Task 5.9: All unit tests pass (4983 tests)
- ✅ Task 5.10: All E2E scenarios pass

**Duplication #5 resolved**: Multiple backend URL env vars consolidated through `ApiServiceSettings` as single source of truth.

---
