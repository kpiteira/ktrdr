# M6 Handoff: CLI & Migration Tools

## Task 6.1 Complete: Create Migration Logic

### Implementation Notes

**Module location:** `ktrdr/config/strategy_migration.py`

**Key functions:**
- `migrate_v2_to_v3(v2_config: dict) -> dict` - Converts v2 strategy to v3 format
- `validate_migration(original: dict, migrated: dict) -> list[str]` - Validates migration preserved data

**Migration rules implemented (per ARCHITECTURE.md lines 617-624):**
1. Convert `indicators` list to dict (key = feature_id, `type` = name)
2. Add `indicator` field to fuzzy_sets (defaults to fuzzy_set key)
3. Generate `nn_inputs` from fuzzy_sets (each gets `timeframes: "all"`)
4. Update version to "3.0"

### Gotchas

**Deep copy is critical**
- The function uses `copy.deepcopy()` to avoid modifying the original config
- Tests verify original config remains unchanged after migration

**feature_id fallback**
- If an indicator lacks `feature_id`, falls back to `name` as the key
- This handles edge cases in older configs

**Existing indicator field preserved**
- If a fuzzy_set already has `indicator` field, it's preserved (not overwritten)
- Allows partial migrations or manually-specified relationships

### Files Created

- `ktrdr/config/strategy_migration.py`: Migration logic (~75 lines)
- `tests/unit/config/test_strategy_migration.py`: 15 unit tests

---

## Task 6.2 Complete: Add CLI `strategy migrate` Command

### Implementation Notes

**Command location:** `ktrdr/cli/strategy_commands.py`

**Command usage:**
```bash
ktrdr strategies migrate <path> [--output PATH] [--backup] [--dry-run]
```

**Note:** The CLI uses `strategies` (plural) as the command group, not `strategy` (singular).

**Features implemented:**
- Single file migration with `--output` for alternate destination
- Directory migration (processes all *.yaml and *.yml files)
- `--backup` creates .bak file before overwriting in place
- `--dry-run` shows what would change without writing
- Automatic v3 format detection (skips already-migrated files)
- Post-migration validation with `StrategyConfigurationLoader`

### Gotchas

**Uses typer, not click**
- The CLI uses `typer` (not `click` as mentioned in design doc)
- Typer is built on click but has different API

**Parent directories created automatically**
- `out_path.parent.mkdir(parents=True, exist_ok=True)` ensures output directory exists

**Validation is non-blocking**
- Migration completes even if validation fails
- Shows warning instead of error (allows manual fixing)

### Files Modified

- `ktrdr/cli/strategy_commands.py`: Added `migrate` command (~80 lines)
- `tests/unit/cli/test_strategy_migrate.py`: New file, 9 tests

---

## Task 6.3 Complete: Add CLI `strategy features` Command

### Implementation Notes

**Command location:** `ktrdr/cli/strategy_commands.py`

**Command usage:**
```bash
ktrdr strategies features <path> [--group-by none|timeframe|fuzzy_set]
```

**Features implemented:**
- Loads v3 strategy with `StrategyConfigurationLoader.load_v3_strategy()`
- Resolves features with `FeatureResolver.resolve(config)`
- Three display modes via `--group-by`:
  - `none` (default): Flat list of all features
  - `timeframe`: Groups features by timeframe with `[5m]`, `[1h]` headers
  - `fuzzy_set`: Groups by fuzzy set showing indicator reference
- Shows strategy name and total feature count
- Proper error handling for v2 strategies (suggests migration)

### Gotchas

**Rich markup escaping**
- Fuzzy set names in `[brackets]` need escaping for Rich console
- Used `\\[{fs_id}]` to display literal brackets

**v2 strategy detection**
- Catches `ValueError` from loader when format detection fails
- Shows helpful message suggesting `strategies migrate` command

### Files Modified

- `ktrdr/cli/strategy_commands.py`: Added `features` command (~75 lines)
- `tests/unit/cli/test_strategy_features.py`: New file, 9 tests

---

## Task 6.4 Complete: Update Strategy Commands Help Text

### Implementation Notes

**Files modified:**
- `ktrdr/cli/strategy_commands.py`: Updated module docstring and `strategies_app` help
- `ktrdr/cli/__init__.py`: Updated help text in `add_typer()` call

**Changes made:**
- Module docstring now lists all 6 commands including migrate and features
- `strategies_app` help includes v3 format mention and usage examples
- Main CLI registration updated to show "Manage trading strategies (v3 format)"

### Gotchas

**Help text override in main CLI**
- The `add_typer()` call in `__init__.py` overrides `strategies_app.help`
- Need to update both locations for changes to take effect

---

## Milestone 6 Complete: CLI E2E Test Results

All CLI E2E tests passed:

| Test | Description | Result |
|------|-------------|--------|
| Test 1 | Dry-run migration shows preview | ✅ PASS |
| Test 2 | Migration creates valid v3 file with nn_inputs | ✅ PASS |
| Test 3 | Validation passes on migrated strategy | ✅ PASS |
| Test 4 | Features listed correctly | ✅ PASS |
| Test 5 | Features grouped by timeframe | ✅ PASS |

**Note:** v2 strategies with `single_symbol` mode need `single` for v3 compatibility.
The migration does not auto-convert enum values, so source v2 files may need
manual adjustment if they use deprecated enum names.

---

## V3 Training Integration Gap (RESOLVED - M6.5)

### Problem (Historical)

Full E2E testing revealed that v3 strategies could not complete training because
TrainingPipelineV3 was not wired into the training workers. The workers used
the v2 TrainingPipeline which had format incompatibilities with v3 configs.

### Resolution (M6.5)

**M6.5 closed the integration gap with targeted wiring changes:**

---

## Task 6.5.1 Complete: Wire V3 Training in LocalTrainingOrchestrator

### Implementation Notes

**File modified:** `ktrdr/api/services/training/local_orchestrator.py`

**Changes made:**
- Added `_execute_v3_training()` method that uses `TrainingPipelineV3`
- Added `_execute_v2_training()` method (extracted legacy code)
- Modified `_execute_training()` to branch based on `_is_v3_format()`
- V3 path: loads typed config, resolves features, saves `metadata_v3.json`

**Key pattern:**
```python
if self._is_v3_format(config):
    result = self._execute_v3_training(config)
else:
    result = self._execute_v2_training(config)
```

### Gotchas

**Labels config location differs**
- V3 labels config is under `config["training"]["labels"]`, not flat at root level
- Need to extract `zigzag_threshold` and `label_lookahead` from nested structure

**Tensor alignment**
- Features and labels may have different lengths due to NaN handling
- Align to minimum length: `features_aligned = features[-min_len:]`

---

## Task 6.5.2 Complete: Wire V3 Backtest in DecisionOrchestrator

### Implementation Notes

**File modified:** `ktrdr/decision/orchestrator.py`

**Changes made:**
- Added `_check_v3_model()` method to detect v3 models via `metadata_v3.json`
- Added `_create_v3_feature_cache()` method to create `FeatureCacheV3`
- Modified `__init__()` to use `FeatureCacheV3` when model is v3

**Key pattern:**
```python
if mode == "backtest":
    if model_path and self._check_v3_model(model_path):
        self.feature_cache = self._create_v3_feature_cache(model_path)
    else:
        self.feature_cache = FeatureCache(self.strategy_config)
```

### Gotchas

**Static methods reused**
- Reuses `BacktestingService.is_v3_model()` and `load_v3_metadata()` from M5
- Also reuses `reconstruct_config_from_metadata()` for config reconstruction

---

## Task 6.5.3 Complete: E2E Test for V3 Train/Backtest

### Implementation Notes

**File created:** `tests/e2e/test_v3_train_backtest.py`

**Tests:**
1. `test_v3_strategy_dry_run_shows_indicators` - V3 dry-run works
2. `test_v3_training_creates_metadata_v3` - Training creates `metadata_v3.json`
3. `test_v3_backtest_uses_correct_features` - Backtest has no feature mismatch
4. `test_v2_strategy_dry_run_still_works` - V2 backward compatibility

**Skips:**
- Training tests skipped if `~/.ktrdr/shared/data/EURUSD_1h.csv` not available
- Backtest test skipped if training didn't run first

---

## M6.5 Integration Verification

**CRITICAL: These checks prove the wiring works:**

| Check | Purpose | Status |
|-------|---------|--------|
| `metadata_v3.json` created | Proves `_save_v3_metadata()` called | ✅ |
| Contains `resolved_features` | Proves `FeatureResolver` used | ✅ |
| No feature mismatch in backtest | Proves `FeatureCacheV3` used | ✅ |
| V2 strategies still work | Backward compatibility | ✅ |

---

## Earlier Fixes Applied (M6 Session)

1. **IndicatorEngine v3 fix**: Added `self.indicators = list(self._indicators.values())`
   to populate the `indicators` list when v3 format is used, fixing "No indicators
   configured" error.

2. **FuzzyEngine v3 fixes**:
   - Updated `generate_multi_timeframe_memberships()` to detect v3 format and
     create FuzzyEngine directly (not via FuzzyConfigLoader which expects v2)
   - Updated `_find_fuzzy_key()` to check `_indicator_map` for v3 indicator matching
   - Fixed logging line that accessed `_membership_functions` (v2-only attribute)

---
