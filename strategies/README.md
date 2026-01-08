# Strategy Examples (V3 Grammar)

> **Important:** This directory contains **examples only**. Do NOT place your actual strategies here.
>
> Your strategies should be saved in: `~/.ktrdr/shared/strategies/`

## What is this directory?

This directory contains reference examples of V3 strategy grammar. Use these as templates when creating your own strategies.

## V3 Strategy Grammar Overview

V3 strategies use **dict-based indicators** and **explicit nn_inputs**:

```yaml
# V3 format (current)
indicators:
  rsi_14:           # indicator_id as key
    type: rsi
    period: 14

nn_inputs:          # Required: explicit feature selection
  - fuzzy_set: rsi_14
    timeframes: all
```

This differs from the deprecated V2 format which used list-based indicators.

## Examples

| File | Description |
|------|-------------|
| `v3_minimal.yaml` | Simplest possible strategy - good for testing |
| `v3_single_indicator.yaml` | Full config with single indicator (RSI) |
| `v3_multi_indicator.yaml` | Combining multiple indicators (RSI + ADX) |
| `v3_multi_timeframe.yaml` | Same indicator across multiple timeframes |
| `v3_multi_symbol.yaml` | Training across multiple symbols |
| `v3_multi_output_indicator.yaml` | Indicators with multiple outputs (ADX with DI+/DI-) |

## Quick Start

1. Copy an example to your strategies directory:
   ```bash
   cp strategies/v3_minimal.yaml ~/.ktrdr/shared/strategies/my_strategy.yaml
   ```

2. Edit the strategy to your needs

3. Validate your strategy:
   ```bash
   ktrdr strategies validate ~/.ktrdr/shared/strategies/my_strategy.yaml
   ```

4. Train:
   ```bash
   ktrdr models train ~/.ktrdr/shared/strategies/my_strategy.yaml
   ```

## Key V3 Concepts

### Indicator IDs
You choose the indicator ID (the dict key). It should be descriptive:
```yaml
indicators:
  rsi_14:         # Good: includes period
  my_rsi:         # Also fine
```

### Fuzzy Set → Indicator Reference
The `indicator` field in fuzzy sets must match an indicator ID:
```yaml
indicators:
  rsi_14:
    type: rsi
    period: 14

fuzzy_sets:
  rsi_momentum:
    indicator: rsi_14    # Must match indicator ID exactly
```

### Multi-Output Indicators
Some indicators (ADX, Aroon) produce multiple columns. All fuzzy sets reference the base indicator ID:
```yaml
indicators:
  adx_14:
    type: adx

fuzzy_sets:
  adx_strength:
    indicator: adx_14    # Not ADX_14 or DI_Plus_14
  di_plus_signal:
    indicator: adx_14    # Same indicator ID
```

## Validation

Always validate strategies before training:

```bash
# Single file
ktrdr strategies validate path/to/strategy.yaml

# Show generated features
ktrdr strategies features path/to/strategy.yaml
```

## Migration from V2

If you have V2 strategies, migrate them:

```bash
ktrdr strategies migrate ~/.ktrdr/shared/strategies/ --backup
```

This converts list-based indicators to dict format and adds `nn_inputs`.
