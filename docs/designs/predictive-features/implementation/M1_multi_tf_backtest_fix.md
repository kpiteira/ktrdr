---
design: docs/designs/predictive-features/multi-timeframe-context/DESIGN.md
architecture: docs/designs/predictive-features/multi-timeframe-context/ARCHITECTURE.md
---

# M1: Multi-TF Backtest Fix

**Thread:** Context (prerequisite)
**JTBD:** "As a researcher, I want to train a multi-timeframe strategy and backtest it end-to-end so that models using 1h+4h+1d features can be evaluated."
**Depends on:** Nothing
**Tasks:** 4

---

## Task 1.1: Add `timeframes` to BacktestConfig and Worker Request

**File(s):**
- `ktrdr/backtesting/engine.py` (modify `BacktestConfig`)
- `ktrdr/backtesting/backtest_worker.py` (modify `BacktestStartRequest`)

**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Add `timeframes: list[str]` field to `BacktestConfig` (dataclass at `engine.py:32-44`) and `BacktestStartRequest` (Pydantic model at `backtest_worker.py:96-108`). Both default to empty list for backward compatibility. Add `get_all_timeframes()` helper that returns `self.timeframes if self.timeframes else [self.timeframe]`.

**Implementation Notes:**
- `BacktestConfig` is a dataclass — add `timeframes: list[str] = field(default_factory=list)`
- `BacktestStartRequest` is a Pydantic model — add `timeframes: list[str] = Field(default_factory=list)`
- The `get_all_timeframes()` helper goes on `BacktestConfig` (the dataclass used by the engine)
- Existing single-TF backtests must work unchanged — if `timeframes` is empty, fall back to `[self.timeframe]`

**Testing Requirements:**
- [ ] `BacktestConfig` with no `timeframes` returns `[timeframe]` from `get_all_timeframes()`
- [ ] `BacktestConfig` with `timeframes=["1h", "1d"]` returns `["1h", "1d"]`
- [ ] `BacktestStartRequest` serialization includes `timeframes` field
- [ ] Existing single-TF backtest config construction still works

**Acceptance Criteria:**
- [ ] `timeframes` field exists on both `BacktestConfig` and `BacktestStartRequest`
- [ ] `get_all_timeframes()` returns correct list for both single-TF and multi-TF cases
- [ ] All existing backtest tests pass unchanged

---

## Task 1.2: Thread Timeframes Through API and Service

**File(s):**
- `ktrdr/api/endpoints/backtesting.py` (extract timeframes from strategy)
- `ktrdr/backtesting/backtesting_service.py` (forward timeframes to worker)
- `ktrdr/backtesting/remote_api.py` (include timeframes in remote request)

**Type:** CODING
**Estimated time:** 2 hours

**Description:**
When a backtest is started, the API endpoint reads the strategy config's full timeframes list (from `training_data.timeframes`) and forwards it through the service layer to the worker. The backtesting service already loads strategy config via `reconstruct_config_from_metadata()` — extract `training_timeframes` from model metadata and include in the worker payload.

**Implementation Notes:**
- In `backtesting.py` endpoint: after loading metadata, extract `metadata.training_timeframes` and pass to service
- In `backtesting_service.py`: add `timeframes` to the worker request payload dict sent via HTTP POST to `/backtests/start`
- In `remote_api.py`: include `timeframes` field in the request body
- `ModelMetadata` already has `training_timeframes: list[str]` — use that as the source
- For single-TF models, `training_timeframes` will be `["1h"]` — this is correct, `get_all_timeframes()` handles it

**Testing Requirements:**
- [ ] API endpoint extracts timeframes from model metadata
- [ ] Service layer includes timeframes in worker request payload
- [ ] Remote API passes timeframes in request body
- [ ] Single-TF model produces `timeframes: ["1h"]` in payload

**Acceptance Criteria:**
- [ ] Full timeframes list flows from API → service → worker
- [ ] Existing single-TF backtests are unaffected

---

## Task 1.3: Multi-TF Data Loading in Backtest Engine

**File(s):**
- `ktrdr/backtesting/engine.py` (modify data loading to use `MultiTimeframeCoordinator`)

**Type:** CODING
**Estimated time:** 3 hours

**Description:**
When `BacktestConfig.get_all_timeframes()` returns multiple timeframes, the backtest engine must load data via `MultiTimeframeCoordinator.load_multi_timeframe_data()` instead of loading a single timeframe. Pass the resulting `dict[str, pd.DataFrame]` to `FeatureCache.compute_features()` (which already accepts this format).

**Implementation Notes:**
- The engine currently loads data for one timeframe only. Add conditional: if `len(config.get_all_timeframes()) > 1`, use `MultiTimeframeCoordinator`
- `MultiTimeframeCoordinator` is at `ktrdr/data/multi_timeframe_coordinator.py` — it returns `dict[timeframe: aligned_DataFrame]`
- `FeatureCache.compute_features()` already accepts `dict[str, pd.DataFrame]` — verified in codebase
- The base timeframe for bar iteration is `config.timeframe` (the primary/first timeframe)
- Data for higher timeframes is forward-filled by `TimeframeSynchronizer` within the coordinator

**Testing Requirements:**
- [ ] Single-TF backtest loads data as before (no regression)
- [ ] Multi-TF backtest loads data for all timeframes via coordinator
- [ ] FeatureCache receives `dict[str, pd.DataFrame]` with all timeframes
- [ ] Feature computation succeeds with multi-TF data
- [ ] Bar iteration uses base timeframe only

**Acceptance Criteria:**
- [ ] Multi-TF model's backtest no longer raises `KeyError` on secondary timeframes
- [ ] Features match between training and backtesting for multi-TF models
- [ ] Existing single-TF backtests pass unchanged

---

## Task 1.4: Validation

**File(s):** None (validation task)
**Type:** VALIDATION
**Estimated time:** 2 hours

**Description:**
Validate the multi-TF backtest fix end-to-end.

**Validation Steps:**
1. Load the `ke2e` skill before designing any validation
2. Invoke `ke2e-test-scout` with: "Train a v3 multi-timeframe strategy (1h+1d) on EURUSD, then backtest it end-to-end. The backtest must complete without KeyError on secondary timeframes."
3. Invoke `ke2e-test-runner` with the identified test recipes
4. Tests must exercise real running infrastructure — real training, real backtest execution
5. Verify: backtest completes, produces trades, feature count matches between training and backtest

**Acceptance Criteria:**
- [ ] Train a multi-TF strategy (e.g., `v3_multi_timeframe.yaml` with 1h+1d) → success
- [ ] Backtest that model → completes without `KeyError`
- [ ] Backtest produces non-zero trades
- [ ] Feature validation passes (FeatureCache validates against `metadata.resolved_features`)
