---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 5: v3 Ready Checkpoint

**Branch:** `feature/indicator-std-m5-checkpoint`
**Builds on:** M4 (all consumers updated)
**Goal:** Verify indicator standardization is complete and v3 Grammar can proceed.

## Purpose

This is a **verification milestone**, not an implementation milestone. No new code is written. Instead, we verify that all prior milestones are complete and the system is ready for Strategy Grammar v3 development.

## E2E Verification Scenario

**Purpose:** Comprehensive verification of indicator standardization
**Duration:** ~2 minutes
**Prerequisites:** M4 complete

```bash
#!/bin/bash
# Run this script to verify M5 readiness

echo "=== M5 Verification: Indicator Standardization Complete ==="
echo ""

# 1. Verify all indicators have get_output_names()
echo "1. Checking indicator interface compliance..."
uv run python -c "
from ktrdr.indicators.indicator_factory import BUILT_IN_INDICATORS

tested = set()
failures = []

for name, cls in BUILT_IN_INDICATORS.items():
    if cls in tested:
        continue
    tested.add(cls)

    # Check interface exists
    if not hasattr(cls, 'get_output_names'):
        failures.append(f'{name}: missing get_output_names()')
        continue

    if not hasattr(cls, 'get_primary_output'):
        failures.append(f'{name}: missing get_primary_output()')
        continue

    # Check consistency
    outputs = cls.get_output_names()
    is_multi = cls.is_multi_output()

    if is_multi and len(outputs) == 0:
        failures.append(f'{name}: is_multi_output=True but no output names')
    if not is_multi and len(outputs) > 0:
        failures.append(f'{name}: is_multi_output=False but has output names')

if failures:
    print('FAILURES:')
    for f in failures:
        print(f'  - {f}')
    exit(1)

print(f'  ✓ {len(tested)} indicator classes verified')
"

# 2. Verify all indicators produce semantic column names
echo "2. Checking indicator output format..."
uv run python -c "
from ktrdr.indicators import IndicatorEngine
from ktrdr.indicators.indicator_factory import BUILT_IN_INDICATORS
from ktrdr.data import DataManager

dm = DataManager()
data = dm.load('EURUSD', '1h', limit=200)

engine = IndicatorEngine()
tested = set()
failures = []

for name, cls in BUILT_IN_INDICATORS.items():
    if cls in tested:
        continue
    tested.add(cls)

    # Create indicator
    try:
        indicator = cls()
    except TypeError:
        try:
            indicator = cls(period=14)
        except:
            continue  # Skip if can't create with defaults

    indicator_id = f'{name}_test'

    try:
        result = engine.compute_indicator(data, indicator, indicator_id)
    except Exception as e:
        failures.append(f'{name}: compute_indicator failed: {e}')
        continue

    # Verify column format
    if cls.is_multi_output():
        expected_outputs = cls.get_output_names()
        for output in expected_outputs:
            col = f'{indicator_id}.{output}'
            if col not in result.columns:
                failures.append(f'{name}: missing column {col}')

        # Verify alias
        if indicator_id not in result.columns:
            failures.append(f'{name}: missing alias column {indicator_id}')
    else:
        if indicator_id not in result.columns:
            failures.append(f'{name}: missing column {indicator_id}')
        if len(result.columns) != 1:
            failures.append(f'{name}: single-output should have 1 column, got {len(result.columns)}')

if failures:
    print('FAILURES:')
    for f in failures:
        print(f'  - {f}')
    exit(1)

print(f'  ✓ {len(tested)} indicators produce correct format')
"

# 3. v2 Smoke Test: Train + Backtest
echo "3. Running v2 smoke test (train + backtest)..."

# Train model (2 months of 1h data)
uv run ktrdr models train strategies/mean_reversion_momentum_v1.yaml EURUSD 1h \
    --start-date 2024-01-01 \
    --end-date 2024-03-01

echo "  ✓ Training completed"

# Backtest the trained model
uv run ktrdr backtest run mean_reversion_momentum_v1 EURUSD 1h \
    --start-date 2024-03-01 \
    --end-date 2024-04-01

echo "  ✓ Backtesting completed (model loads correctly)"

# 4. Verify FeatureCache works
echo "4. Checking FeatureCache integration..."
uv run python -c "
from ktrdr.backtesting.feature_cache import FeatureCache
from ktrdr.indicators import IndicatorFactory, IndicatorEngine
from ktrdr.data import DataManager

dm = DataManager()
data = dm.load('EURUSD', '1h', limit=200)

factory = IndicatorFactory([
    {'name': 'rsi', 'feature_id': 'rsi_14', 'period': 14},
    {'name': 'bbands', 'feature_id': 'bbands_20_2', 'period': 20, 'multiplier': 2.0},
])
indicators = factory.build()
engine = IndicatorEngine(indicators)
indicators_df = engine.apply(data)

cache = FeatureCache(indicators_df)
idx = 50

# Test lookups
cache.get_indicator_value('rsi_14', idx)
cache.get_indicator_value('bbands_20_2.upper', idx)
cache.get_indicator_value('bbands_20_2', idx)  # alias

print('  ✓ FeatureCache lookups work')
"

# 5. Verify unit tests pass
echo "5. Running unit tests..."
make test-unit

# 6. Verify quality gates pass
echo "6. Running quality checks..."
make quality

echo ""
echo "=== M5 VERIFICATION COMPLETE ==="
echo ""
echo "Indicator standardization is complete. Ready for Strategy Grammar v3."
echo ""
echo "Next steps:"
echo "  1. Merge feature/indicator-std-m5-checkpoint to main"
echo "  2. Begin Strategy Grammar v3 development"
echo "  3. M6 (cleanup) happens AFTER v3 is complete"
```

**Success Criteria:**
- [ ] All indicators have `get_output_names()` interface
- [ ] All indicators produce correct column format
- [ ] v2 smoke test passes
- [ ] FeatureCache and FuzzyEngine work
- [ ] All unit tests pass
- [ ] All quality gates pass

---

## Task 5.1: Verification and Documentation

**Type:** VERIFICATION
**Estimated time:** 2 hours

**Task Categories:** Testing, Documentation

**Description:**
Run comprehensive verification and document the completed state.

**Steps:**

1. **Run verification script** (above)

2. **Update design docs with actual state**
   - Mark all checklist items in DESIGN.md as complete
   - Document any deviations from original plan

3. **Create v3 readiness document**
   - List all `get_output_names()` returns for each indicator
   - Document the column naming convention
   - Provide examples for v3 Grammar implementation

4. **Tag the completion**
   ```bash
   git tag -a indicator-std-v1 -m "Indicator standardization complete"
   ```

**Verification Checklist:**

```markdown
## Indicator Standardization Verification

### Interface Compliance (M1)
- [ ] All indicators have `get_output_names()`
- [ ] All indicators have `get_primary_output()`
- [ ] Multi-output consistency: `is_multi_output() == True` ↔ `len(get_output_names()) > 0`

### Adapter Layer (M2)
- [ ] `compute_indicator()` method exists
- [ ] Format detection works for both old and new formats
- [ ] Alias columns created for multi-output indicators

### Single-Output Migration (M3a)
- [ ] All single-output indicators return unnamed Series
- [ ] IndicatorEngine names columns with `indicator_id`

### Multi-Output Migration (M3b)
- [ ] All multi-output indicators return semantic column names
- [ ] Column names match `get_output_names()` exactly
- [ ] IndicatorEngine prefixes with `indicator_id.`

### Consumer Updates (M4)
- [ ] FeatureCache uses direct column lookup
- [ ] FuzzyEngine works with new format
- [ ] Training pipeline produces models with correct feature names

### v2 Compatibility
- [ ] `strategies/rsi_mean_reversion.yaml` trains successfully
- [ ] Existing models can still be loaded (if applicable)
- [ ] No breaking changes to CLI interface
```

**Acceptance Criteria:**
- [ ] All verification checks pass
- [ ] Design docs updated
- [ ] v3 readiness document created
- [ ] Git tag created

---

## v3 Grammar Dependencies Verified

This section documents what Strategy Grammar v3 depends on from indicator standardization.

### 1. `get_output_names()` for Validation

v3 Grammar uses dot notation: `bbands_20_2.upper`

To validate this, v3 needs to:
```python
indicator_class = factory.get_indicator_class('bbands')
valid_outputs = indicator_class.get_output_names()  # ['upper', 'middle', 'lower']
assert 'upper' in valid_outputs  # Validation passes
```

**Verified:** All 10 multi-output indicators return correct output names.

### 2. Consistent Column Naming

v3 expects columns in format:
- Single-output: `{indicator_id}` (e.g., `rsi_14`)
- Multi-output: `{indicator_id}.{output}` (e.g., `bbands_20_2.upper`)

**Verified:** IndicatorEngine produces this format after M3a/M3b.

### 3. Primary Output Alias

v3 allows bare references: `bbands_20_2` without `.upper`

This resolves to the primary output via alias column.

**Verified:** Alias columns created for all multi-output indicators.

### 4. Consumer Compatibility

v3 features pass through same consumers (FeatureCache, FuzzyEngine).

**Verified:** Consumers updated in M4 to use new format.

---

## Milestone 5 Verification

### Completion Checklist

- [ ] Task 5.1: Verification script passes
- [ ] Design docs updated
- [ ] v3 readiness document created
- [ ] Git tag created: `indicator-std-v1`
- [ ] All unit tests pass: `make test-unit`
- [ ] All quality gates pass: `make quality`

### Definition of Done

At the end of M5:
- Indicator standardization is complete
- v2 strategies work unchanged
- v3 Grammar development can begin
- M6 (cleanup) is deferred until after v3 is complete

### What Happens Next

1. **Merge to main** — Indicator standardization is production-ready
2. **Begin v3 Grammar** — Use the standardized interface
3. **M6 Cleanup** — Only after v3 strategies replace v2 strategies
