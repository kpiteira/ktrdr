# Milestone 2 Handoff: All Indicators Migrated

## Task 2.1 Complete: Add Params to momentum indicators (8)

### Implementation Notes

Migrated all 8 momentum indicators to the Params pattern:
- ROC, Momentum, CCI, Williams %R, Stochastic, RVI, Fisher Transform, Aroon

### Pattern Applied

For each indicator:
1. Added `class Params(BaseIndicator.Params)` with Field definitions
2. Removed explicit `__init__` method (BaseIndicator handles validation)
3. Removed `_validate_params` method and schema imports from `schemas.py`
4. Set `display_as_overlay = False` as class attribute for oscillators
5. Updated `compute()` to read from `self.params["field"]` directly

### Gotchas

**RVI column naming (M3b)**: RVI was returning old-style column names like `RVI_10_4_RVI`. Updated to semantic names (`rvi`, `signal`) to match other multi-output indicators.

**Test error message pattern**: Old tests checked for specific error messages like `"period must be >= 4"`. New Pydantic validation uses generic `INDICATOR-InvalidParameters` error code. Update tests to check `exc_info.value.error_code == "INDICATOR-InvalidParameters"`.

**Source field validation**: Old schemas validated source against a list (`["open", "high", "low", "close"]`). New Params classes don't restrict source values - validation happens at compute time if column doesn't exist. Tests expecting source validation at construction time should be updated.

**No _validate_params needed**: With Params classes, validation happens automatically in `BaseIndicator.__init__`. Remove calls to `indicator._validate_params(params)` in tests.

### Key Changes

| Indicator | Params Fields | Notes |
|-----------|--------------|-------|
| ROC | period (1-100), source | |
| Momentum | period (1-100), source | |
| CCI | period (2-100) | |
| Williams %R | period (1-100) | |
| Stochastic | k_period (1-100), d_period (1-20), smooth_k (1-20) | Multi-output |
| RVI | period (4-100), signal_period (1-50) | Multi-output, min period=4 |
| Fisher Transform | period (2-100), smoothing (1-20) | Multi-output |
| Aroon | period (1-200), include_oscillator | Multi-output |

### Tests Added

- `tests/unit/indicators/test_momentum_params_migration.py`: 57 tests validating Params migration for all 8 indicators

### Next Task Notes

Task 2.2 migrates volatility indicators (6): atr, bollinger_bands, bollinger_band_width, keltner_channels, donchian_channels, supertrend.

Follow the same pattern:
1. Add Params class
2. Remove __init__ and _validate_params
3. Set display_as_overlay if needed
4. Update any old-style column naming to semantic names

---

## Task 2.2 Complete: Add Params to volatility indicators (6)

### Implementation Notes

Migrated all 6 volatility indicators to the Params pattern:
- ATR, BollingerBands, BollingerBandWidth, KeltnerChannels, DonchianChannels, SuperTrend

### Pattern Applied

Same pattern as Task 2.1:
1. Added `class Params(BaseIndicator.Params)` with Field definitions
2. Removed explicit `__init__` method
3. Removed `_validate_params` method and schema imports
4. Set `display_as_overlay` as class attribute
5. Updated `compute()` to read from `self.params["field"]` directly

### Gotchas

**Preserve `typing.Any` import**: When replacing imports, don't remove `from typing import Any` if it's used in `get_signals()` or `get_analysis()` return type annotations elsewhere in the file.

**Old test patterns need updating**: Tests using `bb._validate_params(params)` pattern need to be updated to test construction-time validation instead. Tests expecting `ValueError` need to expect `DataError` with `error_code == "INDICATOR-InvalidParameters"`.

### Key Changes

| Indicator | Params Fields | display_as_overlay | Notes |
|-----------|--------------|-------------------|-------|
| ATR | period (1-100) | False | |
| BollingerBands | period (2-200), multiplier (>0, ≤10), source | True | Multi-output |
| BollingerBandWidth | period (2-200), multiplier (>0, ≤10), source | False | |
| KeltnerChannels | period (2-500), atr_period (2-200), multiplier (>0, ≤10) | True | Multi-output |
| DonchianChannels | period (2-500), include_middle | True | Multi-output |
| SuperTrend | period (2-200), multiplier (>0, ≤10) | True | Multi-output |

### Tests Updated

- `tests/unit/indicators/test_volatility_params_migration.py`: New test file with 56 tests
- `tests/unit/indicators/test_bollinger_bands_indicator.py`: Updated validation tests
- `tests/unit/indicators/test_donchian_channels.py`: Updated validation tests

### Next Task Notes

Task 2.3 migrates trend indicators (7): ma_indicators (SMA, EMA, WMA), macd, adx, parabolic_sar, ichimoku.

Note that `ma_indicators.py` has 3 classes (SMA, EMA, WMA) - each needs its own Params class.

---

## Task 2.3 Complete: Add Params to trend indicators (7)

### Implementation Notes

Migrated all 7 trend indicators to the Params pattern:
- SMA, EMA, WMA (in ma_indicators.py), MACD, ADX, ParabolicSAR, Ichimoku

Added WMA to the codebase (was missing). Added `_aliases` for common shorthand lookups: sma, ema, wma.

### Pattern Applied

Same pattern as previous tasks:
1. Added `class Params(BaseIndicator.Params)` with Field definitions
2. Removed explicit `__init__` method
3. Removed `_validate_params` method and schema imports
4. Set `display_as_overlay` as class attribute
5. Updated `compute()` to read from `self.params["field"]` directly

### Gotchas

**Boolean coercion with Pydantic**: Pydantic's default bool handling coerces truthy strings ("yes", "true", "1") to True. If strict boolean validation is needed, use `strict=True` in Field definition. EMA's `adjust` parameter requires this.

**MA indicators don't have "Indicator" suffix**: SMA, EMA, WMA class names don't end with "Indicator", so their canonical registry names are `simplemovingaverage`, `exponentialmovingaverage`, `weightedmovingaverage`. Added `_aliases` list for common shorthand names.

**Match schema.py constraints**: Ensure Params constraints match original schema.py definitions:
- Ichimoku: tenkan (1-50), kijun (1-100), senkou_b (1-200), displacement (1-100)
- ParabolicSAR: initial_af (0.001-0.1), step_af (0.001-0.1), max_af (0.01-1.0)

### Key Changes

| Indicator | Params Fields | display_as_overlay | Notes |
|-----------|--------------|-------------------|-------|
| SMA | period (2-500), source | True | Alias: sma |
| EMA | period (1-500), source, adjust | True | Alias: ema |
| WMA | period (2-500), source | True | Alias: wma, NEW indicator |
| MACD | fast_period (1-100), slow_period (1-200), signal_period (1-50), source | False | Multi-output |
| ADX | period (2-200) | False | Multi-output |
| ParabolicSAR | initial_af (0.001-0.1), step_af (0.001-0.1), max_af (0.01-1.0) | True | |
| Ichimoku | tenkan_period (1-50), kijun_period (1-100), senkou_b_period (1-200), displacement (1-100) | True | Multi-output |

### Tests Added/Updated

- `tests/unit/indicators/test_trend_params_migration.py`: New test file with 68 tests
- `tests/unit/indicators/test_ma_indicators.py`: Updated validation tests to use error_code
- `tests/unit/indicators/test_ichimoku_indicator.py`: Updated validation tests
- `tests/unit/indicators/test_parabolic_sar_indicator.py`: Updated validation tests

### Next Task Notes

Task 2.4 migrates volume indicators (5): obv, vwap, mfi, cmf, ad_line.

Follow the same pattern. Watch for existing tests that check specific error messages.

---

## Task 2.4 Complete: Add Params to volume indicators (5)

### Implementation Notes

Migrated all 5 volume indicators to the Params pattern:
- OBV, VWAP, MFI, CMF, ADLine

### Pattern Applied

Same pattern as previous tasks:
1. Added `class Params(BaseIndicator.Params)` with Field definitions
2. Removed explicit `__init__` method
3. Removed `_validate_params` method and schema imports
4. Set `display_as_overlay` as class attribute
5. Updated `compute()` to read from `self.params["field"]` directly

### Gotchas

**OBV has no parameters**: OBV is unique - it has no configurable parameters. Its Params class is empty (`pass`). Extra kwargs passed to constructor are ignored.

**Keep `typing.Any` import**: CMF and ADLine have `get_signals()` and `get_analysis()` methods that return `dict[str, Any]`, so the `Any` import must be preserved.

**Old tests check error message text**: Tests in `test_mfi_indicator.py` and `test_vwap_indicator.py` checked for specific error message text like `"period must be"`. Updated to check `error_code == "INDICATOR-InvalidParameters"` instead.

### Key Changes

| Indicator | Params Fields | display_as_overlay | Notes |
|-----------|--------------|-------------------|-------|
| OBV | (none) | False | No configurable params |
| VWAP | period (0-200), use_typical_price | True | period=0 for cumulative |
| MFI | period (1-100) | False | |
| CMF | period (2-500) | False | Multi-output |
| ADLine | use_sma_smoothing, smoothing_period (2-200) | False | Multi-output |

### Tests Added/Updated

- `tests/unit/indicators/test_volume_params_migration.py`: New test file with 45 tests
- `tests/unit/indicators/test_mfi_indicator.py`: Updated validation tests to use error_code
- `tests/unit/indicators/test_vwap_indicator.py`: Updated validation tests to use error_code

### Next Task Notes

Task 2.5 migrates remaining indicators: volume_ratio, distance_from_ma, squeeze_intensity, zigzag.

---

## Task 2.5 Complete: Add Params to remaining indicators (4)

### Implementation Notes

Migrated the final 4 indicators to the Params pattern:
- VolumeRatio, DistanceFromMA, SqueezeIntensity, ZigZag

**Total count clarification**: The milestone file mentioned 39 indicators, but the actual count is 31:
- 30 unique classes in `indicator_factory.py`
- Plus WMA added in Task 2.3

All 31 indicators now have their own Params class.

### Pattern Applied

Same pattern as previous tasks:
1. Added `class Params(BaseIndicator.Params)` with Field definitions
2. Removed explicit `__init__` method (or custom `__init__` like ZigZag had)
3. Removed `_validate_params` method and schema imports
4. Set `display_as_overlay` as class attribute
5. Updated `compute()` to read from `self.params["field"]` directly

### Gotchas

**Literal type + strict**: Pydantic doesn't allow `strict=True` on `Literal` type fields. The error: "Unable to apply constraint 'strict' to schema of type 'literal'". Remove `strict=True` from Literal fields (DistanceFromMA's `ma_type`).

**ZigZag used instance attributes**: ZigZag stored `self.threshold` and `self.source` directly and used them in compute. Updated to use `self.params["threshold"]` and `self.params["source"]` consistently.

**Old tests manipulate params directly**: Some tests (like `test_distance_from_ma_indicator.py`) set `indicator.params["ma_type"] = "INVALID"` to test runtime validation. With Params pattern, validation happens at construction time. Updated tests to test construction-time validation instead.

### Key Changes

| Indicator | Params Fields | display_as_overlay | Notes |
|-----------|--------------|-------------------|-------|
| VolumeRatio | period (2-100) | False | |
| DistanceFromMA | period (1-200), ma_type (SMA/EMA), source | False | Literal type for ma_type |
| SqueezeIntensity | bb_period (2-100), bb_multiplier (>0, ≤5), kc_period (2-100), kc_multiplier (>0, ≤5), source | False | Complex indicator using BB + KC |
| ZigZag | threshold (0-1 exclusive), source | True | Price overlay |

### Tests Added/Updated

- `tests/unit/indicators/test_remaining_params_migration.py`: New test file with 40 tests
- `tests/unit/indicators/test_distance_from_ma_indicator.py`: Updated `test_invalid_ma_type_error` to test construction-time validation

### Next Task Notes

Task 2.6 removes the fallback from IndicatorEngine. After this task, all indicators use INDICATOR_REGISTRY exclusively.

---

## Task 2.6 Complete: Remove fallback from IndicatorEngine

### Implementation Notes

Removed BUILT_IN_INDICATORS fallback from IndicatorEngine. All indicator lookups now use INDICATOR_REGISTRY exclusively via `get_or_raise()`.

### Changes Made

1. **indicator_engine.py**: Removed BUILT_IN_INDICATORS import and fallback logic
   - Now uses `INDICATOR_REGISTRY.get_or_raise(definition.type)` for cleaner error handling
   - Error messages now list only registry types (no need to merge two sources)

2. **__init__.py**: Removed BUILT_IN_INDICATORS export from public API

3. **BollingerBandsIndicator**: Added `_aliases = ["bbands"]` for backward compatibility
   - This alias existed in BUILT_IN_INDICATORS but wasn't registered in the class

### Gotchas

**Tests need explicit imports**: Tests that use indicator types like "bbands" must import the indicator module to trigger auto-registration. Without the import, only basic indicators (RSI, EMA, SMA, etc.) are available in test isolation.

Example fix:
```python
# Import to register "bbands" alias
from ktrdr.indicators.bollinger_bands_indicator import BollingerBandsIndicator  # noqa: F401
```

**Canonical names vs aliases**: The registry canonical name is the class name without "Indicator" suffix, lowercased:
- `ATRIndicator` -> canonical: `atr`, alias: `atrindicator`
- `BollingerBandsIndicator` -> canonical: `bollingerbands`, aliases: `bollingerbandsindicator`, `bbands`

### Tests Added/Updated

- `tests/unit/indicators/test_indicator_engine_no_fallback.py`: New tests verifying no BUILT_IN_INDICATORS usage
- `tests/unit/indicators/test_indicator_engine_registry.py`: Updated to remove fallback references
- `tests/unit/indicators/test_indicator_engine_adapter.py`: Added BollingerBandsIndicator import

### Next Task Notes

Task 2.7 updates StrategyValidator to use the registry. The validator still imports BUILT_IN_INDICATORS via lazy import workaround - this needs to be cleaned up.

---

## Task 2.7 Complete: Update StrategyValidator to use registry

### Implementation Notes

Updated StrategyValidator to use INDICATOR_REGISTRY instead of BUILT_IN_INDICATORS:
- Removed lazy import workaround
- Added top-level import of INDICATOR_REGISTRY
- Simplified `_get_normalized_indicator_names()` to use registry directly

### Changes Made

1. **strategy_validator.py**: Replaced all BUILT_IN_INDICATORS usage with INDICATOR_REGISTRY
   - Added `from ktrdr.indicators.base_indicator import INDICATOR_REGISTRY` at top level
   - `_get_normalized_indicator_names()` now returns `set(INDICATOR_REGISTRY.list_types())`
   - `validate_v3_strategy()` uses `INDICATOR_REGISTRY.get()` for dot notation validation
   - Removed lazy import caching mechanism (no longer needed)

### Gotchas

**Registry returns canonical names only**: `INDICATOR_REGISTRY.list_types()` returns canonical names (e.g., "bollingerbands") not aliases (e.g., "bbands"). The registry's `get()` method handles aliases for lookups, but `list_types()` only shows canonical names. This is fine for validation since `get()` is case-insensitive and handles aliases.

**No more circular import risk**: The original lazy import was to avoid circular imports. With the registry pattern and proper module organization, we can now import INDICATOR_REGISTRY at the top level without issues.

### Tests Added/Updated

- `tests/unit/config/test_strategy_validator_registry.py`: New test file with 8 tests verifying INDICATOR_REGISTRY usage

### Next Task Notes

Task 2.8 deletes indicator_factory.py and schemas.py. Before deleting, verify no remaining imports of BUILT_IN_INDICATORS exist:
```bash
git grep -l "BUILT_IN_INDICATORS" -- "*.py" | grep -v __pycache__ | grep -v indicator_factory.py
```

---

## Task 2.8 Complete: Delete indicator_factory.py and schemas.py

### Implementation Notes

Deleted the legacy indicator factory and schemas files. Updated all remaining references to use INDICATOR_REGISTRY.

### Files Changed

**Deleted:**
- `ktrdr/indicators/indicator_factory.py`
- `ktrdr/indicators/schemas.py`

**Updated to use INDICATOR_REGISTRY:**
- `ktrdr/api/endpoints/strategies.py`: Replaced BUILT_IN_INDICATORS with INDICATOR_REGISTRY
- `ktrdr/api/services/indicator_service.py`: Updated to iterate over registry types

**Tests updated:**
- `tests/integration/indicators/test_indicator_interface_standard.py`: Uses INDICATOR_REGISTRY
- `tests/unit/indicators/test_atr_indicator.py`: Removed schema import, updated tests
- `tests/unit/indicators/test_bollinger_bands_indicator.py`: Removed schema import
- `tests/unit/indicators/test_obv_indicator.py`: Removed schema import, updated tests
- `tests/unit/indicators/test_stochastic_indicator.py`: Removed schema import, updated tests
- `tests/unit/indicators/test_williams_r_indicator.py`: Removed schema import, updated tests
- `tests/unit/indicators/test_parameter_schema.py`: Removed schema tests (kept ParameterDefinition tests)

### Gotchas

**Test class naming**: Schema validation test classes were renamed from `TestXxxSchemaValidation` to `TestXxxParamsValidation` to reflect the new validation pattern.

**Error codes changed**: Old schemas used specific error codes like `PARAM-BelowMinimum`. New Params validation uses `INDICATOR-InvalidParameters`. Tests updated accordingly.

**parameter_schema.py still exists**: The ParameterDefinition and ParameterConstraint classes in `parameter_schema.py` are still available as utilities, though the ParameterSchema class is no longer used.

### Next Task Notes

Task 2.9 executes the M2 E2E test to verify all 31 indicators are registered and the factory/schemas files are deleted.

---

## Task 2.9 Complete: Execute M2 E2E Test

### Implementation Notes

E2E validation revealed that indicators were not being auto-registered due to missing imports in `__init__.py`. Fixed by implementing lazy loading pattern to maintain import performance while ensuring all indicators can be loaded on-demand.

### Issue Discovered

**Initial E2E failure**: Only 5 indicators registered (SMA, EMA, WMA, MACD, RSI) instead of 31. The `__init__.py` was only importing a few indicators.

**Import performance regression**: Adding all indicator imports to `__init__.py` increased CLI import time from ~150ms to ~850ms (target: <200ms). This failed the `test_app_import_fast` test.

### Solution: Lazy Loading

Implemented lazy loading pattern in `ktrdr/indicators/__init__.py`:

1. **`ensure_all_registered()`** function: Lazily imports all 31 indicator modules on first call
2. **Circular import fix**: `strategy_validator.py` now uses lazy import helper `_get_indicator_registry()`
3. **Direct module imports for tests**: Tests import from specific modules (e.g., `from ktrdr.indicators.rsi_indicator import RSIIndicator`)

### Key Changes

| File | Change |
|------|--------|
| `ktrdr/indicators/__init__.py` | Added `ensure_all_registered()`, removed eager indicator imports |
| `ktrdr/indicators/indicator_engine.py` | Made convenience methods (`compute_sma`, etc.) use lazy imports |
| `ktrdr/config/strategy_validator.py` | Added `_get_indicator_registry()` helper for lazy import |
| `ktrdr/api/services/indicator_service.py` | Call `ensure_all_registered()` before listing indicators |
| `ktrdr/api/endpoints/strategies.py` | Call `ensure_all_registered()` before listing indicators |
| `tests/unit/indicators/*.py` | Updated imports from `ktrdr.indicators` to specific modules |
| `tests/indicators/indicator_registry.py` | Updated imports to specific modules |

### Gotchas

**Import from specific modules**: Code importing indicator classes should use specific module imports:
```python
# ✅ Correct - imports from specific module
from ktrdr.indicators.rsi_indicator import RSIIndicator

# ❌ Wrong - no longer exported from package
from ktrdr.indicators import RSIIndicator  # ImportError!
```

**Registry access pattern**: Code needing the full registry should call `ensure_all_registered()` first:
```python
from ktrdr.indicators import INDICATOR_REGISTRY, ensure_all_registered

ensure_all_registered()  # Load all 31 indicators
for name in INDICATOR_REGISTRY.list_types():
    ...
```

**Circular import in strategy_validator**: Use the lazy import helper `_get_indicator_registry()` instead of direct import.

### E2E Results

```
✅ 31 canonical indicator types registered
✅ All indicators have Params class
✅ Case-insensitive lookup works (ATR, atr, MACD, BollingerBands, etc.)
✅ indicator_factory.py deleted
✅ schemas.py deleted
✅ make test-unit passes (4784 tests)
✅ make quality passes
✅ CLI import time: ~170ms in test mode (under 200ms target)
```

### M2 Milestone Complete

All success criteria from the milestone file have been validated:
- [x] indicator_factory.py does not exist
- [x] schemas.py does not exist
- [x] INDICATOR_REGISTRY.list_types() returns 31 types (not 39 - see note below)
- [x] All 31 have Params class inheriting from BaseModel
- [x] Case-insensitive lookup works for all
- [x] IndicatorEngine has no BUILT_IN_INDICATORS references
- [x] All indicators instantiate with defaults

**Note on count**: The milestone file stated 39, but the actual count is 31 unique indicator classes. The 39 figure was the number of lookup keys in the old factory (including aliases like "bbands" and "stoch"). The registry has 31 canonical names and 63 total lookup names (including aliases).
