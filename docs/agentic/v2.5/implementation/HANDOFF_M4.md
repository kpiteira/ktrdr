# Handoff: M4 Fix Multi-Symbol Pipeline

## Root Cause Identified

**The multi-symbol training failure is caused by feature/label size mismatch per symbol.**

The issue occurs when:
1. `create_features()` uses `fuzzy_data` (may have fewer rows due to indicator warmup)
2. `create_labels()` uses `price_data` (has original row count)
3. If row counts differ, tensors cannot be properly combined → leads to `X_test = None`

**Example scenario:**
```
price_data[1d]: 1000 rows
fuzzy_data[1d]: 986 rows (14 rows lost to indicator warmup)
features: 986 samples
labels: 1000 samples
→ Size mismatch detected!
```

## Gotchas

### Early Validation Now Catches Mismatches
- **Problem:** Previously, size mismatches propagated to train/test split causing `X_test = None`
- **New behavior:** `TrainingDataError` raised immediately with detailed diagnostics
- **Symptom:** If you see `Feature/label size mismatch for symbol X`, check indicator warmup period

### Debug Logging in Production
The preprocessing trace logs show row counts at each step:
```
📊 [EURUSD] Preprocessing trace:
   • price_data[1d]: 1000 rows
   • fuzzy_data[1d]: 986 rows
   • features: 986 samples, 36 dims
   • labels: 1000 samples
```
This helps identify exactly where data is lost.

## Emergent Patterns

### Validation Sequence
The validation now happens at two levels:
1. **Per-symbol validation** (in `train_strategy()`) - catches feature/label mismatch early
2. **Combination validation** (in `combine_multi_symbol_data()`) - catches cross-symbol issues

### The Fix Path

To actually fix the multi-symbol bug (Task 4.2), likely solutions:
1. **Align features and labels to same index** - Use fuzzy_data's index for labels too
2. **Drop warmup rows from price_data before labeling** - Match fuzzy_data row count
3. **Forward-fill missing fuzzy values** - Instead of dropping rows

## Notes for Task 4.2

The logging added in Task 4.1 will show exactly which symbols have mismatches and why. Run a real multi-symbol training to see the actual values:

```bash
# Trigger multi-symbol research
curl -X POST http://localhost:8000/api/v1/agent/trigger \
  -H "Content-Type: application/json" \
  -d '{"brief": "Train on EURUSD, GBPUSD, USDJPY with RSI", "model": "haiku"}'

# Check backend logs for the preprocessing trace
docker logs ktrdr-backend --since 5m | grep -E "Preprocessing trace|mismatch"
```
