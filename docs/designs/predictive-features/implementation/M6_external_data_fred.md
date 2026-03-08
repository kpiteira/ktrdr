---
design: docs/designs/predictive-features/external-data/DESIGN.md
architecture: docs/designs/predictive-features/external-data/ARCHITECTURE.md
---

# M6: External Data — FRED Training

**Thread:** External Data
**JTBD:** "As a researcher, I want to train a model using FRED yield spread data alongside price indicators so I can evaluate whether carry factor information improves prediction."
**Depends on:** Nothing
**Tasks:** 7

---

## Task 6.1: FRED API Key Setup and Validation

**File(s):**
- `.env.example` (add `FRED_API_KEY`)
- `ktrdr/config/settings.py` (add FRED settings)

**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Add `FRED_API_KEY` environment variable support. Validate key presence and basic API connectivity. FRED requires free API key registration (instant, no approval).

**Implementation Notes:**
- Add `FRED_API_KEY` to `.env.example` with comment about free registration at https://fred.stlouisfed.org/docs/api/api_key.html
- Add settings class or fields in existing settings for FRED config (API key, base URL, rate limit)
- Validation: check env var exists, make a test API call to verify key works
- **Never display the API key value** — only check existence and test connectivity

**Testing Requirements:**
- [ ] Settings load FRED_API_KEY from environment
- [ ] Missing API key raises clear error message with registration URL
- [ ] API connectivity test succeeds with valid key (integration test, skip in CI)

**Acceptance Criteria:**
- [ ] `FRED_API_KEY` documented in `.env.example`
- [ ] Settings class validates key presence
- [ ] Test API call returns data (manual verification)

---

## Task 6.2: Context Data Provider Interface and Registry

**File(s):**
- `ktrdr/data/context/__init__.py` (new package)
- `ktrdr/data/context/base.py` (new: `ContextDataProvider` ABC, `ContextDataResult`, `ContextDataAligner`)
- `ktrdr/data/context/registry.py` (new: `ContextDataProviderRegistry`)

**Type:** CODING
**Estimated time:** 3 hours

**Description:**
Build the provider abstraction layer. `ContextDataProvider` is the ABC all data providers implement. `ContextDataResult` is the return type (source_id, DataFrame, frequency, metadata). `ContextDataAligner` handles forward-fill alignment of lower-frequency data to the primary timeframe index. `ContextDataProviderRegistry` maps provider names to implementations.

**Implementation Notes:**
- `ContextDataProvider` has 3 abstract methods: `fetch()`, `validate()`, `get_source_ids()`
- `fetch()` is async (API calls), returns `list[ContextDataResult]` (one entry may produce multiple series)
- `ContextDataAligner.align(context_df, primary_index, method="forward_fill")` — reindex + ffill + drop leading NaNs
- Registry is a simple dict mapping provider name → provider class
- See architecture doc Section 3 for exact signatures

**Testing Requirements:**
- [ ] `ContextDataProvider` ABC cannot be instantiated directly
- [ ] `ContextDataResult` stores all required fields
- [ ] `ContextDataAligner.align()` forward-fills daily data to hourly index
- [ ] Aligner drops leading NaN rows (before first context observation)
- [ ] Weekend/holiday gaps are correctly forward-filled
- [ ] Registry registers and retrieves providers by name
- [ ] Registry raises clear error for unknown provider

**Acceptance Criteria:**
- [ ] Clean provider interface matching architecture doc
- [ ] Aligner correctly handles daily→hourly and weekly→hourly alignment
- [ ] Registry is extensible (new providers can register without code changes)

---

## Task 6.3: FRED Provider Implementation

**File(s):**
- `ktrdr/data/context/fred_provider.py` (new)

**Type:** CODING
**Estimated time:** 3 hours

**Description:**
Implement `FredDataProvider` that fetches yield data from FRED API, caches locally, and computes yield spreads. Handles single series (e.g., `DGS2`) and multi-series with automatic spread computation (e.g., `[DGS2, IRLTLT01DEM156N]` → individual series + `yield_spread_DGS2_IRLTLT01DEM156N`).

**Implementation Notes:**
- API: GET `https://api.stlouisfed.org/fred/series/observations` with `series_id`, `observation_start`, `observation_end`, `file_type=json`, `api_key`
- Response: `{"observations": [{"date": "2024-01-02", "value": "4.38"}, ...]}` — note `value` is a string
- Handle FRED's "." value for missing data (holidays) — treat as NaN, forward-fill
- Cache: `data/context/fred/{series_id}.csv` with metadata.json tracking last fetch date/range
- Spread: when `config.series` has 2+ items, compute `series[0] - series[1]` → `yield_spread_{s1}_{s2}`
- Rate limit: 120 req/min — add simple delay between requests if fetching multiple series
- `get_source_ids()`: single series → `["fred_{id}"]`, pair → `["fred_{s1}", "fred_{s2}", "yield_spread_{s1}_{s2}"]`

**Testing Requirements:**
- [ ] Single series fetch returns DataFrame with DatetimeIndex and value column
- [ ] Multi-series fetch returns individual series + computed spread
- [ ] FRED "." values handled as NaN
- [ ] Local cache is written and read on subsequent calls
- [ ] `get_source_ids()` returns correct IDs for single and multi-series
- [ ] `validate()` checks series ID format
- [ ] Integration test: fetch DGS2 for a known date range (skip in CI without API key)

**Acceptance Criteria:**
- [ ] Fetch, cache, and return FRED yield data
- [ ] Automatic spread computation for multi-series configs
- [ ] Cache avoids redundant API calls

---

## Task 6.4: Grammar Extension — `context_data` and `data_source`

**File(s):**
- `ktrdr/config/models.py` (add `ContextDataEntry`, `context_data` field on `StrategyConfigurationV3`)
- `ktrdr/config/strategy_validator.py` (validate `data_source` references)

**Type:** CODING
**Estimated time:** 3 hours

**Description:**
Add `ContextDataEntry` Pydantic model and `context_data: Optional[list[ContextDataEntry]]` to `StrategyConfigurationV3`. Add `data_source: Optional[str]` to indicator definitions (via existing `extra="allow"` — no model change needed, but add explicit handling). Update strategy validation to check that every `data_source` reference resolves to a declared context_data entry.

**Implementation Notes:**
- `ContextDataEntry` fields: `provider`, `alignment`, plus optional provider-specific fields (symbol, series, report, currencies, etc.) — see architecture doc Section 2.1
- `data_source` on indicators: since `IndicatorDefinition` uses `model_config = {"extra": "allow"}`, `data_source` already passes through. But add explicit extraction in `IndicatorEngine` and validation in `strategy_validator.py`.
- **IMPORTANT:** Field is `data_source`, NOT `source`. `source` collides with RSI's `source: close` param.
- Validation rules (architecture doc Section 2.4):
  1. Every `data_source` in indicators must resolve to a context_data entry's source IDs
  2. Provider types must be registered
  3. Provider-specific required fields present
  4. Warn (don't error) if context_data entries declared but unused

**Testing Requirements:**
- [ ] `ContextDataEntry` validates provider-specific required fields
- [ ] Strategy with `context_data` and matching `data_source` indicators validates
- [ ] Strategy with `data_source` referencing undeclared context data fails validation
- [ ] Strategy without `context_data` validates unchanged (backward compat)
- [ ] `data_source` and `source` coexist without collision
- [ ] Warning for unused context_data entries

**Acceptance Criteria:**
- [ ] Grammar extension parses and validates correctly
- [ ] All existing v3 strategies validate unchanged
- [ ] New carry strategy YAML from architecture doc validates

---

## Task 6.5: IndicatorEngine Context Data Routing

**File(s):**
- `ktrdr/indicators/indicator_engine.py` (accept and route by `data_source`)

**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Extend `IndicatorEngine` to accept `context_data: Optional[dict[str, pd.DataFrame]]` alongside primary data. When computing an indicator with `data_source` set, look up the DataFrame from `context_data[data_source]` instead of using primary data. The indicator itself is source-agnostic — it receives a DataFrame and computes.

**Implementation Notes:**
- Add `context_data` parameter to `compute_indicators()` (or whatever the entry method is)
- For each indicator: check `indicator_def.data_source` (via extra fields). If set, use `context_data[data_source]`. If not set, use primary data.
- Error if `data_source` references a key not in `context_data` dict
- Column naming: context indicators get prefixed with their data_source for disambiguation (e.g., `yield_spread_rsi_14`)

**Testing Requirements:**
- [ ] Indicator without `data_source` computes on primary data (no change)
- [ ] Indicator with `data_source` computes on the correct context DataFrame
- [ ] Missing `data_source` key in context_data raises clear error
- [ ] Context indicator columns are correctly prefixed

**Acceptance Criteria:**
- [ ] Indicators route to correct data source based on `data_source` field
- [ ] Existing indicator computation unchanged for strategies without `context_data`

---

## Task 6.6: Training Pipeline Context Data Loading

**File(s):**
- `ktrdr/training/training_pipeline.py` (load context data alongside primary)
- `training-host-service/orchestrator.py` (same change — dual dispatch!)
- `ktrdr/models/model_metadata.py` (add `context_data_config` and `context_source_ids`)

**Type:** CODING
**Estimated time:** 3 hours

**Description:**
When a strategy has `context_data`, the training pipeline fetches context data via providers, aligns it to the primary timeframe, and passes it to IndicatorEngine alongside primary data. Save `context_data_config` in model metadata for backtest reproducibility.

**Implementation Notes:**
- **DUAL DISPATCH:** Changes must go in BOTH `training_pipeline.py` AND `training-host-service/orchestrator.py`. We've been burned by this before with `forward_return` labels.
- Load context data: iterate `strategy.context_data`, use `ContextDataProviderRegistry` to get provider, call `provider.fetch()`, then `ContextDataAligner.align()` to primary index
- Pass aligned context dict to IndicatorEngine and FeatureCache
- Save `context_data_config` (serialized list of ContextDataEntry) and `context_source_ids` (ordered source ID list) in ModelMetadata
- For the host service: the orchestrator needs access to providers — add provider initialization alongside existing setup

**Testing Requirements:**
- [ ] Training with `context_data` strategy loads context data via providers
- [ ] Context data is aligned to primary timeframe index
- [ ] IndicatorEngine receives context data dict
- [ ] Model metadata includes `context_data_config` and `context_source_ids`
- [ ] Training without `context_data` works unchanged
- [ ] Host service dispatch matches container worker dispatch

**Acceptance Criteria:**
- [ ] Full training pipeline: strategy with FRED context → fetch yields → compute indicators → train model → save metadata with context config
- [ ] Model metadata contains reproducibility info for backtest

---

## Task 6.7: Validation

**File(s):** None (validation task)
**Type:** VALIDATION
**Estimated time:** 2 hours

**Description:**
Validate external data training pipeline end-to-end.

**Validation Steps:**
1. Load the `ke2e` skill before designing any validation
2. Invoke `ke2e-test-scout` with: "Train a v3 strategy that uses FRED yield spread data as context alongside EURUSD price indicators. The strategy must declare context_data with FRED provider, indicators with data_source referencing yield spread, and training must complete successfully with context features in the model."
3. Invoke `ke2e-test-runner` with the identified test recipes
4. Tests must exercise real infrastructure — real FRED API call, real training
5. Verify: model trains, metadata contains context_data_config, feature count includes context-derived features

**Acceptance Criteria:**
- [ ] Strategy with FRED `context_data` validates
- [ ] FRED data fetched and cached locally
- [ ] Context indicators computed on yield spread data
- [ ] Model trains successfully with combined features
- [ ] Model metadata includes `context_data_config` for backtest reproducibility
