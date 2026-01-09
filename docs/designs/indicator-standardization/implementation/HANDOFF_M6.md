# Handoff Document: Milestone 6 (Cleanup)

This document captures learnings from M6 cleanup tasks.

---

## Task 6.1 Complete: Remove Old Format Detection

### What Was Removed

**Location:** `ktrdr/indicators/indicator_engine.py:350-390`

The old-format handling branch in `compute_indicator()` was removed. This branch:
- Detected indicators returning columns with params embedded (e.g., `upper_20_2.0`)
- Passed through those columns unchanged
- Added an alias column for the primary output

### New Behavior

After M6.1, `compute_indicator()` raises `ValueError` when multi-output indicators return columns that don't match `get_output_names()`:

```python
ValueError: Indicator MockOldFormatIndicator output mismatch:
expected columns ['lower', 'middle', 'upper'],
got ['lower_20_2.0', 'middle_20_2.0', 'upper_20_2.0'].
Indicator must return columns matching get_output_names().
```

### Key Pattern

The three branches in `compute_indicator()` are now:
1. **Exact match** → Prefix columns with `indicator_id.`
2. **Partial overlap** → Raise `ProcessingError` (bug in indicator)
3. **No overlap** → Raise `ValueError` (old format, not migrated)

### Test Changes

- `tests/unit/indicators/test_indicator_engine_v3_only.py` — New tests for v3-only behavior
- `tests/unit/indicators/test_indicator_engine_adapter.py` — Updated old-format tests to expect errors

---

## Task 6.2 Complete: Remove Deprecated Methods

### What Was Removed

**`get_primary_output_suffix()`** removed from:
- `ktrdr/indicators/base_indicator.py` (BaseIndicator)
- `ktrdr/indicators/adx_indicator.py`
- `ktrdr/indicators/aroon_indicator.py`
- `ktrdr/indicators/bollinger_bands_indicator.py`
- `ktrdr/indicators/donchian_channels.py`
- `ktrdr/indicators/ichimoku_indicator.py`
- `ktrdr/indicators/keltner_channels.py`
- `ktrdr/indicators/macd_indicator.py`
- `ktrdr/indicators/rvi_indicator.py`
- `ktrdr/indicators/stochastic_indicator.py`
- `ktrdr/indicators/supertrend_indicator.py`

**Use instead:** `get_primary_output()` (returns first element of `get_output_names()`)

### Methods NOT Removed (Still In Use)

The following were identified for removal but are still in active use:

| Method | Used By | Reason Can't Remove |
|--------|---------|---------------------|
| `get_column_name()` | `get_feature_id()`, indicator subclasses | Fallback for feature ID generation |
| `get_feature_id()` | `apply()` in IndicatorEngine | V2 API path still used across codebase |
| `_feature_id` | `get_feature_id()`, IndicatorFactory | Set by factory, used for v2 indicators |
| `_timeframe` | `get_column_name()`, IndicatorFactory | Multi-timeframe column prefixing |

**Note:** These can be removed once `apply()` is deprecated in favor of `compute()`.

### Test Changes

- `tests/unit/indicators/test_deprecated_methods_removed.py` — Verifies `get_primary_output_suffix` is gone
- `tests/unit/indicators/test_base_indicator.py` — Removed backward compat tests

### Notes for Task 6.3

No `CLEANUP(v3)` comments remain in `ktrdr/`. All deprecated code with that marker has been addressed.

Task 6.3 should delete `column_standardization.py` if it's no longer imported.
