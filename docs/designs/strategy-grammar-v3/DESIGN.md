# Strategy Grammar v3: Design

## Problem Statement

The current strategy grammar conflates three distinct concepts:
1. **Indicator definition** — The calculation (e.g., "RSI with period 14")
2. **Fuzzy interpretation** — How to interpret indicator values (e.g., "oversold when RSI < 30")
3. **Data source** — Which timeframe's data to compute on (e.g., "5-minute bars")

**The root cause:** We called `rsi_14` a `feature_id`, but it's not a feature — it's an indicator. Features are neural network inputs. This terminology error made it seem like the indicator WAS the feature, leading to confusion about where timeframes belong.

This causes:
- Duplicate indicator definitions when the same indicator is used on multiple timeframes
- Semantic confusion (the `timeframe` field on indicators isn't a parameter, it's a data source)
- Inconsistent handling between training and backtesting pipelines
- Implicit NN inputs that are hard to reason about

## Terminology

| Term | What it is | Example |
|------|-----------|---------|
| `indicator_id` | Identifies a calculation | `rsi_14` |
| `fuzzy_set_id` | Identifies an interpretation of indicator values | `rsi_fast` |
| `feature_id` | An actual NN input (timeframe + fuzzy_set + membership) | `5m_rsi_fast_oversold` |

**The transformation chain:**
```
indicator_id → indicator value → fuzzy_set_id → membership degree → feature_id
   rsi_14    →      45.2       →   rsi_fast   →   oversold: 0.0   → 5m_rsi_fast_oversold
                                               →   neutral: 0.8    → 5m_rsi_fast_neutral
                                               →   overbought: 0.1 → 5m_rsi_fast_overbought
```

## Goals

1. **Separation of concerns**: Indicator definitions, fuzzy interpretations, and NN inputs are distinct
2. **Explicit NN inputs**: The strategy clearly states what the neural network receives
3. **No duplication**: Each indicator is defined once, even when used on multiple timeframes
4. **Flexibility**: Different fuzzy interpretations can be applied to different timeframes
5. **Simplicity**: The common case (same fuzzy sets on all timeframes) remains easy

## Non-Goals

- Backward compatibility with v2 format (we'll provide migration tooling)
- Per-symbol fuzzy set variations (not a common need)
- Dynamic/runtime fuzzy set selection

---

## The New Grammar

### Overview

A strategy has four main sections:

```yaml
name: "my_strategy"
version: "3.0"

# 1. What data to load
training_data:
  symbols: [EURUSD, GBPUSD]
  timeframes: [5m, 1h, 1d]

# 2. How to calculate indicators (pure definitions)
indicators:
  rsi_14:
    type: rsi
    period: 14

# 3. How to interpret indicator values (fuzzy memberships)
fuzzy_sets:
  rsi_momentum:
    indicator: rsi_14
    oversold: [0, 20, 35]
    overbought: [65, 80, 100]

# 4. What the neural network sees
nn_inputs:
  - fuzzy_set: rsi_momentum
    timeframes: [5m, 1h, 1d]
```

### Section 1: `training_data`

Defines what data to load. Unchanged from v2.

```yaml
training_data:
  symbols:
    mode: multi_symbol
    list: [EURUSD, GBPUSD, USDJPY]
  timeframes:
    mode: multi_timeframe
    list: [5m, 1h, 1d]
    base_timeframe: 1h
  history_required: 300
```

### Section 2: `indicators`

Pure indicator definitions. Each indicator has a unique ID (the key) and its calculation parameters.

```yaml
indicators:
  # Key is the indicator ID, used to reference it in fuzzy_sets
  rsi_14:
    type: rsi
    period: 14
    source: close      # Optional, defaults to close

  rsi_7:
    type: rsi
    period: 7

  macd_12_26_9:
    type: macd
    fast_period: 12
    slow_period: 26
    signal_period: 9

  bbands_20_2:
    type: bbands
    period: 20
    multiplier: 2.0
```

**Key changes from v2:**
- No `feature_id` field — the key IS the ID
- No `name` field — `type` specifies the indicator type
- No `timeframe` field — timeframes are specified in `nn_inputs`

### Section 3: `fuzzy_sets`

Fuzzy interpretations of indicator values. Each fuzzy set references an indicator and defines membership functions.

```yaml
fuzzy_sets:
  # Key is the fuzzy set ID, used in nn_inputs
  rsi_momentum:
    indicator: rsi_14           # Which indicator to interpret
    oversold:                   # Membership function name
      type: triangular
      parameters: [0, 20, 35]
    neutral:
      type: triangular
      parameters: [30, 50, 70]
    overbought:
      type: triangular
      parameters: [65, 80, 100]

  rsi_extreme:                  # Different interpretation of same indicator
    indicator: rsi_14
    very_oversold:
      type: triangular
      parameters: [0, 10, 20]
    very_overbought:
      type: triangular
      parameters: [80, 90, 100]

  macd_trend:
    indicator: macd_12_26_9
    bearish:
      type: triangular
      parameters: [-50, -10, 0]
    bullish:
      type: triangular
      parameters: [0, 10, 50]
```

**Key changes from v2:**
- Fuzzy set key is no longer coupled to indicator ID
- Explicit `indicator` field links to the indicator definition
- Multiple fuzzy sets can reference the same indicator

### Section 4: `nn_inputs`

Explicit definition of neural network inputs. This is the source of truth for what features the model receives.

```yaml
nn_inputs:
  # Each entry specifies a fuzzy set and which timeframes to apply it to
  - fuzzy_set: rsi_momentum
    timeframes: [5m, 1h]        # Apply this interpretation to 5m and 1h

  - fuzzy_set: rsi_extreme
    timeframes: [1d]            # Different interpretation for daily

  - fuzzy_set: macd_trend
    timeframes: all             # Shorthand: all training timeframes
```

**Generated features:**
For the above config with `training_data.timeframes: [5m, 1h, 1d]`:

```
5m_rsi_momentum_oversold
5m_rsi_momentum_neutral
5m_rsi_momentum_overbought
1h_rsi_momentum_oversold
1h_rsi_momentum_neutral
1h_rsi_momentum_overbought
1d_rsi_extreme_very_oversold
1d_rsi_extreme_very_overbought
5m_macd_trend_bearish
5m_macd_trend_bullish
1h_macd_trend_bearish
1h_macd_trend_bullish
1d_macd_trend_bearish
1d_macd_trend_bullish
```

### Feature Naming Convention

Features are named: `{timeframe}_{fuzzy_set_id}_{membership_name}`

Examples:
- `5m_rsi_momentum_oversold`
- `1h_macd_trend_bullish`
- `1d_rsi_extreme_very_overbought`

This is:
- **Unambiguous**: No collision possible
- **Traceable**: You can find the fuzzy set definition from the name
- **Consistent**: Same pattern everywhere

---

## Complete Example

```yaml
name: "mtf_forex_momentum"
description: "Multi-timeframe forex strategy with timeframe-adapted RSI interpretation"
version: "3.0"

# What data to use
training_data:
  symbols:
    mode: multi_symbol
    list: [EURUSD, GBPUSD, USDJPY]
  timeframes:
    mode: multi_timeframe
    list: [5m, 1h, 1d]
    base_timeframe: 1h
  history_required: 300

# Indicator calculations (defined once)
indicators:
  rsi_14:
    type: rsi
    period: 14

  macd_12_26_9:
    type: macd
    fast_period: 12
    slow_period: 26
    signal_period: 9

  atr_14:
    type: atr
    period: 14

# Fuzzy interpretations
fuzzy_sets:
  rsi_fast:
    indicator: rsi_14
    oversold:
      type: triangular
      parameters: [0, 25, 40]
    neutral:
      type: triangular
      parameters: [35, 50, 65]
    overbought:
      type: triangular
      parameters: [60, 75, 100]

  rsi_slow:
    indicator: rsi_14
    oversold:
      type: triangular
      parameters: [0, 15, 25]
    neutral:
      type: triangular
      parameters: [20, 50, 80]
    overbought:
      type: triangular
      parameters: [75, 85, 100]

  macd_momentum:
    indicator: macd_12_26_9
    bearish:
      type: triangular
      parameters: [-50, -10, 0]
    neutral:
      type: triangular
      parameters: [-5, 0, 5]
    bullish:
      type: triangular
      parameters: [0, 10, 50]

  volatility_regime:
    indicator: atr_14
    low:
      type: triangular
      parameters: [0, 0.5, 1.5]
    moderate:
      type: triangular
      parameters: [1.0, 2.0, 3.5]
    high:
      type: triangular
      parameters: [3.0, 5.0, 10.0]

# Neural network inputs (explicit)
nn_inputs:
  - fuzzy_set: rsi_fast
    timeframes: [5m]            # Fast RSI interpretation for scalping TF

  - fuzzy_set: rsi_slow
    timeframes: [1h, 1d]        # Slow RSI interpretation for trend TFs

  - fuzzy_set: macd_momentum
    timeframes: [1h]            # MACD only on intermediate TF

  - fuzzy_set: volatility_regime
    timeframes: all             # Volatility context on all TFs

# Model configuration (unchanged from v2)
model:
  type: mlp
  architecture:
    hidden_layers: [128, 64, 32]
    activation: relu
    dropout: 0.3
  training:
    learning_rate: 0.001
    epochs: 100
    batch_size: 32

# Decision logic (unchanged from v2)
decisions:
  output_format: classification
  confidence_threshold: 0.65

# Training labels (unchanged from v2)
training:
  method: supervised
  labels:
    source: zigzag
    zigzag_threshold: 0.025
```

---

## Key Decisions

### Decision 1: Indicators as a dictionary (not a list)

**Choice:** `indicators` is a dict where keys are indicator IDs

**Alternatives considered:**
- List with `id` field (current v2 approach)
- List with auto-generated IDs

**Rationale:** Dict keys are naturally unique and provide direct lookup. No need for separate `feature_id` field.

### Decision 2: Fuzzy sets reference indicators explicitly

**Choice:** Each fuzzy set has an `indicator` field pointing to an indicator ID

**Alternatives considered:**
- Fuzzy set key must match indicator ID (current v2 approach)
- Nested structure: indicators contain their fuzzy sets

**Rationale:** Explicit reference allows multiple fuzzy interpretations of the same indicator, which is the core use case for multi-timeframe strategies.

### Decision 3: `nn_inputs` is the source of truth

**Choice:** The `nn_inputs` section explicitly lists what the model receives

**Alternatives considered:**
- Implicit: all fuzzy sets × all timeframes
- Hybrid: fuzzy sets define their timeframes

**Rationale:** Explicit is better than implicit. You can read `nn_inputs` and know exactly what features the model sees. This also means only necessary indicators get computed.

### Decision 4: Feature naming as `{timeframe}_{fuzzy_set}_{membership}`

**Choice:** Use fuzzy set ID in feature name, not indicator ID

**Alternatives considered:**
- `{timeframe}_{indicator}_{membership}` (current v2)
- `{fuzzy_set}_{timeframe}_{membership}`

**Rationale:** The fuzzy set ID is what matters for the NN. Two fuzzy sets on the same indicator produce different features. Timeframe first for easy grouping/sorting.

---

## Migration Path

### From v2 to v3

1. **Indicators**: Convert list to dict, rename `name` to `type`, remove `feature_id`
2. **Fuzzy sets**: Add `indicator` field pointing to the appropriate indicator ID
3. **NN inputs**: Generate from `training_data.timeframes` × fuzzy_sets (preserves current behavior)

Example migration:

**v2:**
```yaml
indicators:
  - name: rsi
    feature_id: rsi_14
    period: 14

fuzzy_sets:
  rsi_14:
    oversold:
      type: triangular
      parameters: [0, 20, 35]

training_data:
  timeframes:
    list: [1h, 1d]
```

**v3:**
```yaml
indicators:
  rsi_14:
    type: rsi
    period: 14

fuzzy_sets:
  rsi_14:
    indicator: rsi_14
    oversold:
      type: triangular
      parameters: [0, 20, 35]

nn_inputs:
  - fuzzy_set: rsi_14
    timeframes: all
```

### Tooling

- `ktrdr strategy migrate <path>` — Migrate v2 strategy to v3
- `ktrdr strategy validate <path>` — Validate v3 strategy
- `ktrdr strategy features <path>` — List generated NN input features

---

## Design Decisions (Resolved)

1. **Shorthand for simple fuzzy sets?**
   **Decision: Yes.** Allow inline triangular notation for conciseness:

   ```yaml
   fuzzy_sets:
     rsi_momentum:
       indicator: rsi_14
       oversold: [0, 20, 35]      # Shorthand for triangular
       overbought: [65, 80, 100]
   ```

2. **Default timeframes?**
   **Decision: Require explicit.** If `nn_inputs` is omitted, the strategy is invalid.
   Explicit is better than implicit — you should always know what your NN sees.

3. **Unused indicator validation?**
   **Decision: Warn.** If an indicator is defined but never referenced in any fuzzy set,
   emit a warning during validation. This catches copy-paste errors without blocking.
