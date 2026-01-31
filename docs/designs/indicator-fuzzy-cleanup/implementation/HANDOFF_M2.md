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
