# 🎯 KTRDR Unified CLI Guide

The KTRDR CLI provides a single, unified interface for all trading operations including data management, strategy configuration, training, and backtesting.

## 📋 Complete Command Reference

### 🔍 Strategy Management Commands

#### **Validate Strategy**
```bash
# Validate a strategy configuration
ktrdr validate strategies/my_strategy.yaml

# Quiet mode
ktrdr validate strategies/my_strategy.yaml --quiet
```

#### **List Strategies**
```bash
# List all strategies
ktrdr list strategies

# List with validation
ktrdr list strategies --validate

# Detailed validation results
ktrdr list strategies --validate --verbose
```

#### **Migrate Strategy (v2 to v3)**
```bash
# Migrate a strategy to v3 format
ktrdr migrate strategies/old_v2_strategy.yaml --backup
```

### 🏋️ Training Commands

#### **Train Strategy**
```bash
# Basic training
ktrdr train strategies/neuro_mean_reversion.yaml \
  --start-date 2024-01-01 \
  --end-date 2024-06-01

# Advanced training with options
ktrdr train strategies/momentum.yaml \
  --start-date 2023-01-01 \
  --end-date 2024-01-01 \
  --epochs 100 \
  --validation-split 0.25 \
  --models-dir custom_models \
  --verbose

# Dry run (validate without training)
ktrdr train strategies/test.yaml \
  --start-date 2024-01-01 \
  --end-date 2024-06-01 \
  --dry-run
```

### 📈 Backtesting Commands

#### **Run Backtest**
```bash
# Basic backtest
ktrdr backtest strategies/neuro_mean_reversion.yaml \
  --start-date 2024-07-01 \
  --end-date 2024-12-31

# Advanced backtest with custom parameters
ktrdr backtest strategies/momentum.yaml \
  --start-date 2023-01-01 \
  --end-date 2024-01-01 \
  --model models/momentum/MSFT_4h_v2 \
  --capital 50000 \
  --commission 0.002 \
  --slippage 0.001 \
  --verbose \
  --output results/backtest_MSFT.json

# Quiet mode (results only)
ktrdr backtest strategies/test.yaml \
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
ktrdr list strategies --validate

# Validate the strategy
ktrdr validate strategies/my_strategy.yaml
```

### 2. **Train Model**
```bash
# Train on historical data
ktrdr train strategies/neuro_mean_reversion.yaml \
  --start-date 2023-01-01 \
  --end-date 2023-12-31 \
  --epochs 100 \
  --verbose
```

### 3. **Backtest Strategy**
```bash
# Test on out-of-sample data
ktrdr backtest strategies/neuro_mean_reversion.yaml \
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
ktrdr validate strategies/test.yaml && \
ktrdr train strategies/test.yaml \
  --start-date 2023-01-01 --end-date 2023-12-31 && \
ktrdr backtest strategies/test.yaml \
  --start-date 2024-01-01 --end-date 2024-06-01
```

### **Configuration Override**
Override strategy parameters:
```bash
# Train with custom epochs
ktrdr train strategies/test.yaml \
  --start-date 2024-01-01 \
  --end-date 2024-06-01 \
  --epochs 200  # Overrides strategy config
```

## 📝 Tips & Best Practices

1. **Always validate strategies before training**:
   ```bash
   ktrdr validate strategies/my_strategy.yaml
   ```

2. **Use verbose mode for debugging**:
   ```bash
   ktrdr train strategies/test.yaml \
     --start-date 2024-01-01 --end-date 2024-06-01 --verbose
   ```

3. **Save backtest results for analysis**:
   ```bash
   ktrdr backtest strategies/test.yaml \
     --start-date 2024-01-01 --end-date 2024-06-01 \
     --output results/$(date +%Y%m%d)_backtest.json
   ```

4. **Check data availability before training**:
   ```bash
   ktrdr data show AAPL --timeframe 1h --rows 5
   ```

### 🔄 Operations Commands

#### **List Operations**
```bash
# List all operations
ktrdr ops

# Filter by status
ktrdr ops --status running
ktrdr ops --status cancelled
ktrdr ops --status failed

# Show only resumable operations (with checkpoints)
ktrdr ops --resumable
```

#### **Check Operation Status**

```bash
# Get detailed status
ktrdr status op_training_20241213_143022_abc123
```

#### **Cancel Operation**

```bash
# Cancel a running operation
ktrdr cancel op_training_20241213_143022_abc123
```

#### **Resume Operation**

```bash
# Resume from checkpoint
ktrdr resume op_training_20241213_143022_abc123
```

### 📦 Checkpoint Commands

#### **View Checkpoint Details**

```bash
# Show checkpoint information before resuming
ktrdr checkpoints show op_training_20241213_143022_abc123

# With verbose output
ktrdr checkpoints show op_training_20241213_143022_abc123 --verbose
```

#### **Delete Checkpoint**

```bash
# Delete with confirmation prompt
ktrdr checkpoints delete op_training_20241213_143022_abc123

# Skip confirmation (use with caution)
ktrdr checkpoints delete op_training_20241213_143022_abc123 --force
```

For more details, see the [Checkpoint & Resume Guide](checkpoint-resume.md).

## 🎯 Quick Reference

| Command | Purpose | Example |
|---------|---------|---------|
| `validate` | Check strategy config | `ktrdr validate strategies/test.yaml` |
| `list strategies` | List all strategies | `ktrdr list strategies --validate` |
| `migrate` | Migrate v2 to v3 | `ktrdr migrate strategies/old.yaml --backup` |
| `train` | Train neural network | `ktrdr train strategies/test.yaml --start-date 2024-01-01 --end-date 2024-06-01` |
| `backtest` | Run trading simulation | `ktrdr backtest strategies/test.yaml --start-date 2024-07-01 --end-date 2024-12-31` |
| `ops` | List operations | `ktrdr ops --status running` |
| `status` | Check operation status | `ktrdr status <operation-id>` |
| `cancel` | Cancel operation | `ktrdr cancel <operation-id>` |
| `resume` | Resume from checkpoint | `ktrdr resume <operation-id>` |
| `data show` | Display price data | `ktrdr data show AAPL -t 1h -r 20` |
| `indicators plot` | Create charts | `ktrdr indicators plot AAPL -t 1h --indicators sma:20,rsi:14:panel` |

## 🚨 Getting Help

```bash
# General help
ktrdr --help

# Command-specific help
ktrdr train --help
ktrdr backtest --help
ktrdr validate --help
```

The unified CLI makes KTRDR operations simple and consistent!