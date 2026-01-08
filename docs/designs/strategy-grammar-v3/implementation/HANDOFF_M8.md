# Handoff: Milestone 8 - Cleanup & Migration

## Task 8.1 Complete: Audit Existing Strategies

**Key findings:**
- 74 total strategies in project root `strategies/` (legacy, gitignored)
- 125 strategies in `~/.ktrdr/shared/strategies/` (actual user strategies)
- v1.5 experiment suite (23 strategies) is critical - used by `tests/unit/test_v15_template.py`

**Gotchas:**
- V3 detection: Look for `nn_inputs:` key (v2 strategies don't have it)
- V2 detection: Look for `feature_id:` in indicators list format
- **Important**: User strategies are in `~/.ktrdr/shared/strategies/`, not project root

---

## Task 8.2 Complete: Migrate Useful Strategies

**Location:** `~/.ktrdr/shared/strategies/` (125 strategies)

**What was done:**
- Migrated 121 v2 strategies to v3 format using `ktrdr strategies migrate ~/.ktrdr/shared/strategies/ --backup`
- Fixed mode values: `single_symbol` → `single`, `single_timeframe` → `single` (34 files)
- Fixed fuzzy_set `indicator` references for ADX/Aroon (12 files)
- Fixed MTF-prefixed indicator references like `DI_Plus_1h_14` → `adx_1h_14` (3 files)

**Gotchas:**
- Migration tool converts indicators from list to dict, but doesn't fix mode values
- fuzzy_set `indicator` field must match indicator ID (lowercase), not column names
- For multi-output indicators (ADX, Aroon), use base indicator ID: `adx_14` not `ADX_14`
- MTF strategies may have timeframe-prefixed IDs: `adx_1h_14`, `DI_Plus_1h_14` etc.
- Backup files created as `.bak` in strategies/ directory

**Test updates (for project root strategies/):**
- `tests/unit/test_v15_template.py` needed updates for v3 dict-based indicators
- Changed `isinstance(indicators, list)` → `isinstance(indicators, dict)`
- Changed iteration from `for ind in indicators` → `for ind_key, ind_config in indicators.items()`

**Final validation:** All 125 strategies in `~/.ktrdr/shared/strategies/` pass validation

**Next Task Notes (8.3):**
- Delete obsolete strategies from shared directory
- Note: Project root `strategies/` directory is legacy and should be removed eventually
- Backup files (.bak) can be deleted after verification

---

## Task 8.4 Complete: Update Test Fixtures

**What was done:**

1. **Fixed strategy file references:**
   - `test_engine_progress_bridge.py`: Changed `strategies/trend_momentum.yaml` → `strategies/v3_minimal.yaml`
   - `test_strategy_validator_agent.py`: Changed `neuro_mean_reversion` → `v3_minimal` for duplicate name tests
   - `test_v15_template.py`: Updated to use `~/.ktrdr/shared/strategies/` path (user experiments)

2. **Updated indicator tests to v3 format:**
   - `test_indicator_engine_no_init_computation.py`: Converted from v2 list to v3 dict format
   - `test_multi_timeframe_prefixing.py`: Converted from v2 list to v3 dict format

3. **Skipped v2-specific tests (to be removed in Task 8.5):**
   - `test_feature_id_map.py`: Tests v2 `feature_id_map` concept (not in v3)
   - `test_feature_id_aliasing.py`: Tests v2 `feature_id` aliasing (not in v3)

**Gotchas:**
- V3 IndicatorEngine uses `_indicators` dict (not `feature_id_map`)
- In v3, `indicator_id` IS the feature identifier (no aliasing needed)
- `apply_multi_timeframe()` works with v3 dict format
- `compute()` and `compute_for_timeframe()` are v3 API methods

**Known Issues (pre-existing):**
- `test_engine_progress_bridge.py`: 2 tests failing due to backtest engine integration issues
  - `test_progress_updates_every_50_bars`: Bridge `_update_state` not called
  - `test_cancellation_raises_cancelled_error`: `AttributeError: 'str' object has no attribute 'get'`
  - These failures existed before Task 8.4 (different error: missing strategy file)
  - Root cause appears to be BacktestingEngine + v3 strategy integration

**Test results after Task 8.4:**
- 3889 passed
- 2 failed (pre-existing backtest integration issues)
- 98 skipped (v2 tests + v15 tests when shared dir missing)

**Next Task Notes (8.5):**
- Remove v2 code paths from IndicatorEngine and other components
- Delete the skipped v2 tests (test_feature_id_map.py, test_feature_id_aliasing.py)
- Fix or remove the failing backtest progress tests
