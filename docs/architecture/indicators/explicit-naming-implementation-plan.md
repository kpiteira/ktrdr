# Implementation Plan: Explicit Indicator Naming

**Status**: Updated based on v3 Architecture
**Date**: 2025-10-13
**Architecture**: [explicit-naming-architecture.md](./explicit-naming-architecture.md)

---

## Overview

This document outlines the phased implementation of the feature_id architecture.

**Key Architecture Decisions**:

- feature_id is **MANDATORY** and **UNIQUE** (no defaults)
- **BREAKING CHANGE** with migration tool
- SMA/EMA transformation → `input_transform` in fuzzy config (proper architecture)
- MACD: feature_id maps to primary output (main line)
- Validation is **STRICT** by default
- Training pipeline simplifies (~130 lines removed)

Each phase is independently testable with clear acceptance criteria and validation updates.

---

## Phase 0: Fix Error Reporting Infrastructure

**Priority**: CRITICAL - MUST BE COMPLETED FIRST

**Goal**: Ensure validation errors are logged, reported clearly, and actionable.

### Why First?

Cannot debug issues without clear error reporting. v1 failed partially because validation was broken/commented out.

### Current State Issues

1. Strategy validation commented out (commit 649c390)
2. Validation errors return 400 with empty body
3. No logging of validation failures
4. Pydantic errors not formatted for users
5. No structured error details

### Tasks

#### Task 0.1: Re-enable and Fix StrategyValidator

**Files**: `ktrdr/config/strategy_validator.py`

**Changes**:

1. Review current validation logic
2. Add comprehensive logging (error level with full context)
3. Format Pydantic ValidationError into user-friendly messages
4. Include context (file, section, field) in all errors
5. Add structured details dict to errors
6. Include actionable suggestions in error messages

**Acceptance Criteria**:

- [ ] Validator logs all errors before raising exceptions
- [ ] Validation errors include: message, code, context, details, suggestions
- [ ] Pydantic errors converted to readable format with field paths
- [ ] Test with invalid strategy: error message explains what's wrong and how to fix
- [ ] No errors silently swallowed

#### Task 0.2: Update API Error Responses

**Files**: `ktrdr/api/endpoints/strategies.py`, `ktrdr/api/endpoints/training.py`

**Changes**:

1. Re-enable validation in endpoints
2. Catch ConfigurationError and format for HTTP response
3. Return structured error detail (not empty body)
4. Log errors server-side with full details before responding
5. Include error code in response for client handling

**Acceptance Criteria**:

- [ ] API returns 400 with structured error body (never empty)
- [ ] Error body includes: error message, code, details, suggestion
- [ ] Server logs show full error context before response
- [ ] Test invalid strategy upload: response explains issue clearly
- [ ] Frontend can parse and display error details

#### Task 0.3: Update ConfigurationError Class

**Files**: `ktrdr/errors.py`

**Changes**:

1. Ensure ConfigurationError supports all required fields:
   - message (str): Human-readable error
   - error_code (str): Machine-readable code (e.g., STRATEGY-MissingFeatureId)
   - context (dict): Where error occurred (file, section, field)
   - details (dict): Structured data (actual vs expected)
   - suggestion (str): How to fix (command to run, example code)
2. Add `to_dict()` method for API serialization
3. Add `format_user_message()` for display

**Example**:

```python
raise ConfigurationError(
    message="Indicator missing required field 'feature_id'",
    error_code="STRATEGY-MissingFeatureId",
    context={"file": "strategy.yaml", "section": "indicators[0]"},
    details={"indicator_type": "rsi", "period": 14},
    suggestion=(
        "Add 'feature_id' to indicator:\n"
        "  - type: \"rsi\"\n"
        "    feature_id: \"rsi_14\"  # ADD THIS\n"
        "    period: 14"
    )
)
```

**Acceptance Criteria**:

- [ ] ConfigurationError captures all required fields
- [ ] Can serialize to dict for API responses
- [ ] Can format user-friendly message with context
- [ ] Test with various error scenarios: all fields populated correctly
- [ ] Error messages include migration tool command when applicable

#### Task 0.4: Add Validation Error Tests

**Files**: `tests/unit/config/test_validation_errors.py`

**Tests**:

1. Schema validation errors (invalid types, missing fields)
2. Semantic validation errors (duplicates, missing references)
3. Error formatting (Pydantic → ConfigurationError)
4. Error serialization (ConfigurationError → dict)
5. API error responses (full HTTP flow)
6. Error message quality (includes all required fields)

**Acceptance Criteria**:

- [ ] All test scenarios pass
- [ ] Coverage > 90% for validation code
- [ ] Test errors include expected message patterns
- [ ] Test errors include expected codes and context

### Validation Updates for Phase 0

**Goal**: Ensure existing validation works correctly with improved error reporting.

**Changes**:

- No changes to validation logic
- Only improve error reporting and logging
- Ensure all existing validations have clear error messages with context

**Test Strategy**:

1. Create invalid strategies covering all validation rules
2. Verify each produces clear, actionable error with all fields
3. Verify errors are logged with full context
4. Verify API returns structured errors (not empty)

### Acceptance Criteria for Phase 0

**ALL MUST PASS**:

- [ ] All validation errors logged before raising
- [ ] API returns 400 with detailed error body (never empty)
- [ ] Error messages include: what's wrong, where, why, how to fix
- [ ] Tests verify error quality (message, code, context, details, suggestion)
- [ ] No validation failures silent or unclear
- [ ] Manual test: Upload invalid strategy → see helpful error in UI/logs
- [ ] All existing validation tests still pass

### Estimated Duration

**2 days**

### Dependencies

None (foundational)

---

## Phase 1: Add Feature ID Support (REQUIRED, BREAKING CHANGE)

**Priority**: HIGH

**Goal**: Add MANDATORY `feature_id` field to indicator configuration. This is a BREAKING CHANGE.

**Architecture Decision**: feature_id is REQUIRED (no defaults) because multiple instances create ambiguity.

### Tasks

#### Task 1.1: Update IndicatorConfig Model

**Files**: `ktrdr/config/models.py`

**Changes**:

1. Add `feature_id` **REQUIRED** field (not optional!)
2. Add `get_feature_id()` method (returns feature_id)
3. Add field validator for feature_id format
   - Pattern: `^[a-zA-Z][a-zA-Z0-9_-]*$`
   - Must start with letter
   - Can contain: letters, numbers, underscore, dash
4. Add reserved word validation
   - Block: `["open", "high", "low", "close", "volume"]`
5. Remove backward compatibility for `name` field (breaking change)

**Example Config**:

```python
class IndicatorConfig(BaseModel):
    type: str = Field(..., description="Indicator type (rsi, ema, macd)")
    feature_id: str = Field(..., description="Unique identifier for fuzzy sets (REQUIRED)")
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator('feature_id')
    @classmethod
    def validate_feature_id(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', v):
            raise ValueError(
                f"feature_id '{v}' must start with letter and contain "
                "only letters, numbers, underscore, or dash"
            )
        if v.lower() in ['open', 'high', 'low', 'close', 'volume']:
            raise ValueError(f"feature_id '{v}' is a reserved word")
        return v
```

**Acceptance Criteria**:

- [ ] IndicatorConfig REQUIRES `feature_id` field
- [ ] `get_feature_id()` returns feature_id
- [ ] Invalid feature_id format raises clear error with examples
- [ ] Reserved words blocked with clear error listing allowed names
- [ ] Old configs (without feature_id) raise clear error pointing to migration tool
- [ ] Error message includes migration command

#### Task 1.2: Add Feature ID Uniqueness Validation

**Files**: `ktrdr/config/models.py` (StrategyConfigurationV2)

**Changes**:

1. Add `model_validator` to check feature_id uniqueness
2. Collect all feature_ids from indicators
3. Detect duplicates
4. Raise clear error with list of duplicates and affected indicators

**Acceptance Criteria**:

- [ ] Duplicate feature_ids rejected with clear error
- [ ] Error message lists all duplicates with context (which indicators)
- [ ] Validation happens at config load (early failure)
- [ ] Error includes suggestions for fixing (use params in feature_id)

#### Task 1.3: Update StrategyValidator for Feature IDs

**Files**: `ktrdr/config/strategy_validator.py`

**Changes**:

1. Update `_validate_indicator_definitions()`:
   - Check feature_id presence (should be caught by Pydantic but double-check)
   - Check feature_id format
   - Check feature_id uniqueness
2. Update `_validate_indicator_fuzzy_matching()`:
   - Use feature_ids (not column names!)
   - Simple set comparison: `feature_ids` vs `fuzzy_keys`
   - STRICT validation (all feature_ids must have fuzzy_sets)
   - Warn about orphaned fuzzy sets (might be intentional)
3. Remove complex column name guessing logic
4. Improve error messages:
   - Suggest adding fuzzy_sets for missing feature_ids
   - Include example fuzzy_sets structure
   - Include migration tool command for old configs

**Key Simplification**:

```python
# NEW: Simple, direct validation
feature_ids = {ind.feature_id for ind in indicators}
fuzzy_keys = set(fuzzy_sets.keys())

missing = feature_ids - fuzzy_keys  # STRICT: must have fuzzy_sets
orphans = fuzzy_keys - feature_ids  # WARNING: might be derived features
```

**Acceptance Criteria**:

- [ ] Validation checks feature_ids match fuzzy_set keys (direct comparison)
- [ ] Missing fuzzy sets reported as errors (STRICT) with feature_id
- [ ] Orphaned fuzzy sets reported as warnings (not errors)
- [ ] Error messages suggest exact fuzzy_sets to add with example structure
- [ ] Validation works without computing indicators (early failure)
- [ ] Old format strategies rejected with clear migration instructions

#### Task 1.4: Add Unit Tests for Feature IDs

**Files**: `tests/unit/config/test_feature_ids.py`

**Tests**:

1. `test_feature_id_required()` - Missing feature_id rejected
2. `test_feature_id_format_valid()` - Valid formats accepted
3. `test_feature_id_format_invalid()` - Invalid formats rejected
4. `test_feature_id_reserved_words()` - Reserved words blocked
5. `test_feature_id_uniqueness()` - Duplicates rejected
6. `test_feature_id_params_naming()` - Can use params (rsi_14, macd_12_26_9)
7. `test_feature_id_semantic_naming()` - Can use semantic names (rsi_fast)
8. `test_old_format_rejected()` - Old configs raise clear error with migration command

**Acceptance Criteria**:

- [ ] All tests pass
- [ ] Coverage > 95% for new code
- [ ] Test invalid inputs produce expected errors with correct error codes
- [ ] Error messages tested for clarity and actionability

### Validation Updates for Phase 1

**Goal**: Validate feature_id configuration correctness.

**New Validations**:

1. feature_id presence (REQUIRED by Pydantic)
2. feature_id format validation (field validator)
3. feature_id uniqueness validation (model validator)
4. feature_id reserved words validation (field validator)
5. feature_id to fuzzy_set matching (strategy validator - STRICT)

**Test Strategy**:

1. Valid configs: various feature_id formats (params, semantic, mixed)
2. Invalid configs: missing, duplicate, invalid format, reserved words
3. Fuzzy set matching: complete, missing (error), orphaned (warning)
4. Old format configs: rejected with migration instructions

### Acceptance Criteria for Phase 1

**CRITICAL - ALL MUST PASS**:

- [ ] IndicatorConfig REQUIRES feature_id field (no defaults)
- [ ] Old configs rejected with clear migration tool instructions
- [ ] Validation catches: missing, invalid format, duplicates, reserved words
- [ ] All validation errors clear and actionable with context
- [ ] feature_id can use params (rsi_14) or semantic names (rsi_fast)
- [ ] All unit tests pass (>95% coverage)
- [ ] BREAKING CHANGE documented clearly in error messages
- [ ] Migration tool command included in all "old format" errors

### Estimated Duration

**2 days**

### Dependencies

Phase 0 complete (error reporting works)

---

## Phase 1.5: Create Migration Tool

**Priority**: HIGH (parallel with Phase 1)

**Goal**: Provide automated migration from old format to new format.

### Tasks

#### Task 1.5.1: Design Migration Tool

**Files**: `scripts/migrate_to_feature_ids.py`

**Functionality**:

1. Read strategy YAML file
2. For each indicator:
   - If has `feature_id`: skip (already migrated)
   - If missing `feature_id`:
     - Instantiate indicator with params
     - Get column name: `indicator.get_column_name()`
     - Use column name as feature_id
3. Update fuzzy_sets if needed:
   - If fuzzy key == old indicator name: update to feature_id
   - If fuzzy key == column name: no change needed
4. Validate result (uniqueness, fuzzy matching)
5. Write migrated strategy (or dry-run to preview)

**CLI Interface**:

```bash
# Dry run (preview)
python scripts/migrate_to_feature_ids.py strategy.yaml --dry-run

# Migrate (overwrites)
python scripts/migrate_to_feature_ids.py strategy.yaml

# Migrate with backup
python scripts/migrate_to_feature_ids.py strategy.yaml --backup

# Migrate all
python scripts/migrate_to_feature_ids.py strategies/*.yaml
```

**Acceptance Criteria**:

- [ ] Tool reads strategy YAML correctly
- [ ] Detects old vs new format
- [ ] Generates feature_ids from column names (preserves fuzzy keys)
- [ ] Validates uniqueness (fails if collision)
- [ ] Updates fuzzy_sets keys if needed
- [ ] Dry-run mode shows changes without writing
- [ ] Backup mode creates .bak file
- [ ] Handles errors gracefully with clear messages
- [ ] Works with all indicator types (handles overrides correctly)

#### Task 1.5.2: Test Migration Tool

**Files**: `tests/unit/scripts/test_migrate_to_feature_ids.py`

**Tests**:

1. Migrate simple strategy (single indicator)
2. Migrate multi-indicator strategy (multiple RSIs)
3. Migrate with EMA (handles adjust parameter exclusion)
4. Migrate with MACD (handles multi-output)
5. Migrate with ZigZag (handles custom format)
6. Handle duplicate feature_ids (should fail with clear error)
7. Dry-run mode (no files written)
8. Backup mode (creates .bak)

**Acceptance Criteria**:

- [ ] All migration scenarios tested
- [ ] Migration preserves functionality (fuzzy sets still match)
- [ ] Collision detection works
- [ ] Edge cases handled (custom formats, multi-output)

#### Task 1.5.3: Create Migration Documentation

**Files**: `docs/migration/feature-ids-migration-guide.md`

**Content**:

1. Why migration needed (breaking change rationale)
2. What changed (feature_id now required)
3. How to migrate (step-by-step with examples)
4. Migration tool usage (all commands with examples)
5. Common issues and solutions
6. FAQ

**Acceptance Criteria**:

- [ ] Documentation clear and complete
- [ ] Examples show before/after
- [ ] Troubleshooting section covers common issues
- [ ] Links to architecture doc for details

### Estimated Duration

**1-2 days** (parallel with Phase 1)

### Dependencies

None (can start with Phase 1)

---

## Phase 2: Implement Feature ID Aliasing in IndicatorEngine

**Status**: ✅ **COMPLETE** (2025-10-15)

**Priority**: HIGH

**Goal**: Make IndicatorEngine produce DataFrames with both column names and feature_id aliases.

**Completion Summary**:

- ✅ Task 2.1: feature_id_map initialization (commit 6b4bc07)
- ✅ Task 2.2: feature_id aliasing in apply() (commit 6d26491)
- ✅ Task 2.3: Generic multi-output support for 12 indicators (commit bb5c8a0)
- ✅ Task 2.4: 22 unit tests, all passing
- ✅ Quality checks passing (lint, format, type check)

**See**: [PHASE-STATUS-AND-VALIDATION.md](./PHASE-STATUS-AND-VALIDATION.md) for detailed validation

### Tasks

#### Task 2.1: Update IndicatorEngine Initialization

**Files**: `ktrdr/indicators/indicator_engine.py`

**Changes**:

1. Add `feature_id_map: dict[str, str]` attribute
   - Maps: column_name → feature_id
   - Built during initialization
2. Update `__init__()` to accept indicator configs
3. Update `_initialize_from_configs()`:
   - Validate each config (IndicatorConfig model)
   - Build indicator instance
   - Get column name from indicator
   - Get feature_id from config
   - Store mapping: `feature_id_map[column_name] = feature_id`

**Key Insight**: Build mapping during init, use during apply.

**Acceptance Criteria**:

- [ ] IndicatorEngine tracks feature_id_map
- [ ] Map populated during initialization from configs
- [ ] Map keys are actual column names (from get_column_name())
- [ ] Map values are feature_ids from configs
- [ ] Handles indicators without configs (direct instances) gracefully

#### Task 2.2: Update IndicatorEngine.apply() for Aliasing

**Files**: `ktrdr/indicators/indicator_engine.py`

**Changes**:

1. Compute indicators (existing logic unchanged)
2. Add computed columns to result DataFrame
3. For each computed column:
   - Check if column_name in feature_id_map
   - If yes and feature_id != column_name: add alias column
   - Alias references same data (not copied!)

**Implementation Note**:

```python
# Both columns point to same data (not copied)
result[column_name] = indicator_result  # Technical name
if column_name in feature_id_map:
    feature_id = feature_id_map[column_name]
    if feature_id != column_name:
        result[feature_id] = indicator_result  # Alias
```

**Acceptance Criteria**:

- [ ] DataFrame contains original column names
- [ ] DataFrame contains feature_id aliases (if different from column name)
- [ ] Aliases reference same data (verified: not copied, same object)
- [ ] When feature_id == column_name: no duplicate column
- [ ] Multi-output indicators handled correctly (each output can have alias)

#### Task 2.3: Handle Multi-Output Indicators (MACD)

**Files**: `ktrdr/indicators/macd_indicator.py`, potentially others

**Current Behavior**: MACD produces 3 columns with specific naming pattern.

**Change Needed**: Designate primary output for feature_id mapping.

**Options**:

1. Add `get_primary_output_name()` method to multi-output indicators
2. Use first column as primary (convention)
3. Document primary output in indicator docstring

**Recommendation**: Use naming convention (column without "_signal_" or "_hist_" suffix is primary)

**Acceptance Criteria**:

- [ ] MACD primary output identified (main line)
- [ ] feature_id maps to primary output only
- [ ] Secondary outputs (signal, hist) still accessible via column names
- [ ] Tests verify primary output mapping
- [ ] Documentation explains multi-output feature_id behavior

#### Task 2.4: Add Integration Tests for Aliasing

**Files**: `tests/integration/indicators/test_feature_id_aliasing.py`

**Tests**:

1. Single indicator with explicit feature_id (different from column name)
2. Single indicator with feature_id == column name (no duplicate)
3. Multiple indicators with different feature_ids
4. Multi-output indicator (MACD) with feature_id
5. Indicator with custom get_column_name() (EMA, ZigZag)
6. Verify data identity (alias is reference, not copy)

**For each test**:

- Create config with feature_id
- Build IndicatorEngine
- Apply to sample data
- Verify DataFrame structure (expected columns present)
- Verify data identity (same object, not duplicated)
- Verify values match between column name and feature_id

**Acceptance Criteria**:

- [ ] All integration tests pass
- [ ] DataFrame structure verified (has both technical and user-facing columns)
- [ ] Data identity verified (aliases reference same data)
- [ ] Multi-output handling verified (primary output only)
- [ ] Custom naming (EMA, ZigZag) handled correctly

### Validation Updates for Phase 2

**Goal**: Ensure IndicatorEngine produces correct DataFrame structure.

**New Validations**:

1. feature_id_map correctness (keys=column names, values=feature_ids)
2. DataFrame structure (has expected columns)
3. Alias data identity (not duplicated)
4. No duplicate columns when feature_id == column name

**Test Strategy**:

1. Unit test feature_id_map building
2. Integration test DataFrame structure
3. Integration test data identity (memory address comparison)
4. Edge cases: feature_id == column name, multi-output, custom naming

### Acceptance Criteria for Phase 2

**ALL MUST PASS**:

- [ ] IndicatorEngine produces feature_id aliases
- [ ] DataFrame has both technical names and user-facing IDs
- [ ] Aliasing works for single-output indicators
- [ ] Aliasing works for multi-output indicators (primary only)
- [ ] No data duplication (aliases reference same data - verified)
- [ ] Custom get_column_name() indicators work (EMA, ZigZag)
- [ ] Integration tests pass (>90% coverage)
- [ ] No changes to indicator implementations (backward compatible)

### Estimated Duration

**2-3 days**

### Dependencies

Phase 1 complete (feature_id in config models)

---

## Phase 3: Update Training Pipeline to Use Feature IDs

**Status**: ⏳ **PENDING** - Ready to Start

**Priority**: CRITICAL

**Goal**: Simplify training pipeline by removing complex name mapping logic, using feature_ids directly.

**WARNING**: Highest risk phase. Extensive validation required.

---

## ⚠️ CRITICAL WARNING FOR PHASE 3 IMPLEMENTERS ⚠️

### 🚨 DO NOT ADD CODE - DELETE CODE! 🚨

**The training pipeline ALREADY HAS feature_id aliases from Phase 2!**

Lines 298-346 in `training_pipeline.py` are **LEGACY HACKS** written BEFORE Phase 2 was completed. They manually re-do work that Phase 2 already does automatically.

### What Phase 2 Already Gives You

When `IndicatorEngine.apply()` is called (Line 296), the resulting DataFrame ALREADY contains:

1. ✅ **Technical column names** (e.g., `rsi_7`, `macd_12_26_9`)
2. ✅ **feature_id aliases** (e.g., `rsi_fast`, `macd_standard`)
3. ✅ **Multi-output handling** (MACD primary output already mapped)
4. ✅ **Both columns point to same data** (no duplication)

**You can immediately use `result["rsi_fast"]` - it already exists!**

### The Legacy Hacks (Lines 298-346) - TO BE DELETED

```python
# Line 296: This ALREADY gives you feature_id aliases!
indicator_results = indicator_engine.apply(price_data)  # ✅ Has feature_ids!

# Lines 298-340: LEGACY HACKS - DELETE ALL OF THIS! ❌
for config in indicator_configs:
    feature_id = config.get("feature_id", config["name"])  # ❌ HACK: Manual extraction
    indicator_type = config["name"].upper()

    # ❌ HACK: Manual prefix matching (but aliases already exist!)
    for col in indicator_results.columns:
        if col.upper().startswith(indicator_type):

            # ❌ HACK: Manual SMA/EMA transformation (should be in fuzzy layer - Phase 3.5)
            if indicator_type in ["SMA", "EMA"]:
                mapped_results[feature_id] = price_data["close"] / indicator_results[col]
                break

            # ❌ HACK: Manual MACD handling (Phase 2.3 already does this!)
            elif indicator_type == "MACD":
                if "_MACD_" in col and "_signal_" not in col:
                    mapped_results[feature_id] = indicator_results[col]
                    break
```

### Why These Are Hacks

1. **Manual column matching** (Lines 298-318): Unnecessary! Phase 2 already created the feature_id aliases.
2. **Manual MACD handling** (Lines 325-335): Unnecessary! Phase 2.3 already maps feature_id → primary output.
3. **Manual SMA/EMA transformation** (Lines 318-324): Wrong location! Should be in fuzzy layer (Phase 3.5), not training.

### What Phase 3 Should Actually Do

**BEFORE (Current - 70+ lines of hacks)**:

```python
# Complex type inference, prefix matching, manual transformations
mapped_results = {}
for config in indicator_configs:
    feature_id = config.get("feature_id", config["name"])
    indicator_type = config["name"].upper()

    # 40+ lines of manual column matching...
    for col in indicator_results.columns:
        if col.upper().startswith(indicator_type):
            # Manual transformations, MACD handling, etc...
            mapped_results[feature_id] = ...
```

**AFTER (Phase 3 - 15 lines, clean and simple)**:

```python
# Just combine DataFrames - feature_ids already exist!
result = price_data.copy()
for col in indicator_results.columns:
    if col not in result.columns:
        result[col] = indicator_results[col]  # feature_ids already here!
```

### Anti-Patterns to AVOID in Phase 3

❌ **DO NOT** add more column name matching logic
❌ **DO NOT** add more prefix matching (startswith, contains, etc.)
❌ **DO NOT** add more indicator type inference
❌ **DO NOT** keep the SMA/EMA transformations here (move to Phase 3.5)
❌ **DO NOT** keep the MACD special handling (Phase 2.3 already does it)

✅ **DO** trust the feature_id aliases from Phase 2
✅ **DO** delete Lines 298-346
✅ **DO** simplify to ~15 lines
✅ **DO** verify outputs match old behavior (parallel validation test)

### Before You Start Phase 3

1. ✅ Read [PHASE-STATUS-AND-VALIDATION.md](./PHASE-STATUS-AND-VALIDATION.md) - explains what Phase 2 accomplished
2. ✅ Read Phase 2 tests (`test_feature_id_map.py`, `test_feature_id_aliasing.py`) - proves aliases work
3. ✅ Run `IndicatorEngine.apply()` with a strategy config - inspect the DataFrame columns
4. ✅ Understand: feature_ids ALREADY EXIST in the DataFrame - you just need to USE them!

### Summary

**Phase 3 is a DELETION phase, not an addition phase.**

- **Remove** 70+ lines of hacks (Lines 298-346)
- **Replace** with ~15 lines trusting Phase 2
- **Validate** outputs match (parallel validation test)
- **Trust** the feature_id aliases Phase 2 created

**If you find yourself adding complex logic, STOP. You're doing it wrong.**

---

**See**: [PHASE-STATUS-AND-VALIDATION.md](./PHASE-STATUS-AND-VALIDATION.md) Section "Current Training Pipeline (Still Has Hacks)" for detailed analysis of each hack.

### Architecture Decision Impact

**Removes**: ~130 lines of complex mapping logic

- Lines 298-340: Manual column name matching (~40 lines)
- Lines 318-324: SMA/EMA transformation (~10 lines, moves to Phase 3.5)
- Lines 325-335: MACD special handling (~15 lines)
- Multi-timeframe duplicate logic (~65 lines)

**Adds**: ~20 lines of simple indicator computation (trust Phase 2 aliases)

**Key Change**: SMA/EMA transformations move to fuzzy `input_transform` (Phase 3.5)

### Tasks

#### Task 3.1: Create Parallel Validation Test (CRITICAL)

**Files**: `tests/integration/training/test_training_equivalence.py`

**Purpose**: Validate new training path produces same results as old path.

**Test Strategy**:

1. Select 2-3 existing strategies (include SMA/EMA, MACD, multi-timeframe)
2. Migrate strategies to new format (with feature_ids)
3. Capture old training outputs:
   - Indicator results DataFrame
   - Fuzzy memberships DataFrame
   - Feature columns used by model
   - Model predictions (sample)
4. Run new training code
5. Capture new training outputs (same checkpoints)
6. Compare outputs:
   - DataFrame structures match
   - Column names match (via feature_ids)
   - Values match (numerical comparison with tolerance)
   - Model inputs match

**Acceptance Criteria**:

- [ ] Test framework runs old vs new training automatically
- [ ] Can capture and compare intermediate outputs at each stage
- [ ] Test identifies any differences with clear reporting
- [ ] Test passes (outputs equivalent within numerical tolerance)
- [ ] Test runs in CI (automated regression check)

#### Task 3.2: Simplify Single-Timeframe Indicator Calculation

**Files**: `ktrdr/training/training_pipeline.py` (lines 275-346)

**Current**: ~70 lines with type inference, mapping, transformations

**New**: ~15 lines using IndicatorEngine with feature_ids

**⚠️ CRITICAL REMINDER**: Lines 298-346 are LEGACY HACKS that duplicate work Phase 2 already does. Your job is to DELETE this code and trust the feature_id aliases that `IndicatorEngine.apply()` already provides. If you find yourself writing complex logic, you're doing it wrong!

**Changes**:

1. ❌ **DELETE** type inference logic (lines 277-291) - not needed anymore
2. ❌ **DELETE** name mapping logic (lines 298-318) - Phase 2 already created aliases
3. ❌ **DELETE** SMA/EMA transformation (lines 318-324) - will move to fuzzy layer in Phase 3.5
4. ❌ **DELETE** MACD special handling (lines 325-335) - Phase 2.3 already handles this
5. ✅ **TRUST** IndicatorEngine.apply() - it already gives you feature_id aliases!

**Simplified Logic**:

```python
def _calculate_indicators_single_timeframe(
    price_data: pd.DataFrame,
    indicator_configs: list[dict[str, Any]],
) -> pd.DataFrame:
    """Calculate indicators using feature_ids (simplified)."""

    # Build engine (validates configs, creates feature_id aliases)
    indicator_engine = IndicatorEngine(indicators=indicator_configs)

    # Apply indicators (result has feature_ids)
    indicator_results = indicator_engine.apply(price_data)

    # Combine with price data
    result = price_data.copy()
    for col in indicator_results.columns:
        if col not in result.columns:
            result[col] = indicator_results[col]

    # Safety: handle inf values
    result = result.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    return result
```

**Acceptance Criteria**:

- [ ] New logic produces same output as old logic (validated by Task 3.1)
- [ ] Code reduced from ~70 lines to ~15 lines
- [ ] No complex prefix matching or type inference
- [ ] feature_ids present in result DataFrame
- [ ] All existing training tests pass (may need updates for feature_ids)
- [ ] Parallel validation test passes (outputs match)

#### Task 3.3: Simplify Multi-Timeframe Indicator Calculation

**Files**: `ktrdr/training/training_pipeline.py` (lines 348-425)

**Current**: ~75 lines with duplicate logic per timeframe

**New**: ~20 lines, shared logic

**Changes**: Similar to Task 3.2 but applied per timeframe

**Acceptance Criteria**:

- [ ] New logic produces same output as old logic (validated by Task 3.1)
- [ ] Code reduced from ~75 lines to ~20 lines
- [ ] Logic shared with single-timeframe where possible
- [ ] All multi-timeframe tests pass
- [ ] Parallel validation test passes

#### Task 3.4: Update Training Tests

**Files**: `tests/unit/training/test_training_pipeline.py`

**Updates**:

1. Update test fixtures to use feature_ids
2. Update assertions to check for feature_id columns
3. Update expected outputs (column names are feature_ids)
4. Add tests for feature_id presence in outputs

**Acceptance Criteria**:

- [ ] All training tests updated for feature_ids
- [ ] All tests pass
- [ ] Coverage maintained >85%
- [ ] Tests verify feature_ids in outputs at each stage

### Validation Updates for Phase 3

**Goal**: Ensure training produces correct outputs with feature_ids.

**CRITICAL Validations**:

1. **Output Equivalence**: New path produces same results as old path (Task 3.1)
2. **Feature Presence**: feature_ids present in indicator results
3. **Fuzzy Compatibility**: Fuzzy engine can find feature_ids
4. **Model Training**: Full training pipeline completes successfully
5. **Model Features**: Trained model uses correct feature_ids

**Test Strategy**:

1. Parallel validation (old vs new) - AUTOMATED, REQUIRED
2. Integration tests (full training flow) - AUTOMATED
3. Manual validation (train model, inspect features) - MANUAL
4. Regression tests (compare with previous model outputs) - AUTOMATED

### Acceptance Criteria for Phase 3

**CRITICAL - DO NOT PROCEED WITHOUT THESE**:

- [ ] **Parallel validation test passes** (old output == new output)
- [ ] All training unit tests pass
- [ ] All training integration tests pass
- [ ] Manual training run completes successfully
- [ ] Inspect trained model: features match expected feature_ids
- [ ] No breaking changes to training behavior (outputs equivalent)
- [ ] Code complexity reduced (~130 lines removed)
- [ ] Training logs show feature_ids being used
- [ ] No errors during full training pipeline
- [ ] Performance acceptable (within 10% of baseline)

### Estimated Duration

**3-4 days** (includes extensive testing)

### Dependencies

Phase 2 complete (IndicatorEngine produces aliases)

---

## Phase 3.5: Implement Input Transform in Fuzzy System

**Priority**: HIGH (parallel with or after Phase 3)

**Goal**: Move SMA/EMA transformation from training pipeline to fuzzy layer (proper architecture).

**Architecture Decision**: Add `input_transform` to fuzzy configuration - see [input-transform-design.md](./input-transform-design.md)

### Why Fuzzy Layer?

Transformation is about **how to fuzzify** a moving average, not about:

- Indicator computation (indicator computes MA correctly)
- Training logic (needs to work in backtesting/live trading too)

**Location**: Fuzzy configuration - where fuzzification is specified.

### Tasks

#### Task 3.5.1: Add Input Transform Config Models

**Files**: `ktrdr/fuzzy/config.py`

**Changes**:

1. Add `PriceRatioTransformConfig` model
2. Add `IdentityTransformConfig` model (default)
3. Create `InputTransformConfig` union type
4. Add `input_transform` optional field to `FuzzySetConfigModel`

**Models**:

```python
class PriceRatioTransformConfig(BaseModel):
    """Transform indicator to price ratio."""
    type: Literal["price_ratio"] = "price_ratio"
    reference: str = Field(..., description="Price column (open/high/low/close)")

class IdentityTransformConfig(BaseModel):
    """No transformation (default)."""
    type: Literal["identity"] = "identity"

InputTransformConfig = Annotated[
    Union[PriceRatioTransformConfig, IdentityTransformConfig],
    Field(discriminator="type")
]
```

**Acceptance Criteria**:

- [ ] Transform config models validate correctly
- [ ] Reference field validates (must be valid price column)
- [ ] Union discriminator works (can parse from YAML)
- [ ] Optional field (defaults to identity if omitted)

#### Task 3.5.2: Update Fuzzy Engine with Transform Logic

**Files**: `ktrdr/fuzzy/engine.py`

**Changes**:

1. Update `fuzzify()` signature: add `context_data` parameter
2. Add `_apply_input_transform()` method
3. Apply transform before fuzzification if configured

**Implementation**:

```python
def fuzzify(
    self,
    indicator: str,
    values: Union[float, pd.Series, np.ndarray],
    context_data: Optional[pd.DataFrame] = None  # NEW
) -> Union[dict, pd.DataFrame]:
    """Fuzzify with optional input transform."""

    # Get config
    fuzzy_set_config = self._config.root[indicator]

    # Apply input transform if configured
    if hasattr(fuzzy_set_config, 'input_transform') and fuzzy_set_config.input_transform:
        values = self._apply_input_transform(
            fuzzy_set_config.input_transform,
            values,
            context_data
        )

    # Fuzzify (existing logic)
    return self._fuzzify_values(indicator, values)

def _apply_input_transform(
    self,
    transform_config: InputTransformConfig,
    values: Union[float, pd.Series, np.ndarray],
    context_data: Optional[pd.DataFrame]
) -> Union[float, pd.Series, np.ndarray]:
    """Apply configured transformation."""

    if transform_config.type == "identity":
        return values

    elif transform_config.type == "price_ratio":
        if context_data is None:
            raise ProcessingError("price_ratio requires context_data")

        reference = transform_config.reference
        if reference not in context_data.columns:
            raise ProcessingError(f"Reference '{reference}' not in context_data")

        # Compute ratio: reference / indicator_value
        reference_values = context_data[reference]
        return reference_values / values
```

**Acceptance Criteria**:

- [ ] Transform applied before fuzzification
- [ ] Price ratio computed correctly (reference / indicator)
- [ ] Identity transform returns values unchanged
- [ ] Error if price_ratio missing context_data
- [ ] Error if reference column not found
- [ ] Works with scalar, Series, and array inputs

#### Task 3.5.3: Update Training Pipeline to Pass Context Data

**Files**: `ktrdr/training/training_pipeline.py`

**Changes**:

1. Remove SMA/EMA transformation logic (delete ~30 lines)
2. Pass combined DataFrame (with price columns) to fuzzy engine

**Before**:

```python
# OLD: Training does transformation
if indicator_type in ["SMA", "EMA"]:
    mapped_results[name] = price_data["close"] / indicator_results[col]
```

**After**:

```python
# NEW: Pass context data, fuzzy engine handles it
fuzzy_engine.fuzzify(
    feature_id,
    indicator_values,
    context_data=combined_data  # Includes price columns
)
```

**Acceptance Criteria**:

- [ ] SMA/EMA transformation logic removed from training
- [ ] Context data (price + indicators) passed to fuzzy engine
- [ ] Parallel validation test passes (outputs match old behavior)
- [ ] Code simpler (~30 lines removed)

#### Task 3.5.4: Update Migration Tool for Input Transforms

**Files**: `scripts/migrate_to_feature_ids.py`

**Changes**:

1. Detect SMA/EMA indicators
2. Add `input_transform` to their fuzzy_sets

**Logic**:

```python
for ind in strategy['indicators']:
    if ind['type'] in ['sma', 'ema']:
        feature_id = ind['feature_id']

        # Add input_transform to fuzzy_sets
        if feature_id in strategy['fuzzy_sets']:
            strategy['fuzzy_sets'][feature_id]['input_transform'] = {
                'type': 'price_ratio',
                'reference': 'close'
            }
```

**Acceptance Criteria**:

- [ ] Migration tool detects SMA/EMA
- [ ] Adds input_transform to their fuzzy_sets
- [ ] Preserves existing fuzzy set definitions
- [ ] Warns user about added transforms
- [ ] Documents change in migration output

#### Task 3.5.5: Add Tests for Input Transforms

**Files**:

- `tests/unit/fuzzy/test_input_transforms.py` (new)
- `tests/integration/fuzzy/test_transform_integration.py` (new)

**Unit Tests**:

1. Test PriceRatioTransform config validation
2. Test IdentityTransform config validation
3. Test price ratio computation (scalar, Series, array)
4. Test missing context_data error
5. Test invalid reference column error
6. Test identity transform (no change)

**Integration Tests**:

1. Test SMA with price_ratio in full pipeline
2. Test EMA with price_ratio in full pipeline
3. Test RSI without transform (identity)
4. Test mixed indicators (some with, some without)
5. Test migration tool adds transforms correctly

**Acceptance Criteria**:

- [ ] All unit tests pass (>95% coverage)
- [ ] All integration tests pass
- [ ] Tests verify numerical correctness (matches old transformation)
- [ ] Tests verify error handling

### Validation Updates for Phase 3.5

**Goal**: Ensure input transforms work correctly.

**Validations**:

1. Transform config validates correctly
2. Transform computation numerically correct
3. Fuzzy engine applies transforms before fuzzification
4. Training pipeline simpler (transformation logic removed)
5. Migration tool adds transforms correctly

**Test Strategy**:

1. Unit tests (transform logic)
2. Integration tests (full fuzzy pipeline)
3. Parallel validation (old vs new outputs match)
4. Migration tests (SMA/EMA detected and transformed)

### Acceptance Criteria for Phase 3.5

**ALL MUST PASS**:

- [ ] Input transform config models work
- [ ] Fuzzy engine applies transforms correctly
- [ ] Price ratio computation matches old training logic
- [ ] Training pipeline simplified (~30 lines removed)
- [ ] Migration tool adds transforms for SMA/EMA
- [ ] All unit tests pass (>95% coverage)
- [ ] All integration tests pass
- [ ] Parallel validation passes (outputs equivalent)
- [ ] No regression in training behavior
- [ ] Documentation updated with examples

### Estimated Duration

**3.5 days**

**Breakdown**:

- Task 3.5.1 (Config models): 0.5 days
- Task 3.5.2 (Fuzzy engine): 1 day
- Task 3.5.3 (Training pipeline): 0.5 days
- Task 3.5.4 (Migration tool): 0.5 days
- Task 3.5.5 (Testing): 1 day

### Dependencies

Phase 3 complete (training pipeline simplified)

---

## Phase 4: Update Fuzzy Engine for Feature IDs

**Priority**: MEDIUM

**Goal**: Update fuzzy engine to use feature_ids, improve error messages.

### Tasks

#### Task 4.1: Update FuzzyEngine Validation

**Files**: `ktrdr/fuzzy/fuzzy_engine.py`

**Changes**:

1. Update `generate_memberships()` to expect feature_ids
2. Improve error when feature_id not found:
   - List available feature_ids
   - Suggest close matches (typo detection with Levenshtein distance)
   - Include context (which fuzzy set)
3. Add validation that all referenced feature_ids exist

**Error Example**:

```python
if feature_id not in data.columns:
    available = [col for col in data.columns if not col.startswith("_")]
    suggestion = find_close_match(feature_id, available)  # Typo detection

    raise FuzzyError(
        f"Feature ID '{feature_id}' not found in indicator data",
        error_code="FUZZY-FeatureNotFound",
        context={"fuzzy_set": fuzzy_set_name},
        details={
            "feature_id": feature_id,
            "available_features": available,
            "close_match": suggestion  # e.g., "Did you mean 'rsi_14'?"
        },
        suggestion=(
            f"Check feature_id in fuzzy_sets configuration.\n"
            f"Available: {', '.join(available[:10])}\n"
            f"Did you mean '{suggestion}'?" if suggestion else ""
        )
    )
```

**Acceptance Criteria**:

- [ ] Error messages include available feature_ids
- [ ] Error messages suggest close matches (typo detection)
- [ ] Error includes structured details for API responses
- [ ] Error includes context (which fuzzy set)

#### Task 4.2: Add Fuzzy Engine Tests

**Files**: `tests/unit/fuzzy/test_fuzzy_engine.py`

**New Tests**:

1. `test_fuzzy_with_feature_ids()` - Normal operation
2. `test_fuzzy_missing_feature_id()` - Error with suggestions
3. `test_fuzzy_typo_detection()` - Suggests close match (rsi_1 → rsi_14)
4. `test_fuzzy_error_structure()` - Verify error has all required fields

**Acceptance Criteria**:

- [ ] All tests pass
- [ ] Coverage >90% for error paths
- [ ] Error messages validated (include suggestions)

### Validation Updates for Phase 4

**Goal**: Ensure fuzzy engine works correctly with feature_ids.

**Validations**:

1. feature_id lookup works
2. Error messages helpful with suggestions
3. All fuzzy sets reference valid feature_ids

**Test Strategy**:

1. Unit tests (error cases, typo detection)
2. Integration tests (full fuzzy processing)
3. Manual test (trigger error, verify message quality)

### Acceptance Criteria for Phase 4

- [ ] FuzzyEngine uses feature_ids correctly
- [ ] Error messages helpful and actionable with suggestions
- [ ] All fuzzy tests pass
- [ ] No breaking changes to fuzzy logic
- [ ] Typo detection works (suggests close matches)

### Estimated Duration

**1 day**

### Dependencies

Phase 3 complete (training uses feature_ids)

---

## Phase 5: Documentation and Examples

**Priority**: MEDIUM

**Goal**: Document new feature_id system and provide comprehensive migration guidance.

### Tasks

#### Task 5.1: Update Strategy Documentation

**Files**: `docs/strategies/indicator-configuration.md`

**Updates**:

1. Document indicator configuration with feature_ids
2. Show before/after migration examples
3. Explain when to use params vs semantic naming
4. Explain feature_id requirements (mandatory, unique)
5. Document input transforms (price_ratio for SMA/EMA fuzzification)

#### Task 5.3: Update Example Strategies

**Files**: `strategies/*.yaml`

**Updates**:

1. Migrate all example strategies using migration tool
2. Add comments explaining feature_id usage
3. Show variety of naming patterns (params, semantic, mixed)
4. Document input transforms in fuzzy sets (SMA/EMA examples)

#### Task 5.4: Create Video Tutorial (Optional)

**Content**:

1. Screen recording of migration process
2. Explanation of feature_id concept
3. Common pitfalls and solutions
4. Q&A section

### Acceptance Criteria for Phase 5

- [ ] Documentation complete and clear
- [ ] Migration guide comprehensive with examples
- [ ] All example strategies migrated and working
- [ ] Comments in examples explain choices
- [ ] User feedback: documentation clear and helpful (after release)

### Estimated Duration

**1-2 days**

### Dependencies

Phases 1-4 complete

---

## Phase 6: Comprehensive System Testing

**Priority**: HIGH

**Goal**: Validate entire system works end-to-end with feature_ids.

### Tasks

#### Task 6.1: End-to-End Training Tests

**Tests** (all automated):

1. Train model with explicit feature_ids (new format)
2. Train model with params naming (rsi_14, macd_12_26_9)
3. Train model with semantic naming (rsi_fast, macd_trend)
4. Train model with mixed naming
5. Train model with input transforms (SMA/EMA with price_ratio)
6. Train multi-output indicators (MACD)
7. Train multi-timeframe model with feature_ids
8. Train multi-symbol model with feature_ids

**For each test**:

- Training completes successfully without errors
- No warnings (except expected)
- Model produces predictions
- Feature names in model match expected feature_ids
- Performance metrics reasonable

**Acceptance Criteria**:

- [ ] All E2E tests pass
- [ ] Training completes without errors for all formats
- [ ] Model features match configuration exactly
- [ ] Multi-output indicators work (MACD)
- [ ] Multi-timeframe works
- [ ] Multi-symbol works
- [ ] Input transforms work (SMA/EMA with price_ratio)

#### Task 6.2: Regression Testing

**Purpose**: Ensure new system produces equivalent results to old system.

**Method**:

1. Select 3-5 existing strategies (variety: simple, complex, multi-timeframe)
2. Train models with OLD code (pre-feature_id, from git)
3. Migrate strategies
4. Train models with NEW code (post-feature_id)
5. Compare outputs:
   - Feature columns (should match via feature_ids)
   - Fuzzy memberships (should match)
   - Model predictions (should match within tolerance)
   - Model performance metrics (should match within tolerance)

**Acceptance Criteria**:

- [ ] New models perform equivalent to old models (within 1% metrics)
- [ ] Feature differences explainable (feature_id naming)
- [ ] No unexplained performance degradation
- [ ] No data corruption or value changes

#### Task 6.3: Performance Testing

**Purpose**: Ensure feature_id aliasing doesn't degrade performance.

**Tests**:

1. Benchmark indicator computation (with aliasing)
2. Benchmark training pipeline (new vs old)
3. Benchmark memory usage (aliases shouldn't duplicate data)
4. Benchmark validation time (should be faster - early validation)

**Acceptance Criteria**:

- [ ] Performance within 5% of baseline (training time)
- [ ] Memory usage not increased (aliases are references)
- [ ] No performance regressions in production-critical paths
- [ ] Validation faster (early failure without computation)

#### Task 6.4: Manual Validation Checklist

**Purpose**: Human verification of system behavior.

**Checklist**:

- [ ] Upload strategy with feature_ids → validates correctly
- [ ] Upload strategy without feature_ids → clear error with migration command
- [ ] Upload invalid strategy → error message clear and helpful
- [ ] Start training with feature_ids → completes successfully
- [ ] Inspect training logs → feature_ids visible at each stage
- [ ] Inspect trained model → features match config exactly
- [ ] Test model predictions → work correctly
- [ ] Upload strategy with duplicate feature_ids → clear error
- [ ] Upload strategy with missing fuzzy sets → clear error with suggestion
- [ ] Upload strategy with orphaned fuzzy sets → warning shown
- [ ] Run migration tool → migrates correctly, preserves functionality

### Acceptance Criteria for Phase 6

**ALL MUST PASS**:

- [ ] All E2E tests pass (8 scenarios)
- [ ] Regression tests show equivalence (within tolerance)
- [ ] Performance tests show no degradation (within 5%)
- [ ] Manual validation checklist 100% complete
- [ ] No critical bugs found (P0/P1)
- [ ] All P2 bugs documented and triaged
- [ ] System ready for production deployment

### Estimated Duration

**2-3 days**

### Dependencies

All previous phases complete

---

## Phase 7: Eliminate Sample Data Computation in IndicatorEngine Init

**Status**: 🔄 **IN PROGRESS** - Redesigning approach

**Priority**: LOW (Performance Optimization)

**Goal**: Eliminate **ALL** indicator computation on sample data during IndicatorEngine initialization.

### Background

Currently, IndicatorEngine computes each indicator **twice**:

1. **First computation (initialization)**: On sample data (100 rows) to determine:
   - Whether indicator is multi-output (returns DataFrame vs Series)
   - Primary output column name for multi-output indicators
   - Technical column name format

2. **Second computation (apply)**: On real training data (e.g., 518 rows) to get actual indicator values

For a strategy with 36 indicators, this means **72 indicator computations** (36 during init + 36 during apply).

**Performance Impact**:

- Initialization overhead proportional to number of indicators
- Noticeable delay with many indicators or complex computations
- Unnecessary computation on dummy data just for type detection

### Root Cause Analysis

The unnecessary computation on sample data occurs in:

**File**: `ktrdr/indicators/indicator_engine.py`

**Methods that MUST be eliminated**:

1. `_is_multi_output_indicator()` (lines ~218-249):
   - Creates 100-row sample DataFrame
   - Calls `indicator.compute(sample_data)`
   - Checks if result is DataFrame
   - **Completely unnecessary** - indicators should declare this!

2. `_get_primary_output_column()` (lines ~251-291):
   - Creates 100-row sample DataFrame
   - Calls `indicator.compute(sample_data)`
   - Extracts first column name
   - **Completely unnecessary** - can derive from indicator.get_column_name()!

3. `_get_technical_column_name()` (lines ~293-318):
   - Creates temp indicator instance
   - Calls `get_column_name()`
   - **This one is OK** - doesn't compute, just builds string

**Why This Happens**:

- Need to know if indicator is multi-output to handle correctly
- Need to know column names to build feature_id_map
- Current approach: "let's just compute it and see what we get"
- **Better approach**: Indicators should be self-describing!

### Proposed Solution

**Approach**: Self-describing indicators with declarative metadata

**Key Insight**: Indicators know their own structure! They should declare:

1. Whether they produce single or multiple outputs (class property)
2. How to construct their column names (method that doesn't compute)

**NO CACHE NEEDED** - This is just proper OOP design, not caching!

### Tasks

#### Task 7.1: Add Self-Describing Methods to BaseIndicator

**File**: `ktrdr/indicators/base_indicator.py`

**Changes**:

1. Add `is_multi_output()` class method (returns False by default):

```python
@classmethod
def is_multi_output(cls) -> bool:
    """
    Declare whether this indicator produces multiple output columns.

    Returns:
        bool: True if indicator returns DataFrame (multiple columns),
              False if indicator returns Series (single column).

    Note:
        Multi-output indicators MUST override this to return True.
        This method should NOT compute anything - it's a declaration!
    """
    return False
```

2. Add `get_primary_output_suffix()` class method (returns None by default):

```python
@classmethod
def get_primary_output_suffix(cls) -> Optional[str]:
    """
    Get suffix for primary output column of multi-output indicators.

    For multi-output indicators, defines which column is "primary".
    Returns None if primary output has no suffix (just base name + params).

    Returns:
        Optional[str]: Suffix for primary column, or None

    Examples:
        - MACD: returns None (primary is "MACD_12_26", no suffix)
        - BollingerBands: returns "upper" (primary is "upper_20_2.0")
        - Stochastic: returns "k" (primary is "k_14_3")
    """
    return None
```

**Why This Works**:

- No computation needed - just returns a constant
- Fast - direct method call, no sample data creation
- Clear - indicator declares its own behavior
- Maintainable - each indicator documents its structure

**Acceptance Criteria**:

- [ ] Methods added to BaseIndicator
- [ ] Clear docstrings explain purpose
- [ ] Default implementations provided (False, None)
- [ ] No computation in these methods (just return constants)

#### Task 7.2: Update Multi-Output Indicators

**Files**:
- `ktrdr/indicators/macd_indicator.py`
- `ktrdr/indicators/bollinger_bands_indicator.py`
- `ktrdr/indicators/stochastic_indicator.py`
- `ktrdr/indicators/adx_indicator.py`
- `ktrdr/indicators/ichimoku_indicator.py`
- Any other multi-output indicators

**Changes**: Override the class methods for each multi-output indicator

**Example 1: MACD**:

```python
class MACDIndicator(BaseIndicator):
    """MACD indicator (multi-output: MACD line, signal, histogram)."""

    @classmethod
    def is_multi_output(cls) -> bool:
        """MACD produces multiple outputs."""
        return True

    @classmethod
    def get_primary_output_suffix(cls) -> None:
        """Primary output is MACD line with no suffix (e.g., 'MACD_12_26')."""
        return None
```

**Example 2: BollingerBands**:

```python
class BollingerBandsIndicator(BaseIndicator):
    """Bollinger Bands (multi-output: upper, middle, lower)."""

    @classmethod
    def is_multi_output(cls) -> bool:
        """Bollinger Bands produces multiple outputs."""
        return True

    @classmethod
    def get_primary_output_suffix(cls) -> str:
        """Primary output is upper band."""
        return "upper"
```

**Example 3: Stochastic**:

```python
class StochasticIndicator(BaseIndicator):
    """Stochastic oscillator (multi-output: %K, %D)."""

    @classmethod
    def is_multi_output(cls) -> bool:
        """Stochastic produces multiple outputs."""
        return True

    @classmethod
    def get_primary_output_suffix(cls) -> str:
        """Primary output is %K line."""
        return "k"
```

**Acceptance Criteria**:

- [ ] All multi-output indicators identified
- [ ] Each overrides `is_multi_output()` to return True
- [ ] Each overrides `get_primary_output_suffix()` appropriately
- [ ] Docstrings explain which column is primary and why
- [ ] No computation in these methods

#### Task 7.3: Simplify `_build_feature_id_map()` in IndicatorEngine

**File**: `ktrdr/indicators/indicator_engine.py`

**Current Code** (lines ~166-215): Creates sample data, computes indicators

**New Code** (NO sample data computation!):

```python
def _build_feature_id_map(
    self, configs: list, indicators: list[BaseIndicator]
) -> None:
    """
    Build feature_id_map mapping technical column names to feature_ids.

    Uses indicator metadata (is_multi_output, get_column_name) to determine
    column names WITHOUT computing indicators on sample data.

    Args:
        configs: List of IndicatorConfig objects
        indicators: List of indicator instances (parallel to configs)
    """
    from ..config.models import IndicatorConfig

    for config, indicator in zip(configs, indicators):
        if not isinstance(config, IndicatorConfig):
            continue

        feature_id = config.feature_id
        indicator_class = type(indicator)

        # Use class method - NO COMPUTATION!
        if indicator_class.is_multi_output():
            # Multi-output: get primary column name using suffix
            suffix = indicator_class.get_primary_output_suffix()
            if suffix:
                # Column like "upper_20_2.0" for BollingerBands
                column_name = indicator.get_column_name(suffix=suffix)
            else:
                # Column like "MACD_12_26" for MACD (no suffix)
                column_name = indicator.get_column_name()

            self.feature_id_map[column_name] = feature_id
            logger.debug(
                f"Mapped multi-output indicator primary column '{column_name}' "
                f"to feature_id '{feature_id}'"
            )
        else:
            # Single-output: column name is just the base name + params
            column_name = indicator.get_column_name()
            self.feature_id_map[column_name] = feature_id
            logger.debug(
                f"Mapped column '{column_name}' to feature_id '{feature_id}'"
            )
```

**What Changed**:

- ❌ **REMOVED**: `_is_multi_output_indicator()` call (computed on sample data)
- ❌ **REMOVED**: `_get_primary_output_column()` call (computed on sample data)
- ✅ **ADDED**: `indicator_class.is_multi_output()` (instant, no computation)
- ✅ **ADDED**: `indicator_class.get_primary_output_suffix()` (instant, no computation)
- ✅ **KEPT**: `indicator.get_column_name()` (already fast, just builds string)

**Acceptance Criteria**:

- [ ] No sample data creation in `_build_feature_id_map()`
- [ ] Uses `is_multi_output()` class method
- [ ] Uses `get_primary_output_suffix()` class method
- [ ] Uses `get_column_name()` for actual column construction
- [ ] Produces same feature_id_map as before (correctness)
- [ ] Much faster (no indicator computation)

#### Task 7.4: Delete Obsolete Methods

**File**: `ktrdr/indicators/indicator_engine.py`

**Methods to DELETE** (they compute on sample data - no longer needed!):

1. `_is_multi_output_indicator()` (lines ~218-249)
   - Creates 100-row DataFrame
   - Calls `indicator.compute()`
   - **Delete entire method** - replaced by `indicator_class.is_multi_output()`

2. `_get_primary_output_column()` (lines ~251-291)
   - Creates 100-row DataFrame
   - Calls `indicator.compute()`
   - **Delete entire method** - replaced by `indicator.get_column_name(suffix=...)`

**Method to KEEP**:

- `_get_technical_column_name()` - This is OK, doesn't compute, just builds string

**Acceptance Criteria**:

- [ ] `_is_multi_output_indicator()` deleted
- [ ] `_get_primary_output_column()` deleted
- [ ] No other code references these deleted methods
- [ ] All tests still pass

#### Task 7.5: Add Tests for Self-Describing Indicators

**Files**:

- `tests/unit/indicators/test_indicator_metadata.py` (new)
- `tests/unit/indicators/test_feature_id_map.py` (update to verify no computation)

**New Tests**:

1. **Test class methods don't compute**:

```python
def test_is_multi_output_does_not_compute():
    """Verify is_multi_output() doesn't call compute()."""
    # Mock compute to detect if called
    with patch.object(RSIIndicator, 'compute') as mock_compute:
        result = RSIIndicator.is_multi_output()
        assert result is False
        mock_compute.assert_not_called()  # Should NOT compute!

def test_multi_output_indicators_declare_correctly():
    """Test multi-output indicators return True."""
    assert MACDIndicator.is_multi_output() is True
    assert BollingerBandsIndicator.is_multi_output() is True
    assert StochasticIndicator.is_multi_output() is True

def test_single_output_indicators_declare_correctly():
    """Test single-output indicators return False."""
    assert RSIIndicator.is_multi_output() is False
    assert SMAIndicator.is_multi_output() is False
    assert EMAIndicator.is_multi_output() is False
```

2. **Test primary output suffixes**:

```python
def test_primary_output_suffixes():
    """Test multi-output indicators declare correct suffixes."""
    # MACD: no suffix (primary is "MACD_12_26")
    assert MACDIndicator.get_primary_output_suffix() is None

    # BollingerBands: "upper" suffix
    assert BollingerBandsIndicator.get_primary_output_suffix() == "upper"

    # Stochastic: "k" suffix
    assert StochasticIndicator.get_primary_output_suffix() == "k"
```

3. **Test initialization performance**:

```python
def test_initialization_faster_without_sample_computation():
    """Test IndicatorEngine init doesn't compute on sample data."""
    configs = [
        {'name': 'rsi', 'feature_id': 'rsi_14', 'period': 14},
        {'name': 'macd', 'feature_id': 'macd_std'},
    ]

    # Mock compute to detect if called during init
    with patch.object(RSIIndicator, 'compute') as mock_rsi, \
         patch.object(MACDIndicator, 'compute') as mock_macd:

        engine = IndicatorEngine(indicators=configs)

        # Should NOT be called during init!
        mock_rsi.assert_not_called()
        mock_macd.assert_not_called()

    # Verify feature_id_map was still built correctly
    assert 'rsi_14' in engine.feature_id_map
    assert any('MACD' in col for col in engine.feature_id_map)
```

4. **Test correctness**:

```python
def test_feature_id_map_correctness():
    """Test feature_id_map is correct without sample computation."""
    configs = [
        {'name': 'rsi', 'feature_id': 'my_rsi', 'period': 14},
        {'name': 'macd', 'feature_id': 'my_macd'},
        {'name': 'bbands', 'feature_id': 'my_bbands', 'period': 20},
    ]

    engine = IndicatorEngine(indicators=configs)

    # RSI: single-output, column = feature_id
    assert 'rsi_14' in engine.feature_id_map
    assert engine.feature_id_map['rsi_14'] == 'my_rsi'

    # MACD: multi-output, primary column maps to feature_id
    macd_col = [c for c in engine.feature_id_map if 'MACD' in c][0]
    assert engine.feature_id_map[macd_col] == 'my_macd'

    # BollingerBands: multi-output, primary = upper band
    assert 'upper_20_2.0' in engine.feature_id_map
    assert engine.feature_id_map['upper_20_2.0'] == 'my_bbands'
```

**Acceptance Criteria**:

- [ ] Tests verify indicators are self-describing (class methods work)
- [ ] Tests verify NO computation during init (mock compute, assert not called)
- [ ] Tests verify feature_id_map correctness
- [ ] Tests verify multi-output and single-output indicators
- [ ] All existing tests still pass

### Validation for Phase 7

**Goal**: Ensure NO computation on sample data during IndicatorEngine initialization

**Critical Validations**:

1. **No Computation**: Mock `indicator.compute()` and verify NOT called during init
2. **Correctness**: feature_id_map matches previous behavior
3. **Performance**: Init faster (no 100-row DataFrame creation)
4. **Compatibility**: All existing tests pass (no behavior changes)

**Test Strategy**:

1. Mock tests: Verify `compute()` never called during init
2. Correctness tests: Verify feature_id_map correct for all indicator types
3. Performance tests: Measure init time improvement
4. Regression tests: All existing tests must pass

### Overall Acceptance Criteria for Phase 7

**ALL MUST PASS**:

- [ ] BaseIndicator has `is_multi_output()` and `get_primary_output_suffix()` class methods
- [ ] All multi-output indicators override these methods correctly
- [ ] `_build_feature_id_map()` uses class methods, NOT sample computation
- [ ] `_is_multi_output_indicator()` method DELETED (computed on sample data)
- [ ] `_get_primary_output_column()` method DELETED (computed on sample data)
- [ ] Tests verify NO `compute()` calls during init (mocking)
- [ ] Tests verify feature_id_map correctness
- [ ] All existing tests pass (no regressions)
- [ ] Init significantly faster (no sample data computation)
- [ ] Documentation updated

### Performance Impact

**Before Optimization**:

- IndicatorEngine.__init__() creates 100-row DataFrames for each unique indicator class
- Calls `indicator.compute(sample_data)` to detect multi-output and get column names
- For 36 indicators with 12 unique classes: **12 unnecessary computations**

**After Optimization**:

- IndicatorEngine.__init__() calls `is_multi_output()` (instant, no computation)
- Calls `get_column_name()` with optional suffix (just string building)
- For 36 indicators with 12 unique classes: **0 computations**

**Expected Speedup**:

- Init time reduced by time taken to compute 12 indicators on 100-row data
- Particularly beneficial for expensive indicators (MACD, Bollinger Bands, etc.)
- Also faster for strategies with repeated indicator types

**Measurement**:

Use mocking to verify `compute()` is never called during init

### Estimated Duration

**1-2 days**

**Breakdown**:

- Task 7.1 (Add class methods to BaseIndicator): 1 hour
- Task 7.2 (Update multi-output indicators): 2 hours
- Task 7.3 (Simplify `_build_feature_id_map()`): 2 hours
- Task 7.4 (Delete obsolete methods): 30 minutes
- Task 7.5 (Add tests and verification): 3 hours

### Dependencies

- None (can be done anytime after Phase 2 is complete)
- Ideally after Phase 6 (after system is stable and tested)

### Risk Assessment

**Risk Level**: LOW

**Risks**:

- Cache introduces bugs (metadata incorrect)
- Thread-safety issues (if multi-threaded)
- Memory leak (cache grows too large)

**Mitigations**:

- Comprehensive correctness tests (cached vs non-cached metadata)
- Thread-safety analysis (add locks if needed)
- Cache monitoring (track size, alert if too large)
- Performance benchmarks (verify speedup, detect regressions)

### Alternative Approaches Considered

1. **Type Hint Inspection**:
   - Pro: No computation needed
   - Con: Not all indicators have accurate type hints
   - Con: Doesn't solve column name discovery
   - Decision: Rejected - too unreliable

2. **Instance-Level Cache**:
   - Pro: Simpler implementation
   - Con: Doesn't help with repeated indicator types
   - Con: Less memory efficient
   - Decision: Rejected - class-level cache more effective

3. **On-Demand Metadata Computation**:
   - Pro: No caching complexity
   - Con: No performance improvement
   - Decision: Rejected - doesn't solve problem

### Success Metrics

**Performance**:

- [ ] Initialization time reduced by at least 50% for strategies with repeated indicator types
- [ ] Cache hit rate >80% for typical strategies (after first engine creation)

**Quality**:

- [ ] Zero correctness bugs (cached metadata matches non-cached)
- [ ] Zero regressions (all existing tests pass)
- [ ] Cache size <100KB (negligible memory overhead)

**Code Quality**:

- [ ] Implementation clean and well-documented
- [ ] Cache behavior clear from code and logs
- [ ] Easy to understand and maintain

---

## Rollback Plan

### If Critical Issues Found

**Before Phase 3 (Training Changes)**:

- Rollback is simple: revert config model changes
- No training impact
- Users see "old format not supported" errors

**After Phase 3 (Training Changes)**:

- More complex: training pipeline changed
- Rollback procedure:
  1. Revert training_pipeline.py changes
  2. Revert IndicatorEngine changes
  3. Revert config model changes
  4. System returns to pre-feature_id state
  5. Migrated strategies need reverse migration (or manual revert)

### Rollback Triggers

- Training produces incorrect results (regression test fails by >5%)
- Performance degrades >10%
- Critical validation bug found (false positives/negatives)
- Data corruption detected
- Blocker bugs found in production

### Rollback Testing

**Before each major phase**, verify rollback procedure:

1. Apply phase changes
2. Run tests (should pass)
3. Create rollback branch
4. Revert phase changes
5. Run tests (should still pass)
6. Verify system returns to previous state
7. Document rollback steps

---

## Timeline Summary

| Phase | Duration | Dependencies | Risk |
|-------|----------|--------------|------|
| Phase 0: Error Reporting | 2 days | None | Low |
| Phase 1: Config Model | 2 days | Phase 0 | Low |
| Phase 1.5: Migration Tool | 1-2 days | None (parallel Phase 1) | Low |
| Phase 2: IndicatorEngine | 2-3 days | Phase 1 | Medium |
| Phase 3: Training Pipeline | 3-4 days | Phase 2 | **HIGH** |
| Phase 3.5: Input Transform (Fuzzy) | 3.5 days | Phase 3 | Medium |
| Phase 4: Fuzzy Engine | 1 day | Phase 3 | Low |
| Phase 5: Documentation | 1-2 days | Phase 1-4 | Low |
| Phase 6: System Testing | 2-3 days | Phase 1-4 | Medium |
| Phase 7: IndicatorEngine Optimization | 2 days | Phase 2+ (ideally after Phase 6) | Low |

**Total Duration**: 19.5-25.5 days (~4-5 weeks)

**Critical Path**: Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 6

**Note**: Phase 7 is optional performance optimization and can be done anytime after Phase 2 is stable.

---

## Risk Management

### HIGH Risk: Phase 3 (Training Pipeline)

**Risks**:

- Training produces different results (breaks models)
- Performance degrades significantly
- Edge cases not handled (multi-timeframe, multi-symbol)
- Transformation logic breaks (SMA/EMA ratios)

**Mitigations**:

- **Parallel validation test (REQUIRED)** - old vs new outputs must match
- Extensive regression testing with multiple strategies
- Performance benchmarks before/after
- Manual validation with spot checks
- Gradual rollout (test environment first)

### Medium Risk: Phase 2 (IndicatorEngine)

**Risks**:

- Aliasing creates data duplication (memory issue)
- Multi-output indicators not handled correctly
- Performance impact from additional columns

**Mitigations**:

- Reference same data (don't copy) - verified in tests
- Explicit primary output designation for multi-output
- Performance benchmarks
- Memory usage monitoring

### Medium Risk: Phase 3.5 (Input Transform in Fuzzy System)

**Risks**:

- Input transform doesn't match old transformation logic exactly
- Numerical differences affect training
- Migration tool doesn't handle correctly

**Mitigations**:

- Unit tests verify exact numerical match
- Integration tests with old strategies
- Parallel training comparison

### Low Risk: Phases 0, 1, 4, 5

These phases are relatively low risk:

- Don't change core training logic (Phase 0, 1, 4, 5)
- Fix existing issues (Phase 0)
- Well-isolated (Phase 4, 5)
- Clear validation criteria

---

## Success Metrics

### Technical Metrics

1. **Code Complexity**: Training pipeline reduced by ~150 lines (measured)
2. **Test Coverage**: Maintained >85% overall, >90% for new code (measured)
3. **Performance**: Within 5% of baseline (benchmarked)
4. **Validation**: Early failure without computation (verified)

### User Experience Metrics

1. **Error Clarity**: 100% of validation errors include suggestions (audited)
2. **Migration Success**: >95% of strategies migrate successfully (tracked)
3. **Documentation**: Migration guide complete with examples (reviewed)
4. **Support**: <10 migration-related support tickets (tracked post-release)

### Quality Metrics

1. **Regression**: 0 unexplained differences >1% in training outputs (tested)
2. **Bugs**: <3 P2 bugs, 0 P0/P1 bugs (tracked)
3. **Rollback**: Rollback procedure tested and documented (verified)
4. **Stability**: 0 training failures in phase 6 testing (measured)

---

## Post-Implementation

### Immediate (Week 1)

- [ ] Monitor training pipeline for errors
- [ ] Collect user feedback on feature_ids and migration
- [ ] Address any P0/P1 bugs immediately
- [ ] Update documentation based on user questions
- [ ] Monitor support channels for migration issues

### Short-term (Month 1)

- [ ] Review migration success rate (target >95%)
- [ ] Collect feedback on input transform usage
- [ ] Consider additional transform types if needed (log, standardization, etc.)
- [ ] Improve validation error messages based on user feedback
- [ ] Add feature_id and input_transform examples to documentation

### Long-term (Month 3+)

- [ ] Evaluate: Are current transform types sufficient?
- [ ] Consider: Advanced features (feature_id templates, groups)
- [ ] Review: Any remaining pain points in configuration
- [ ] Consider: Additional transform types (standardization, differencing, etc.)

---

## Open Questions to Resolve Before Implementation

### Q1: SMA/EMA Transformation Location

**Question**: Where should SMA/EMA transformation (price/MA ratio) live?

**Decision**: Input transform in fuzzy configuration (see [explicit-naming-architecture.md](./explicit-naming-architecture.md) Q1)

**Rationale**: Transformation is about _how to fuzzify_ a moving average, not indicator computation or training logic. Belongs in fuzzy realm where fuzzification is specified.

### Q2: Migration Tool Behavior on Collision

**Question**: What if migration creates duplicate feature_ids?

**Options**:

- A) Fail with error, require manual fix (CHOSEN)
- B) Auto-rename with suffix (rsi_14, rsi_14_2)
- C) Prompt user interactively

**Decision**: A (fail) - collisions must be resolved explicitly

### Q3: Feature ID Validation Timing

**Question**: When should feature_id uniqueness be validated?

**Options**:

- A) Config load (Pydantic validator) (CHOSEN)
- B) Strategy validator (after config load)
- C) Both (redundant but safe)

**Decision**: A (config load) - fail as early as possible

---

## Conclusion

This implementation plan provides a phased, testable approach with:

- **Clear phases**: Each with specific goals and acceptance criteria
- **Risk mitigation**: Parallel validation, rollback procedures
- **Breaking change**: Accepted with migration tool and clear path
- **Validation**: Updated at each phase with strict checks
- **Architecture**: Proper separation (transformations in indicators)

**Total duration**: 3-4 weeks with appropriate testing.

**Critical success factors**:

1. Phase 0 must establish solid error reporting
2. Phase 3 parallel validation MUST pass (training equivalence)
3. Migration tool must work reliably (>95% success rate)
4. Documentation must be clear and comprehensive
