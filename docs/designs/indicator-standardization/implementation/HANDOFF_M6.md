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

### Notes for Task 6.2

The remaining `CLEANUP(v3)` comments are in:
- `ktrdr/indicators/base_indicator.py:155` — `get_primary_output_suffix()`
- `ktrdr/indicators/rvi_indicator.py:63` — same deprecated method

These are deprecated methods that should be removed in Task 6.2.
