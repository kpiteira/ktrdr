# Indicator & Fuzzy System Architecture Audit

**Date**: 2026-01-28
**Status**: Pre-Design Discovery
**Triggered by**: `ATRIndicator` lookup failure despite being listed in available types

## Executive Summary

Both the indicator and fuzzy systems suffer from significant architectural debt that makes them:
- **Hard to maintain**: Adding a new type requires touching 5+ files
- **Error-prone**: Case sensitivity bugs, typos in registries, incomplete schemas
- **Inconsistent**: Different validation patterns, case handling varies by location
- **Not DRY**: Same information duplicated across multiple registries

The immediate bug (ATRIndicator) was a symptom of a deeper problem: mixed-case registry keys combined with `.lower()` lookups created invisible gaps.

---

## Part 1: Indicator System Audit

### 1.1 Registry Structure

**Location**: `ktrdr/indicators/indicator_factory.py` (lines 41-170)

**Current state**: 170 lines to register ~39 indicators. Each indicator has 3-5 key variants:

```python
# Example: ATR has 4 entries
"ATR": ATRIndicator,           # UPPERCASE acronym
"ATRIndicator": ATRIndicator,  # PascalCase class name
"atr": ATRIndicator,           # lowercase
"atrindicator": ATRIndicator,  # lowercase full (added as bugfix)
```

**Problems**:
1. Exponential growth - each new indicator needs 4+ entries
2. Easy to miss a variant (the original bug)
3. Typo at line 159: `"keltnerchanelsindicator"` (missing 'n')
4. Memory waste storing duplicate mappings

### 1.2 Lookup Inconsistency

**Problem**: Registry stores mixed-case keys, but lookups always use `.lower()`:

| Location | Code | Issue |
|----------|------|-------|
| `indicator_engine.py:94` | `BUILT_IN_INDICATORS.get(definition.type.lower())` | Works for lowercase keys only |
| `strategy_validator.py:788` | `indicator_type.lower()` | Same pattern |

Since lookups use `.lower()`, the PascalCase keys (`"ATRIndicator"`) are **never matched** - they're dead code that clutters the registry and creates false confidence.

### 1.3 Adding a New Indicator (Current Process)

To add a new indicator, you must:

1. Create `ktrdr/indicators/new_indicator.py`
2. Add import to `indicator_factory.py` (line 8-37)
3. Add 4+ entries to `BUILT_IN_INDICATORS` dict
4. Update `ktrdr/indicators/__init__.py` exports
5. (Optional) Add to `categories.py` (lines 83-142)
6. (Optional) Add parameter schema to `schemas.py` (lines 607-630)
7. (Optional) Register in `tests/unit/indicators/indicator_registry.py`

**Result**: 5-7 files touched for a simple addition. Easy to forget one.

### 1.4 Parameter Validation Inconsistency

Two patterns coexist:

**Pattern A - Inline validation** (`rsi_indicator.py`):
```python
def _validate_params(self, params):
    period = params.get("period", 14)
    if not isinstance(period, int):
        raise DataError("RSI period must be an integer", ...)
    if period < 2:
        raise DataError("RSI period must be at least 2", ...)
```

**Pattern B - Schema validation** (`bollinger_bands_indicator.py`):
```python
def _validate_params(self, params):
    return BOLLINGER_BANDS_SCHEMA.validate(params)
```

**Impact**:
- Different error messages/codes
- Some indicators lack any validation
- `schemas.py` has schemas for only 21/39 indicators

### 1.5 Incomplete Schema Coverage

**File**: `ktrdr/indicators/schemas.py` (lines 607-630)

```python
PARAMETER_SCHEMAS = {
    "RSI": RSI_SCHEMA,
    "SMA": SMA_SCHEMA,
    # ... 21 total
}
```

**Missing schemas** (16 indicators):
- ADXIndicator
- AroonIndicator
- DonchianChannelsIndicator
- KeltnerChannelsIndicator
- ADLineIndicator
- CMFIndicator
- VolumeRatioIndicator
- DistanceFromMAIndicator
- FisherTransformIndicator
- SqueezeIntensityIndicator
- SuperTrendIndicator
- ZigZagIndicator
- BollingerBandWidthIndicator
- MomentumIndicator
- ROCIndicator
- WilliamsRIndicator

### 1.6 Circular Import Workaround

**File**: `ktrdr/config/strategy_validator.py` (lines 724-735)

```python
def _get_normalized_indicator_names(self) -> set[str]:
    """Lazy-load indicator names to avoid circular import."""
    if self._cached_indicator_names is None:
        from ktrdr.indicators.indicator_factory import BUILT_IN_INDICATORS
        # ...
```

This works but indicates architectural coupling that should be resolved.

### 1.7 Test Registry Duplication

**File**: `tests/unit/indicators/indicator_registry.py` (lines 81-289)

Tests maintain a separate registry with default params, reference values, and tolerances. This duplicates information that should be derivable from the main registry.

---

## Part 2: Fuzzy System Audit

### 2.1 No Registry Pattern

Unlike indicators which use `BUILT_IN_INDICATORS`, fuzzy membership functions use hardcoded dispatch:

**Location**: `ktrdr/fuzzy/membership.py` (lines 495-512)

```python
mf_type_lower = mf_type.lower()
if mf_type_lower == "triangular":
    return TriangularMF(parameters)
elif mf_type_lower == "trapezoidal":
    return TrapezoidalMF(parameters)
elif mf_type_lower == "gaussian":
    return GaussianMF(parameters)
else:
    raise ConfigurationError(...)
```

### 2.2 Hardcoded Type Dispatch (3 Locations!)

The same if/elif chain appears in THREE places:

| Location | Lines | Case-insensitive? |
|----------|-------|-------------------|
| `ktrdr/fuzzy/membership.py` | 495-512 | Yes (`.lower()`) |
| `ktrdr/fuzzy/config.py` | 325-330 | **NO** |
| `ktrdr/fuzzy/multi_timeframe_engine.py` | 218-233 | Yes (`.lower()`) |

**Bug risk**: `config.py` lacks `.lower()`, so `"Triangular"` would fail there but work elsewhere.

### 2.3 Parameter Validation Duplication

Each membership function class duplicates validation logic:

**TriangularMF** (lines 78-99):
```python
if len(parameters) != 3:
    raise ConfigurationError(...)
if not all(isinstance(p, (int, float)) for p in parameters):
    raise ConfigurationError(...)
if not (a <= b <= c):
    raise ConfigurationError(...)
```

**TrapezoidalMF** (lines 236-259): Nearly identical but for 4 parameters.

**GaussianMF** (lines 392-399): Different parameter structure, but same validation pattern.

### 2.4 Dual v2/v3 Mode Complexity

**File**: `ktrdr/fuzzy/engine.py` (lines 76-128)

The `FuzzyEngine` supports both v2 (legacy) and v3 (strategy) config formats:

```python
is_v3_format = isinstance(config, dict) and (
    not config or isinstance(next(iter(config.values())), FuzzySetDefinition)
)

if is_v3_format:
    self._initialize_v3(config)
else:
    self._initialize_membership_functions(config)
```

Both paths build the same internal structure but with different code paths - maintenance burden.

### 2.5 Configuration System Duplication

**V2 Config** (`ktrdr/fuzzy/config.py`):
- `FuzzyConfigModel`
- `FuzzySetConfigModel`
- Uses `TriangularMFConfig`, `TrapezoidalMFConfig`, `GaussianMFConfig`

**V3 Config** (`ktrdr/config/models.py`):
- `FuzzySetDefinition`
- Part of `StrategyConfigurationV3`
- Uses shorthand syntax `[a, b, c]` -> triangular

Two complete config systems for the same domain.

---

## Part 3: Cross-Cutting Issues

### 3.1 Inconsistent Patterns Between Systems

| Aspect | Indicators | Fuzzy |
|--------|------------|-------|
| Registry | Dict-based (`BUILT_IN_INDICATORS`) | Hardcoded if/elif |
| Case handling | `.lower()` at lookup | Inconsistent (2/3 use `.lower()`) |
| Adding new type | Edit registry dict | Edit 3 if/elif blocks |
| Validation | Mix of inline/schema | All inline, duplicated |
| Discovery | `BUILT_IN_INDICATORS.keys()` | Hardcoded list |

### 3.2 Common Anti-Patterns

1. **Manual registration** instead of auto-discovery
2. **Case normalization at lookup** instead of canonical storage
3. **Validation logic scattered** across implementations
4. **Multiple sources of truth** (factory, tests, schemas, categories)
5. **No introspection** - can't programmatically query capabilities

### 3.3 Impact on Agent-Generated Strategies

The agent generating `adaptive_volatility_breakout_v1` likely used `ATRIndicator` because:
- It appears in the available types list
- The class is named `ATRIndicator`
- No documentation says "use lowercase only"

The system should accept any reasonable variant, not require memorizing which forms work.

---

## Part 4: Problem Summary

### Critical Issues (Must Fix)

| ID | Issue | Impact | Location |
|----|-------|--------|----------|
| C1 | Registry stores mixed-case keys but lookup uses `.lower()` | Bugs like ATRIndicator | `indicator_factory.py` |
| C2 | Fuzzy type dispatch hardcoded in 3 places | Adding MF type requires 3 edits | `membership.py`, `config.py`, `multi_timeframe_engine.py` |
| C3 | Case handling inconsistent in fuzzy config | `"Triangular"` fails in config.py | `config.py:325` |

### High-Priority Issues

| ID | Issue | Impact | Location |
|----|-------|--------|----------|
| H1 | 170 lines for 39 indicators | Maintenance nightmare | `indicator_factory.py` |
| H2 | Parameter schemas missing for 16 indicators | Incomplete validation | `schemas.py` |
| H3 | Validation patterns inconsistent | Unpredictable errors | Various |
| H4 | Adding indicator requires 5+ file edits | Friction, errors | Multiple |

### Medium-Priority Issues

| ID | Issue | Impact | Location |
|----|-------|--------|----------|
| M1 | Circular import workaround | Technical debt | `strategy_validator.py` |
| M2 | Test registry duplicates main registry | Not DRY | `indicator_registry.py` |
| M3 | Dual v2/v3 fuzzy engine paths | Complexity | `engine.py` |
| M4 | No introspection for capabilities | Hard to document | Both systems |

---

## Part 5: Design Goals

A redesigned system should:

1. **Single canonical registration** - One line per type, auto-generate variants
2. **Case-insensitive by default** - Normalize at storage, not lookup
3. **Auto-discovery** - New type = new file, no registry edits
4. **Consistent validation** - Schema-based for all types
5. **Single source of truth** - Derive test data, categories, docs from registry
6. **Uniform patterns** - Indicators and fuzzy use same registry pattern
7. **Introspectable** - Query available types, their parameters, outputs programmatically

---

## Next Steps

1. **Design** (`/kdesign`): Create a unified registry system for both indicators and fuzzy membership functions
2. **Implement**: Refactor both systems to use the new pattern
3. **Migrate**: Ensure backward compatibility during transition
4. **Validate**: Verify agent-generated strategies work with any reasonable type name format

---

## Appendix A: Files Involved

### Indicator System
- `ktrdr/indicators/indicator_factory.py` - Registry (170 lines)
- `ktrdr/indicators/indicator_engine.py` - Lookup logic
- `ktrdr/indicators/base_indicator.py` - Base class
- `ktrdr/indicators/schemas.py` - Parameter schemas (incomplete)
- `ktrdr/indicators/categories.py` - Categorization
- `ktrdr/indicators/__init__.py` - Exports
- `ktrdr/config/strategy_validator.py` - Validation
- `ktrdr/config/models.py` - `IndicatorDefinition`
- `ktrdr/api/services/indicator_service.py` - API service
- `tests/unit/indicators/indicator_registry.py` - Test registry

### Fuzzy System
- `ktrdr/fuzzy/membership.py` - MF classes + factory
- `ktrdr/fuzzy/config.py` - V2 config models
- `ktrdr/fuzzy/engine.py` - FuzzyEngine
- `ktrdr/fuzzy/multi_timeframe_engine.py` - MTF engine
- `ktrdr/config/models.py` - `FuzzySetDefinition`

## Appendix B: Existing Type Registry Sizes

| System | Types | Registry Entries | Ratio |
|--------|-------|------------------|-------|
| Indicators | 39 | 170+ | 4.4x |
| Fuzzy MF | 3 | 3 (hardcoded) | 1x |

The indicator registry has 4.4x more entries than necessary due to case variants.
