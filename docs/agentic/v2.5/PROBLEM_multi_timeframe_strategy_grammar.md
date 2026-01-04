# Problem Statement: Multi-Timeframe Strategy Grammar

**Date:** 2026-01-04
**Discovered during:** M5 (Fix Multi-Timeframe Pipeline)
**Status:** Design needed

---

## Current State

Strategies currently define indicators with a `timeframe` field:

```yaml
indicators:
- name: RSI
  feature_id: rsi_5m
  period: 14
  timeframe: 5m
- name: RSI
  feature_id: rsi_1h
  period: 14
  timeframe: 1h

fuzzy_sets:
  rsi_5m:
    oversold: ...
  rsi_1h:
    oversold: ...
```

The `timeframe` field is treated as if it were an indicator parameter, but it's not.

---

## The Problem

**An indicator's parameters define the indicator. A timeframe defines which data it operates on.**

These are fundamentally different concepts:

| Concept | Example | Belongs to |
|---------|---------|------------|
| Indicator parameter | `period: 14` | Indicator definition |
| Data source | `timeframe: 5m` | Data/execution context |

Current problems:

1. **Semantic confusion**: `timeframe` appears as an indicator parameter but isn't one
2. **Duplication**: Same indicator (RSI-14) is defined twice with identical parameters
3. **Implicit coupling**: The `feature_id` naming convention (`rsi_5m`) encodes the timeframe, creating redundancy
4. **No validation**: Nothing enforces that `feature_id: rsi_5m` actually uses 5m data
5. **Unclear intent**: Is this "RSI computed on 5m data" or "RSI that should only be used for 5m strategies"?

---

## Impact

### Training Path
- Works because `FuzzyNeuralProcessor` uses the `feature_id` (from fuzzy_sets keys) and adds timeframe prefix
- The indicator `timeframe` field is largely ignored
- Final features: `5m_rsi_5m_oversold`, `1h_rsi_1h_oversold`

### Backtest Path
- Had collisions because both indicators produced `rsi_14`
- Required workaround: store `timeframe` on indicator, prefix column names
- Still semantically wrong - we're patching around a grammar problem

### Agent (Strategy Design)
- Must understand this implicit convention when generating strategies
- No clear specification of "compute RSI on all timeframes" vs "compute RSI only on 5m"

---

## Questions to Resolve

### 1. Indicator Definition vs Application

Should we separate these?

**Option A: Current (implicit)**
```yaml
indicators:
- name: RSI
  feature_id: rsi_5m
  period: 14
  timeframe: 5m  # Implicit: "compute on 5m data"
```

**Option B: Explicit mapping**
```yaml
indicators:
- name: RSI
  id: rsi_14
  period: 14

indicator_timeframes:
  rsi_14: [5m, 1h]  # Compute this indicator on these timeframes
```

**Option C: Timeframe in fuzzy_sets only**
```yaml
indicators:
- name: RSI
  period: 14  # No feature_id, no timeframe

fuzzy_sets:
  5m:
    rsi:  # Implicitly uses RSI on 5m data
      oversold: ...
  1h:
    rsi:  # Implicitly uses RSI on 1h data
      oversold: ...
```

### 2. Feature Naming Convention

How should features be named?

| Convention | Example | Pros | Cons |
|------------|---------|------|------|
| `{timeframe}_{indicator}_{param}` | `5m_rsi_14` | Clear, systematic | Verbose |
| `{indicator}_{timeframe}` | `rsi_5m` | Current convention | Ambiguous (is 5m a param?) |
| `{timeframe}/{indicator}` | Hierarchical | Clean separation | Breaking change |

### 3. Backward Compatibility

How do we handle existing strategies?

- Validate and reject old format?
- Auto-migrate on load?
- Support both formats with deprecation warning?

### 4. What Does `timeframe` on Indicator Mean?

Current interpretations (all different!):

1. **Training**: "Compute this indicator on this timeframe's OHLCV data"
2. **Backtest**: "Prefix column name with this timeframe" (workaround)
3. **Agent**: "This indicator is conceptually associated with this timeframe"

We need ONE clear meaning.

---

## Proposed Direction

The cleanest solution separates concerns:

```yaml
# Strategy specifies which timeframes to use
training_data:
  timeframes: [5m, 1h]

# Indicators are defined once (parameters only)
indicators:
- name: RSI
  period: 14
- name: SMA
  period: 20

# Fuzzy sets specify which indicator+timeframe combinations to use
fuzzy_sets:
  5m_rsi:      # System computes RSI on 5m, names it "5m_rsi"
    oversold: [0, 25, 40]
  1h_rsi:      # System computes RSI on 1h, names it "1h_rsi"
    oversold: [0, 30, 45]
  5m_sma:
    below: ...
```

The fuzzy_set key `{timeframe}_{indicator}` becomes the source of truth for:
- Which indicator to compute
- On which timeframe's data
- What to name the resulting feature

---

## Next Steps

1. [ ] Design review with Karl
2. [ ] Document chosen approach in DESIGN.md
3. [ ] Create migration plan for existing strategies
4. [ ] Update strategy validator
5. [ ] Update training pipeline
6. [ ] Update backtest pipeline
7. [ ] Update agent strategy generation prompts
