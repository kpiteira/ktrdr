# Unified Type Registry System: Architecture

## Overview

This design introduces a shared `TypeRegistry` pattern that both indicators and fuzzy membership functions use. Types auto-register when their class is defined (via `__init_subclass__`), eliminating manual registry maintenance. All lookups are case-insensitive.

## High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           ktrdr/core/                                   │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                      TypeRegistry[T]                              │  │
│  │  • register(cls, name, aliases)                                   │  │
│  │  • get(name) / get_or_raise(name)                                 │  │
│  │  • list_types() / get_params_schema(name)                         │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                    ▲                               ▲
                    │ uses                          │ uses
        ┌───────────┴───────────┐       ┌──────────┴──────────┐
        │                       │       │                     │
┌───────┴───────────────────────┴───┐ ┌─┴─────────────────────┴───────┐
│      ktrdr/indicators/            │ │       ktrdr/fuzzy/            │
│                                   │ │                               │
│  INDICATOR_REGISTRY ◄─────────┐   │ │  MEMBERSHIP_REGISTRY ◄────┐   │
│         │                     │   │ │         │                 │   │
│         │ auto-registers      │   │ │         │ auto-registers  │   │
│         ▼                     │   │ │         ▼                 │   │
│  ┌─────────────┐              │   │ │  ┌─────────────┐          │   │
│  │BaseIndicator│──────────────┘   │ │  │Membership   │──────────┘   │
│  │  __init_    │                  │ │  │Function     │              │
│  │  subclass__ │                  │ │  │  __init_    │              │
│  └──────┬──────┘                  │ │  │  subclass__ │              │
│         │                         │ │  └──────┬──────┘              │
│         │ inherits                │ │         │ inherits            │
│         ▼                         │ │         ▼                     │
│  ┌─────────────┐                  │ │  ┌─────────────┐              │
│  │RSIIndicator │                  │ │  │TriangularMF │              │
│  │ATRIndicator │                  │ │  │TrapezoidalMF│              │
│  │MACDIndicator│                  │ │  │ GaussianMF  │              │
│  │    ...      │                  │ │  └─────────────┘              │
│  └─────────────┘                  │ │                               │
│                                   │ │                               │
│  ┌─────────────┐                  │ │  ┌─────────────┐              │
│  │Indicator    │ queries registry │ │  │FuzzyEngine  │ queries      │
│  │Engine       │──────────────────┤ │  │             │ registry     │
│  └─────────────┘                  │ │  └─────────────┘──────────────┤
└───────────────────────────────────┘ └───────────────────────────────┘
```

### Component Relationships (Structured Summary)

| Component | Type | Depends On | Used By |
|-----------|------|------------|---------|
| `TypeRegistry` | Generic class | None | `INDICATOR_REGISTRY`, `MEMBERSHIP_REGISTRY` |
| `INDICATOR_REGISTRY` | Instance of `TypeRegistry` | `TypeRegistry` | `IndicatorEngine`, `StrategyValidator`, `IndicatorService` |
| `MEMBERSHIP_REGISTRY` | Instance of `TypeRegistry` | `TypeRegistry` | `FuzzyEngine`, `FuzzyService` |
| `BaseIndicator` | Abstract base class | `INDICATOR_REGISTRY` (registers to) | All indicator classes inherit from it |
| `MembershipFunction` | Abstract base class | `MEMBERSHIP_REGISTRY` (registers to) | All MF classes inherit from it |
| `IndicatorEngine` | Consumer | `INDICATOR_REGISTRY` (queries) | Training pipeline, backtesting |
| `FuzzyEngine` | Consumer | `MEMBERSHIP_REGISTRY` (queries) | Training pipeline, backtesting |

## Component Structure

```
ktrdr/core/
    type_registry.py        # NEW: Generic TypeRegistry class

ktrdr/indicators/
    base_indicator.py       # MODIFIED: Add __init_subclass__, Params pattern
    indicator_engine.py     # MODIFIED: Use registry instead of dict
    indicator_factory.py    # DELETE: Replaced by auto-registration
    [all indicator files]   # MODIFIED: Add Params class to each

ktrdr/fuzzy/
    membership.py           # MODIFIED: Add __init_subclass__, Params pattern
    engine.py               # MODIFIED: Remove v2, use registry
    config.py               # DELETE: V2 config models
    migration.py            # DELETE: V2 migration utilities

ktrdr/config/
    strategy_validator.py   # MODIFIED: Use registry for validation

scripts/
    migrate_strategy_types.py   # NEW: One-time migration script
```

## Components

### TypeRegistry

**Location**: `ktrdr/core/type_registry.py` (new)

**Purpose**: Generic, reusable registry for any type system. Handles registration, case-insensitive lookup, and schema introspection.

**Key behaviors**:
- Stores types by canonical lowercase name
- Supports aliases (e.g., "bbands" → BollingerBandsIndicator)
- Provides `get_or_raise()` with helpful error messages listing available types
- Can retrieve the `Params` schema for any registered type

**Interface** (illustrative):
```python
class TypeRegistry[T]:
    def register(cls: type[T], canonical_name: str, aliases: list[str] = None)
    def get(name: str) -> type[T] | None
    def get_or_raise(name: str) -> type[T]  # Raises with available types
    def list_types() -> list[str]           # Canonical names only
    def get_params_schema(name: str) -> type[BaseModel] | None
```

### BaseIndicator

**Location**: `ktrdr/indicators/base_indicator.py` (modified)

**Changes**:
- Add `__init_subclass__` that auto-registers subclasses
- Define `Params` base class pattern that all indicators must implement
- Module-level `INDICATOR_REGISTRY` instance

**Registration logic**:
- Canonical name derived from class name: `RSIIndicator` → `rsi`
- Skips abstract classes and test classes (checks module path)
- Registers full lowercase name as alias: `rsiindicator`
- Respects `_aliases` class attribute for custom aliases

**Params pattern**:
```python
class SomeIndicator(BaseIndicator):
    class Params(BaseModel):
        period: int = Field(default=14, ge=2)
        source: str = Field(default="close")
```

### MembershipFunction

**Location**: `ktrdr/fuzzy/membership.py` (modified)

**Changes**: Same pattern as BaseIndicator:
- Add `__init_subclass__` for auto-registration
- Module-level `MEMBERSHIP_REGISTRY` instance
- Required `Params` class per membership function type
- Delete `MembershipFunctionFactory` class

**Canonical names**: `TriangularMF` → `triangular`, `GaussianMF` → `gaussian`

### IndicatorEngine

**Location**: `ktrdr/indicators/indicator_engine.py` (modified)

**Changes**:
- Replace `BUILT_IN_INDICATORS.get()` with `INDICATOR_REGISTRY.get_or_raise()`
- Remove import of `indicator_factory`

The engine's responsibility stays the same — it just uses the registry instead of a manual dict.

### FuzzyEngine

**Location**: `ktrdr/fuzzy/engine.py` (modified)

**Changes**:
- Delete all v2 mode detection and code paths
- Accept only `dict[str, FuzzySetDefinition]` (v3 format)
- Use `MEMBERSHIP_REGISTRY` for type lookup instead of hardcoded if/elif
- Remove `_config` attribute and v2-related methods

Estimated deletion: ~400 lines of v2 code.

### Strategy Validator

**Location**: `ktrdr/config/strategy_validator.py` (modified)

**Changes**:
- Replace lazy-loaded `BUILT_IN_INDICATORS` import with `INDICATOR_REGISTRY`
- The circular import workaround may become unnecessary (registry is in a separate module)

## Data Flow

### Registration Flow (Import Time)

```
┌──────────────────┐      ┌───────────────────┐      ┌──────────────────┐
│  Python Import   │      │  Class Definition │      │    Registry      │
│                  │      │                   │      │                  │
│ import rsi_      │─────▶│ class RSIIndicator│─────▶│ __init_subclass__│
│ indicator        │      │ (BaseIndicator)   │      │ triggered        │
└──────────────────┘      └───────────────────┘      └────────┬─────────┘
                                                              │
                                                              ▼
                                                     ┌──────────────────┐
                                                     │ Derive canonical │
                                                     │ name: "rsi"      │
                                                     └────────┬─────────┘
                                                              │
                                                              ▼
                                                     ┌──────────────────┐
                                                     │ Register:        │
                                                     │ "rsi" → class    │
                                                     │ "rsiindicator" → │
                                                     │   class (alias)  │
                                                     └──────────────────┘
```

**Registration Steps (Structured Summary):**

1. Python imports a module containing an indicator class (e.g., `rsi_indicator.py`)
2. Class definition `class RSIIndicator(BaseIndicator)` triggers `__init_subclass__`
3. Registration logic checks: is class abstract? is it in test module? → skip if yes
4. Canonical name derived: strip "Indicator" suffix, lowercase → `"rsi"`
5. Aliases collected: full lowercase classname (`"rsiindicator"`) + any `_aliases` class attribute
6. `INDICATOR_REGISTRY.register(RSIIndicator, "rsi", ["rsiindicator"])` called
7. Registry stores: `{"rsi": RSIIndicator, "rsiindicator": RSIIndicator}`

All registration happens at import time. By the time application code runs, registries are fully populated.

### Registration Logic Details

The `__init_subclass__` hook uses these rules to determine whether to register a class:

**Skip Registration If:**

1. **Abstract class**: `inspect.isabstract(cls)` returns `True`
   - Checks for unimplemented `@abstractmethod` decorators
   - Allows intermediate abstract classes like `OscillatorIndicator(BaseIndicator, ABC)`

2. **Test class**: Module path indicates test code
   ```python
   module = cls.__module__
   if module.startswith("tests.") or ".tests." in module:
       # Skip — don't pollute production registry with test mocks
   ```

**Name Derivation:**

1. Strip known suffixes: `"Indicator"` for indicators, `"MF"` for membership functions
2. Lowercase the result
3. Examples: `RSIIndicator` → `rsi`, `BollingerBandsIndicator` → `bollingerbands`, `TriangularMF` → `triangular`

**Alias Collection:**

1. Full lowercase class name (e.g., `rsiindicator`)
2. Any names in `cls._aliases` list (e.g., `["bbands", "bollinger"]`)

**Collision Handling:**

If canonical name or any alias is already registered, raise `ValueError` immediately:
```python
raise ValueError(
    f"Cannot register {cls.__name__} as '{name}': "
    f"already registered to {existing.__name__}"
)
```

### Lookup Flow (Runtime)

```
┌──────────────────┐      ┌───────────────────┐      ┌──────────────────┐
│  Strategy YAML   │      │  IndicatorEngine  │      │    Registry      │
│                  │      │                   │      │                  │
│ type: "ATR"      │─────▶│ _create_indicator │─────▶│ get_or_raise()   │
│ period: 14       │      │                   │      │                  │
└──────────────────┘      └───────────────────┘      └────────┬─────────┘
                                                              │
                                    ┌─────────────────────────┘
                                    │
                                    ▼
                          ┌──────────────────┐
                          │ Normalize:       │
                          │ "ATR" → "atr"    │
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐      ┌──────────────────┐
                          │ Lookup:          │      │ Instantiate:     │
                          │ "atr" → class    │─────▶│ ATRIndicator(    │
                          │                  │      │   period=14)     │
                          └──────────────────┘      └──────────────────┘
```

**Lookup Steps (Structured Summary):**

1. Strategy YAML specifies `type: "ATR"` with params `period: 14`
2. `IndicatorEngine._create_indicator()` receives the definition
3. Engine calls `INDICATOR_REGISTRY.get_or_raise("ATR")`
4. Registry normalizes input: `"ATR".lower()` → `"atr"`
5. Registry looks up `"atr"` in internal dict → finds `ATRIndicator` class
6. Engine instantiates: `ATRIndicator(period=14)`
7. If lookup fails: `ValueError` raised with list of all available types

Any case variant (`ATR`, `atr`, `ATRIndicator`, `atrindicator`) resolves to the same class.

## State Management

| State | Where | Lifecycle |
|-------|-------|-----------|
| `INDICATOR_REGISTRY` | `base_indicator.py` module level | Populated at import, read-only after |
| `MEMBERSHIP_REGISTRY` | `membership.py` module level | Populated at import, read-only after |

Registries are effectively immutable after import completes. Thread-safe for reads.

## Import Requirements

For auto-registration to work, indicator/MF modules must be imported before the registry is queried. This is ensured by the package `__init__.py` files:

```python
# ktrdr/indicators/__init__.py
from ktrdr.indicators.base_indicator import INDICATOR_REGISTRY

# Import all indicator modules to trigger registration
from ktrdr.indicators.rsi_indicator import RSIIndicator
from ktrdr.indicators.atr_indicator import ATRIndicator
from ktrdr.indicators.macd_indicator import MACDIndicator
# ... all 39 indicators

__all__ = ["INDICATOR_REGISTRY", "RSIIndicator", ...]
```

**Critical Rule**: Consumers must import from `ktrdr.indicators`, not directly from submodules:

```python
# ✅ Correct — triggers all registrations via __init__.py
from ktrdr.indicators import INDICATOR_REGISTRY

# ❌ Wrong — registry may be empty if other modules not yet imported
from ktrdr.indicators.base_indicator import INDICATOR_REGISTRY
```

Same pattern applies to `ktrdr.fuzzy` and `MEMBERSHIP_REGISTRY`.

## Error Handling

| Situation | Error | Message Quality |
|-----------|-------|-----------------|
| Unknown type name | `ValueError` | Lists all available types |
| Invalid indicator params | `DataError` | Wraps Pydantic errors in `details["validation_errors"]` |
| Invalid MF params | `ConfigurationError` | Wraps Pydantic errors in `details["validation_errors"]` |
| V2 config passed to FuzzyEngine | `ConfigurationError` | Clear "v2 no longer supported" message |
| Name collision at registration | `ValueError` | Names both classes involved, fails fast |

**Note**: Pydantic `ValidationError` is wrapped at the base class level (`BaseIndicator`, `MembershipFunction`) to provide a consistent exception interface. Callers only need to catch `DataError` or `ConfigurationError`.

## Integration Points

| Component | Current State | Change Needed |
|-----------|---------------|---------------|
| `IndicatorEngine` | Uses `BUILT_IN_INDICATORS` dict | Switch to `INDICATOR_REGISTRY` |
| `StrategyValidator` | Lazy-loads `BUILT_IN_INDICATORS` | Switch to `INDICATOR_REGISTRY` |
| `IndicatorService` (API) | Iterates `BUILT_IN_INDICATORS` | Switch to `INDICATOR_REGISTRY.list_types()` |
| `FuzzyEngine` | Dual v2/v3 mode | V3 only, use `MEMBERSHIP_REGISTRY` |
| `FuzzyService` (API) | Uses v2 config models | Switch to v3 only |
| `TrainingPipeline` | Uses `FuzzyConfigLoader` | Remove, use v3 config directly |
| `MultiTimeframeFuzzyEngine` | Has own type dispatch | Use `MEMBERSHIP_REGISTRY` |

## Files to Delete

| File | Lines | Reason |
|------|-------|--------|
| `ktrdr/indicators/indicator_factory.py` | ~170 | Registry replaced by auto-registration |
| `ktrdr/indicators/schemas.py` | ~630 | Params classes replace parameter schemas |
| `ktrdr/fuzzy/config.py` | ~680 | V2 config models |
| `ktrdr/fuzzy/migration.py` | ~100 | V2→V3 migration utilities |
| Sections of `ktrdr/fuzzy/engine.py` | ~400 | V2 code paths |

## Migration Considerations

Existing strategy files use various type name formats (`RSIIndicator`, `ATR`, `BollingerBands`). A migration script will normalize these to canonical lowercase (`rsi`, `atr`, `bollingerbands`).

The v2 fuzzy config format is no longer supported. Any code using `FuzzyConfig` or `FuzzyConfigLoader` must be updated to use v3 `FuzzySetDefinition` format.

## Verification Approach

| Component | How to Verify |
|-----------|---------------|
| TypeRegistry | Unit tests for registration, lookup, collision handling |
| Auto-registration | Integration test: import indicators, verify all 39 registered |
| IndicatorEngine | Existing tests should pass unchanged |
| FuzzyEngine v3-only | Unit test: v2 config raises clear error |
| Migration script | Dry-run on test strategies, verify round-trip |
| Params completeness | Test that every registered type has a Params class |

---

## Implementation Planning Summary

This section consolidates the architecture into structured requirements for implementation planning.

### New Components to Create

| Component | Location | Purpose |
|-----------|----------|---------|
| `TypeRegistry` class | `ktrdr/core/type_registry.py` | Generic registry with case-insensitive lookup |
| Migration script | `scripts/migrate_strategy_types.py` | Normalize type names in strategy YAMLs |

### Existing Components to Modify

| Component | Location | Changes Required |
|-----------|----------|------------------|
| `BaseIndicator` | `ktrdr/indicators/base_indicator.py` | Add `__init_subclass__`, add `INDICATOR_REGISTRY` instance |
| `MembershipFunction` | `ktrdr/fuzzy/membership.py` | Add `__init_subclass__`, add `MEMBERSHIP_REGISTRY` instance, delete `MembershipFunctionFactory` |
| All 39 indicator classes | `ktrdr/indicators/*.py` | Add `Params` nested class to each |
| All 3 MF classes | `ktrdr/fuzzy/membership.py` | Add `Params` nested class to each |
| `IndicatorEngine` | `ktrdr/indicators/indicator_engine.py` | Replace `BUILT_IN_INDICATORS` with `INDICATOR_REGISTRY` |
| `FuzzyEngine` | `ktrdr/fuzzy/engine.py` | Delete v2 code paths, use `MEMBERSHIP_REGISTRY` |
| `StrategyValidator` | `ktrdr/config/strategy_validator.py` | Replace `BUILT_IN_INDICATORS` with `INDICATOR_REGISTRY` |
| `IndicatorService` | `ktrdr/api/services/indicator_service.py` | Use `INDICATOR_REGISTRY` |
| `FuzzyService` | `ktrdr/api/services/fuzzy_service.py` | Remove v2 config handling |
| `TrainingPipeline` | `ktrdr/training/training_pipeline.py` | Remove `FuzzyConfigLoader` usage |
| `MultiTimeframeFuzzyEngine` | `ktrdr/fuzzy/multi_timeframe_engine.py` | Use `MEMBERSHIP_REGISTRY` |

### Files to Delete

| File | Lines | Blocked By |
|------|-------|------------|
| `ktrdr/indicators/indicator_factory.py` | ~170 | All consumers migrated to registry |
| `ktrdr/indicators/schemas.py` | ~630 | All indicators have Params classes |
| `ktrdr/fuzzy/config.py` | ~680 | All consumers migrated to v3 |
| `ktrdr/fuzzy/migration.py` | ~100 | No v2 code remaining |

### Skills to Update

| Skill | Location | Changes Required |
|-------|----------|------------------|
| `technical-indicators` | `.claude/skills/technical-indicators/SKILL.md` | Update "Adding a New Indicator" section |
| `fuzzy-logic-engine` | `.claude/skills/fuzzy-logic-engine/SKILL.md` | Remove v2 references, add "Adding a New MF" section |
