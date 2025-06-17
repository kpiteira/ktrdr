# 💻 Multi-Timeframe CLI Commands

## Overview

KTRDR's multi-timeframe CLI commands provide powerful command-line access to multi-timeframe trading analysis, decision generation, and performance monitoring.

## Table of Contents

1. [Installation](#installation)
2. [Command Structure](#command-structure)
3. [Core Commands](#core-commands)
4. [Advanced Usage](#advanced-usage)
5. [Configuration](#configuration)
6. [Examples](#examples)
7. [Troubleshooting](#troubleshooting)

---

## 🚀 Installation

Multi-timeframe commands are included with KTRDR. Ensure you have the development environment set up:

```bash
# Clone and setup KTRDR
git clone <repository-url>
cd ktrdr2
./setup_dev.sh

# Verify installation
uv run ktrdr multi-timeframe --help
```

---

## 🏗️ Command Structure

All multi-timeframe commands follow this pattern:

```bash
uv run ktrdr multi-timeframe [COMMAND] [ARGS] [OPTIONS]
```

### Available Commands

- **`decide`** - Generate trading decisions
- **`analyze`** - Analyze performance and consensus
- **`status`** - Check data availability and quality
- **`strategies`** - List compatible strategies
- **`compare`** - Compare consensus methods

### Global Options

| Option | Description | Default |
|--------|-------------|---------|
| `--help` | Show help message | - |
| `--verbose` | Enable detailed output | false |
| `--format` | Output format (json/table/yaml) | table |

---

## 🎯 Core Commands

### 1. decide - Generate Trading Decision

Generate a multi-timeframe trading decision for a symbol.

#### Syntax
```bash
uv run ktrdr multi-timeframe decide SYMBOL STRATEGY_FILE [OPTIONS]
```

#### Parameters
- **`SYMBOL`** - Trading symbol (e.g., AAPL, MSFT)
- **`STRATEGY_FILE`** - Path to strategy configuration file

#### Options

| Option | Type | Description | Default |
|--------|------|-------------|---------|
| `--timeframes` | str | Comma-separated timeframes | From strategy |
| `--mode` | str | Trading mode (backtest/paper/live) | backtest |
| `--model` | str | Path to neural model file | None |
| `--portfolio` | float | Total portfolio value | 100000 |
| `--capital` | float | Available capital | 50000 |
| `--format` | str | Output format (json/table/yaml) | table |
| `--verbose` | flag | Show detailed information | false |

#### Examples

**Basic decision generation:**
```bash
uv run ktrdr multi-timeframe decide AAPL strategies/my_strategy.yaml
```

**With specific timeframes:**
```bash
uv run ktrdr multi-timeframe decide AAPL strategies/my_strategy.yaml \
  --timeframes 1h,4h,1d
```

**With neural model:**
```bash
uv run ktrdr multi-timeframe decide AAPL strategies/my_strategy.yaml \
  --model models/my_model.pt \
  --timeframes 1h,4h,1d \
  --verbose
```

**JSON output for automation:**
```bash
uv run ktrdr multi-timeframe decide AAPL strategies/my_strategy.yaml \
  --format json \
  --timeframes 1h,4h,1d
```

#### Output Example (Table Format)

```
Multi-Timeframe Decision for AAPL
================================

Decision Summary
---------------
Signal:           BUY
Confidence:       0.85
Position:         FLAT
Timestamp:        2024-01-15 10:30:00+00:00

Consensus Analysis
-----------------
Method:           weighted_majority
Agreement Score:  0.82
Primary TF:       4h (weight: 0.3)

Timeframe Breakdown
------------------
Timeframe | Signal | Confidence | Weight | Contribution
----------|--------|------------|--------|-------------
1h        | BUY    | 0.90       | 0.5    | 0.45
4h        | BUY    | 0.80       | 0.3    | 0.24
1d        | HOLD   | 0.60       | 0.2    | 0.12

Data Quality
-----------
Overall Score:    0.95
Processing Time:  150ms
Indicators Used:  rsi, sma, ema
```

#### Output Example (JSON Format)

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
    "primary_timeframe": "4h"
  },
  "metadata": {
    "processing_time_ms": 150,
    "data_quality_score": 0.95
  }
}
```

---

### 2. analyze - Performance Analysis

Analyze multi-timeframe decision performance and consensus patterns.

#### Syntax
```bash
uv run ktrdr multi-timeframe analyze SYMBOL STRATEGY_FILE [OPTIONS]
```

#### Options

| Option | Type | Description | Default |
|--------|------|-------------|---------|
| `--timeframes` | str | Comma-separated timeframes | From strategy |
| `--mode` | str | Trading mode | backtest |
| `--history` | int | Number of decisions to analyze | 20 |
| `--format` | str | Output format | table |

#### Examples

**Basic analysis:**
```bash
uv run ktrdr multi-timeframe analyze AAPL strategies/my_strategy.yaml
```

**Extended history analysis:**
```bash
uv run ktrdr multi-timeframe analyze AAPL strategies/my_strategy.yaml \
  --history 100 \
  --timeframes 1h,4h,1d
```

**JSON output for analysis:**
```bash
uv run ktrdr multi-timeframe analyze AAPL strategies/my_strategy.yaml \
  --format json \
  --history 50
```

#### Output Example

```
Multi-Timeframe Analysis for AAPL
=================================

Strategy Information
-------------------
Name:             my_multi_timeframe_strategy
Timeframes:       1h, 4h, 1d
Primary TF:       4h
Consensus Method: weighted_majority

Performance Summary
------------------
Total Decisions:        50
Average Confidence:     0.76
Average Processing:     145ms
Data Quality Score:     0.92

Signal Distribution
------------------
BUY:  18 (36%)
SELL: 12 (24%)  
HOLD: 20 (40%)

Consensus Analysis
-----------------
Unanimous Decisions:    20 (40%)
Majority Decisions:     25 (50%)
Split Decisions:        5  (10%)
Average Agreement:      0.78

Timeframe Performance
--------------------
Timeframe | Decisions | Avg Confidence | Signal Strength
----------|-----------|----------------|----------------
1h        | 50        | 0.82          | 0.78
4h        | 50        | 0.75          | 0.71
1d        | 50        | 0.68          | 0.65

Recent Trends
------------
Last 10 decisions show increasing consensus strength
Recommendation: Current strategy performing well
```

---

### 3. status - Data Quality Check

Check data availability and quality across timeframes.

#### Syntax
```bash
uv run ktrdr multi-timeframe status SYMBOL [OPTIONS]
```

#### Options

| Option | Type | Description | Default |
|--------|------|-------------|---------|
| `--timeframes` | str | Comma-separated timeframes | 1h,4h,1d |
| `--lookback` | int | Number of periods to check | 100 |

#### Examples

**Basic status check:**
```bash
uv run ktrdr multi-timeframe status AAPL
```

**Extended lookback:**
```bash
uv run ktrdr multi-timeframe status AAPL \
  --timeframes 1h,4h,1d \
  --lookback 200
```

#### Output Example

```
Data Status for AAPL
====================

Overall Quality Score: 0.95

Timeframe Analysis
-----------------
Timeframe | Available | Data Points | Quality | Freshness | Missing
----------|-----------|-------------|---------|-----------|--------
1h        | ✓         | 200         | 0.95    | 0.98      | 8
4h        | ✓         | 50          | 0.92    | 0.95      | 3  
1d        | ✓         | 12          | 0.98    | 0.92      | 0

Data Freshness
-------------
1h: Last update 30 minutes ago ✓
4h: Last update 2 hours ago ✓
1d: Last update 10 hours ago ✓

Recommendations
--------------
✓ Data quality is excellent across all timeframes
✓ All timeframes have sufficient data points
⚠ Consider refreshing 4h data for better freshness
```

---

### 4. strategies - List Compatible Strategies

List strategies that support multi-timeframe analysis.

#### Syntax
```bash
uv run ktrdr multi-timeframe strategies [OPTIONS]
```

#### Options

| Option | Type | Description | Default |
|--------|------|-------------|---------|
| `--directory` | str | Strategy directory path | strategies/ |
| `--format` | str | Output format | table |
| `--validate` | flag | Validate strategy files | false |

#### Examples

**List all strategies:**
```bash
uv run ktrdr multi-timeframe strategies
```

**With validation:**
```bash
uv run ktrdr multi-timeframe strategies --validate
```

**JSON output:**
```bash
uv run ktrdr multi-timeframe strategies --format json
```

#### Output Example

```
Multi-Timeframe Compatible Strategies
====================================

Strategy Files Found: 5

Strategy Details
---------------
Name                              | Timeframes    | Primary | Consensus Method
----------------------------------|---------------|---------|------------------
adaptive-multi-timeframe-strategy | 1h,4h,1d     | 4h      | weighted_majority
mean_reversion_strategy           | 1h,4h        | 4h      | hierarchical  
trend_momentum_strategy           | 1h,4h,1d     | 1d      | simple_consensus
rsi-mean-reversion-strategy       | 1h,4h        | 1h      | weighted_majority
volume-surge-momentum-strategy    | 5m,1h,4h     | 1h      | weighted_majority

Validation Results
-----------------
✓ All strategies passed validation
✓ No configuration errors found
```

---

### 5. compare - Compare Consensus Methods

Compare performance of different consensus methods.

#### Syntax
```bash
uv run ktrdr multi-timeframe compare SYMBOL STRATEGY_FILE [OPTIONS]
```

#### Options

| Option | Type | Description | Default |
|--------|------|-------------|---------|
| `--methods` | str | Comma-separated methods to compare | All methods |
| `--timeframes` | str | Timeframes to analyze | From strategy |
| `--format` | str | Output format | table |
| `--samples` | int | Number of test samples | 20 |

#### Available Methods
- `weighted_majority` - Uses timeframe weights
- `hierarchical` - Primary timeframe dominates
- `simple_consensus` - Equal weight voting

#### Examples

**Compare all methods:**
```bash
uv run ktrdr multi-timeframe compare AAPL strategies/my_strategy.yaml
```

**Compare specific methods:**
```bash
uv run ktrdr multi-timeframe compare AAPL strategies/my_strategy.yaml \
  --methods weighted_majority,hierarchical
```

**Extended comparison:**
```bash
uv run ktrdr multi-timeframe compare AAPL strategies/my_strategy.yaml \
  --samples 50 \
  --format json
```

#### Output Example

```
Consensus Method Comparison for AAPL
====================================

Test Parameters
--------------
Strategy:         my_strategy.yaml
Timeframes:       1h, 4h, 1d
Test Samples:     20
Analysis Period:  Last 20 decisions

Method Performance
-----------------
Method             | Avg Confidence | Agreement Score | Decision Speed | Conflicts
-------------------|----------------|-----------------|----------------|----------
weighted_majority  | 0.78          | 0.82           | 145ms         | 3
hierarchical       | 0.75          | 0.79           | 132ms         | 2
simple_consensus   | 0.71          | 0.76           | 138ms         | 5

Signal Distribution Comparison
-----------------------------
Method             | BUY | SELL | HOLD
-------------------|-----|------|-----
weighted_majority  | 8   | 5    | 7
hierarchical       | 9   | 4    | 7
simple_consensus   | 7   | 6    | 7

Recommendations
--------------
✓ weighted_majority: Best overall confidence and agreement
✓ hierarchical: Fastest processing, fewer conflicts
⚠ simple_consensus: Lower confidence, more conflicts

Optimal Choice: weighted_majority for this strategy and timeframe combination
```

---

## 🔧 Advanced Usage

### Batch Processing

Process multiple symbols with shell scripting:

```bash
#!/bin/bash
# batch_decisions.sh

SYMBOLS=("AAPL" "MSFT" "GOOGL" "TSLA")
STRATEGY="strategies/my_strategy.yaml"

for symbol in "${SYMBOLS[@]}"; do
  echo "Processing $symbol..."
  uv run ktrdr multi-timeframe decide "$symbol" "$STRATEGY" \
    --format json \
    --timeframes 1h,4h,1d > "results/${symbol}_decision.json"
done

echo "Batch processing complete!"
```

### Pipeline Integration

Use in data pipelines with JSON output:

```bash
# Generate decision and extract signal
SIGNAL=$(uv run ktrdr multi-timeframe decide AAPL strategies/my_strategy.yaml \
  --format json | jq -r '.decision.signal')

# Use signal in conditional logic
if [ "$SIGNAL" = "BUY" ]; then
  echo "Executing buy order..."
  # Your buy logic here
elif [ "$SIGNAL" = "SELL" ]; then
  echo "Executing sell order..."
  # Your sell logic here
fi
```

### Monitoring Scripts

Create monitoring dashboard data:

```bash
#!/bin/bash
# monitor_quality.sh

SYMBOLS=("AAPL" "MSFT" "GOOGL")
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

for symbol in "${SYMBOLS[@]}"; do
  quality=$(uv run ktrdr multi-timeframe status "$symbol" \
    --format json | jq -r '.overall_quality')
  
  echo "$TIMESTAMP,$symbol,$quality" >> quality_log.csv
done
```

### Custom Output Processing

Process output with custom tools:

```bash
# Generate and analyze decision
uv run ktrdr multi-timeframe decide AAPL strategies/my_strategy.yaml \
  --format json | python process_decision.py

# process_decision.py
import json
import sys

data = json.load(sys.stdin)
signal = data['decision']['signal']
confidence = data['decision']['confidence']

if signal == 'BUY' and confidence > 0.8:
    print("High confidence buy signal detected!")
    # Send alert, place order, etc.
```

---

## ⚙️ Configuration

### Environment Variables

Set default values using environment variables:

```bash
export KTRDR_DEFAULT_TIMEFRAMES="1h,4h,1d"
export KTRDR_DEFAULT_MODE="backtest"
export KTRDR_DEFAULT_FORMAT="table"
export KTRDR_STRATEGY_DIR="strategies/"
```

### Configuration Files

Create CLI configuration file at `~/.ktrdr/cli.yaml`:

```yaml
multi_timeframe:
  default_timeframes: ["1h", "4h", "1d"]
  default_mode: "backtest"
  default_format: "table"
  portfolio:
    total_value: 100000
    available_capital: 50000
  performance:
    timeout_seconds: 30
    max_concurrent: 3
```

### Shell Aliases

Add useful aliases to your shell configuration:

```bash
# ~/.bashrc or ~/.zshrc

# Common multi-timeframe commands
alias mtf-decide='uv run ktrdr multi-timeframe decide'
alias mtf-analyze='uv run ktrdr multi-timeframe analyze'
alias mtf-status='uv run ktrdr multi-timeframe status'

# Quick analysis
alias mtf-check='mtf-status --timeframes 1h,4h,1d'
alias mtf-quick='mtf-decide --format json --timeframes 1h,4h,1d'

# Monitoring
alias mtf-monitor='watch -n 30 "mtf-status AAPL"'
```

---

## 📖 Examples

### Example 1: Complete Workflow

```bash
# 1. Check data quality first
uv run ktrdr multi-timeframe status AAPL --timeframes 1h,4h,1d

# 2. Generate decision if data is good
uv run ktrdr multi-timeframe decide AAPL strategies/my_strategy.yaml \
  --timeframes 1h,4h,1d \
  --verbose

# 3. Analyze recent performance
uv run ktrdr multi-timeframe analyze AAPL strategies/my_strategy.yaml \
  --history 50

# 4. Compare consensus methods if needed
uv run ktrdr multi-timeframe compare AAPL strategies/my_strategy.yaml \
  --methods weighted_majority,hierarchical
```

### Example 2: Automated Trading Signal

```bash
#!/bin/bash
# trading_signal.sh

SYMBOL="AAPL"
STRATEGY="strategies/adaptive-multi-timeframe-strategy.yaml"

# Check data quality
QUALITY=$(uv run ktrdr multi-timeframe status "$SYMBOL" \
  --format json | jq -r '.overall_quality')

if (( $(echo "$QUALITY > 0.8" | bc -l) )); then
  # Generate decision
  DECISION=$(uv run ktrdr multi-timeframe decide "$SYMBOL" "$STRATEGY" \
    --format json --timeframes 1h,4h,1d)
  
  SIGNAL=$(echo "$DECISION" | jq -r '.decision.signal')
  CONFIDENCE=$(echo "$DECISION" | jq -r '.decision.confidence')
  
  if [ "$SIGNAL" = "BUY" ] && (( $(echo "$CONFIDENCE > 0.8" | bc -l) )); then
    echo "Strong BUY signal for $SYMBOL (confidence: $CONFIDENCE)"
    # Execute buy order
  elif [ "$SIGNAL" = "SELL" ] && (( $(echo "$CONFIDENCE > 0.8" | bc -l) )); then
    echo "Strong SELL signal for $SYMBOL (confidence: $CONFIDENCE)"
    # Execute sell order
  else
    echo "No action for $SYMBOL (signal: $SIGNAL, confidence: $CONFIDENCE)"
  fi
else
  echo "Data quality too low for $SYMBOL (quality: $QUALITY)"
fi
```

### Example 3: Portfolio Analysis

```bash
#!/bin/bash
# portfolio_analysis.sh

SYMBOLS=("AAPL" "MSFT" "GOOGL" "TSLA" "NVDA")
STRATEGY="strategies/adaptive-multi-timeframe-strategy.yaml"

echo "Portfolio Multi-Timeframe Analysis"
echo "=================================="
echo

for symbol in "${SYMBOLS[@]}"; do
  echo "Analyzing $symbol..."
  
  # Get decision
  result=$(uv run ktrdr multi-timeframe decide "$symbol" "$STRATEGY" \
    --format json --timeframes 1h,4h,1d 2>/dev/null)
  
  if [ $? -eq 0 ]; then
    signal=$(echo "$result" | jq -r '.decision.signal')
    confidence=$(echo "$result" | jq -r '.decision.confidence')
    agreement=$(echo "$result" | jq -r '.consensus.agreement_score')
    
    printf "%-6s | %-4s | %.2f | %.2f\n" "$symbol" "$signal" "$confidence" "$agreement"
  else
    printf "%-6s | ERROR\n" "$symbol"
  fi
done

echo
echo "Summary: Signal | Confidence | Agreement"
```

### Example 4: Strategy Backtesting

```bash
#!/bin/bash
# backtest_strategy.sh

SYMBOL="AAPL"
STRATEGIES=("strategies/mean_reversion_strategy.yaml" 
           "strategies/trend_momentum_strategy.yaml"
           "strategies/adaptive-multi-timeframe-strategy.yaml")

echo "Strategy Comparison for $SYMBOL"
echo "==============================="

for strategy in "${STRATEGIES[@]}"; do
  name=$(basename "$strategy" .yaml)
  echo
  echo "Testing: $name"
  echo "----------------"
  
  # Analyze performance
  uv run ktrdr multi-timeframe analyze "$SYMBOL" "$strategy" \
    --history 20 \
    --timeframes 1h,4h,1d
done
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Command Not Found
```
bash: ktrdr: command not found
```

**Solution**: Use the full command with uv:
```bash
uv run ktrdr multi-timeframe --help
```

#### 2. Invalid Symbol Format
```
Error: Invalid symbol format 'INVALID@SYMBOL'
```

**Solution**: Use valid symbol format:
```bash
# Correct formats
uv run ktrdr multi-timeframe decide AAPL strategies/my_strategy.yaml
uv run ktrdr multi-timeframe decide EURUSD strategies/my_strategy.yaml
uv run ktrdr multi-timeframe decide BTC-USD strategies/my_strategy.yaml
```

#### 3. Strategy File Not Found
```
Error: Strategy file not found: 'nonexistent.yaml'
```

**Solution**: Check file path and existence:
```bash
# List available strategies
ls strategies/

# Use correct path
uv run ktrdr multi-timeframe decide AAPL strategies/mean_reversion_strategy.yaml
```

#### 4. Insufficient Data
```
Error: Insufficient data for decision generation
```

**Solutions**:
```bash
# Check data status first
uv run ktrdr multi-timeframe status AAPL --timeframes 1h,4h,1d

# Load fresh data if needed
uv run ktrdr ib-load AAPL 1h --mode refresh

# Use shorter lookback in strategy
# Edit strategy file: lookback_periods: 20
```

#### 5. Invalid Timeframe
```
Error: Invalid timeframe 'invalid_tf'
```

**Solution**: Use valid timeframes:
```bash
# Valid timeframes: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
uv run ktrdr multi-timeframe decide AAPL strategies/my_strategy.yaml \
  --timeframes 1h,4h,1d
```

### Debug Commands

```bash
# Enable verbose output
uv run ktrdr multi-timeframe decide AAPL strategies/my_strategy.yaml --verbose

# Check configuration
uv run ktrdr multi-timeframe strategies --validate

# Test with minimal data
uv run ktrdr multi-timeframe status AAPL --lookback 10

# View logs
tail -f logs/ktrdr.log | grep multi_timeframe
```

### Performance Issues

#### Slow Decision Generation
```bash
# Check processing time
time uv run ktrdr multi-timeframe decide AAPL strategies/my_strategy.yaml

# Reduce lookback periods in strategy
# Use fewer indicators
# Check system resources with htop
```

#### Memory Issues
```bash
# Monitor memory usage
htop

# Reduce concurrent operations
# Use smaller datasets
# Clear old log files
```

### Getting Help

```bash
# Command help
uv run ktrdr multi-timeframe --help
uv run ktrdr multi-timeframe decide --help

# Check version and installation
uv run ktrdr --version

# Run diagnostics
uv run ktrdr test-ib --verbose
```

---

## 📚 Related Documentation

- [Multi-Timeframe Trading Guide](../user-guides/multi-timeframe-trading.md)
- [Multi-Timeframe API Reference](../api/multi-timeframe-api.md)
- [Strategy Configuration](../configuration/multi-timeframe-strategies.md)
- [CLI Installation Guide](./index.md)

---

*For more CLI commands and options, see the [complete CLI reference](./index.md).*