---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 6: Cleanup (DEFERRED)

**Branch:** `feature/indicator-std-m6-cleanup`
**Builds on:** M5 + Strategy Grammar v3 complete
**Goal:** Remove all v2 compatibility code.

## IMPORTANT: Deferred Milestone

**DO NOT implement this milestone until:**

1. Strategy Grammar v3 is fully implemented
2. All v2 strategies have been migrated to v3
3. v2 strategies can be deleted from the codebase
4. No production systems depend on v2 format

**Trigger condition:** When `strategies/*.yaml` only contains v3 format strategies.

---

## What Gets Cleaned Up

All code marked with `# CLEANUP(v3)` comments, plus:

### 1. Old Format Detection in IndicatorEngine

**File:** `ktrdr/indicators/indicator_engine.py`

Remove the old-format detection branch in `compute_indicator()`:

```python
# CLEANUP(v3): Remove this entire block
if expected_outputs != actual_columns:
    # OLD FORMAT handling...
```

After cleanup, only the new-format path remains.

### 2. Deprecated Methods in BaseIndicator

**File:** `ktrdr/indicators/base_indicator.py`

Remove:
- `get_primary_output_suffix()` — replaced by `get_primary_output()`
- `get_column_name()` — indicators no longer responsible for naming
- `get_feature_id()` — caller provides indicator_id

### 3. Unused Column Standardization Module

**File:** `ktrdr/indicators/column_standardization.py`

Delete entire file (463 lines). Verify no imports exist:

```bash
grep -r "column_standardization" ktrdr/
grep -r "ColumnStandardizer" ktrdr/
```

### 4. Feature ID Mapping in IndicatorEngine

**File:** `ktrdr/indicators/indicator_engine.py`

Remove:
- `_build_feature_id_map()` — no longer needed
- `_create_feature_id_aliases()` — aliases created differently now
- `feature_id_map` attribute

### 5. v2 Strategy Loader Compatibility

**File:** `ktrdr/strategies/strategy_loader.py` (if exists)

Remove any v2-specific parsing or conversion logic.

---

## E2E Test Scenario

**Purpose:** Verify v3-only operation after cleanup
**Duration:** ~30 seconds
**Prerequisites:** All v2 strategies deleted

```bash
# 1. Verify no v2 strategies exist
ls strategies/*.yaml | while read f; do
    if ! grep -q "version: 3" "$f"; then
        echo "ERROR: $f is not v3 format"
        exit 1
    fi
done
echo "All strategies are v3 format ✓"

# 2. Verify column_standardization.py deleted
if [ -f "ktrdr/indicators/column_standardization.py" ]; then
    echo "ERROR: column_standardization.py should be deleted"
    exit 1
fi
echo "column_standardization.py deleted ✓"

# 3. Verify no CLEANUP(v3) comments remain
if grep -r "CLEANUP(v3)" ktrdr/; then
    echo "ERROR: CLEANUP(v3) comments still exist"
    exit 1
fi
echo "No CLEANUP(v3) comments ✓"

# 4. Run v3 strategy training
uv run ktrdr train strategies/some_v3_strategy.yaml --dry-run

# 5. Run tests
make test-unit
make quality

echo "M6 cleanup complete ✓"
```

---

## Task 6.1: Remove Old Format Detection

**File:** `ktrdr/indicators/indicator_engine.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Cross-Component

**Description:**
Remove the old-format detection branch from `compute_indicator()`. Only the new-format path should remain.

**Before:**
```python
def compute_indicator(self, data, indicator, indicator_id):
    result = indicator.compute(data)

    if not indicator.is_multi_output():
        # Single-output handling...
        pass

    expected = set(indicator.get_output_names())
    actual = set(result.columns)

    if expected == actual:
        # NEW FORMAT
        # ... prefix columns ...
    else:
        # CLEANUP(v3): Remove this block
        # OLD FORMAT
        # ... pass through ...
```

**After:**
```python
def compute_indicator(self, data, indicator, indicator_id):
    result = indicator.compute(data)

    if not indicator.is_multi_output():
        return pd.DataFrame({indicator_id: result}, index=data.index)

    # Multi-output: prefix all columns
    expected = set(indicator.get_output_names())
    actual = set(result.columns)

    if expected != actual:
        raise ValueError(
            f"Indicator {indicator_id} output mismatch: "
            f"expected {expected}, got {actual}"
        )

    prefixed = result.rename(columns={
        name: f"{indicator_id}.{name}"
        for name in result.columns
    })

    primary = indicator.get_primary_output()
    if primary:
        prefixed[indicator_id] = prefixed[f"{indicator_id}.{primary}"]

    return prefixed
```

**Tests:**
- Existing tests should pass (format detection was for backward compat)
- Add test that old-format indicators now raise error

**Acceptance Criteria:**
- [ ] Old-format detection removed
- [ ] Only new-format path remains
- [ ] Error raised for mismatched column names

---

## Task 6.2: Remove Deprecated Methods

**File:** `ktrdr/indicators/base_indicator.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Cross-Component

**Description:**
Remove deprecated methods from BaseIndicator.

**Methods to remove:**
- `get_primary_output_suffix()` — replaced by `get_primary_output()`
- `get_column_name()` — no longer used
- `get_feature_id()` — no longer used
- `_feature_id` attribute — no longer used
- `_timeframe` attribute — handled differently

**Before removal, verify no usages:**
```bash
grep -r "get_primary_output_suffix" ktrdr/
grep -r "get_column_name" ktrdr/
grep -r "get_feature_id" ktrdr/
grep -r "_feature_id" ktrdr/
```

**Tests:**
- Remove tests for deprecated methods
- Existing tests should still pass

**Acceptance Criteria:**
- [ ] All deprecated methods removed
- [ ] No remaining usages in codebase
- [ ] Tests updated

---

## Task 6.3: Delete Unused Files and Clean Imports

**Files:** Multiple
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Cleanup

**Description:**
Delete unused files and clean up imports.

**Files to delete:**
1. `ktrdr/indicators/column_standardization.py`

**Imports to clean:**
- Remove any imports of deleted modules
- Remove any `# CLEANUP(v3)` comments

**Verification:**
```bash
# Find all CLEANUP(v3) comments
grep -rn "CLEANUP(v3)" ktrdr/

# Verify no dangling imports
uv run python -c "import ktrdr; print('Import successful')"

# Run full test suite
make test-unit
```

**Acceptance Criteria:**
- [ ] `column_standardization.py` deleted
- [ ] No `CLEANUP(v3)` comments remain
- [ ] All imports clean (no dangling references)
- [ ] Full test suite passes

---

## Milestone 6 Verification

### Pre-Cleanup Checklist

Before starting M6, verify:

- [ ] Strategy Grammar v3 is fully implemented
- [ ] All v2 strategies converted to v3
- [ ] No production dependency on v2 format
- [ ] `grep -r "CLEANUP(v3)" ktrdr/` lists all cleanup items

### Post-Cleanup Verification

```bash
# 1. No CLEANUP comments remain
! grep -r "CLEANUP(v3)" ktrdr/

# 2. column_standardization.py deleted
! test -f ktrdr/indicators/column_standardization.py

# 3. Deprecated methods removed
! grep -r "get_primary_output_suffix" ktrdr/
! grep -r "get_column_name" ktrdr/indicators/

# 4. Tests pass
make test-unit
make quality

# 5. v3 strategies work
uv run ktrdr train strategies/v3_example.yaml --dry-run
```

### Completion Checklist

- [ ] Task 6.1: Old format detection removed
- [ ] Task 6.2: Deprecated methods removed
- [ ] Task 6.3: Unused files deleted
- [ ] All `CLEANUP(v3)` comments addressed
- [ ] Unit tests pass: `make test-unit`
- [ ] Quality gates pass: `make quality`
- [ ] v3 strategies work end-to-end

### Definition of Done

At the end of M6:
- No v2 compatibility code remains
- Codebase is clean and v3-only
- `column_standardization.py` deleted
- All deprecated methods removed
- Indicator standardization is complete and clean
