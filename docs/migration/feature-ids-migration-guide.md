# Feature ID Migration Guide

**Version**: 2.1
**Date**: 2025-10-14
**Status**: Official Migration Guide

---

## Table of Contents

1. [Why Migration is Needed](#why-migration-is-needed)
2. [What Changed](#what-changed)
3. [Before You Start](#before-you-start)
4. [Migration Process](#migration-process)
5. [Migration Tool Usage](#migration-tool-usage)
6. [Manual Migration](#manual-migration)
7. [Validation After Migration](#validation-after-migration)
8. [Common Issues and Solutions](#common-issues-and-solutions)
9. [FAQ](#faq)
10. [Support Resources](#support-resources)

---

## Why Migration is Needed

###  The Problem with Implicit Naming

In the old format, indicators could be defined without explicit `feature_id` fields:

```yaml
# OLD FORMAT (No longer supported)
indicators:
  - type: "rsi"
    params: {period: 14}
  - type: "rsi"
    params: {period: 21}

fuzzy_sets:
  rsi_14:  # Which RSI does this reference?
    oversold: [0, 20, 40]
```

**Critical Issue**: When multiple instances of the same indicator exist with different parameters, the system cannot safely determine which indicator each fuzzy set references.

### The Solution: Explicit feature_id

The new format requires an explicit `feature_id` for each indicator:

```yaml
# NEW FORMAT (Required)
indicators:
  - type: "rsi"
    feature_id: "rsi_14"  # EXPLICIT reference
    params: {period: 14}
  - type: "rsi"
    feature_id: "rsi_21"  # EXPLICIT reference
    params: {period: 21}

fuzzy_sets:
  rsi_14:  # Unambiguous reference to first RSI
    oversold: [0, 20, 40]
  rsi_21:  # Unambiguous reference to second RSI
    oversold: [0, 20, 40]
```

---

## What Changed

### Breaking Changes

1. **`feature_id` is now REQUIRED** for all indicators
2. **`feature_id` must be UNIQUE** within each strategy
3. **Old configs without `feature_id` will be rejected** with clear error messages

### Non-Breaking Changes

- Indicator computation logic is unchanged
- Fuzzy set structure is unchanged
- Training pipeline behavior is unchanged (same outputs)
- Model compatibility is preserved

### Migration Timeline

- **Phase 0-1**: Completed - `feature_id` field added to config models
- **Phase 1.5**: Current - Migration tool available
- **Going Forward**: All strategies must have explicit `feature_id` fields

---

## Before You Start

### Prerequisites

✅ **Backup your strategies** - The migration tool can create `.bak` files automatically
✅ **Check dependencies** - Ensure you have the latest ktrdr version
✅ **Test environment** - Try migration in a test environment first

### Check If Migration is Needed

Run the migration tool in **dry-run mode** to preview changes:

```bash
uv run python scripts/migrate_to_feature_ids.py strategies/your_strategy.yaml --dry-run
```

If output shows "No changes needed", your strategy is already migrated.

---

## Migration Process

### Step 1: Backup Your Strategies

```bash
# Create manual backup
cp strategies/my_strategy.yaml strategies/my_strategy.yaml.backup

# Or use the tool's built-in backup (creates .bak files)
# Shown in Step 3
```

### Step 2: Dry-Run Migration (Preview)

Preview what changes will be made WITHOUT modifying files:

```bash
uv run python scripts/migrate_to_feature_ids.py strategies/my_strategy.yaml --dry-run
```

**Expected Output**:
```
================================================================================
Feature ID Migration Tool
================================================================================

🔍 DRY-RUN MODE: No files will be modified

[1/1] Processing: strategies/my_strategy.yaml
  ✅ 3 indicator(s) updated

================================================================================
Migration Summary
================================================================================
Files processed: 1
Successful: 1
Failed: 0
Total changes: 3

⚠️  DRY-RUN: No files were modified. Run without --dry-run to apply changes.
```

### Step 3: Run Migration with Backup

Apply changes with automatic backup:

```bash
uv run python scripts/migrate_to_feature_ids.py strategies/my_strategy.yaml --backup
```

This creates `strategies/my_strategy.yaml.bak` before modifying the original file.

### Step 4: Validate Migrated Strategy

Validate that the migrated strategy loads correctly:

```bash
# Try loading the strategy
ktrdr strategy validate strategies/my_strategy.yaml

# Or test with training (if applicable)
ktrdr models train --strategy strategies/my_strategy.yaml --dry-run
```

### Step 5: Test Functionality

Ensure the strategy works as expected:

```bash
# Run a quick backtest or training session
ktrdr models train --strategy strategies/my_strategy.yaml
```

Verify that:
- Training completes without errors
- Model features match expected `feature_id` values
- Results are consistent with pre-migration behavior

---

## Migration Tool Usage

### Basic Usage

#### Single File Migration

```bash
uv run python scripts/migrate_to_feature_ids.py strategy.yaml
```

#### Dry-Run (Preview Only)

```bash
uv run python scripts/migrate_to_feature_ids.py strategy.yaml --dry-run
```

#### With Backup

```bash
uv run python scripts/migrate_to_feature_ids.py strategy.yaml --backup
```

#### Batch Migration

Migrate all strategies in a directory:

```bash
uv run python scripts/migrate_to_feature_ids.py strategies/*.yaml --backup
```

### Command-Line Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview changes without modifying files |
| `--backup` | Create `.bak` backup before modifying files |
| `--help` | Show help message with all options |

### Migration Tool Behavior

#### Automatic feature_id Generation

The tool generates `feature_id` values by:

1. Instantiating the indicator with its parameters
2. Getting the column name via `indicator.get_column_name()`
3. Using the column name as the `feature_id`

This ensures `feature_id` values match existing fuzzy set keys (no breaking changes).

#### Examples:

| Indicator | Params | Generated `feature_id` |
|-----------|--------|----------------------|
| RSI | `{period: 14}` | `rsi_14` |
| RSI | `{period: 21}` | `rsi_21` |
| EMA | `{period: 20}` | `ema_20` |
| MACD | `{fast_period: 12, slow_period: 26, signal_period: 9}` | `macd_12_26_9` |
| SMA | `{period: 50}` | `sma_50` |
| ZigZag | `{threshold: 0.05}` | `ZigZag_5` |

#### Duplicate Detection

If multiple indicators would generate the same `feature_id`, migration fails with a clear error:

```
❌ Failed: Duplicate feature_id 'rsi_14' would be created for indicator 1 (type: rsi).
Multiple indicators with identical parameters require manually distinct feature_ids.
```

**Solution**: Manually assign unique `feature_id` values. See [Manual Migration](#manual-migration).

---

## Manual Migration

### When Manual Migration is Needed

- **Duplicate feature_ids**: Multiple indicators with identical params
- **Custom naming preferences**: Want semantic names instead of param-based
- **Complex strategies**: Large configs with many indicators

### Manual Migration Steps

#### 1. Add `feature_id` to Each Indicator

```yaml
# Before
indicators:
  - type: "rsi"
    params: {period: 14}

# After
indicators:
  - type: "rsi"
    feature_id: "rsi_14"  # ADD THIS
    params: {period: 14}
```

#### 2. Ensure Uniqueness

Each `feature_id` must be unique:

```yaml
# ❌ WRONG - Duplicate feature_ids
indicators:
  - type: "rsi"
    feature_id: "rsi"  # DUPLICATE!
    params: {period: 14}
  - type: "rsi"
    feature_id: "rsi"  # DUPLICATE!
    params: {period: 21}

# ✅ CORRECT - Unique feature_ids
indicators:
  - type: "rsi"
    feature_id: "rsi_14"  # Unique
    params: {period: 14}
  - type: "rsi"
    feature_id: "rsi_21"  # Unique
    params: {period: 21}
```

#### 3. Update Fuzzy Set Keys (if needed)

Ensure fuzzy set keys match `feature_id` values:

```yaml
indicators:
  - type: "rsi"
    feature_id: "rsi_fast"  # Custom semantic name
    params: {period: 7}

fuzzy_sets:
  rsi_fast:  # Must match feature_id
    oversold: [0, 20, 40]
```

### Naming Patterns

#### Pattern 1: Use Parameters (Recommended)

Clear, explicit, matches generated names:

```yaml
indicators:
  - type: "rsi"
    feature_id: "rsi_14"
    params: {period: 14}

  - type: "macd"
    feature_id: "macd_12_26_9"
    params: {fast_period: 12, slow_period: 26, signal_period: 9}
```

#### Pattern 2: Semantic Names

More readable, requires manual mapping:

```yaml
indicators:
  - type: "rsi"
    feature_id: "rsi_fast"
    params: {period: 7}

  - type: "rsi"
    feature_id: "rsi_slow"
    params: {period: 21}

  - type: "macd"
    feature_id: "macd_trend"
    params: {fast_period: 12, slow_period: 26, signal_period: 9}
```

#### Pattern 3: Mixed (Most Common)

Combines both approaches:

```yaml
indicators:
  - type: "rsi"
    feature_id: "rsi_14"  # Param-based
    params: {period: 14}

  - type: "macd"
    feature_id: "macd_trend"  # Semantic
    params: {fast_period: 12, slow_period: 26, signal_period: 9}

  - type: "ema"
    feature_id: "ema_short"  # Semantic
    params: {period: 9}
```

### feature_id Naming Rules

**Format**: `^[a-zA-Z][a-zA-Z0-9_-]*$`

✅ **Valid**:
- `rsi_14`
- `macd_12_26_9`
- `ema_short`
- `my-custom-indicator`

❌ **Invalid**:
- `14_rsi` (cannot start with number)
- `rsi 14` (no spaces allowed)
- `@rsi_14` (no special characters except `_` and `-`)

**Reserved Words** (cannot be used):
- `open`, `high`, `low`, `close`, `volume`

---

## Validation After Migration

### Automatic Validation

The system automatically validates:

1. ✅ `feature_id` is present for all indicators
2. ✅ `feature_id` format is valid
3. ✅ `feature_id` values are unique
4. ✅ Reserved words are not used
5. ✅ Fuzzy sets reference valid `feature_id` values

### Manual Validation Checklist

After migration, verify:

- [ ] Strategy file loads without errors
- [ ] All indicators have `feature_id` fields
- [ ] All `feature_id` values are unique
- [ ] Fuzzy set keys match `feature_id` values
- [ ] Training completes successfully
- [ ] Model features match expected `feature_id` values

### Validation Commands

```bash
# Validate strategy config
ktrdr strategy validate strategies/my_strategy.yaml

# Test with dry-run training
ktrdr models train --strategy strategies/my_strategy.yaml --dry-run

# Run full training (if applicable)
ktrdr models train --strategy strategies/my_strategy.yaml
```

---

## Common Issues and Solutions

### Issue 1: Duplicate feature_id Error

**Error Message**:
```
Duplicate feature_id 'rsi_14' would be created for indicator 1 (type: rsi).
Multiple indicators with identical parameters require manually distinct feature_ids.
```

**Cause**: Multiple indicators have identical parameters, which would generate the same `feature_id`.

**Solution**: Manually assign unique `feature_id` values:

```yaml
# If you actually want two RSI(14) instances (rare)
indicators:
  - type: "rsi"
    feature_id: "rsi_14_primary"
    params: {period: 14}
  - type: "rsi"
    feature_id: "rsi_14_secondary"
    params: {period: 14}
```

**Most Common Case**: This is actually a config error - you probably meant different parameters:

```yaml
# Fix by using correct parameters
indicators:
  - type: "rsi"
    feature_id: "rsi_14"
    params: {period: 14}
  - type: "rsi"
    feature_id: "rsi_21"  # Different period!
    params: {period: 21}
```

### Issue 2: Missing feature_id Error

**Error Message**:
```
❌ Validation Error: Missing required field 'feature_id'

Location: indicators[0]
Field: feature_id

Details:
  - Indicator type: rsi
  - Missing feature_id (REQUIRED since v2.1)

Migration Required:
  This strategy uses the old format. Please migrate using:

  python scripts/migrate_to_feature_ids.py your_strategy.yaml
```

**Cause**: Strategy hasn't been migrated yet.

**Solution**: Run the migration tool (see [Migration Process](#migration-process)).

### Issue 3: Reserved Word Error

**Error Message**:
```
feature_id 'close' is a reserved word.
Reserved words: open, high, low, close, volume
```

**Cause**: Used a reserved word as `feature_id`.

**Solution**: Choose a different name:

```yaml
# ❌ Wrong
indicators:
  - type: "sma"
    feature_id: "close"  # Reserved!
    params: {period: 20}

# ✅ Correct
indicators:
  - type: "sma"
    feature_id: "sma_20"
    params: {period: 20}
```

### Issue 4: Fuzzy Set Mismatch Error

**Error Message**:
```
Indicators missing fuzzy_sets: {'rsi_fast'}
Add fuzzy_sets entries for these feature_ids.
```

**Cause**: An indicator has a `feature_id` but no corresponding fuzzy set.

**Solution**: Add the missing fuzzy set:

```yaml
indicators:
  - type: "rsi"
    feature_id: "rsi_fast"
    params: {period: 7}

fuzzy_sets:
  rsi_fast:  # ADD THIS
    oversold: [0, 20, 40]
    neutral: [30, 50, 70]
    overbought: [60, 80, 100]
```

### Issue 5: Invalid feature_id Format

**Error Message**:
```
feature_id '14_rsi' must start with a letter and contain only letters, numbers, underscore, or dash
```

**Cause**: `feature_id` doesn't follow naming rules.

**Solution**: Fix the format:

```yaml
# ❌ Wrong
indicators:
  - type: "rsi"
    feature_id: "14_rsi"  # Starts with number!

# ✅ Correct
indicators:
  - type: "rsi"
    feature_id: "rsi_14"
```

---

## FAQ

### Q1: Do I need to migrate immediately?

**A**: Yes. The old format (without `feature_id`) is no longer supported. Strategies without `feature_id` will be rejected with a clear error message directing you to this migration guide.

### Q2: Will migration break my existing strategies?

**A**: No. The migration tool generates `feature_id` values that match existing column names, so fuzzy sets continue to reference the correct indicators. Your training results should be identical after migration.

### Q3: Can I use custom names instead of param-based names?

**A**: Yes! You can use semantic names like `rsi_fast` instead of `rsi_14`. Just ensure they're unique and that your fuzzy sets reference the correct `feature_id`.

### Q4: What if I have hundreds of strategies to migrate?

**A**: Use batch migration:

```bash
uv run python scripts/migrate_to_feature_ids.py strategies/*.yaml --backup
```

This processes all strategies in one command, with progress reporting.

### Q5: Can I undo a migration?

**A**: Yes, if you used `--backup`:

```bash
# Restore from backup
mv strategies/my_strategy.yaml.bak strategies/my_strategy.yaml
```

Or restore from your own backups.

### Q6: Will this affect my trained models?

**A**: No. Trained models are unaffected. The `feature_id` change is only in the configuration format, not in the model structure.

### Q7: What about multi-output indicators like MACD?

**A**: The `feature_id` maps to the primary output (main line for MACD). Secondary outputs (signal, histogram) remain accessible via their column names but are not directly referenced by `feature_id`.

Example:
```yaml
indicators:
  - type: "macd"
    feature_id: "macd_12_26_9"  # References main line
    params: {fast_period: 12, slow_period: 26, signal_period: 9}

fuzzy_sets:
  macd_12_26_9:  # Fuzzifies main MACD line
    bullish: [0, 5, 20]
```

### Q8: Can I test migration without modifying files?

**A**: Yes! Use `--dry-run`:

```bash
uv run python scripts/migrate_to_feature_ids.py strategy.yaml --dry-run
```

This shows exactly what changes would be made without touching any files.

### Q9: What if migration fails partway through?

**A**: The tool validates each file completely before writing. If any validation fails, the original file is left unchanged. With `--backup`, you have an additional safety net.

### Q10: Where can I get help?

**A**: See [Support Resources](#support-resources) below.

---

## Support Resources

### Documentation

- **Architecture Document**: [docs/architecture/indicators/explicit-naming-architecture.md](../architecture/indicators/explicit-naming-architecture.md)
- **Implementation Plan**: [docs/architecture/indicators/explicit-naming-implementation-plan.md](../architecture/indicators/explicit-naming-implementation-plan.md)
- **API Documentation**: <http://localhost:8000/api/v1/docs> (when server running)

### Getting Help

1. **GitHub Issues**: <https://github.com/[your-repo]/ktrdr2/issues>
   - Search for existing issues
   - Create new issue with `[migration]` tag

2. **Discord Community**: [Join our Discord](#) (if applicable)

3. **Email Support**: support@yourdomain.com (if applicable)

### Reporting Bugs

When reporting migration issues, please include:

1. Strategy file (or minimal example)
2. Full error message
3. Migration command used
4. ktrdr version: `ktrdr --version`
5. Expected vs actual behavior

### Example Bug Report Template

```
**Description**: Migration fails with duplicate feature_id error

**Command**:
`uv run python scripts/migrate_to_feature_ids.py my_strategy.yaml`

**Error**:
```
Duplicate feature_id 'rsi_14' would be created for indicator 1
```

**Strategy Config** (minimal example):
```yaml
indicators:
  - type: "rsi"
    params: {period: 14}
  - type: "rsi"
    params: {period: 14}  # Duplicate params
```

**Expected**: Clear error explaining the issue
**Actual**: Confusing error message

**Version**: ktrdr 2.1.0
```

---

## Appendix: Full Migration Example

### Before Migration

```yaml
# strategies/example_strategy.yaml (OLD FORMAT)
name: "Example Strategy"
version: "1.0"
description: "Multi-indicator strategy example"

indicators:
  - type: "rsi"
    params: {period: 14}
  - type: "rsi"
    params: {period: 21}
  - type: "ema"
    params: {period: 20}
  - type: "macd"
    params: {fast_period: 12, slow_period: 26, signal_period: 9}

fuzzy_sets:
  rsi_14:
    oversold: {type: "triangular", parameters: [0, 20, 40]}
    neutral: {type: "triangular", parameters: [30, 50, 70]}
    overbought: {type: "triangular", parameters: [60, 80, 100]}
  rsi_21:
    oversold: {type: "triangular", parameters: [0, 20, 40]}
    neutral: {type: "triangular", parameters: [30, 50, 70]}
    overbought: {type: "triangular", parameters: [60, 80, 100]}
  ema_20:
    below: {type: "triangular", parameters: [0.93, 0.97, 1.00]}
    at_ma: {type: "triangular", parameters: [0.98, 1.00, 1.02]}
    above: {type: "triangular", parameters: [1.00, 1.03, 1.07]}
  macd_12_26_9:
    strong_bearish: {type: "triangular", parameters: [-100, -50, -10]}
    bearish: {type: "triangular", parameters: [-20, -5, 0]}
    neutral: {type: "triangular", parameters: [-5, 0, 5]}
    bullish: {type: "triangular", parameters: [0, 5, 20]}
    strong_bullish: {type: "triangular", parameters: [10, 50, 100]}

model: {...}
decisions: {...}
training: {...}
```

### After Migration

```yaml
# strategies/example_strategy.yaml (NEW FORMAT)
name: "Example Strategy"
version: "1.0"
description: "Multi-indicator strategy example"

indicators:
  - type: "rsi"
    feature_id: "rsi_14"  # ADDED
    params: {period: 14}
  - type: "rsi"
    feature_id: "rsi_21"  # ADDED
    params: {period: 21}
  - type: "ema"
    feature_id: "ema_20"  # ADDED
    params: {period: 20}
  - type: "macd"
    feature_id: "macd_12_26_9"  # ADDED
    params: {fast_period: 12, slow_period: 26, signal_period: 9}

# Fuzzy sets UNCHANGED (keys already matched generated feature_ids)
fuzzy_sets:
  rsi_14:
    oversold: {type: "triangular", parameters: [0, 20, 40]}
    neutral: {type: "triangular", parameters: [30, 50, 70]}
    overbought: {type: "triangular", parameters: [60, 80, 100]}
  rsi_21:
    oversold: {type: "triangular", parameters: [0, 20, 40]}
    neutral: {type: "triangular", parameters: [30, 50, 70]}
    overbought: {type: "triangular", parameters: [60, 80, 100]}
  ema_20:
    below: {type: "triangular", parameters: [0.93, 0.97, 1.00]}
    at_ma: {type: "triangular", parameters: [0.98, 1.00, 1.02]}
    above: {type: "triangular", parameters: [1.00, 1.03, 1.07]}
  macd_12_26_9:
    strong_bearish: {type: "triangular", parameters: [-100, -50, -10]}
    bearish: {type: "triangular", parameters: [-20, -5, 0]}
    neutral: {type: "triangular", parameters: [-5, 0, 5]}
    bullish: {type: "triangular", parameters: [0, 5, 20]}
    strong_bullish: {type: "triangular", parameters: [10, 50, 100]}

model: {...}
decisions: {...}
training: {...}
```

**Key Changes**:
- Added `feature_id` to all 4 indicators
- Fuzzy sets unchanged (keys already matched)
- Functionality preserved (training results identical)

---

## Changelog

### Version 2.1 (2025-10-14)
- Initial migration guide created
- Migration tool released
- `feature_id` field now required

---

**END OF MIGRATION GUIDE**
