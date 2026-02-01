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

