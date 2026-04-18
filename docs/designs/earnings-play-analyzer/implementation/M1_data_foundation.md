# M1: Data Foundation

**Goal**: Fetch historical earnings data and current IV stats for a ticker, display raw numbers via CLI. Proves the data pipeline works end-to-end.

**Success criteria**: `epa analyze AAPL` outputs a formatted table of historical earnings moves + current IV data, sourced from yfinance, with data cached in SQLite.

---

## Task 1.1: Project Scaffolding

**Files to create**:
- `pyproject.toml` — project metadata, dependencies (click, rich, yfinance, anthropic, pytest, ruff)
- `epa/__init__.py` — version string
- `epa/__main__.py` — `from epa.cli import cli; cli()`
- `epa/cli.py` — Click group with stub `analyze` command
- `epa/config.py` — Config loader (reads `~/.epa/config.toml`, env vars, CLI args)

**Behavior**:
- `pip install -e .` works
- `epa` prints help
- `epa analyze AAPL` prints "Not yet implemented" (placeholder)
- Config loads `ANTHROPIC_API_KEY` from env, other settings from TOML with defaults

**Tests**:
- `test_cli.py`: CLI group exists, help renders, analyze command accepts ticker arg
- `test_config.py`: Config loads defaults when no file exists, respects env vars

---

## Task 1.2: Data Models

**Files to create**:
- `epa/data/__init__.py`
- `epa/data/models.py` — all dataclasses: `EarningsEvent`, `EarningsHistory`, `OptionsSnapshot`, `OptionQuote`, `IVData`

**Behavior**:
- All models are frozen dataclasses with type hints
- Models have `to_dict()` / `from_dict()` methods for JSON serialization
- `EarningsHistory` computes summary stats (avg, median, stdev) from events list

**Tests**:
- `test_models.py`: Construct each model, verify serialization roundtrip, verify computed stats

---

## Task 1.3: SQLite Store

**Files to create**:
- `epa/store/__init__.py`
- `epa/store/db.py` — `EpaStore` class with schema init, prediction CRUD, config CRUD, watchlist, caching

**Behavior**:
- Creates `~/.epa/epa.db` on first use (directory auto-created)
- Schema migration: version table tracks schema version, applies migrations sequentially
- All methods handle SQLite errors gracefully (log + continue for non-critical ops)
- Data cache: `get_cached(key, ttl_seconds)` / `set_cached(key, data_json, ttl_seconds)`

**Tests**:
- `test_db.py`: Using in-memory SQLite (`:memory:`), test: save/load prediction, config CRUD, watchlist add/remove/list, cache set/get/expiry

---

## Task 1.4: yfinance Provider — Earnings History

**Files to create**:
- `epa/data/providers/__init__.py`
- `epa/data/providers/yfinance_provider.py` — `YFinanceProvider` class

**Behavior (this task: earnings history only)**:
- `get_earnings_history(ticker, quarters=16)` → `EarningsHistory`
- Fetches earnings dates from yfinance
- For each earnings date, fetches close price before and after
- Computes actual move percentage and direction
- Handles BMO vs AMC (BMO: compare prior close to same-day close; AMC: compare same-day close to next-day open/close)
- Returns `EarningsHistory` with computed summary stats
- Caches result in SQLite data_cache (TTL: 24 hours)

**Tests**:
- `test_yfinance_provider.py`: Mock yfinance responses with fixture data. Test: correct move calculation for BMO and AMC events, handles missing data, cache hit avoids re-fetch.

**Fixture files**:
- `epa/tests/fixtures/aapl_earnings_dates.json`
- `epa/tests/fixtures/aapl_price_history.json`

---

## Task 1.5: yfinance Provider — Options & IV Data

**Files to modify**:
- `epa/data/providers/yfinance_provider.py` — add `get_options_snapshot()`, `get_iv_data()`, `get_next_earnings_date()`

**Behavior**:
- `get_options_snapshot(ticker, target_expiry)` → `OptionsSnapshot`
  - Fetches options chain for nearest expiry on/after target date
  - Parses calls and puts into `OptionQuote` objects
  - Computes ATM straddle price and implied move
  - If Greeks are missing from yfinance, computes delta from Black-Scholes (utility function)
  - Cache TTL: 15 minutes

- `get_iv_data(ticker)` → `IVData`
  - Computes current ATM IV from options chain
  - Loads IV history from SQLite cache
  - If history < 30 days: flags as bootstrapping, uses VIX percentile for S&P 500 tickers
  - Computes IV rank and IV percentile from available history
  - Saves current IV to cache for future rank calculations

- `get_next_earnings_date(ticker)` → `EarningsEvent | None`
  - Returns next upcoming earnings date, or None if not found
  - Supports manual override from store config

**Tests**:
- `test_yfinance_options.py`: Mock yfinance option chain responses. Test: correct ATM straddle computation, implied move calculation, IV rank with full history, IV rank bootstrap behavior.

**Fixture files**:
- `epa/tests/fixtures/aapl_options_chain.json`

---

## Task 1.6: CLI Analyze (Raw Output)

**Files to modify**:
- `epa/cli.py` — implement `analyze` command with raw data output
- `epa/orchestrator.py` (new) — `Orchestrator` class that coordinates data fetching

**Behavior**:
- `epa analyze AAPL` fetches all data and prints formatted output:
  ```
  AAPL — Next earnings: 2026-04-24 (AMC)
  
  Historical Earnings Moves (12 quarters)
  ┌──────────┬───────┬───────────┐
  │ Date     │ Move  │ Direction │
  ├──────────┼───────┼───────────┤
  │ 2026-01  │ 3.2%  │ ▲ UP      │
  │ 2025-10  │ 5.1%  │ ▼ DOWN    │
  │ ...      │       │           │
  └──────────┴───────┴───────────┘
  Avg: 4.2% | Med: 3.8% | Max: 8.1% | StdDev: 1.9%
  Direction bias: 58% UP
  
  Current IV Data
  IV Rank: 72 | IV Percentile: 81
  Implied Move: 5.1%
  ATM Straddle: $9.85 (195 strike)
  ```
- `--json` flag outputs raw JSON instead
- `--earnings-date` overrides the detected earnings date
- `--budget` stores account size in config for later use

**Tests**:
- `test_orchestrator.py`: With mocked provider, verify orchestrator calls all data methods and assembles output correctly.

---

## Task 1.7: M1 Validation

**Goal**: End-to-end test with real yfinance data (integration test, marked slow).

**Files to create**:
- `epa/tests/test_m1_e2e.py`

**Test cases**:
1. `epa analyze AAPL` with live yfinance data — produces output without errors
2. Second run of same ticker — data served from cache (verify no yfinance call)
3. `epa analyze INVALIDTICKER` — graceful error message
4. `epa analyze AAPL --json` — outputs valid JSON
5. Verify SQLite database created at expected path with expected tables

**Validation script** (manual):
```bash
pip install -e .
epa analyze AAPL
epa analyze MSFT --json
epa analyze AAPL  # should be fast (cached)
```

**Done when**: Karl can run `epa analyze <ticker>` for any optionable stock and see accurate historical earnings data + current IV stats.
