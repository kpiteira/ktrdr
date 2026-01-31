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
