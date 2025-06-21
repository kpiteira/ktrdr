# Derived Indicators Usage Guide

## Overview

Derived indicators are composite technical indicators that combine multiple base indicators to provide enhanced market insights. KTRDR provides three derived indicators that were specifically created to support advanced neuro-fuzzy trading strategies.

## Available Derived Indicators

### 1. Bollinger Band Width

**Purpose**: Measures the compression/expansion of Bollinger Bands relative to the middle band (SMA).

**Formula**: `(upper_band - lower_band) / middle_band`

**Interpretation**:
- Higher values = Greater volatility (expanded bands)
- Lower values = Lower volatility (compressed bands)
- Very low values often precede volatility breakouts

**Configuration Example**:
```yaml
indicators:
  - name: bollinger_band_width
    type: BollingerBandWidth
    bb_period: 20          # Period for underlying Bollinger Bands
    bb_multiplier: 2.0     # Standard deviation multiplier
    source: close          # Price source (close, high, low, etc.)
```

**Usage in Strategy**:
```yaml
# In your strategy YAML file
indicators:
  - name: bb_width
    type: BollingerBandWidth
    bb_period: 20
    bb_multiplier: 2.0

fuzzy_sets:
  bb_width:
    low: [0.0, 0.02, 0.05]      # Low volatility
    medium: [0.03, 0.08, 0.15]   # Medium volatility  
    high: [0.12, 0.25, 1.0]     # High volatility
```

### 2. Volume Ratio

**Purpose**: Compares current volume to its simple moving average to identify volume spikes.

**Formula**: `current_volume / volume_sma`

**Interpretation**:
- 1.0 = Volume at average levels
- > 1.0 = Above average volume (increased interest)
- < 1.0 = Below average volume (decreased interest)
- Values > 2.0 often indicate significant events

**Configuration Example**:
```yaml
indicators:
  - name: volume_ratio
    type: VolumeRatio
    sma_period: 20         # Period for volume SMA calculation
    source: volume         # Always use 'volume' column
```

**Usage in Strategy**:
```yaml
# In your strategy YAML file
indicators:
  - name: vol_ratio
    type: VolumeRatio
    sma_period: 14

fuzzy_sets:
  vol_ratio:
    low: [0.0, 0.5, 0.8]       # Below average volume
    normal: [0.7, 1.0, 1.3]    # Normal volume
    high: [1.2, 2.0, 5.0]      # High volume spike
```

### 3. Squeeze Intensity

**Purpose**: Measures how compressed Bollinger Bands are within Keltner Channels, indicating low volatility periods that often precede strong moves.

**Formula**: Complex calculation measuring BB/KC compression ratio

**Interpretation**:
- 1.0 = Full squeeze (BB completely inside KC)
- 0.0 = No squeeze (BB outside KC)
- Values > 0.7 indicate strong squeeze conditions
- Squeezes often precede volatility expansion

**Configuration Example**:
```yaml
indicators:
  - name: squeeze_intensity
    type: SqueezeIntensity
    bb_period: 20          # Bollinger Bands period
    bb_multiplier: 2.0     # Bollinger Bands multiplier
    kc_period: 20          # Keltner Channels period
    kc_multiplier: 2.0     # Keltner Channels multiplier
    source: close          # Price source
```

**Usage in Strategy**:
```yaml
# In your strategy YAML file
indicators:
  - name: squeeze
    type: SqueezeIntensity
    bb_period: 20
    bb_multiplier: 2.0
    kc_period: 20
    kc_multiplier: 1.5

fuzzy_sets:
  squeeze:
    no_squeeze: [0.0, 0.1, 0.3]    # No squeeze condition
    mild_squeeze: [0.2, 0.5, 0.7]  # Mild squeeze
    strong_squeeze: [0.6, 0.8, 1.0] # Strong squeeze
```

## Complete Strategy Example

Here's a complete strategy that uses all three derived indicators:

```yaml
name: advanced_squeeze_strategy
description: Strategy using derived indicators for squeeze detection

indicators:
  # Base indicators
  - name: rsi
    type: RSI
    period: 14
  
  # Derived indicators
  - name: bb_width
    type: BollingerBandWidth
    bb_period: 20
    bb_multiplier: 2.0
    
  - name: volume_ratio
    type: VolumeRatio
    sma_period: 20
    
  - name: squeeze_intensity
    type: SqueezeIntensity
    bb_period: 20
    bb_multiplier: 2.0
    kc_period: 20
    kc_multiplier: 1.5

fuzzy_sets:
  rsi:
    oversold: [0, 20, 35]
    neutral: [25, 50, 75]
    overbought: [65, 80, 100]
    
  bb_width:
    compressed: [0.0, 0.02, 0.05]
    normal: [0.03, 0.08, 0.15]
    expanded: [0.12, 0.25, 1.0]
    
  volume_ratio:
    low_volume: [0.0, 0.5, 0.8]
    normal_volume: [0.7, 1.0, 1.3]
    high_volume: [1.2, 2.0, 5.0]
    
  squeeze_intensity:
    no_squeeze: [0.0, 0.1, 0.3]
    building_squeeze: [0.2, 0.5, 0.7]
    strong_squeeze: [0.6, 0.8, 1.0]

model:
  type: mlp
  features:
    fuzzy_features: true
    price_features: false
    volume_features: true
  training:
    epochs: 50
    batch_size: 32
    learning_rate: 0.001

training:
  labels:
    method: zigzag
    zigzag_threshold: 0.03
    label_lookahead: 5
  data_split:
    train: 0.7
    validation: 0.2
    test: 0.1
```

## CLI Usage

Test individual derived indicators:

```bash
# Test Bollinger Band Width
ktrdr indicators test BollingerBandWidth --symbol AAPL --timeframe 1h \
  --bb-period 20 --bb-multiplier 2.0

# Test Volume Ratio  
ktrdr indicators test VolumeRatio --symbol AAPL --timeframe 1h \
  --sma-period 20

# Test Squeeze Intensity
ktrdr indicators test SqueezeIntensity --symbol AAPL --timeframe 1h \
  --bb-period 20 --kc-period 20
```

## API Usage

Via REST API:

```bash
# Calculate Bollinger Band Width
curl -X POST "http://localhost:8000/api/v1/indicators/calculate" \
  -H "Content-Type: application/json" \
  -d '{
    "indicator_type": "BollingerBandWidth",
    "symbol": "AAPL", 
    "timeframe": "1h",
    "parameters": {
      "bb_period": 20,
      "bb_multiplier": 2.0,
      "source": "close"
    }
  }'
```

## Best Practices

1. **Combine with Base Indicators**: Derived indicators work best when combined with traditional indicators like RSI, MACD
2. **Parameter Tuning**: Adjust periods and multipliers based on your timeframe and market conditions
3. **Squeeze Detection**: Use Squeeze Intensity + Volume Ratio to identify high-probability breakout setups
4. **Volatility Timing**: Use Bollinger Band Width to time entries during low volatility periods
5. **Validation**: Always backtest your parameter combinations before live trading

## Troubleshooting

### Common Issues:

1. **Missing Volume Data**: Volume Ratio requires volume column in your data
2. **Insufficient Data**: All derived indicators need sufficient historical data for their calculations
3. **Parameter Conflicts**: Ensure BB/KC parameters are compatible across indicators

### Error Messages:

- `DataError: Required columns missing` - Check your data has all required OHLCV columns
- `DataError: Insufficient data` - Increase your data history or reduce indicator periods
- `ValidationError: Invalid parameters` - Check your parameter values are within valid ranges

## Architecture Notes

These derived indicators follow KTRDR's architectural principles:

- **Separation of Concerns**: Mathematical calculations are isolated in indicator classes
- **Indicator Engine Integration**: Automatic integration with API, CLI, and strategy processing
- **Training Pipeline Agnostic**: Training pipeline remains indicator-agnostic
- **Schema Validation**: All parameters are validated using JSON schemas
- **Error Handling**: Proper error handling with descriptive messages

For more advanced usage, see the [Strategy Configuration Guide](../configuration/schema.md) and [Neural Networks Guide](neural-networks.md).