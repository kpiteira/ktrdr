# Handoff: M4 Fix Multi-Symbol Pipeline

## Finding: Multi-Symbol Training Works Correctly

**After E2E testing, multi-symbol training works correctly.** The original concern about `X_test = None` for multi-symbol strategies is NOT occurring.

### E2E Test Results (2026-01-04)

```text
📊 [EURUSD] Preprocessing trace:
   • price_data[1d]: 1288 rows
   • fuzzy_data[1d]: 1288 rows
   • features: 1288 samples, 9 dims
   • labels: 1288 samples

📊 [GBPUSD] Preprocessing trace:
   • price_data[1d]: 1288 rows
   • fuzzy_data[1d]: 1288 rows
   • features: 1288 samples, 9 dims
   • labels: 1288 samples

📊 [USDJPY] Preprocessing trace:
   • price_data[1d]: 1288 rows
   • fuzzy_data[1d]: 1288 rows
   • features: 1288 samples, 9 dims
   • labels: 1288 samples

🔗 Combining data from 3 symbols:
   EURUSD: 1288 samples, 9 features
   GBPUSD: 1288 samples, 9 features
   USDJPY: 1288 samples, 9 features
✅ Combined total: 3864 samples, 9 features
```

**Training result:** `test_accuracy = 0.4935` (49.35%)

## What Was Added

1. **Preprocessing trace logging** - Shows row counts at each step per symbol
2. **Early validation** - Raises `TrainingDataError` if feature/label sizes don't match
3. **Combination validation** - Checks for empty data, dimension mismatches
4. **Unit tests** - `test_multi_symbol_data_alignment.py` (7 tests)

## Separate Bug Discovered

The training operation returns correct metrics:

```json
"test_metrics": {"test_accuracy": 0.4935...}
```

But the experiment file shows:

```yaml
test_accuracy: 0
```

**This is a bug in the research worker's experiment saving code**, not in the training pipeline. Should be tracked as a separate issue.

## Tasks Status

- **Task 4.1** ✅ Complete - Added logging, confirmed multi-symbol works
- **Task 4.2** ⏭️ Skip - No bug to fix in training pipeline
- **Task 4.3** 📋 Optional - E2E test could serve as regression guard

## Validation Sequence (For Future Reference)

The validation now happens at two levels:

1. **Per-symbol** (in `train_strategy()`) - catches feature/label mismatch early
2. **Combination** (in `combine_multi_symbol_data()`) - catches cross-symbol issues
