# Investigation: Strategy Validation Failure

**Date**: 2025-12-15
**Issue**: Claude-designed strategies fail TrainingService validation
**Status**: ✅ FIXED (commit e9edfbf)

---

## Problem Statement

When the agent triggers a research cycle:
1. Design phase completes successfully (Claude designs a strategy, saves it)
2. Training phase fails immediately with validation error

```
[STRATEGY-ValidationFailed] Strategy validation failed: 1 error(s) found
```

---

## Root Cause Analysis

### Finding 1: Two Different Validation Systems

There are **two separate validation systems** with different rules:

| Validator | Location | Used By |
|-----------|----------|---------|
| `StrategyValidator` | `ktrdr/config/strategy_validator.py` | Agent's `validate_strategy_config` and `save_strategy_config` tools |
| `_validate_strategy_config` | `ktrdr/api/endpoints/strategies.py` | TrainingService before training starts |

The agent's validator **passes**, but the training validator **fails**.

### Finding 2: Case Sensitivity Mismatch

The training validator's fuzzy set validation is **case-sensitive** and fails due to case mismatch:

**Working Strategy** (`neuro_mean_reversion.yaml`):
```yaml
indicators:
- name: "rsi"      # lowercase
  feature_id: rsi_14

fuzzy_sets:
  rsi_14:          # base_name = "rsi"
    oversold: ...
```
- Indicator name: `rsi` (lowercase)
- Fuzzy set key: `rsi_14` → base name `rsi`
- Comparison: `rsi` in `{"rsi", ...}` ✅

**Failing Strategy** (`trend_harmony_confluence_20251215_013225.yaml`):
```yaml
indicators:
- name: Ichimoku   # PascalCase
  feature_id: ichimoku_9

fuzzy_sets:
  ichimoku_9:      # base_name = "ichimoku"
    bearish_cloud: ...
```
- Indicator name: `Ichimoku` (PascalCase)
- Fuzzy set key: `ichimoku_9` → base name `ichimoku`
- Comparison: `ichimoku` in `{"Ichimoku", ...}` ❌ **Case mismatch!**

### Finding 3: API Returns PascalCase Names

The `/api/v1/indicators/` endpoint returns:
```json
{"id": "IchimokuIndicator", "name": "Ichimoku", ...}
{"id": "RSIIndicator", "name": "RSI", ...}
{"id": "SuperTrendIndicator", "name": "SuperTrend", ...}
```

Claude uses these PascalCase names because that's what the API provides.

### Validation Code (Relevant Section)

```python
# ktrdr/api/endpoints/strategies.py, line ~450
# Extract base indicator name (e.g., "rsi_14" -> "rsi")
base_name = fuzzy_name.split("_")[0]

# Check both the full name and the base name
if (
    fuzzy_name not in all_possible_targets     # "ichimoku_9" not in {"Ichimoku", ...}
    and base_name not in all_possible_targets  # "ichimoku" not in {"Ichimoku", ...} ← FAILS
):
    invalid_fuzzy_refs.append(fuzzy_name)
```

The comparison is case-sensitive, so `ichimoku != Ichimoku`.

---

## Fix Options

### Option A: Fix Training Validator (Recommended)

Make the fuzzy set validation case-insensitive by lowercasing both sides:

```python
# Build all_possible_targets with lowercase names
all_possible_targets_lower = {name.lower() for name in all_possible_targets}

# Compare with lowercase
if (
    fuzzy_name.lower() not in all_possible_targets_lower
    and base_name.lower() not in all_possible_targets_lower
):
    invalid_fuzzy_refs.append(fuzzy_name)
```

**Pros**:
- Single fix in one location
- Backward compatible
- Doesn't require changes to Claude's prompts

**Cons**:
- Slightly more permissive validation

### Option B: Modify Claude's Prompts

Update the system prompt to instruct Claude to use lowercase indicator names:

```
When specifying indicator names in strategies, always use lowercase
(e.g., "rsi" not "RSI", "ichimoku" not "Ichimoku")
```

**Pros**:
- No code changes
- Makes generated strategies match existing patterns

**Cons**:
- Prompt engineering is fragile
- Claude might still use PascalCase based on API response
- Need to regenerate prompt for all design tools

### Option C: Fix API Response

Change the indicators API to return lowercase names:

```json
{"id": "IchimokuIndicator", "name": "ichimoku", ...}
```

**Pros**:
- Fixes root cause at source
- Consistent with existing working strategies

**Cons**:
- Breaking change for existing API consumers
- May need migration for existing strategies

### Option D: Align Both Validators

Merge the two validators or ensure they have identical rules.

**Pros**:
- Eliminates validation divergence
- Single source of truth

**Cons**:
- Larger refactor
- Risk of breaking existing save functionality

---

## Recommendation

**Option A** is the safest and most targeted fix:
1. Minimal code change (one location)
2. No breaking changes
3. Fixes the immediate problem
4. Backward compatible with existing strategies

If we want a longer-term solution, we could also implement **Option D** to unify the validators, but that's a larger scope.

---

## Test Plan (for chosen fix)

1. Run existing strategy validation tests
2. Validate a working strategy (should still pass)
3. Validate a Claude-generated strategy with PascalCase names (should now pass)
4. Trigger a full agent cycle and verify training starts

---

## Files Involved

| File | Role |
|------|------|
| `ktrdr/api/endpoints/strategies.py` | Training validator with case-sensitive check |
| `ktrdr/config/strategy_validator.py` | Agent's validator (doesn't have this check) |
| `ktrdr/agents/strategy_utils.py` | Uses agent's validator for save |
| `ktrdr/api/services/training/context.py` | Calls training validator before training |

---

## Next Steps

1. Discuss fix options with Karl
2. Implement chosen fix
3. Add test case for case-insensitive fuzzy set validation
4. Re-run E2E test to verify full cycle completes
