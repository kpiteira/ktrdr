# M4: Cleanup Handoff

## Task 4.1 Complete: Remove redundant validation from indicators

**Status:** No changes needed — acceptance criteria already met.

**Findings:**
All files mentioned in task already use Params classes correctly with `DataError` (not `ValueError`):
- `ktrdr/indicators/ad_line.py` — Params with `use_sma_smoothing`, `smoothing_period`
- `ktrdr/indicators/donchian_channels.py` — Params with `period`, `include_middle`
- `ktrdr/indicators/fisher_transform.py` — Params with `period`, `smoothing`
- `ktrdr/indicators/keltner_channels.py` — Params with `period`, `atr_period`, `multiplier`
- `ktrdr/indicators/adx_indicator.py` — Params with `period`
- `ktrdr/indicators/cmf_indicator.py` — Params with `period`
- `ktrdr/indicators/supertrend_indicator.py` — Params with `period`, `multiplier`
- `ktrdr/indicators/zigzag_indicator.py` — Params with `threshold`, `source`

None have `_validate_params` overrides or `raise ValueError` for param validation.

**Verification:**
```bash
grep -rn "raise ValueError" ktrdr/indicators/*.py | grep -v indicator_engine
# Returns: No matches (criteria met)
```

**Tests:** 4900 passed, 5 skipped

---

## Task 4.1b Complete: Remove double validation in compute() methods

**Status:** No changes needed — no `_validate_params` calls exist in any `compute()` methods.

**Verification:**
- Only calls are in `base_indicator.py:163` inside `__init__` (correct for old-style)
- No compute() method calls `_validate_params`

---

## Task 4.2 Complete: Replace assert statements in FuzzyEngine

**Status:** No changes needed — no `assert isinstance` or any `assert` statements exist in `engine.py`.

---

## Task 4.3 Complete: Fix [CRITICAL BUG] workaround

**Changes made:**
- `ktrdr/indicators/williams_r_indicator.py` — Replaced scary log with proper `DataError`
- `ktrdr/indicators/ma_indicators.py` — Same fix for EMA

**Before (workaround):**
```python
if isinstance(high_data, pd.DataFrame):
    logger.error("[CRITICAL BUG] data['high'] returned DataFrame!")
    high_data = high_data.iloc[:, 0]  # Silently take first column
```

**After (proper error):**
```python
if duplicate_cols:
    raise DataError(
        message=f"Williams %R received DataFrame with duplicate columns: {duplicate_cols}",
        error_code="DATA-DuplicateColumns",
        details={"duplicate_columns": duplicate_cols}
    )
```

---

## Task 4.4 Complete: Remove dead code

**Changes made:**
- Removed `BollingerBandsIndicator.get_name()` method (unused)
- Removed corresponding test `test_get_name_method`

---

## Task 4.5 Complete: Execute M4 E2E Test

**All checks passed:**
- [x] No ValueError in indicator param validation
- [x] No _validate_params calls in compute() methods
- [x] No assert isinstance in FuzzyEngine
- [x] No [CRITICAL BUG] in codebase
- [x] No dead get_name() method
- [x] Invalid params raise DataError (tested: adx, cmf, keltnerchannels)
- [x] `make test-unit` passes (4899 passed, 5 skipped)
- [x] `make quality` passes

**M4 Milestone Complete.**

---

