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

**Additional fixes (post-8.4):**

4. **Fixed v3 compatibility bug in feature_cache.py:**
   - `ktrdr/backtesting/feature_cache.py`: Updated indicator iteration to handle both v2 list and v3 dict formats
   - Bug: Code assumed `indicators` was always a list, causing `AttributeError: 'str' object has no attribute 'get'`
   - Fix: Check `isinstance(indicators_config, dict)` and iterate over keys for v3

5. **Deleted obsolete v2-only tests:**
   - `test_feature_id_map.py`: Tested v2 `feature_id_map` attribute (not needed in v3)
   - `test_feature_id_aliasing.py`: Tested v2 aliasing (not needed in v3 - indicator_id IS the feature_id)

**Final test results:**
- 3891 passed
- 0 failed
- 76 skipped (v15 tests when shared dir missing)

---

## Task 8.5 Complete: Remove V2 Code Paths

**What was removed:**

1. **IndicatorEngine (`ktrdr/indicators/indicator_engine.py`):**
   - `feature_id_map` attribute - v2 column name → feature_id mapping
   - `_build_feature_id_map()` method - built mapping from v2 configs
   - `_create_feature_id_aliases()` method - created duplicate columns for aliasing
   - Call to `_create_feature_id_aliases()` in `apply()` method

2. **feature_cache.py (`ktrdr/backtesting/feature_cache.py`):**
   - Removed v2 list format handling
   - Now raises ValueError if strategy config uses v2 format (list-based indicators)

3. **exceptions.py (`ktrdr/errors/exceptions.py`):**
   - Removed v2 factory methods:
     - `missing_feature_id()` - v2 indicator missing feature_id field
     - `duplicate_feature_id()` - v2 duplicate feature_id values
     - `invalid_feature_id_format()` - v2 feature_id format validation
     - `reserved_feature_id()` - v2 reserved word validation
   - Removed `ErrorCodes` import (no longer used)

4. **error_codes.py (`ktrdr/errors/error_codes.py`):**
   - Removed v2-specific error codes:
     - `STRATEGY_MISSING_FEATURE_ID`
     - `STRATEGY_DUPLICATE_FEATURE_ID`
     - `STRATEGY_INVALID_FEATURE_ID_FORMAT`
     - `STRATEGY_RESERVED_FEATURE_ID`

5. **Deleted obsolete test files:**
   - `tests/unit/api/test_strategy_error_responses.py` - tested v2 error factory methods
   - `tests/unit/config/test_validation_errors.py` - tested v2 error factory methods
   - `tests/unit/test_configuration_error.py` - tested v2 error factory methods

**What was preserved:**
- `strategy_migration.py` - users may still need to migrate old v2 strategies
- `get_feature_id()` method in base_indicator.py - this is the v3 API
- `_feature_id` attribute in base_indicator.py - used by indicator factory

**Gotchas:**
- The term "feature_id" is still valid in v3 context - it's how indicators identify themselves via `get_feature_id()`
- In v3, `indicator_id` (the dict key) IS the feature_id - no aliasing needed
- Strategy loader `_detect_v2_format()` and `_is_v3_format()` are preserved for migration support

**Test results after Task 8.5:**
- 3836 passed
- 0 failed
- 76 skipped (v15 tests when shared dir missing)

### FeatureCache Deep Cleanup (Additional Task 8.5 Work)

**What was done:**

1. **FeatureCache consolidation:**
   - Deleted old v2 FeatureCache class (dict-based strategy config approach)
   - Renamed FeatureCacheV3 → FeatureCache (clean v3 interface)
   - Simplified `get_features_for_timestamp()` to return `dict[str, float] | None`
   - Removed obsolete compatibility methods

2. **Orchestrator v3-only:**
   - Removed v2/v3 branching in DecisionOrchestrator
   - Now requires v3 model for backtest mode (raises ValueError for v2)
   - Renamed `_create_v3_feature_cache()` → `_create_feature_cache()`
   - Updated `make_decision()` to use v3 interface (dict return, not tuple)

3. **Deleted obsolete tests:**
   - `tests/unit/backtesting/test_feature_cache_new_format.py` - v2 tests
   - `tests/integration/indicators/test_full_pipeline_new_format.py` - v2 integration
   - `TestFeatureCacheOrderValidation` class - tested removed method

**What was NOT done (deferred):**
- TrainingPipeline/TrainingPipelineV3 consolidation - requires changes to local_orchestrator
- ModelMetadata/ModelMetadataV3 rename - used across many components
- These have workarounds via TYPE_CHECKING aliases

**Test results after FeatureCache cleanup:**
- 3823 passed
- 0 failed
- 76 skipped

---

## Deep Cleanup Continued (Task 8.5 Extended)

### TrainingPipeline Cleanup

**What was done:**

1. **TrainingPipeline.train_strategy() deleted:**
   - Removed ~360 lines of v2 orchestration code
   - Static utility methods preserved (load_market_data, calculate_indicators, etc.)
   - TrainingPipelineV3 remains for v3 feature preparation

2. **LocalTrainingOrchestrator v3-only:**
   - Removed v2/v3 branching
   - Deleted `_execute_v2_training()` method
   - Now raises ValueError for v2 format strategies

3. **Obsolete tests deleted:**
   - TestTrainStrategyHighLevel class
   - test_train_strategy_accepts_checkpoint_callback
   - test_execute_v2_training_method_exists

### ModelMetadata Cleanup

**What was done:**

1. **ModelMetadata consolidated:**
   - Renamed ModelMetadataV3 → ModelMetadata
   - Added backwards compatibility alias: `ModelMetadataV3 = ModelMetadata`
   - File reduced from ~630 lines to ~120 lines

2. **Dead code deleted:**
   - Old ModelMetadata class (~200 lines)
   - ModelMetadataManager class (~150 lines)
   - All supporting dataclasses (TrainingDataInfo, DeploymentCapabilities, etc.)
   - model_storage_v2.py entire file (~560 lines) - not imported anywhere
   - Module-level metadata_manager instance

**Total lines deleted:** ~2,000 lines of v2 code

**Test results:**
- 3817 passed
- 0 failed
- 76 skipped

**Next Task Notes (8.6):**
- Update documentation to reflect v3-only world
- Add deprecation note for v2 format
- Ensure examples use v3 format
