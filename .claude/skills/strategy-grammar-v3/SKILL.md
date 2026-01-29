---
name: strategy-grammar-v3
description: Use when working with V3 strategy YAML files, strategy configuration models (IndicatorDefinition, FuzzySetDefinition, NNInputSpec), feature resolution, strategy validation, strategy migration from V2, fuzzy set shorthand, multi-output indicators with dot notation, or agent strategy generation.
---

# Strategy Grammar V3

**When this skill is loaded, announce it to the user by outputting:**
`🛠️✅ SKILL strategy-grammar-v3 loaded!`

Load this skill when working on:

- V3 strategy YAML structure or examples
- Config models (IndicatorDefinition, FuzzySetDefinition, NNInputSpec)
- Strategy loading, validation, or migration
- Feature resolution and canonical ordering
- Multi-output indicators (dot notation)
- Fuzzy set shorthand expansion
- Agent strategy generation or validation
- Training/backtesting feature alignment

---

## Core Concept

V3 solves V2's fundamental problem: conflating indicators, fuzzy sets, and features.

**V3 has three cleanly separated sections:**

1. **Indicators** — What to compute (dict of calculation definitions)
2. **Fuzzy Sets** — How to interpret values (dict referencing indicators)
3. **NN Inputs** — What the model sees (explicit list of features)

### The Transformation Chain

```
indicator_id → value → fuzzy_set_id → membership degrees → feature_ids
   rsi_14    → 45.2  →  rsi_fast   → oversold: 0.0      → 5m_rsi_fast_oversold
                                    → neutral: 0.8       → 5m_rsi_fast_neutral
                                    → overbought: 0.1    → 5m_rsi_fast_overbought
```

### Feature Naming

`{timeframe}_{fuzzy_set_id}_{membership_name}` — unambiguous, traceable, consistent.

---

## V3 Strategy YAML Structure

```yaml
name: "my_strategy"
version: "3.0"

training_data:
  symbols:
    mode: single          # or multi_symbol
    symbol: EURUSD        # for single
    # list: [EURUSD, GBPUSD]  # for multi_symbol
  timeframes:
    mode: single          # or multi_timeframe
    timeframe: "1h"       # for single
    # list: ["5m", "1h", "1d"]  # for multi_timeframe
    # base_timeframe: "5m"      # for multi_timeframe

# Section 1: Pure calculation definitions
indicators:
  rsi_14:                 # Key IS the indicator_id
    type: rsi             # Indicator type
    period: 14            # Type-specific params
  macd_12_26_9:
    type: macd
    fast_period: 12
    slow_period: 26
    signal_period: 9

# Section 2: Interpretations of indicator values
fuzzy_sets:
  rsi_momentum:           # Key IS the fuzzy_set_id
    indicator: rsi_14     # REQUIRED: which indicator to interpret
    oversold: [0, 25, 40]       # Shorthand → triangular
    neutral: [35, 50, 65]
    overbought: [60, 75, 100]
  macd_trend:
    indicator: macd_12_26_9
    bearish: [-2, -0.5, 0]
    bullish: [0, 0.5, 2]

# Section 3: Explicit model inputs
nn_inputs:
  - fuzzy_set: rsi_momentum
    timeframes: all       # or ["5m", "1h"]
  - fuzzy_set: macd_trend
    timeframes: ["1h"]

model:
  type: mlp
  architecture:
    hidden_layers: [64, 32]
    activation: relu
    dropout: 0.2

decisions:
  output_format: classification
  confidence_threshold: 0.6

training:
  method: supervised
  labels:
    source: zigzag
    zigzag_threshold: 0.025
```

---

## V3 vs V2 Differences

| Aspect | V2 | V3 |
|--------|----|----|
| Indicators | List with `feature_id` field | Dict (keys are IDs) |
| Field name | `name` | `type` |
| Fuzzy linking | Implicit (key = indicator ID) | Explicit `indicator` field |
| NN inputs | Implicit (every fuzzy × every TF) | Explicit `nn_inputs` list |
| Feature name | `{indicator}_{membership}` | `{timeframe}_{fuzzy_set}_{membership}` |
| Multi-output | Not supported | Dot notation (`bbands_20_2.upper`) |
| Timeframe in indicator | Yes (`timeframe` field) | No (specified in `nn_inputs`) |

---

## Shorthand Notation

Array shorthand expands to full membership function at parse time:

```yaml
# Shorthand (preferred)
oversold: [0, 20, 35]

# Equivalent full form
oversold:
  type: triangular
  parameters: [0, 20, 35]
```

---

## Multi-Output Indicators (Dot Notation)

Indicators like Bollinger Bands, MACD, and ADX produce multiple outputs. Reference specific outputs with dot notation:

```yaml
indicators:
  bbands_20_2:
    type: bbands
    period: 20
    multiplier: 2.0

fuzzy_sets:
  bb_upper:
    indicator: bbands_20_2.upper    # Specific output
    high: [1.5, 2.0, 3.0]
  bb_lower:
    indicator: bbands_20_2.lower
    low: [-3.0, -2.0, -1.5]
```

Multi-output indicators and their outputs:

| Indicator | Outputs |
|-----------|---------|
| `bbands` | `upper`, `middle`, `lower` |
| `macd` | `line`, `signal`, `histogram` |
| `adx` | `adx`, `plus_di`, `minus_di` |
| `stochastic` | `k`, `d` |
| `ichimoku` | `tenkan`, `kijun`, `senkou_a`, `senkou_b`, `chikou` |

---

## Feature Resolution & Canonical Ordering

**Location:** `ktrdr/config/feature_resolver.py`

The `FeatureResolver` is the **single source of truth** for feature ordering. The order it produces MUST be preserved through training, checkpoint, and backtesting.

### Order Rules

1. `nn_inputs` list order (YAML order preserved)
2. Within each nn_input: timeframes order
3. Within each timeframe: membership function order

### Example

```yaml
nn_inputs:
  - fuzzy_set: rsi_momentum    # memberships: oversold, neutral, overbought
    timeframes: [5m, 1h]
```

Produces (in this exact order):
1. `5m_rsi_momentum_oversold`
2. `5m_rsi_momentum_neutral`
3. `5m_rsi_momentum_overbought`
4. `1h_rsi_momentum_oversold`
5. `1h_rsi_momentum_neutral`
6. `1h_rsi_momentum_overbought`

### Usage

```python
from ktrdr.config.feature_resolver import FeatureResolver, ResolvedFeature

resolver = FeatureResolver()
features: list[ResolvedFeature] = resolver.resolve(config)

# Each ResolvedFeature has:
#   feature_id, timeframe, fuzzy_set_id, membership_name,
#   indicator_id, indicator_output (None or "upper" etc.)

# Helper: which indicators needed for a timeframe
needed = resolver.get_indicators_for_timeframe(features, "1h")
```

---

## Pydantic Models

**Location:** `ktrdr/config/models.py`

```python
class IndicatorDefinition(BaseModel):
    type: str                          # rsi, macd, bbands, etc.
    model_config = {"extra": "allow"}  # Flat params (period, source, etc.)

class FuzzySetDefinition(BaseModel):
    indicator: str                     # indicator_id (supports dot notation)
    # Remaining fields = membership functions
    # Shorthand expanded at parse time by model_validator

class NNInputSpec(BaseModel):
    fuzzy_set: str                     # fuzzy_set_id
    timeframes: Union[list[str], str]  # "all" or ["5m", "1h"]

class StrategyConfigurationV3(BaseModel):
    name: str
    version: str = "3.0"
    training_data: TrainingDataConfiguration
    indicators: dict[str, IndicatorDefinition]
    fuzzy_sets: dict[str, FuzzySetDefinition]
    nn_inputs: list[NNInputSpec]
    model: dict[str, Any]
    decisions: dict[str, Any]
    training: dict[str, Any]
```

---

## Strategy Loading

**Location:** `ktrdr/config/strategy_loader.py`

```python
loader = StrategyConfigurationLoader()
config = loader.load_v3_strategy("path/to/strategy.yaml")
```

V3 detection: `indicators` is a dict AND `nn_inputs` is present.

If the file is V2 format, raises an error suggesting migration.

---

## Validation

**Location:** `ktrdr/config/strategy_validator.py`

### Validation Rules

1. All `indicator` references in fuzzy_sets exist in indicators
2. All `fuzzy_set` references in nn_inputs exist in fuzzy_sets
3. All timeframes in nn_inputs are valid ("all" or listed in training_data)
4. Dot notation outputs are valid for the indicator type
5. Warns about unused indicators (defined but not referenced)

### Agent-Specific Validation

- Indicator types must exist in `BUILT_IN_INDICATORS`
- Membership parameter counts must match type (triangular=3, trapezoid=4, etc.)
- Strategy name uniqueness

### Common Errors

| Error | Fix |
|-------|-----|
| `fuzzy_sets.X.indicator: 'Y' not found` | Create the indicator or fix the reference |
| `nn_inputs[0].fuzzy_set: 'X' not found` | Create the fuzzy set or fix the reference |
| `Invalid output 'Z' for indicator type` | Check indicator's `get_output_names()` |
| `Indicator 'X' defined but not referenced` | Warning — add fuzzy set or remove indicator |

---

## Migration (V2 → V3)

**Location:** `ktrdr/config/strategy_migration.py`

```python
from ktrdr.config.strategy_migration import migrate_v2_to_v3

v3_config = migrate_v2_to_v3(v2_config_dict)
```

Rules:
1. Indicators list → dict (key = old `feature_id`)
2. `name` → `type`
3. Add `indicator` field to each fuzzy_set (defaults to key name)
4. Generate `nn_inputs` from all fuzzy_sets × "all" timeframes
5. Set version to "3.0"

---

## Common Patterns

### Same indicator, different interpretations per timeframe

```yaml
fuzzy_sets:
  rsi_fast:
    indicator: rsi_14
    oversold: [0, 25, 35]      # More reactive
  rsi_slow:
    indicator: rsi_14
    oversold: [0, 15, 25]      # More extreme

nn_inputs:
  - fuzzy_set: rsi_fast
    timeframes: [5m]            # Fast for short TF
  - fuzzy_set: rsi_slow
    timeframes: [1h, 1d]       # Slow for longer TFs
```

### Selective timeframe usage

```yaml
nn_inputs:
  - fuzzy_set: rsi_momentum
    timeframes: [5m, 1h]       # Momentum on shorter TFs
  - fuzzy_set: macd_trend
    timeframes: [1h, 1d]       # Trend on longer TFs
  - fuzzy_set: volatility
    timeframes: all             # Context everywhere
```

### Multi-output indicator ensemble

```yaml
indicators:
  adx_14:
    type: adx
    period: 14

fuzzy_sets:
  adx_strength:
    indicator: adx_14.adx
    weak: [0, 20, 30]
    strong: [50, 65, 100]
  di_direction:
    indicator: adx_14.plus_di
    bearish: [0, 25, 50]
    bullish: [50, 75, 100]
```

---

## Integration with Training & Backtesting

### Training

The `FeatureResolver` determines what to compute. Training pipeline:
1. Resolves features → canonical ordered list
2. Groups indicators by timeframe (efficiency)
3. Computes indicators with `prefix_columns=False` (FuzzyNeuralProcessor handles prefixing)
4. Applies fuzzy sets → membership degrees
5. Assembles features in canonical order
6. Stores `resolved_features` in `ModelMetadataV3`

### Backtesting

Must produce **exact same features in exact same order** as training:
1. Loads `ModelMetadataV3.resolved_features` (canonical order)
2. Computes features using same pipeline
3. Validates feature names match
4. Reorders columns to match training order

**If feature order doesn't match → garbage predictions.**

---

## Key Files

| File | Purpose |
|------|---------|
| `ktrdr/config/models.py` | Pydantic models (IndicatorDefinition, FuzzySetDefinition, etc.) |
| `ktrdr/config/strategy_loader.py` | YAML parsing, V3 detection |
| `ktrdr/config/strategy_validator.py` | Validation rules, agent validation |
| `ktrdr/config/feature_resolver.py` | FeatureResolver, ResolvedFeature, canonical ordering |
| `ktrdr/config/strategy_migration.py` | V2 → V3 migration |
| `ktrdr/cli/v3_utils.py` | CLI helpers (is_v3, dry_run display) |
| `ktrdr/agents/strategy_utils.py` | Agent strategy generation/validation |
| `strategies/` | Example V3 strategy YAML files |
| `docs/designs/strategy-grammar-v3/` | Design documentation |

---

## Gotchas

### Feature ordering is sacred
The order from `FeatureResolver.resolve()` is the canonical order. It must be preserved in model metadata and matched exactly during backtesting. Mismatched order = garbage model output.

### Shorthand only works for triangular
`[a, b, c]` expands to `{type: triangular, parameters: [a, b, c]}`. Other types (trapezoid, gaussian, sigmoid) require full form.

### Dot notation requires multi-output indicator
Using `rsi_14.value` on a single-output indicator like RSI is an error. Only use dot notation for indicators that return multiple outputs.

### V2 detection is gone
The validator only handles V3. If a V2 file is loaded, it must be migrated first. There's no automatic fallback.

### `prefix_columns=False` in training
Training uses `prefix_columns=False` because FuzzyNeuralProcessor handles column prefixing. Backtesting uses `prefix_columns=True`. Don't change this — it's intentional.

### Multiple fuzzy sets can reference the same indicator
This is a V3 feature, not a bug. One indicator (e.g., `rsi_14`) can have multiple interpretations (e.g., `rsi_fast` and `rsi_slow`).
