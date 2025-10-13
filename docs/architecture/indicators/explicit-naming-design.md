# Design Document: Explicit Indicator Naming

**Status**: Draft
**Date**: 2025-10-13
**Author**: Claude Code
**Issue**: Implicit indicator naming causes fuzzy set mismatches

---

## Problem Statement

### Current Architecture Issues

1. **Implicit Naming**: Indicator column names are auto-generated from parameters
   - `rsi(period=14)` → `rsi_14`
   - `macd(12,26,9)` → `macd_12_26_9`
   - `stochastic(14,3)` → `stochastic_14_3_3` (includes default `smooth_k=3`)

2. **Fuzzy Set Coupling**: Fuzzy sets must match these auto-generated names
   ```yaml
   indicators:
     - name: "macd"
       fast_period: 12
       slow_period: 26
       signal_period: 9

   fuzzy_sets:
     macd_12_26_9:  # Must guess this name!
       bullish: [0, 10, 50]
   ```

3. **Error-Prone**:
   - User wants `macd_standard` but system expects `macd_12_26_9`
   - Float formatting: `bbands_20_2` vs `bollingerbands_20_2.0`
   - Default parameters: `stochastic_14_3` vs `stochastic_14_3_3`

4. **Hard to Validate**: Cannot validate fuzzy set names without instantiating indicators

---

## Proposed Solution

### New Grammar: Explicit Indicator Naming

```yaml
indicators:
  # Base indicator type + unique name
  - indicator: "rsi"           # What to instantiate (base indicator class)
    name: "rsi_14"             # Unique ID for this indicator instance
    period: 14
    source: "close"

  - indicator: "rsi"           # Same indicator, different config
    name: "rsi_fast"           # Different unique name
    period: 7
    source: "close"

  - indicator: "macd"
    name: "macd_standard"      # User-friendly descriptive name
    fast_period: 12
    slow_period: 26
    signal_period: 9
    source: "close"

  - indicator: "macd"
    name: "macd_fast"          # Another MACD with different params
    fast_period: 5
    slow_period: 13
    signal_period: 5

fuzzy_sets:
  # Fuzzy sets reference indicator.name
  rsi_14:
    extreme_oversold: [0, 10, 25]
    oversold: [15, 30, 40]
    neutral: [35, 50, 65]
    overbought: [60, 70, 85]
    extreme_overbought: [75, 90, 100]

  rsi_fast:
    oversold: [0, 20, 35]
    neutral: [30, 50, 70]
    overbought: [65, 80, 100]

  macd_standard:
    strong_bearish: [-100, -50, -10]
    bearish: [-20, -5, 0]
    neutral: [-5, 0, 5]
    bullish: [0, 5, 20]
    strong_bullish: [10, 50, 100]

  macd_fast:
    bearish: [-50, -10, 0]
    neutral: [-5, 0, 5]
    bullish: [0, 10, 50]
```

---

## Benefits

### 1. Explicit > Implicit
- No auto-generation magic
- No guessing required
- Clear separation of concerns

### 2. User-Friendly
- Descriptive names: `macd_standard`, `rsi_fast`, `bb_tight`, `bb_wide`
- Self-documenting: name explains the variant
- Easy to understand strategy at a glance

### 3. Simple Validation
```python
indicator_names = {ind["name"] for ind in indicators}
fuzzy_names = set(fuzzy_sets.keys())

# Validation is trivial
missing_fuzzy = indicator_names - fuzzy_names
orphan_fuzzy = fuzzy_names - indicator_names
```

### 4. Flexible
- Same indicator with different parameters gets different names
- Can use nicknames or systematic naming
- User chooses the convention

### 5. No Default Parameter Surprises
- `name` is what you see in fuzzy_sets
- No need to know that `stochastic` has `smooth_k=3` default

---

## Implementation Plan

### Phase 1: Configuration Model Updates

#### 1.1 Update `IndicatorConfig` Model
**File**: `ktrdr/config/models.py`

```python
class IndicatorConfig(BaseModel):
    """Configuration for a technical indicator."""

    # NEW: Required field for indicator type
    indicator: str = Field(
        ...,
        description="Base indicator type (rsi, macd, bbands, etc.)"
    )

    # ENHANCED: Now required and used as unique identifier
    name: str = Field(
        ...,
        description="Unique name for this indicator instance (used in fuzzy_sets)"
    )

    # Parameters remain the same
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for indicator initialization"
    )

    # For flat YAML format, all other fields go into params
    @model_validator(mode='before')
    @classmethod
    def extract_params(cls, data: Any) -> Any:
        """Extract non-standard fields into params."""
        if isinstance(data, dict):
            reserved = {'indicator', 'name', 'params'}
            params = data.get('params', {})

            # Move all non-reserved fields to params
            for key, value in list(data.items()):
                if key not in reserved:
                    params[key] = value

            data['params'] = params
        return data

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure name is valid identifier."""
        if not v or not v.strip():
            raise ValueError("Indicator name cannot be empty")
        # Allow alphanumeric, underscore, dash
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', v):
            raise ValueError(
                f"Indicator name '{v}' must start with letter and "
                "contain only letters, numbers, underscore, or dash"
            )
        return v.strip()
```

#### 1.2 Add Validation for Name Uniqueness
**File**: `ktrdr/config/models.py`

```python
class StrategyConfigurationV2(BaseModel):
    # ... existing fields ...

    @model_validator(mode='after')
    def validate_indicator_names_unique(self) -> 'StrategyConfigurationV2':
        """Ensure all indicator names are unique."""
        if self.indicators:
            names = [ind.name for ind in self.indicators]
            duplicates = {name for name in names if names.count(name) > 1}
            if duplicates:
                raise ValueError(
                    f"Duplicate indicator names found: {duplicates}. "
                    "Each indicator must have a unique 'name' field."
                )
        return self
```

### Phase 2: Indicator Factory Updates

#### 2.1 Update `IndicatorFactory.build()`
**File**: `ktrdr/indicators/indicator_factory.py`

```python
def build(
    self,
    indicator_type: str,  # RENAMED from indicator_name
    params: dict[str, Any],
    custom_name: Optional[str] = None  # NEW: for explicit naming
) -> BaseIndicator:
    """Build an indicator instance.

    Args:
        indicator_type: Base indicator type (rsi, macd, etc.)
        params: Initialization parameters
        custom_name: Optional custom name (overrides auto-generated name)

    Returns:
        Configured indicator instance
    """
    # ... existing lookup logic ...

    indicator = indicator_class(**params)

    # If custom_name provided, override the auto-generated name
    if custom_name:
        # Store custom name for get_column_name()
        indicator._custom_column_name = custom_name

    return indicator
```

#### 2.2 Update `BaseIndicator.get_column_name()`
**File**: `ktrdr/indicators/base_indicator.py`

```python
def get_column_name(self, suffix: Optional[str] = None) -> str:
    """Generate column name for indicator output.

    Returns custom name if set, otherwise generates from parameters.
    """
    # Use custom name if provided (via strategy config)
    if hasattr(self, '_custom_column_name'):
        base = self._custom_column_name
    else:
        # Fall back to auto-generated name (backward compatibility)
        base = self._generate_column_name()

    suffix_str = f"_{suffix}" if suffix else ""
    return f"{base}{suffix_str}"

def _generate_column_name(self) -> str:
    """Generate column name from parameters (legacy behavior)."""
    base_name = self.name.lower()
    param_str = ""

    if "period" in self.params:
        param_str += f"_{self.params['period']}"

    for key, value in self.params.items():
        if key in ["period", "source"]:
            continue
        if isinstance(value, (int, float, str)):
            param_str += f"_{value}"

    return f"{base_name}{param_str}"
```

### Phase 3: Validation Updates

#### 3.1 Simplify Indicator-Fuzzy Matching
**File**: `ktrdr/config/strategy_validator.py`

```python
def _validate_indicator_fuzzy_matching(
    self, indicators: list[dict[str, Any]], fuzzy_sets: dict[str, Any]
) -> ValidationResult:
    """Validate indicator-fuzzy set matching with explicit naming.

    With explicit naming, this is trivial:
    - Every indicator.name must have a fuzzy_sets entry
    - Every fuzzy_sets key should correspond to an indicator.name (warning only)
    """
    result = ValidationResult(is_valid=True)

    # Extract indicator names
    indicator_names = set()
    for ind in indicators:
        if isinstance(ind, dict) and "name" in ind:
            indicator_names.add(ind["name"])

    fuzzy_names = set(fuzzy_sets.keys())

    # Check 1: Every indicator must have fuzzy sets
    missing_fuzzy = indicator_names - fuzzy_names
    for name in missing_fuzzy:
        result.is_valid = False
        result.errors.append(
            f"Indicator '{name}' has no corresponding fuzzy_sets entry. "
            f"Add 'fuzzy_sets.{name}' section with fuzzy set definitions."
        )

    # Check 2: Warn about orphan fuzzy sets (might be intentional)
    orphan_fuzzy = fuzzy_names - indicator_names
    for name in orphan_fuzzy:
        result.warnings.append(
            f"Fuzzy set '{name}' doesn't match any indicator name. "
            f"This may be intentional for derived features, or could be a typo."
        )

    return result
```

#### 3.2 Add Name Syntax Validation
**File**: `ktrdr/config/strategy_validator.py`

```python
def _validate_indicator_definitions(
    self, indicators: list[dict[str, Any]]
) -> ValidationResult:
    """Validate indicator definitions for required fields."""
    result = ValidationResult(is_valid=True)

    for i, ind in enumerate(indicators):
        # Check required fields
        if "indicator" not in ind:
            result.is_valid = False
            result.errors.append(
                f"Indicator #{i+1} missing required 'indicator' field "
                f"(base indicator type like 'rsi', 'macd', etc.)"
            )

        if "name" not in ind:
            result.is_valid = False
            result.errors.append(
                f"Indicator #{i+1} missing required 'name' field "
                f"(unique identifier for this indicator instance)"
            )

        # Validate name format
        if "name" in ind:
            name = ind["name"]
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', name):
                result.is_valid = False
                result.errors.append(
                    f"Indicator name '{name}' is invalid. "
                    f"Must start with letter and contain only letters, "
                    f"numbers, underscore, or dash."
                )

    return result
```

### Phase 4: Indicator Engine & Training Pipeline Updates

#### 4.1 Update Indicator Engine
**File**: `ktrdr/indicators/indicator_engine.py`

Simplified - no backward compatibility, just validate and use new format:

```python
def __init__(
    self, indicators: Optional[Union[list[dict], list[BaseIndicator]]] = None
):
    """Initialize IndicatorEngine with indicator configuration."""
    self.indicators: list[BaseIndicator] = []

    if indicators:
        if isinstance(indicators[0], dict):
            # Validate new format
            self._validate_indicator_format(indicators)

            # Build indicators from configuration
            factory = IndicatorFactory()
            for config in indicators:
                indicator_type = config["indicator"]  # Required
                custom_name = config["name"]          # Required
                params = {k: v for k, v in config.items()
                         if k not in ["indicator", "name"]}

                indicator = factory.build(
                    indicator_type=indicator_type,
                    params=params,
                    custom_name=custom_name
                )
                self.indicators.append(indicator)
        else:
            # Direct indicator instances
            self.indicators = indicators

def _validate_indicator_format(self, indicators: list[dict]) -> None:
    """Validate indicators use new explicit naming format."""
    for i, ind in enumerate(indicators, 1):
        if "indicator" not in ind:
            raise ConfigurationError(
                f"Indicator #{i} missing 'indicator' field. "
                f"Run: python scripts/migrate_indicator_naming.py <strategy.yaml>",
                error_code="STRATEGY-LegacyFormat"
            )
        if "name" not in ind:
            raise ConfigurationError(
                f"Indicator #{i} missing 'name' field.",
                error_code="STRATEGY-MissingName"
            )
```

#### 4.2 Update Training Pipeline
**File**: `ktrdr/training/training_pipeline.py`

The training pipeline has complex indicator name mapping logic (lines 277-310, 364-410) that tries to match auto-generated names to fuzzy sets. This entire logic can be **simplified** with explicit naming:

**Current Problem** (lines 298-310):
```python
# Create a mapping from original indicator names to calculated column names
# This allows fuzzy sets to match the original indicator names
mapped_results = pd.DataFrame(index=indicator_results.index)

# Map indicator results to original names for fuzzy matching
for config in indicator_configs:
    original_name = config["name"]  # e.g., 'rsi'
    indicator_type = config["name"].upper()  # e.g., 'RSI'

    # Find the calculated column that matches this indicator
    # Look for columns that start with the indicator type
    # COMPLEX MATCHING LOGIC HERE
```

**New Solution** (simplified):
```python
# With explicit naming, no mapping needed!
# Column names already match fuzzy set names

indicator_results = indicator_engine.apply(price_data)

# Fuzzy sets can directly reference column names
fuzzy_results = fuzzy_engine.generate_memberships(
    indicator_results,
    fuzzy_configs  # Keys match column names exactly
)
```

**Required Changes:**

1. **Remove name mapping logic** (lines 298-318, 398-420):
   - No longer need to "map indicator results to original names"
   - Column names from indicators already match fuzzy set keys

2. **Remove indicator config fixing** (lines 277-291, 364-378):
   ```python
   # DELETE THIS ENTIRE BLOCK - no longer needed!
   # Old code tried to infer 'type' from 'name'
   # New code requires explicit 'indicator' field

   # Simply pass through - validation happens in IndicatorEngine
   indicator_configs = config.get("indicators", [])
   ```

3. **Update multi-timeframe processing** (lines 461-473):
   ```python
   # OLD: Match by guessing indicator names
   for indicator_name, indicator_data in tf_indicators.items():
       if indicator_name in fuzzy_configs:
           # Fuzzify...

   # NEW: Direct match (names are explicit)
   for col_name in tf_indicators.columns:
       if col_name in fuzzy_configs:
           membership_values = fuzzy_engine.fuzzify(
               col_name,
               tf_indicators[col_name]
           )
           fuzzy_results.update(membership_values)
   ```

#### 4.3 Estimated Lines of Code Reduction

With explicit naming, we can **remove approximately 80-100 lines** of complex mapping logic from training_pipeline.py:
- Lines 298-318: Name mapping for single-timeframe (20 lines)
- Lines 398-420: Name mapping for multi-timeframe (22 lines)
- Lines 277-291: Type inference logic (14 lines)
- Lines 364-378: Duplicate type inference (14 lines)
- Associated error handling and edge cases (30+ lines)

**Net effect**: Simpler, more maintainable code that's easier to debug.

### Phase 5: Migration Support

#### 5.1 Migration Script
**File**: `scripts/migrate_indicator_naming.py`

A standalone script to migrate strategies (not integrated into CLI):

```python
#!/usr/bin/env python3
"""
Migrate strategy files to explicit indicator naming format.

Usage:
    python scripts/migrate_indicator_naming.py strategies/my_strategy.yaml
    python scripts/migrate_indicator_naming.py strategies/*.yaml --dry-run
"""

import argparse
import sys
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from ktrdr.indicators.indicator_factory import IndicatorFactory


def migrate_strategy(strategy_path: Path, output_path: Path = None, dry_run: bool = False):
    """Migrate a strategy file to explicit naming format."""

    print(f"Processing: {strategy_path}")

    with open(strategy_path) as f:
        config = yaml.safe_load(f)

    if "indicators" not in config:
        print("  ⚠️  No indicators section found, skipping")
        return False

    factory = IndicatorFactory()
    migrated = []
    changes = []

    for i, ind in enumerate(config["indicators"], 1):
        if not isinstance(ind, dict):
            continue

        # If already has 'indicator' field, already migrated
        if "indicator" in ind:
            migrated.append(ind)
            continue

        # Extract indicator type from 'name' field
        indicator_type = ind.get("name", "")

        # Generate column name from actual indicator
        try:
            params = {k: v for k, v in ind.items() if k != "name"}
            temp_indicator = factory.build(indicator_type, params)
            generated_name = temp_indicator.get_column_name()
        except Exception as e:
            print(f"  ❌ Failed to instantiate indicator #{i} ({indicator_type}): {e}")
            return False

        # Create new format
        new_ind = {
            "indicator": indicator_type,
            "name": generated_name,
        }

        # Copy all other parameters
        for key, value in ind.items():
            if key != "name":
                new_ind[key] = value

        migrated.append(new_ind)
        changes.append(f"  - {indicator_type} → {generated_name}")

    if changes:
        print(f"  ✓ {len(changes)} indicators to migrate:")
        for change in changes:
            print(change)

        config["indicators"] = migrated

        if not dry_run:
            output = output_path or strategy_path.with_suffix('.migrated.yaml')
            with open(output, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            print(f"  ✓ Saved to: {output}")
        else:
            print("  (dry-run, no files written)")

        return True
    else:
        print("  ✓ Already migrated or no changes needed")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Migrate strategy files to explicit indicator naming"
    )
    parser.add_argument(
        "strategies",
        nargs="+",
        type=Path,
        help="Strategy file(s) to migrate"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without writing files"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory (default: same as input)"
    )

    args = parser.parse_args()

    total = 0
    migrated = 0

    for strategy_path in args.strategies:
        if not strategy_path.exists():
            print(f"❌ File not found: {strategy_path}")
            continue

        total += 1
        output_path = None
        if args.output_dir:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            output_path = args.output_dir / strategy_path.name

        if migrate_strategy(strategy_path, output_path, args.dry_run):
            migrated += 1
        print()

    print(f"Summary: {migrated}/{total} strategies migrated")


if __name__ == "__main__":
    main()
```

**Usage:**
```bash
# Dry run to see changes
python scripts/migrate_indicator_naming.py strategies/mtf_forex_neural.yaml --dry-run

# Migrate single strategy
python scripts/migrate_indicator_naming.py strategies/mtf_forex_neural.yaml

# Migrate all strategies
python scripts/migrate_indicator_naming.py strategies/*.yaml

# Migrate to different directory
python scripts/migrate_indicator_naming.py strategies/*.yaml --output-dir migrated_strategies/
```

### Phase 6: Documentation Updates

#### 6.1 Update Strategy Documentation
**File**: `docs/strategies/indicator-configuration.md`

Add section explaining:
- The two-field system: `indicator` + `name`
- Naming conventions and best practices
- Examples of good indicator names
- Migration guide for existing strategies

#### 6.2 Add to CLAUDE.md
**File**: `CLAUDE.md`

Add to architectural principles:
```markdown
## Indicator Naming Convention

Indicators use explicit two-field naming:

1. **indicator**: Base indicator type (what to instantiate)
   - Examples: "rsi", "macd", "bbands"
   - Maps to indicator class in factory

2. **name**: Unique identifier (what to call it)
   - Used in fuzzy_sets, column names, feature references
   - Must be unique within strategy
   - Can be descriptive ("macd_standard") or systematic ("macd_12_26_9")

This eliminates implicit name generation and makes fuzzy set matching trivial.
```

---

## Breaking Change: No Backward Compatibility

### Design Decision

**No graceful degradation.** Explicit naming is required immediately. This simplifies the codebase significantly and prevents maintaining two parallel systems.

### Legacy Format Detection & Rejection

```python
def validate_indicator_format(indicators: list[dict]) -> None:
    """Validate that indicators use new explicit naming format.

    Raises ConfigurationError if legacy format detected.
    """
    if not indicators:
        return

    for i, ind in enumerate(indicators, 1):
        if not isinstance(ind, dict):
            continue

        # Check for required fields
        if "indicator" not in ind:
            raise ConfigurationError(
                f"Indicator #{i} uses legacy format (missing 'indicator' field).\n\n"
                f"BREAKING CHANGE: Strategies now require explicit indicator naming.\n"
                f"Each indicator must have:\n"
                f"  - indicator: base type (rsi, macd, etc.)\n"
                f"  - name: unique identifier\n\n"
                f"To migrate your strategy:\n"
                f"  python scripts/migrate_indicator_naming.py {strategy_path}\n\n"
                f"Example:\n"
                f"  OLD: - name: 'rsi'\\n"
                f"         period: 14\n"
                f"  NEW: - indicator: 'rsi'\\n"
                f"         name: 'rsi_14'\\n"
                f"         period: 14",
                error_code="STRATEGY-LegacyFormat"
            )

        if "name" not in ind:
            raise ConfigurationError(
                f"Indicator #{i} missing required 'name' field.\n\n"
                f"Each indicator must have a unique 'name' for referencing in fuzzy_sets.\n"
                f"Example: name: 'rsi_14' or name: 'macd_standard'",
                error_code="STRATEGY-MissingName"
            )
```

### Implementation Simplification

With no backward compatibility:

1. **Remove all format detection code** ❌
2. **Remove legacy support paths** ❌
3. **Remove auto-migration on load** ❌
4. **One simple validation check** ✅
5. **Clear error with migration instructions** ✅

---

## Testing Strategy

### 1. Unit Tests

```python
# Test indicator name generation
def test_explicit_naming():
    config = IndicatorConfig(
        indicator="rsi",
        name="rsi_custom",
        params={"period": 14}
    )
    assert config.name == "rsi_custom"

# Test name uniqueness validation
def test_duplicate_names_rejected():
    with pytest.raises(ValueError, match="Duplicate indicator names"):
        StrategyConfigurationV2(
            indicators=[
                {"indicator": "rsi", "name": "rsi_14", "period": 14},
                {"indicator": "rsi", "name": "rsi_14", "period": 7},  # Duplicate!
            ]
        )

# Test fuzzy set matching
def test_fuzzy_set_matching():
    validator = StrategyValidator()
    result = validator._validate_indicator_fuzzy_matching(
        indicators=[
            {"indicator": "rsi", "name": "rsi_14", "period": 14}
        ],
        fuzzy_sets={
            "rsi_14": {"oversold": [0, 20, 40]}
        }
    )
    assert result.is_valid
    assert len(result.errors) == 0
```

### 2. Integration Tests

```python
def test_end_to_end_training_with_explicit_names():
    """Test complete training flow with explicit naming."""
    strategy = load_strategy("tests/fixtures/explicit_naming_strategy.yaml")

    # Train model
    result = train_strategy(strategy)

    # Verify fuzzy features use custom names
    assert "rsi_fast_oversold" in result.feature_names
    assert "macd_standard_bullish" in result.feature_names
```

### 3. Migration Tests

```python
def test_migration_preserves_functionality():
    """Test that migrated strategy produces same results."""
    # Load and train with legacy format
    legacy_results = train_strategy("legacy_strategy.yaml")

    # Migrate to explicit format
    migrate_strategy("legacy_strategy.yaml", "migrated_strategy.yaml")

    # Train with migrated format
    migrated_results = train_strategy("migrated_strategy.yaml")

    # Results should be equivalent
    assert_features_equivalent(legacy_results, migrated_results)
```

---

## Rollout Plan (Simplified - Breaking Change)

### Step 1: Create Migration Script
- [ ] Write `scripts/migrate_indicator_naming.py`
- [ ] Test migration on sample strategies
- [ ] Verify auto-generated names are correct

### Step 2: Migrate All Strategies
- [ ] Run migration script on all strategy files
- [ ] Review and commit migrated strategies
- [ ] Update fuzzy_sets to match new names if needed

### Step 3: Core Implementation
- [ ] Update `IndicatorConfig` model (require `indicator` and `name`)
- [ ] Add name uniqueness validation
- [ ] Update `IndicatorFactory.build()` to accept `custom_name`
- [ ] Update `BaseIndicator.get_column_name()` to use custom name
- [ ] Add validation error with migration instructions
- [ ] Add unit tests

### Step 4: Engine & Pipeline Updates
- [ ] Update `IndicatorEngine.__init__()` with format validation
- [ ] Remove name mapping logic from `training_pipeline.py` (~80-100 lines)
- [ ] Simplify fuzzy set matching (direct column name lookup)
- [ ] Add integration tests

### Step 5: Documentation
- [ ] Update CLAUDE.md with new naming convention
- [ ] Update strategy documentation
- [ ] Add examples of explicit naming
- [ ] Document migration process

### Step 6: Verification
- [ ] Run full test suite
- [ ] Train a model with migrated strategy
- [ ] Verify fuzzy features use new names correctly
- [ ] Commit and deploy

**Timeline**: Can be completed in 1-2 days (not weeks!)

---

## Risk Analysis

### Risks

1. **Breaking Change**: Existing strategies will need migration
   - **Mitigation**: Auto-migration tool, grace period, clear warnings

2. **User Confusion**: Two fields might confuse users
   - **Mitigation**: Clear docs, examples, helpful error messages

3. **Migration Errors**: Auto-generated names might not match expectations
   - **Mitigation**: Review tool, dry-run mode, validation checks

4. **Performance Impact**: Extra field validation
   - **Mitigation**: Minimal - validation is O(n) where n = indicator count

### Success Criteria

1. ✅ All existing strategies can be auto-migrated successfully
2. ✅ Validation catches 100% of fuzzy set mismatches
3. ✅ User-friendly error messages guide corrections
4. ✅ No performance regression in training pipeline
5. ✅ Documentation clearly explains new format

---

## Examples

### Before (Current - Implicit)

```yaml
indicators:
  - name: "macd"
    fast_period: 12
    slow_period: 26
    signal_period: 9

fuzzy_sets:
  macd_12_26_9:  # Must guess this!
    bullish: [0, 10, 50]
```

### After (New - Explicit)

```yaml
indicators:
  - indicator: "macd"        # What to create
    name: "macd_standard"    # What to call it
    fast_period: 12
    slow_period: 26
    signal_period: 9

fuzzy_sets:
  macd_standard:  # Matches indicator.name - clear!
    bullish: [0, 10, 50]
```

---

## Open Questions

1. **Should `name` field support templates?**
   - e.g., `name: "rsi_{period}"` auto-expands to `rsi_14`
   - **Decision**: No - keep it simple and explicit

2. **Allow duplicate names across timeframes?**
   - e.g., `rsi_14` on 5m and 1h timeframes
   - **Decision**: No - name must be globally unique within strategy
   - Multi-timeframe indicators handled separately

3. **Support name aliases?**
   - e.g., `aliases: ["rsi_primary", "momentum_short"]`
   - **Decision**: Not in v1 - add if users request it

4. **Validate name doesn't conflict with reserved keywords?**
   - e.g., prevent `name: "close"` or `name: "volume"`
   - **Decision**: Yes - add reserved word check

---

## Appendix: Validation Error Messages

### Good Error Messages

```
❌ Indicator 'macd_standard' has no corresponding fuzzy_sets entry.
   Add a fuzzy_sets.macd_standard section with set definitions.

❌ Indicator #3 missing required 'name' field.
   Each indicator needs a unique name for referencing in fuzzy_sets.

   Example:
     - indicator: "rsi"
       name: "rsi_14"  # Add this!
       period: 14

❌ Duplicate indicator name 'rsi_14' found.
   Each indicator must have a unique 'name' field.

   Suggestion: Use descriptive names like:
     - rsi_short, rsi_medium, rsi_long
     - rsi_5m, rsi_1h, rsi_1d

⚠️  Fuzzy set 'old_indicator_name' doesn't match any indicator.
   This may be a typo or leftover from previous version.
   Available indicator names: rsi_14, macd_standard, bb_tight
```

---

## Conclusion

This design solves the implicit naming problem with an explicit, user-friendly approach that:
- Eliminates auto-generation surprises
- Makes validation trivial
- Improves strategy readability
- Provides clear migration path

**Recommendation**: Implement this design in phases with auto-migration support.
