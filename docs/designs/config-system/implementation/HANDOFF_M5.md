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

