# 🎯 KTRDR Unified CLI Guide

The KTRDR CLI provides a single, unified interface for all trading operations including data management, strategy configuration, training, and backtesting.

## 📋 Complete Command Reference

### 🔍 Strategy Management Commands

#### **Validate Strategy**
```bash
# Validate a strategy configuration
ktrdr strategies validate strategies/my_strategy.yaml

# Quiet mode
ktrdr strategies validate strategies/my_strategy.yaml --quiet
```

#### **Upgrade Strategy**
```bash
# Upgrade to neuro-fuzzy format (creates .upgraded.yaml)
ktrdr strategies upgrade strategies/old_strategy.yaml

# Upgrade in place (overwrites original)
ktrdr strategies upgrade strategies/old_strategy.yaml --inplace

# Specify custom output
ktrdr strategies upgrade strategies/old_strategy.yaml -o strategies/new_strategy.yaml
```

#### **List Strategies**
```bash
# List all strategies
ktrdr strategies list

# List with validation
ktrdr strategies list --validate

# Detailed validation results
ktrdr strategies list --validate --verbose
```

### 🏋️ Training Commands

#### **Train Strategy**
```bash
# Basic training
ktrdr models train strategies/neuro_mean_reversion.yaml AAPL 1h \
  --start-date 2024-01-01 \
  --end-date 2024-06-01

# Advanced training with options
ktrdr models train strategies/momentum.yaml MSFT 4h \
  --start-date 2023-01-01 \
  --end-date 2024-01-01 \
  --epochs 100 \
  --validation-split 0.25 \
  --models-dir custom_models \
  --verbose

# Dry run (validate without training)
ktrdr models train strategies/test.yaml AAPL 1h \
  --start-date 2024-01-01 \
  --end-date 2024-06-01 \
  --dry-run
```

### 📈 Backtesting Commands

#### **Run Backtest**
```bash
# Basic backtest
ktrdr strategies backtest strategies/neuro_mean_reversion.yaml AAPL 1h \
  --start-date 2024-07-01 \
  --end-date 2024-12-31

# Advanced backtest with custom parameters
ktrdr strategies backtest strategies/momentum.yaml MSFT 4h \
  --start-date 2023-01-01 \
  --end-date 2024-01-01 \
  --model models/momentum/MSFT_4h_v2 \
  --capital 50000 \
  --commission 0.002 \
  --slippage 0.001 \
  --verbose \
  --output results/backtest_MSFT.json

# Quiet mode (results only)
ktrdr strategies backtest strategies/test.yaml AAPL 1h \
  --start-date 2024-01-01 \
  --end-date 2024-06-01 \
  --quiet \
  --output results.json
```

### 📊 Data Management Commands

#### **Show Data**
```bash
# Display price data
ktrdr data show AAPL --timeframe 1h --rows 20

# Show last N rows
ktrdr data show AAPL --timeframe 1d --rows 10 --tail

# Specific columns
ktrdr data show AAPL -t 1h -c open,high,low,close
```

#### **Load Data**
```bash
# Load data from data source
ktrdr data load AAPL --timeframe 1h --mode recent

# Load specific date range
ktrdr data load MSFT --timeframe 4h \
  --start-date 2024-01-01 \
  --end-date 2024-06-01

# Verbose mode with progress
ktrdr data load TSLA --timeframe 1d --mode full --verbose
```

### 🎨 Visualization Commands

#### **Plot Charts**
```bash
# Basic candlestick chart
ktrdr indicators plot AAPL --timeframe 1h

# Chart with indicators
ktrdr indicators plot AAPL -t 1h \
  --indicators sma:20,sma:50 \
  --days 30

# Advanced plotting
ktrdr indicators plot MSFT -t 4h \
  --indicators rsi:14:panel,macd:12:26:9:panel \
  --start-date 2024-01-01 \
  --end-date 2024-06-01 \
  --theme dark \
  --save output/chart.html
```

### 🔮 Fuzzy Logic Commands

#### **Fuzzify Data**
```bash
# Apply fuzzy logic to indicators
ktrdr fuzzy compute AAPL --indicator RSI --timeframe 1h

# Custom fuzzy configuration
ktrdr fuzzy compute MSFT --indicator MACD \
  --timeframe 4h \
  --fuzzy-config config/custom_fuzzy.yaml \
  --verbose
```

## 🚀 Complete Workflow Example

### 1. **Prepare Strategy**
```bash
# Check available strategies
ktrdr strategies list --validate

# Upgrade old strategy if needed
ktrdr strategies upgrade strategies/old_momentum.yaml
```

### 2. **Train Model**
```bash
# Train on historical data
ktrdr models train strategies/neuro_mean_reversion.yaml AAPL 1h \
  --start-date 2023-01-01 \
  --end-date 2023-12-31 \
  --epochs 100 \
  --verbose
```

### 3. **Backtest Strategy**
```bash
# Test on out-of-sample data
ktrdr strategies backtest strategies/neuro_mean_reversion.yaml AAPL 1h \
  --start-date 2024-01-01 \
  --end-date 2024-06-01 \
  --model models/neuro_mean_reversion/AAPL_1h_v1 \
  --verbose \
  --output results/AAPL_backtest.json
```

### 4. **Analyze Results**
```bash
# Plot backtest performance
ktrdr indicators plot AAPL --timeframe 1h \
  --start-date 2024-01-01 \
  --end-date 2024-06-01 \
  --backtest-results results/AAPL_backtest.json
```

## 🛠️ Advanced Features

### **Pipeline Mode**
Chain commands together:
```bash
# Validate, train, and backtest in sequence
ktrdr strategies validate strategies/test.yaml && \
ktrdr models train strategies/test.yaml AAPL 1h \
  --start-date 2023-01-01 --end-date 2023-12-31 && \
ktrdr strategies backtest strategies/test.yaml AAPL 1h \
  --start-date 2024-01-01 --end-date 2024-06-01
```

### **Batch Processing**
Process multiple symbols:
```bash
# Train on multiple symbols
for symbol in AAPL MSFT GOOGL; do
  ktrdr models train strategies/universal.yaml $symbol 1h \
    --start-date 2023-01-01 \
    --end-date 2023-12-31
done
```

### **Configuration Override**
Override strategy parameters:
```bash
# Train with custom epochs
ktrdr models train strategies/test.yaml AAPL 1h \
  --start-date 2024-01-01 \
  --end-date 2024-06-01 \
  --epochs 200  # Overrides strategy config
```

## 📝 Tips & Best Practices

1. **Always validate strategies before training**:
   ```bash
   ktrdr strategies validate strategies/my_strategy.yaml
   ```

2. **Use verbose mode for debugging**:
   ```bash
   ktrdr models train strategies/test.yaml AAPL 1h \
     --start-date 2024-01-01 --end-date 2024-06-01 --verbose
   ```

3. **Save backtest results for analysis**:
   ```bash
   ktrdr strategies backtest strategies/test.yaml AAPL 1h \
     --start-date 2024-01-01 --end-date 2024-06-01 \
     --output results/$(date +%Y%m%d)_AAPL.json
   ```

4. **Check data availability before training**:
   ```bash
   ktrdr data show AAPL --timeframe 1h --rows 5
   ```

## 🎯 Quick Reference

| Command | Purpose | Example |
|---------|---------|---------|
| `strategies validate` | Check strategy config | `ktrdr strategies validate strategies/test.yaml` |
| `strategies upgrade` | Upgrade to neuro-fuzzy | `ktrdr strategies upgrade strategies/old.yaml` |
| `strategies list` | List all strategies | `ktrdr strategies list --validate` |
| `models train` | Train neural network | `ktrdr models train strategies/test.yaml AAPL 1h --start-date 2024-01-01 --end-date 2024-06-01` |
| `strategies backtest` | Run trading simulation | `ktrdr strategies backtest strategies/test.yaml AAPL 1h --start-date 2024-07-01 --end-date 2024-12-31` |
| `data show` | Display price data | `ktrdr data show AAPL -t 1h -r 20` |
| `indicators plot` | Create charts | `ktrdr indicators plot AAPL -t 1h --indicators sma:20,rsi:14:panel` |
| `fuzzy compute` | Apply fuzzy logic | `ktrdr fuzzy compute AAPL --indicator RSI -t 1h` |

## 🚨 Getting Help

```bash
# General help
ktrdr --help

# Command-specific help
ktrdr models train --help
ktrdr strategies backtest --help
ktrdr strategies validate --help
```

The unified CLI makes KTRDR operations simple and consistent! 🚀