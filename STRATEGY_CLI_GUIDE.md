# 📋 Strategy Configuration CLI Guide

The KTRDR CLI now includes integrated strategy management commands for validating and upgrading trading strategies to be compatible with the neuro-fuzzy training system.

## 🎯 Available Commands

All strategy commands are part of the main `ktrdr` CLI:

### 1. **List Strategies** 
```bash
# Basic listing
ktrdr strategy-list

# List with validation status
ktrdr strategy-list --validate

# Detailed validation results
ktrdr strategy-list --validate --verbose

# List from custom directory
ktrdr strategy-list -d my_strategies --validate
```

### 2. **Validate Strategy**
```bash
# Validate a specific strategy
ktrdr strategy-validate strategies/my_strategy.yaml

# Quiet mode (minimal output)
ktrdr strategy-validate strategies/my_strategy.yaml --quiet
```

### 3. **Upgrade Strategy**
```bash
# Upgrade to new format (creates .upgraded.yaml file)
ktrdr strategy-upgrade strategies/old_strategy.yaml

# Upgrade in place (overwrites original - use with caution!)
ktrdr strategy-upgrade strategies/old_strategy.yaml --inplace

# Specify custom output path
ktrdr strategy-upgrade strategies/old_strategy.yaml -o strategies/new_strategy.yaml

# Quiet mode
ktrdr strategy-upgrade strategies/old_strategy.yaml --quiet
```

## 📊 Example Workflow

### Step 1: Check Current Strategies
```bash
$ ktrdr strategy-list --validate

📂 Strategies in strategies:
============================================================
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ File                          ┃ Name                   ┃ Status     ┃ Issues              ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ mean_reversion_strategy.yaml  │ mean_reversion_strategy│ ❌ Invalid │ 5 errors, 19 warnings│
│ neuro_mean_reversion.yaml     │ neuro_mean_reversion   │ ✅ Valid   │                     │
│ trend_momentum_strategy.yaml  │ trend_momentum_strategy│ ❌ Invalid │ 5 errors, 13 warnings│
└───────────────────────────────┴────────────────────────┴────────────┴─────────────────────┘
```

### Step 2: Validate Specific Strategy
```bash
$ ktrdr strategy-validate strategies/mean_reversion_strategy.yaml

🔍 Validating strategy: strategies/mean_reversion_strategy.yaml
============================================================
❌ Strategy configuration has issues:

🚨 Errors (5):
  1. Missing required section: decisions
  2. Missing required section: training
  3. Missing required model field: architecture
  4. Missing required model field: training
  5. Missing required model field: features

⚠️  Warnings (19):
  1. Detected old model format with input_size/output_size
  2. Legacy fuzzy set format detected...

💡 Run 'ktrdr strategy-upgrade' to automatically fix issues
```

### Step 3: Upgrade the Strategy
```bash
$ ktrdr strategy-upgrade strategies/mean_reversion_strategy.yaml

🔧 Upgrading strategy: strategies/mean_reversion_strategy.yaml
📁 Output path: strategies/mean_reversion_strategy.upgraded.yaml
============================================================
📊 Current validation status:
  🚨 5 errors
  ⚠️  19 warnings
  📋 5 missing sections

✅ Strategy upgrade completed!
💾 Upgraded configuration saved to: strategies/mean_reversion_strategy.upgraded.yaml

🔍 Validating upgraded strategy...
✅ Upgraded strategy is valid!

============================================================
🚀 Your strategy is now ready for neuro-fuzzy training!
💡 Use: uv run python -m ktrdr.training.cli --strategy strategies/mean_reversion_strategy.upgraded.yaml
```

### Step 4: Train with Upgraded Strategy
```bash
# Now you can use the upgraded strategy for training
uv run python -m ktrdr.training.cli \
  --strategy strategies/mean_reversion_strategy.upgraded.yaml \
  --symbol AAPL \
  --timeframe 1h \
  --start-date 2024-01-01 \
  --end-date 2024-06-01
```

## 🔍 What Gets Upgraded?

The upgrade process adds these missing sections with sensible defaults:

1. **Neural Network Configuration**
   - MLP architecture with configurable hidden layers
   - Training parameters (learning rate, batch size, epochs)
   - Feature engineering settings
   - Early stopping configuration

2. **Training Configuration**
   - ZigZag labeling for supervised learning
   - Train/validation/test splits
   - Fitness metrics

3. **Decision Logic**
   - Output format (classification)
   - Confidence thresholds
   - Position awareness
   - Signal filtering rules

4. **Orchestrator Settings**
   - Max position size
   - Signal cooldown periods
   - Mode-specific settings (backtest/paper/live)

5. **Risk Management**
   - Position sizing strategy
   - Risk per trade limits
   - Maximum portfolio risk

6. **Backtesting Configuration**
   - Default date ranges
   - Initial capital
   - Transaction costs
   - Slippage settings

## ✅ Best Practices

1. **Always validate before training**: Run `strategy-validate` to ensure your strategy is properly configured

2. **Keep original files**: Use the default behavior (creates `.upgraded.yaml`) instead of `--inplace` to preserve originals

3. **Review upgraded files**: Check the upgraded YAML to ensure the defaults make sense for your strategy

4. **Test incrementally**: After upgrading, run a small training test before full-scale training

## 🚨 Common Issues

- **"Strategy file not found"**: Ensure the path is correct and file exists
- **"Missing required section"**: Use `strategy-upgrade` to add missing sections
- **"Legacy fuzzy set format"**: Old format will be automatically converted during upgrade

## 🎯 Ready Strategies

These strategies are ready for immediate use:
- ✅ `neuro_mean_reversion.yaml` - Complete neuro-fuzzy configuration
- ✅ `mean_reversion_strategy.upgraded.yaml` - Upgraded from old format
- ✅ `trend_momentum_strategy.upgraded.yaml` - Upgraded from old format