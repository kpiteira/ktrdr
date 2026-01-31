---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 2: All Indicators Migrated

**Branch:** `feature/type-registry-m2`
**Builds on:** M1
**Goal:** All 39 indicators use Params pattern, factory deleted

## E2E Validation

### Test: indicators/registry-migration-complete

**Location:** `tests/unit/indicators/test_registry_migration_complete.py`

**Success Criteria:**
- [ ] indicator_factory.py does not exist
- [ ] schemas.py does not exist
- [ ] INDICATOR_REGISTRY.list_types() returns exactly 39 types
- [ ] All 39 have Params class inheriting from BaseModel
- [ ] Case-insensitive lookup works for all
- [ ] IndicatorEngine has no BUILT_IN_INDICATORS references
- [ ] All indicators instantiate with defaults

---

## Task 2.1: Add Params to momentum indicators (8)

**Files:** roc, momentum, cci, williams_r, stochastic, rvi, fisher_transform, aroon
**Type:** CODING
**Estimated time:** 2 hours

**Pattern:**
```python
class Params(BaseIndicator.Params):
    period: int = Field(default=14, ge=2, le=100)
    # ... other params with constraints
```

**Acceptance Criteria:**
- [ ] All 8 have Params class
- [ ] All 8 in INDICATOR_REGISTRY

---

## Task 2.2: Add Params to volatility indicators (6)

**Files:** atr, bollinger_bands, bollinger_band_width, keltner_channels, donchian_channels, supertrend
**Type:** CODING
**Estimated time:** 1.5 hours

**Acceptance Criteria:**
- [ ] All 6 have Params class
- [ ] All 6 in INDICATOR_REGISTRY

---

## Task 2.3: Add Params to trend indicators (7)

**Files:** ma_indicators (SMA, EMA, WMA), macd, adx, parabolic_sar, ichimoku
**Type:** CODING
**Estimated time:** 1.5 hours

**Note:** ma_indicators.py has 3 classes (SMA, EMA, WMA)

**Acceptance Criteria:**
- [ ] All 7 have Params class
- [ ] All 7 in INDICATOR_REGISTRY

---

## Task 2.4: Add Params to volume indicators (5)

**Files:** obv, vwap, mfi, cmf, ad_line
**Type:** CODING
**Estimated time:** 1 hour

**Acceptance Criteria:**
- [ ] All 5 have Params class
- [ ] All 5 in INDICATOR_REGISTRY

---

## Task 2.5: Add Params to remaining indicators (13)

**Files:** volume_ratio, distance_from_ma, squeeze_intensity, zigzag, plus others
**Type:** CODING
**Estimated time:** 2 hours

**Verification:** Cross-reference with indicator_factory.py to ensure all 39 covered

**Acceptance Criteria:**
- [ ] INDICATOR_REGISTRY.list_types() returns exactly 39
- [ ] All have Params class

---

## Task 2.6: Remove fallback from IndicatorEngine

**File:** `ktrdr/indicators/indicator_engine.py`
**Type:** CODING
**Estimated time:** 30 min

**Changes:**
- Remove import of BUILT_IN_INDICATORS
- Remove fallback logic
- Use INDICATOR_REGISTRY.get_or_raise() only

**Acceptance Criteria:**
- [ ] No reference to BUILT_IN_INDICATORS
- [ ] All tests pass

---

## Task 2.7: Update StrategyValidator to use registry

**File:** `ktrdr/config/strategy_validator.py`
**Type:** CODING
**Estimated time:** 30 min

**Changes:**
- Remove lazy import workaround
- Import INDICATOR_REGISTRY at top level
- Update _get_normalized_indicator_names()

**Acceptance Criteria:**
- [ ] No lazy imports
- [ ] Uses INDICATOR_REGISTRY
- [ ] Validation still works

---

## Task 2.8: Delete indicator_factory.py and schemas.py

**Files to delete:**
- `ktrdr/indicators/indicator_factory.py`
- `ktrdr/indicators/schemas.py`

**Type:** CODING
**Estimated time:** 30 min

**Verification:**
```bash
git grep -l "indicator_factory" -- "*.py" | grep -v __pycache__ || echo "No references"
git grep -l "from ktrdr.indicators.schemas" -- "*.py" || echo "No references"
```

**Acceptance Criteria:**
- [ ] Both files deleted
- [ ] No remaining imports
- [ ] All tests pass

---

## Task 2.9: Execute M2 E2E Test

**Type:** VALIDATION

**E2E Test:**
```bash
uv run python -c "
from ktrdr.indicators import INDICATOR_REGISTRY

types = INDICATOR_REGISTRY.list_types()
assert len(types) == 39, f'Expected 39, got {len(types)}'

for name in types:
    schema = INDICATOR_REGISTRY.get_params_schema(name)
    assert schema is not None, f'{name} missing Params'

for name in ['ATR', 'atr', 'MACD', 'BollingerBands']:
    assert INDICATOR_REGISTRY.get(name) is not None

print(f'M2 E2E PASSED - {len(types)} indicators registered')
"

test ! -f ktrdr/indicators/indicator_factory.py && echo 'indicator_factory.py deleted'
test ! -f ktrdr/indicators/schemas.py && echo 'schemas.py deleted'
```

**Acceptance Criteria:**
- [ ] E2E test passes
- [ ] `make test-unit` passes
- [ ] `make quality` passes
