---
design: docs/designs/predictive-features/external-data/DESIGN.md
architecture: docs/designs/predictive-features/external-data/ARCHITECTURE.md
---

# M9: External Data — Backtest + CFTC

**Thread:** External Data
**JTBD:** "As a researcher, I want to backtest strategies trained with external data (FRED, cross-pair, CFTC) so I can evaluate whether carry factor and positioning data improve out-of-sample performance."
**Depends on:** M6 (External Data: FRED Training)
**Tasks:** 6

---

## Task 9.1: Model Bundle Context Data Config Storage

**File(s):**
- `ktrdr/backtesting/model_bundle.py` (read `context_data_config` from metadata)
- `ktrdr/backtesting/engine.py` (load context data during backtest)

**Type:** CODING
**Estimated time:** 2 hours

**Description:**
During backtesting, the engine reads `context_data_config` from the model's `metadata_v3.json` (saved during training in M6) and fetches the same external data. This ensures backtest uses identical context data pipeline as training.

**Implementation Notes:**
- `model_bundle.py` already loads metadata — add `context_data_config` extraction
- Engine checks: if metadata has `context_data_config`, iterate entries, use provider registry to fetch, align to primary data index
- Pass aligned context data to FeatureCache alongside primary data
- **Key constraint:** backtest must reproduce exact same feature pipeline as training. `context_source_ids` in metadata is the validation check.
- Edge case: if context data is unavailable during backtest (API down, no cache), fail with clear error — don't silently skip

**Testing Requirements:**
- [ ] Model with `context_data_config` in metadata triggers context data loading
- [ ] Context data fetched via same providers as training
- [ ] Aligned context data passed to FeatureCache
- [ ] Feature validation matches training features (including context-derived)
- [ ] Model without `context_data_config` works unchanged (backward compat)
- [ ] Missing context data raises clear error

**Acceptance Criteria:**
- [ ] Backtest of model trained with context data reproduces feature pipeline
- [ ] Context features match between training and backtest

---

## Task 9.2: IB Context Provider (Cross-Pair)

**File(s):**
- `ktrdr/data/context/ib_context_provider.py` (new)

**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Implement `IbContextDataProvider` — thin wrapper around existing `IbDataProvider`/`DataRepository`. For IB context (cross-pair symbols like GBPUSD), reuse existing data loading infrastructure. Returns OHLCV DataFrame for the context symbol.

**Implementation Notes:**
- `fetch()`: delegate to `DataRepository.load_from_cache(symbol, timeframe, start_date, end_date)` — IB data is already cached by `ktrdr data load`
- `validate()`: check symbol exists in cache
- `get_source_ids()`: return `[config.symbol]` (e.g., `["GBPUSD"]`)
- No new API calls needed — IB context symbols must be pre-loaded via `ktrdr data load GBPUSD 1h`
- Register in `ContextDataProviderRegistry` as "ib"

**Testing Requirements:**
- [ ] Fetch returns OHLCV DataFrame for cached symbol
- [ ] Missing symbol raises clear error with hint to run `ktrdr data load`
- [ ] `get_source_ids()` returns symbol name
- [ ] Integration: strategy with IB cross-pair context validates and loads data

**Acceptance Criteria:**
- [ ] IB context provider reuses existing data infrastructure
- [ ] Cross-pair data available for indicator computation

---

## Task 9.3: CFTC COT Provider

**File(s):**
- `ktrdr/data/context/cftc_provider.py` (new)

**Type:** CODING
**Estimated time:** 3 hours

**Description:**
Implement `CftcCotProvider` that fetches CFTC Commitment of Traders data, extracts net speculative positioning for the configured currency, computes percentile over rolling windows (52-week and 156-week), and returns weekly DataFrames.

**Implementation Notes:**
- Use `cot_reports` Python library for data download/parsing (add as dependency)
- Report type: "Traders in Financial Futures" (TFF) for currency futures
- Extract: net speculative long, net speculative short, net position
- Compute: `net_pct_52w` = percentile of net position over 52-week rolling window (0-100 scale)
- `net_pct_156w` = same over 156-week (3-year) rolling window
- Cache: `data/context/cftc/{report}.csv`
- `get_source_ids()`: `["cot_{report}_net_pos", "cot_{report}_net_pct"]`
- Weekly data forward-filled to hourly — handled by `ContextDataAligner` (from M6)
- 3-day lag (Tuesday snapshot, Friday release) — acceptable for a feature that changes weekly

**Testing Requirements:**
- [ ] Fetch returns weekly DataFrame with net_position and percentile columns
- [ ] Percentile computation is correct (0-100 scale, rolling window)
- [ ] Cache written and reused
- [ ] `get_source_ids()` returns correct IDs
- [ ] `validate()` checks currency code format
- [ ] Integration: COT data aligns to hourly index via forward-fill

**Acceptance Criteria:**
- [ ] CFTC positioning data fetched and processed
- [ ] Percentile computation over correct rolling windows
- [ ] Data cached and aligned to hourly timeframe

---

## Task 9.4: Train Strategy with Multi-Source Context

**File(s):**
- `strategies/eurusd_carry_momentum_v1.yaml` (new — from architecture doc Section 2.3)

**Type:** MIXED
**Estimated time:** 3 hours

**Description:**
Create and train a strategy that combines EURUSD price indicators with FRED yield spread + cross-pair (GBPUSD) + CFTC positioning context. This validates the full multi-provider pipeline end-to-end.

**Implementation Notes:**
- Strategy from architecture doc Section 2.3 — uses carry_direction (yield spread RSI), gbp_momentum (cross-pair RSI), and positioning (COT percentile EMA) fuzzy sets
- Must pre-load GBPUSD data: `ktrdr data load GBPUSD 1h --start-date 2019-01-01 --end-date 2025-01-01`
- FRED API key must be configured
- Train: `ktrdr models train eurusd_carry_momentum_v1.yaml`
- Verify: model metadata contains all 3 context data entries, all source IDs present

**Acceptance Criteria:**
- [ ] Strategy with FRED + IB + CFTC context validates
- [ ] Training completes with all context features
- [ ] Model metadata captures all context data configurations

---

## Task 9.5: Backtest with External Data

**File(s):** None (execution/evaluation task)
**Type:** MIXED
**Estimated time:** 2 hours

**Description:**
Backtest the carry momentum strategy from Task 9.4. Verify context data is loaded from model metadata, features are computed identically to training, and backtest produces meaningful results.

**Implementation Notes:**
- Backtest: `ktrdr backtest run eurusd_carry_momentum_v1 --start-date 2024-01-01 --end-date 2025-01-01`
- Engine reads `context_data_config` from metadata → fetches FRED + IB + CFTC data → aligns → computes features
- Compare: model with external data vs model without (price-only baseline)
- Key metrics: Sharpe ratio, win rate, does carry factor add value?

**Acceptance Criteria:**
- [ ] Backtest with external data completes without errors
- [ ] Context features present in backtest feature vector
- [ ] Results include trades (not empty)
- [ ] Comparison vs price-only baseline documented

---

## Task 9.6: Validation

**File(s):** None (validation task)
**Type:** VALIDATION
**Estimated time:** 2 hours

**Description:**
Validate external data backtest pipeline end-to-end.

**Validation Steps:**
1. Load the `ke2e` skill before designing any validation
2. Invoke `ke2e-test-scout` with: "Train a strategy with FRED yield spread + cross-pair + CFTC positioning context data, then backtest it. Verify context data loads during backtest from model metadata, features match training, and backtest produces results."
3. Invoke `ke2e-test-runner` with the identified test recipes
4. Tests must exercise real infrastructure — real FRED API, real training, real backtest
5. Verify: model metadata has context_data_config, backtest loads context data, feature count matches, trades generated

**Acceptance Criteria:**
- [ ] Full pipeline: train with external data → backtest with external data → results
- [ ] Context data reproducible from model metadata alone
- [ ] Feature count and order match between training and backtest
- [ ] Multiple data providers work together (FRED + IB + CFTC)
