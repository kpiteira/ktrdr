---
design: docs/designs/strategy-grammar-v3/DESIGN.md
architecture: docs/designs/strategy-grammar-v3/ARCHITECTURE.md
---

# Milestone 8: Cleanup & Migration

**Branch:** `feature/strategy-grammar-v3-m8`
**Prerequisite:** M7 complete (full v3 system works)
**Builds on:** M7 Agent Integration

## Goal

Remove all v2 remnants from the codebase. Migrate useful v2 strategies to v3. Update all test fixtures.

## Why This Milestone

- Final cleanup prevents confusion and maintenance burden
- Useful strategies preserved via migration
- Test fixtures must use v3 for ongoing testing

---

## Tasks

### Task 8.1: Audit Existing Strategies

**File(s):** `strategies/` directory
**Type:** RESEARCH
**Estimated time:** 1 hour

**Task Categories:** Configuration

**Description:**
Audit all existing strategies to determine which to migrate vs delete.

**Implementation Notes:**

Criteria for keeping:
- Used in integration tests
- Demonstrates a useful pattern
- Minimal complexity (good for examples)

Criteria for deleting:
- Broken or incomplete
- Duplicates another strategy
- Only used for one-off experiments

Create inventory:
```markdown
| Strategy | Status | Action | Notes |
|----------|--------|--------|-------|
| neuro_mean_reversion.yaml | v2 | Migrate | Used in tests |
| test_strategy_1.yaml | v2 | Delete | Experiment |
| ... | ... | ... | ... |
```

**Acceptance Criteria:**
- [ ] All strategies audited
- [ ] Clear decision for each (migrate/delete)
- [ ] Inventory documented

---

### Task 8.2: Migrate Useful Strategies

**File(s):** `strategies/*.yaml`
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** Configuration

**Description:**
Migrate all strategies marked for keeping to v3 format.

**Implementation Notes:**

Use the migration tool:
```bash
ktrdr strategy migrate strategies/ --backup
```

Then verify each:
```bash
for f in strategies/*.yaml; do
    ktrdr strategy validate "$f"
done
```

Manual adjustments may be needed for:
- Complex fuzzy set definitions
- Non-standard indicator configurations
- Edge cases the migration tool doesn't handle

**Testing Requirements:**

*Smoke Test:*
```bash
# Verify all strategies are now v3
for f in strategies/*.yaml; do
    if ! grep -q "nn_inputs:" "$f"; then
        echo "FAIL: $f missing nn_inputs"
        exit 1
    fi
done
echo "All strategies are v3"
```

**Acceptance Criteria:**
- [ ] All kept strategies migrated to v3
- [ ] All strategies pass `ktrdr strategy validate`
- [ ] Backups preserved (in case of issues)

---

### Task 8.3: Delete Obsolete Strategies

**File(s):** `strategies/` directory
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Configuration

**Description:**
Remove strategies marked for deletion in the audit.

**Implementation Notes:**

```bash
# Delete obsolete strategies (list from audit)
rm strategies/obsolete_1.yaml
rm strategies/obsolete_2.yaml
# ...

# Remove backup files after verification
rm strategies/*.bak

# Commit with clear message
git add -A strategies/
git commit -m "cleanup(strategies): Remove obsolete v2 strategies

Deleted:
- obsolete_1.yaml (reason)
- obsolete_2.yaml (reason)

Remaining strategies migrated to v3 format."
```

**Acceptance Criteria:**
- [ ] Obsolete strategies deleted
- [ ] Deletion documented in commit message

---

### Task 8.4: Update Test Fixtures

**File(s):** `tests/fixtures/strategies/`, `tests/conftest.py`
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Configuration

**Description:**
Update all test strategy fixtures to v3 format.

**Implementation Notes:**

Locations to check:
- `tests/fixtures/strategies/` — Strategy YAML files
- `tests/conftest.py` — Inline strategy dicts in fixtures
- `tests/unit/*/` — Test files with embedded strategies
- `tests/integration/*/` — Integration test strategies

For each:
1. Migrate to v3 format
2. Verify tests still pass
3. Update assertions if needed (feature names changed)

```bash
# Find all YAML files in tests
find tests/ -name "*.yaml" -o -name "*.yml" | while read f; do
    if grep -q "feature_id:" "$f"; then
        echo "V2 fixture: $f"
    fi
done
```

**Testing Requirements:**

After migration:
```bash
make test-unit
make test-integration
```

**Acceptance Criteria:**
- [ ] All test fixtures use v3 format
- [ ] All tests pass
- [ ] No v2 terminology in test files

---

### Task 8.5: Remove V2 Code Paths

**File(s):** Various
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Cross-Component

**Description:**
Remove v2 detection and handling code from main paths.

**Implementation Notes:**

Code to remove/simplify:

1. **Strategy Loader**: Remove v2 detection (already rejects v2, but may have dead code)
   ```python
   # Remove: if self._is_v2_format(config): ...
   # Keep: if not self._is_v3_format(config): raise ValueError(...)
   ```

2. **Config Models**: Remove any v2 model classes if they exist
   ```python
   # Remove: class StrategyConfigurationV2
   # Remove: class IndicatorConfigV2
   ```

3. **Indicator Engine**: Remove old list-based initialization
   ```python
   # Remove: def __init__(self, indicators: list[dict])
   # Keep: def __init__(self, indicators: dict[str, IndicatorDefinition])
   ```

4. **Fuzzy Engine**: Remove old initialization patterns

5. **Training Pipeline**: Remove v2 handling branches

Search for v2 remnants:
```bash
# Find potential v2 code
grep -r "feature_id" ktrdr/ --include="*.py" | grep -v migration
grep -r "v2" ktrdr/ --include="*.py" | grep -v migration
grep -r "is_v2" ktrdr/ --include="*.py"
```

**Note:** Keep migration code (`strategy_migration.py`) — users may still need to migrate old strategies.

**Acceptance Criteria:**
- [ ] No v2 handling in main code paths
- [ ] Migration code preserved
- [ ] All tests pass after removal

---

### Task 8.6: Update Documentation

**File(s):** `docs/`, `README.md`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Configuration

**Description:**
Update documentation to reflect v3-only world.

**Implementation Notes:**

Files to update:
- `README.md` — Strategy examples should be v3
- `docs/guides/` — Any strategy guides
- `docs/api/` — API documentation if strategies are mentioned

Add deprecation note:
```markdown
> **Note:** Strategy Grammar v2 is deprecated. Use `ktrdr strategy migrate`
> to upgrade existing strategies to v3 format.
```

**Acceptance Criteria:**
- [ ] All examples use v3 format
- [ ] Deprecation noted for v2
- [ ] No broken links

---

## E2E Test Scenario

**Purpose:** Prove v2 is fully removed from main paths
**Duration:** ~30 seconds
**Prerequisites:** M7 complete

### Test Steps

```bash
#!/bin/bash
# M8 E2E Test: Cleanup & Migration

set -e

echo "=== M8 E2E Test: Cleanup & Migration ==="

# Test 1: No v2 strategies remain
echo "Test 1: Checking for v2 strategies..."
V2_COUNT=$(find strategies/ -name "*.yaml" -exec grep -l "feature_id:" {} \; 2>/dev/null | wc -l)
if [ "$V2_COUNT" -gt 0 ]; then
    echo "FAIL: Found $V2_COUNT v2 strategies"
    find strategies/ -name "*.yaml" -exec grep -l "feature_id:" {} \;
    exit 1
fi
echo "  No v2 strategies found: OK"
echo "Test 1: PASS"

# Test 2: All strategies validate as v3
echo "Test 2: Validating all strategies..."
for f in strategies/*.yaml; do
    if ! ktrdr strategy validate "$f" > /dev/null 2>&1; then
        echo "FAIL: $f does not validate"
        ktrdr strategy validate "$f"
        exit 1
    fi
done
echo "  All strategies valid: OK"
echo "Test 2: PASS"

# Test 3: No v2 code in main paths (excluding migration)
echo "Test 3: Checking for v2 code remnants..."
V2_CODE=$(grep -r "feature_id" ktrdr/ --include="*.py" | grep -v migration | grep -v test | wc -l)
if [ "$V2_CODE" -gt 0 ]; then
    echo "WARNING: Found $V2_CODE potential v2 references"
    grep -r "feature_id" ktrdr/ --include="*.py" | grep -v migration | grep -v test
    # This is a warning, not a failure — may be false positives
fi
echo "Test 3: PASS"

# Test 4: Test fixtures are v3
echo "Test 4: Checking test fixtures..."
V2_FIXTURES=$(find tests/ -name "*.yaml" -exec grep -l "feature_id:" {} \; 2>/dev/null | wc -l)
if [ "$V2_FIXTURES" -gt 0 ]; then
    echo "FAIL: Found $V2_FIXTURES v2 test fixtures"
    find tests/ -name "*.yaml" -exec grep -l "feature_id:" {} \;
    exit 1
fi
echo "  All test fixtures v3: OK"
echo "Test 4: PASS"

# Test 5: Full test suite passes
echo "Test 5: Running test suite..."
make test-unit
echo "Test 5: PASS"

echo ""
echo "=== M8 E2E Test: ALL PASSED ==="
```

### Success Criteria

- [ ] No v2 strategies in `strategies/`
- [ ] All strategies validate as v3
- [ ] No v2 code in main paths (migration code allowed)
- [ ] All test fixtures are v3
- [ ] Full test suite passes

---

## Post-Milestone: Indicator Standardization M6

After M8 is complete and verified, trigger indicator standardization M6 (cleanup):

> **IMPORTANT:** Indicator Standardization M6 removes v2 compatibility code from
> indicators. This should only happen after v3 strategies are fully deployed
> and verified.
>
> See: [docs/designs/indicator-standardization/DESIGN.md](../../designs/indicator-standardization/DESIGN.md)

---

## Completion Checklist

- [ ] Task 8.1: Strategy audit complete
- [ ] Task 8.2: Useful strategies migrated
- [ ] Task 8.3: Obsolete strategies deleted
- [ ] Task 8.4: Test fixtures updated
- [ ] Task 8.5: V2 code paths removed
- [ ] Task 8.6: Documentation updated
- [ ] All unit tests pass: `make test-unit`
- [ ] All integration tests pass: `make test-integration`
- [ ] E2E test script passes
- [ ] M1-M7 E2E tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] Code reviewed and merged
- [ ] Trigger Indicator Standardization M6

---

## Final Verification

After M8 completion, run the complete verification:

```bash
# 1. All strategies valid
for f in strategies/*.yaml; do ktrdr strategy validate "$f"; done

# 2. Full test suite
make test-unit
make test-integration
make test-e2e

# 3. Quality gates
make quality

# 4. No v2 references (except migration code)
grep -r "feature_id\|v2" ktrdr/ --include="*.py" | grep -v migration | grep -v test

# 5. Training + backtest works
ktrdr train strategies/v3_test_example.yaml --epochs 1 --output /tmp/final_test
ktrdr backtest /tmp/final_test --symbol EURUSD --start 2024-01-01 --end 2024-01-31

echo "Strategy Grammar v3 migration complete!"
```
