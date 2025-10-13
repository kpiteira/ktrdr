# Explicit Indicator Naming - Implementation Status

## ✅ Completed Phases

### Phase 1: Configuration Model Updates (COMPLETE)
**Commit:** `3d9bc50` - feat(config): implement explicit indicator naming (Phase 1)

- ✅ Renamed `type` → `indicator` field in `IndicatorConfig`
- ✅ Made `name` field required (was optional)
- ✅ Added name validation (alphanumeric, underscore, dash, must start with letter)
- ✅ Implemented flat YAML support via custom `__init__`
- ✅ Added name uniqueness validation in `StrategyConfigurationV2`
- ✅ 16 comprehensive tests

**Files Modified:**
- [ktrdr/config/models.py](../../ktrdr/config/models.py:77-136)
- [tests/unit/config/test_explicit_indicator_naming.py](../../tests/unit/config/test_explicit_indicator_naming.py) (new)

### Phase 2: Indicator Factory & Base Indicator (COMPLETE)
**Commit:** `edd10a8` - feat(indicators): implement explicit naming in factory and base indicator (Phase 2)

- ✅ Updated `IndicatorFactory` to use `config.indicator` instead of `config.type`
- ✅ Store custom name as `_custom_column_name` attribute on indicators
- ✅ Updated `BaseIndicator.get_column_name()` to use custom name if available
- ✅ Added `_generate_column_name()` for backward compatibility
- ✅ 11 comprehensive tests
- ✅ Updated 7 existing factory tests to new schema

**Files Modified:**
- [ktrdr/indicators/indicator_factory.py](../../ktrdr/indicators/indicator_factory.py:242-283)
- [ktrdr/indicators/base_indicator.py](../../ktrdr/indicators/base_indicator.py:157-208)
- [tests/unit/indicators/test_explicit_naming_factory.py](../../tests/unit/indicators/test_explicit_naming_factory.py) (new)
- [tests/unit/indicators/test_indicator_factory.py](../../tests/unit/indicators/test_indicator_factory.py)

### Phase 5: Migration Script (COMPLETE - UNCOMMITTED)
**Status:** Tests pass, quality checks pass, ready to commit

- ✅ Created migration script to convert legacy → explicit naming format
- ✅ Auto-generates names matching legacy auto-generation logic
- ✅ Smart parameter ordering (MACD: 12_26_9 not 12_9_26)
- ✅ Dry-run mode, batch processing, custom output directory
- ✅ Already-migrated file detection
- ✅ 15 comprehensive tests
- ✅ All quality checks passing

**Files Created:**
- [scripts/migrate_indicator_naming.py](../../scripts/migrate_indicator_naming.py) (new)
- [tests/unit/scripts/test_migrate_indicator_naming.py](../../tests/unit/scripts/test_migrate_indicator_naming.py) (new)

**Usage:**
```bash
# Dry run to see what would change
./scripts/migrate_indicator_naming.py strategy.yaml --dry-run

# Migrate file(s)
./scripts/migrate_indicator_naming.py strategy.yaml
./scripts/migrate_indicator_naming.py config/strategies/*.yaml --output-dir migrated/
```

## ⏳ Remaining Phases

### Phase 3: Validation Updates (NOT STARTED)
**Estimated Effort:** Medium (~2-3 hours)

**Tasks:**
1. Simplify indicator-fuzzy matching validation
   - Remove auto-generation logic from validation
   - Direct name matching: `fuzzy_sets.rsi_14` matches `indicators[].name == "rsi_14"`
   - Update validation error messages

2. Add indicator definition validation
   - Ensure all fuzzy_sets reference valid indicator names
   - Clear error messages for typos/mismatches

**Files to Modify:**
- `ktrdr/config/strategy_validator.py`
- `ktrdr/fuzzy/config.py` (validation logic)

### Phase 4: Engine & Pipeline Updates (IN PROGRESS)
**Estimated Effort:** High (~4-6 hours)

**Blockers:** Training pipeline tests fail due to schema mismatch

**Tasks:**

#### Phase 4.1: IndicatorEngine (DONE)
- ✅ Already validates through `IndicatorConfig` model
- ✅ No code changes needed

#### Phase 4.2: TrainingPipeline Simplification (BLOCKED)
**Current Status:** Tests using old schema

**Required Changes:**
1. Remove name-to-type mapping logic (~20 lines in `_calculate_indicators_single_timeframe`)
2. Remove indicator name mapping logic (~45 lines per method)
3. Simplify multi-timeframe handling (~50 lines)
4. **Total:** ~80-100 lines can be removed

**Test Updates Needed:**
- [tests/unit/training/test_training_pipeline_features.py](../../tests/unit/training/test_training_pipeline_features.py)
  - Update all `indicator_configs` to use new schema
  - Update column name assertions (`"rsi"` → `"rsi_14"`)
  - 5 tests currently failing

**Files to Modify:**
- `ktrdr/training/training_pipeline.py` (lines 272-381, 450-478)
- All tests that create indicator configs

### Phase 6: Documentation (NOT STARTED)
**Estimated Effort:** Low (~1 hour)

**Tasks:**
1. Update [CLAUDE.md](../../CLAUDE.md) with new naming convention examples
2. Update strategy documentation with migration guide
3. Add examples of new format to README/docs

## 🔧 How to Complete Remaining Work

### Step 1: Fix Phase 4.2 (TrainingPipeline)

```bash
# 1. Update test configs to new schema
# In tests/unit/training/test_training_pipeline_features.py:
# OLD: {"name": "rsi", "period": 14}
# NEW: {"indicator": "rsi", "name": "rsi_14", "period": 14}

# 2. Update column name assertions
# OLD: assert "rsi" in result["1D"].columns
# NEW: assert "rsi_14" in result["1D"].columns

# 3. Simplify TrainingPipeline._calculate_indicators_single_timeframe()
# Remove lines 272-291 (name-to-type mapping)
# Remove lines 298-340 (indicator name mapping)
# Replace with direct column usage (indicators now have explicit names)

# 4. Run tests
make test-unit

# 5. Run quality checks
make quality
```

### Step 2: Implement Phase 3 (Validation)

```bash
# Update validation to use direct name matching
# Remove auto-generation logic from validators
# Add tests for new validation behavior
```

### Step 3: Complete Phase 6 (Documentation)

```bash
# Add examples to CLAUDE.md
# Update strategy docs with migration guide
```

## 📊 Summary

**Progress:** 3/6 phases complete (50%)
- ✅ Phase 1: Configuration Models
- ✅ Phase 2: Factory & Base Indicator
- ⏳ Phase 3: Validation (not started)
- ⚠️  Phase 4: Pipeline (partially done, blocked by tests)
- ✅ Phase 5: Migration Script (complete, uncommitted)
- ⏳ Phase 6: Documentation (not started)

**Test Status:**
- ✅ 42 new tests passing (16 config + 11 factory + 15 migration)
- ❌ 5 training pipeline tests failing (need schema updates)
- ✅ All quality checks passing

**Next Steps:**
1. ✅ Commit Phase 5 (migration script)
2. Fix training pipeline tests (Phase 4.2)
3. Simplify TrainingPipeline code
4. Implement Phase 3 validation
5. Update documentation (Phase 6)
6. Mark PR as ready for review
