# 📋 Strategy Configuration CLI Guide

The KTRDR CLI now includes integrated strategy management commands for validating and upgrading trading strategies to be compatible with the neuro-fuzzy training system.

## 🎯 Available Commands

All strategy commands are part of the main `ktrdr` CLI:

### 1. **List Strategies**
```bash
# Basic listing
ktrdr list strategies

# List with validation status
ktrdr list strategies --validate

# Detailed validation results
ktrdr list strategies --validate --verbose

# List from custom directory
ktrdr list strategies -d my_strategies --validate
```

### 2. **Validate Strategy**
```bash
# Validate a specific strategy
ktrdr validate strategies/my_strategy.yaml

# Quiet mode (minimal output)
ktrdr validate strategies/my_strategy.yaml --quiet
```

### 3. **Migrate Strategy (v2 to v3)**
```bash
# Migrate to v3 format (creates backup)
ktrdr migrate strategies/old_v2_strategy.yaml --backup

# Preview migration without writing
ktrdr migrate strategies/old_v2_strategy.yaml --dry-run
```

## 📊 Example Workflow

### Step 1: Check Current Strategies
```bash
$ ktrdr list strategies --validate

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
$ ktrdr validate strategies/mean_reversion_strategy.yaml

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

💡 Run 'ktrdr migrate' to automatically fix issues
```

### Step 3: Migrate the Strategy
```bash
$ ktrdr migrate strategies/mean_reversion_strategy.yaml --backup

🔧 Migrating strategy: strategies/mean_reversion_strategy.yaml
============================================================
✅ Strategy migration completed!

🔍 Validating migrated strategy...
✅ Migrated strategy is valid!

🚀 Your strategy is now ready for training!
```

### Step 4: Train with Migrated Strategy
```bash
# Now you can use the migrated strategy for training
ktrdr train strategies/mean_reversion_strategy.yaml \
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

1. **Always validate before training**: Run `ktrdr validate` to ensure your strategy is properly configured

2. **Keep original files**: Use the `--backup` flag with migration to preserve originals

3. **Review migrated files**: Check the migrated YAML to ensure the defaults make sense for your strategy

4. **Test incrementally**: After migrating, run a small training test before full-scale training

## 🚨 Common Issues

- **"Strategy file not found"**: Ensure the path is correct and file exists
- **"Missing required section"**: Use `ktrdr migrate` to add missing sections
- **"Legacy fuzzy set format"**: Old format will be automatically converted during migration

## 🎯 Ready Strategies

These strategies are ready for immediate use:
- ✅ `neuro_mean_reversion.yaml` - Complete neuro-fuzzy configuration
- ✅ `mean_reversion_strategy.upgraded.yaml` - Upgraded from old format
- ✅ `trend_momentum_strategy.upgraded.yaml` - Upgraded from old format