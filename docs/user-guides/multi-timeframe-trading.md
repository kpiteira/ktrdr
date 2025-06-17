# 📊 Multi-Timeframe Trading Guide

## Overview

KTRDR's Multi-Timeframe Enhancement allows you to make more informed trading decisions by analyzing multiple timeframes simultaneously. This guide covers everything you need to know to use this powerful feature effectively.

## Table of Contents

1. [Concepts](#concepts)
2. [Getting Started](#getting-started)
3. [Configuration](#configuration)
4. [CLI Commands](#cli-commands)
5. [API Usage](#api-usage)
6. [Strategy Examples](#strategy-examples)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## 📖 Concepts

### What is Multi-Timeframe Analysis?

Multi-timeframe analysis is a professional trading technique that examines the same asset across different time periods to:

- **Identify trend direction** from higher timeframes
- **Find precise entry points** from lower timeframes  
- **Reduce false signals** through timeframe confirmation
- **Improve risk management** with better context

### Timeframe Hierarchy

KTRDR uses a three-tier approach:

| Timeframe | Purpose | Weight | Typical Use |
|-----------|---------|--------|-------------|
| **1h** | Entry/Exit Timing | 40-60% | Precise signal generation |
| **4h** | Strategy Context | 20-40% | Primary trend analysis |
| **1d** | Market Direction | 10-30% | Overall market bias |

### Consensus Methods

- **weighted_majority**: Combines signals using timeframe weights
- **hierarchical**: Primary timeframe dominates, others confirm
- **simple_consensus**: All timeframes have equal vote

---

## 🚀 Getting Started

### Prerequisites

1. **KTRDR Environment**: Ensure KTRDR is properly installed
2. **Data Access**: Market data for all required timeframes
3. **Strategy File**: Multi-timeframe configuration

### Quick Start

1. **Create a multi-timeframe strategy**:
```bash
# Copy an example strategy
cp strategies/adaptive-multi-timeframe-strategy.yaml strategies/my_strategy.yaml
```

2. **Generate your first decision**:
```bash
uv run ktrdr multi-timeframe decide AAPL strategies/my_strategy.yaml \
  --timeframes 1h,4h,1d \
  --verbose
```

3. **Check data availability**:
```bash
uv run ktrdr multi-timeframe status AAPL --timeframes 1h,4h,1d
```

---

## ⚙️ Configuration

### Strategy File Structure

Create a YAML file with multi-timeframe configuration:

```yaml
name: "my_multi_timeframe_strategy"
version: "2.0"
description: "Multi-timeframe momentum strategy"

# Timeframe configurations
timeframe_configs:
  1h:
    weight: 0.5              # 50% influence on final decision
    primary: false           # Not the primary timeframe
    lookback_periods: 50     # Data points to analyze
    min_data_quality: 0.8    # Minimum data quality threshold
  4h:
    weight: 0.3              # 30% influence
    primary: true            # Primary decision timeframe
    lookback_periods: 30     # Fewer periods for higher TF
    min_data_quality: 0.9    # Higher quality requirement
  1d:
    weight: 0.2              # 20% influence
    primary: false           # Context timeframe
    lookback_periods: 20     # Long-term context
    min_data_quality: 0.85   # Good quality required

# Indicators across timeframes
indicators:
  - name: rsi
    period: 14
    timeframes: ["1h", "4h", "1d"]
  - name: sma
    period: 20
    timeframes: ["1h", "4h", "1d"]
  - name: ema
    period: 12
    timeframes: ["4h", "1d"]  # Only for higher timeframes

# Fuzzy logic configuration
fuzzy_sets:
  rsi:
    oversold:
      type: triangular
      parameters: [0, 30, 50]
    neutral:
      type: triangular
      parameters: [30, 50, 70]
    overbought:
      type: triangular
      parameters: [50, 70, 100]
  sma_position:
    below:
      type: triangular
      parameters: [0.9, 0.95, 1.0]
    near:
      type: triangular
      parameters: [0.95, 1.0, 1.05]
    above:
      type: triangular
      parameters: [1.0, 1.05, 1.1]

# Fuzzy rules with timeframe context
fuzzy_rules:
  - name: bullish_momentum
    conditions:
      - indicator: rsi
        set: oversold
        timeframe: 1h
      - indicator: sma_position
        set: above
        timeframe: 4h
    action:
      signal: BUY
      confidence: 0.8
  - name: bearish_momentum
    conditions:
      - indicator: rsi
        set: overbought
        timeframe: 1h
      - indicator: sma_position
        set: below
        timeframe: 4h
    action:
      signal: SELL
      confidence: 0.75

# Multi-timeframe specific settings
multi_timeframe:
  consensus_method: "weighted_majority"
  min_agreement_score: 0.6
  conflicting_signal_resolution: "favor_primary"
  data_quality_threshold: 0.8
  max_timeframe_lag: 300  # 5 minutes max lag

# Neural network configuration (optional)
neural_config:
  model_type: "multi_timeframe_lstm"
  hidden_layers: [128, 64, 32]
  dropout_rate: 0.2
  learning_rate: 0.001
  use_fuzzy_features: true
  timeframe_fusion_method: "attention"

# Risk management
risk_management:
  max_position_size: 0.1
  stop_loss_pct: 0.02
  take_profit_pct: 0.04
  max_correlation: 0.7
```

### Configuration Options

#### Timeframe Weights
- Must sum to 1.0 across all timeframes
- Higher weights = more influence on final decision
- Typical distribution: 1h(50%), 4h(30%), 1d(20%)

#### Consensus Methods
- `weighted_majority`: Uses timeframe weights for voting
- `hierarchical`: Primary timeframe breaks ties
- `simple_consensus`: Equal weight for all timeframes

#### Data Quality Thresholds
- Values between 0.0 and 1.0
- Higher values require better data quality
- Recommended: 0.8+ for trading decisions

---

## 💻 CLI Commands

### Decision Generation

```bash
# Basic decision
uv run ktrdr multi-timeframe decide SYMBOL STRATEGY_FILE

# With specific timeframes
uv run ktrdr multi-timeframe decide AAPL strategies/my_strategy.yaml \
  --timeframes 1h,4h,1d

# With custom settings
uv run ktrdr multi-timeframe decide AAPL strategies/my_strategy.yaml \
  --timeframes 1h,4h,1d \
  --mode backtest \
  --portfolio 200000 \
  --capital 100000 \
  --format json \
  --verbose

# With neural model
uv run ktrdr multi-timeframe decide AAPL strategies/my_strategy.yaml \
  --model models/my_model.pt \
  --timeframes 1h,4h,1d
```

### Analysis Commands

```bash
# Analyze timeframe performance
uv run ktrdr multi-timeframe analyze AAPL strategies/my_strategy.yaml \
  --history 50 \
  --format table

# Check data status
uv run ktrdr multi-timeframe status AAPL \
  --timeframes 1h,4h,1d \
  --lookback 200

# Compare consensus methods
uv run ktrdr multi-timeframe compare AAPL strategies/my_strategy.yaml \
  --methods weighted_majority,hierarchical,simple_consensus

# List compatible strategies
uv run ktrdr multi-timeframe strategies \
  --format json
```

### Output Formats

- `json`: Machine-readable JSON output
- `table`: Human-readable table format
- `yaml`: YAML format for configuration

### Command Options

| Option | Description | Default |
|--------|-------------|---------|
| `--timeframes` | Comma-separated timeframe list | From strategy |
| `--mode` | Trading mode (backtest/paper/live) | backtest |
| `--format` | Output format (json/table/yaml) | table |
| `--verbose` | Detailed output and logging | false |
| `--portfolio` | Total portfolio value | 100000 |
| `--capital` | Available capital | 50000 |
| `--model` | Path to neural model file | None |
| `--history` | Number of historical decisions | 20 |
| `--lookback` | Data lookback periods | 100 |

---

## 🌐 API Usage

### Starting the API Server

```bash
# Start with Docker (recommended)
./docker_dev.sh start

# Or start directly
uv run python -m ktrdr.api.main
```

### API Endpoints

#### Generate Decision
```bash
curl -X POST "http://localhost:8000/api/v1/multi-timeframe-decisions/decide" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "strategy_config_path": "strategies/my_strategy.yaml",
    "timeframes": ["1h", "4h", "1d"],
    "mode": "backtest",
    "portfolio_state": {
      "total_value": 100000,
      "available_capital": 50000,
      "positions": {},
      "risk_exposure": 0.0
    }
  }'
```

#### Analyze Performance
```bash
curl -X POST "http://localhost:8000/api/v1/multi-timeframe-decisions/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "strategy_config_path": "strategies/my_strategy.yaml",
    "timeframes": ["1h", "4h", "1d"],
    "mode": "backtest",
    "analysis_params": {
      "history_limit": 50,
      "include_consensus_breakdown": true
    }
  }'
```

#### Check Data Status
```bash
curl "http://localhost:8000/api/v1/multi-timeframe-decisions/status/AAPL?timeframes=1h,4h,1d&lookback=100"
```

#### Batch Operations
```bash
curl -X POST "http://localhost:8000/api/v1/multi-timeframe-decisions/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL", "MSFT", "GOOGL"],
    "strategy_config_path": "strategies/my_strategy.yaml",
    "timeframes": ["1h", "4h", "1d"],
    "mode": "backtest"
  }'
```

### Response Examples

#### Decision Response
```json
{
  "symbol": "AAPL",
  "timestamp": "2024-01-15T10:30:00Z",
  "decision": {
    "signal": "BUY",
    "confidence": 0.85,
    "current_position": "FLAT",
    "reasoning": {
      "consensus_method": "weighted_majority",
      "timeframe_scores": {
        "1h": {"signal": "BUY", "confidence": 0.9},
        "4h": {"signal": "BUY", "confidence": 0.8},
        "1d": {"signal": "HOLD", "confidence": 0.6}
      }
    }
  },
  "consensus": {
    "method": "weighted_majority",
    "agreement_score": 0.82,
    "conflicting_timeframes": [],
    "primary_timeframe_weight": 0.3
  },
  "metadata": {
    "data_quality_score": 0.95,
    "processing_time_ms": 150,
    "timeframes_analyzed": ["1h", "4h", "1d"]
  }
}
```

---

## 📈 Strategy Examples

### 1. Momentum Strategy

```yaml
name: "momentum_multi_timeframe"
timeframe_configs:
  1h: {weight: 0.6, primary: true}   # Focus on short-term
  4h: {weight: 0.4, primary: false}  # Trend confirmation

indicators:
  - name: rsi
    period: 14
    timeframes: ["1h", "4h"]
  - name: ema
    period: 20
    timeframes: ["1h", "4h"]

fuzzy_rules:
  - name: momentum_buy
    conditions:
      - {indicator: rsi, set: neutral, timeframe: 1h}
      - {indicator: ema, set: above, timeframe: 4h}
    action: {signal: BUY, confidence: 0.8}

multi_timeframe:
  consensus_method: "weighted_majority"
  min_agreement_score: 0.7
```

### 2. Mean Reversion Strategy

```yaml
name: "mean_reversion_multi_timeframe"
timeframe_configs:
  1h: {weight: 0.4, primary: false}  # Entry timing
  4h: {weight: 0.4, primary: true}   # Main analysis
  1d: {weight: 0.2, primary: false}  # Context

indicators:
  - name: rsi
    period: 14
    timeframes: ["1h", "4h", "1d"]
  - name: bollinger_bands
    period: 20
    std_dev: 2
    timeframes: ["4h", "1d"]

fuzzy_rules:
  - name: oversold_bounce
    conditions:
      - {indicator: rsi, set: oversold, timeframe: 1h}
      - {indicator: rsi, set: neutral, timeframe: 4h}
      - {indicator: bollinger_bands, set: below_lower, timeframe: 4h}
    action: {signal: BUY, confidence: 0.85}

multi_timeframe:
  consensus_method: "hierarchical"
  conflicting_signal_resolution: "favor_primary"
```

### 3. Trend Following Strategy

```yaml
name: "trend_following_multi_timeframe"
timeframe_configs:
  4h: {weight: 0.5, primary: true}   # Main trend
  1d: {weight: 0.5, primary: false}  # Long-term context

indicators:
  - name: sma
    period: 50
    timeframes: ["4h", "1d"]
  - name: adx
    period: 14
    timeframes: ["4h", "1d"]

fuzzy_rules:
  - name: strong_uptrend
    conditions:
      - {indicator: sma, set: above, timeframe: 4h}
      - {indicator: sma, set: above, timeframe: 1d}
      - {indicator: adx, set: strong, timeframe: 4h}
    action: {signal: BUY, confidence: 0.9}

multi_timeframe:
  consensus_method: "simple_consensus"
  min_agreement_score: 0.8
```

---

## 🏆 Best Practices

### Timeframe Selection

1. **Standard Combinations**:
   - **Scalping**: 1m, 5m, 15m
   - **Day Trading**: 5m, 15m, 1h
   - **Swing Trading**: 1h, 4h, 1d
   - **Position Trading**: 4h, 1d, 1w

2. **Timeframe Ratios**:
   - Use 4:1 or 6:1 ratios between timeframes
   - Example: 1h, 4h, 1d (4:1 ratio)
   - Avoid too similar timeframes (1h vs 2h)

### Weight Distribution

1. **Balanced Approach**: 50%-30%-20%
2. **Timing Focus**: 60%-25%-15% (higher weight on entry timeframe)
3. **Trend Focus**: 30%-40%-30% (higher weight on trend timeframe)

### Consensus Configuration

1. **Conservative Trading**: 
   - `min_agreement_score: 0.8`
   - `consensus_method: "simple_consensus"`

2. **Active Trading**:
   - `min_agreement_score: 0.6`
   - `consensus_method: "weighted_majority"`

3. **Trend Following**:
   - `consensus_method: "hierarchical"`
   - `conflicting_signal_resolution: "favor_primary"`

### Data Quality Management

1. **Set appropriate thresholds**:
   - Production: `min_data_quality: 0.9`
   - Development: `min_data_quality: 0.8`

2. **Monitor data freshness**:
   - `max_timeframe_lag: 300` (5 minutes)
   - Regular data status checks

3. **Handle missing data gracefully**:
   - Use fallback consensus methods
   - Implement data quality alerts

### Performance Optimization

1. **Limit lookback periods**:
   - 1h: 50-100 periods
   - 4h: 30-50 periods  
   - 1d: 20-30 periods

2. **Cache frequently used data**:
   - Use data manager caching
   - Implement result caching for batch operations

3. **Monitor performance metrics**:
   - Decision latency < 1 second
   - Throughput > 10 decisions/second

---

## 🔧 Troubleshooting

### Common Issues

#### 1. No Decision Generated
```
Error: Unable to generate decision - insufficient data
```

**Solutions**:
- Check data availability: `uv run ktrdr multi-timeframe status SYMBOL`
- Verify timeframe data exists: `uv run ktrdr show-data SYMBOL --timeframe 1h`
- Lower data quality thresholds temporarily
- Check IB connection if using live data

#### 2. Conflicting Signals
```
Warning: Conflicting signals across timeframes
```

**Solutions**:
- Review consensus method in strategy file
- Adjust timeframe weights
- Set `conflicting_signal_resolution: "favor_primary"`
- Increase `min_agreement_score` for more conservative decisions

#### 3. Poor Performance
```
Warning: Decision latency > 2 seconds
```

**Solutions**:
- Reduce lookback periods in strategy config
- Limit number of indicators
- Use data caching
- Check system resources

#### 4. Data Quality Issues
```
Error: Data quality below threshold (0.65 < 0.8)
```

**Solutions**:
- Check data gaps: `uv run ktrdr gap-analysis SYMBOL`
- Update data: `uv run ktrdr ib-load SYMBOL --mode refresh`
- Lower quality thresholds temporarily
- Use data repair tools

### Debug Commands

```bash
# Verbose decision generation
uv run ktrdr multi-timeframe decide AAPL strategies/my_strategy.yaml --verbose

# Check detailed data status
uv run ktrdr multi-timeframe status AAPL --timeframes 1h,4h,1d --verbose

# Analyze consensus performance
uv run ktrdr multi-timeframe analyze AAPL strategies/my_strategy.yaml \
  --history 100 --format json

# Compare different consensus methods
uv run ktrdr multi-timeframe compare AAPL strategies/my_strategy.yaml \
  --methods weighted_majority,hierarchical
```

### Log Analysis

Check logs for detailed information:
```bash
# View recent logs
tail -f logs/ktrdr.log

# Search for multi-timeframe errors
grep "multi.timeframe" logs/ktrdr.log | grep ERROR

# Check consensus building logs
grep "consensus" logs/ktrdr.log
```

### Performance Monitoring

```bash
# Run performance tests
uv run pytest tests/performance/test_multi_timeframe_performance.py -v

# Monitor system resources
htop

# Check decision metrics
uv run ktrdr multi-timeframe analyze AAPL strategies/my_strategy.yaml \
  --history 1000 --format json | jq '.performance_metrics'
```

---

## 📚 Additional Resources

- [Multi-Timeframe API Reference](../api/multi-timeframe-api.md)
- [Strategy Configuration Guide](../configuration/multi-timeframe-strategies.md)
- [Neural Network Integration](../neural/multi-timeframe-models.md)
- [Backtesting with Multi-Timeframe](../backtesting/multi-timeframe-backtesting.md)

---

## 🤝 Support

For additional help:

1. **Documentation**: Check the full docs at `docs/`
2. **Examples**: Review strategy files in `strategies/`
3. **Tests**: See test examples in `tests/integration/`
4. **Issues**: Report problems via the project issue tracker

---

*Happy Multi-Timeframe Trading! 🚀*