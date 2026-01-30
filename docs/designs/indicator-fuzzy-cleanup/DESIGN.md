# Unified Type Registry System: Design

## Problem Statement

The indicator and fuzzy systems use manually-maintained registries that are error-prone and create unnecessary friction. The indicator registry has 170+ entries for 39 types (4.4x bloat from case variants), while the fuzzy system uses hardcoded if/elif chains duplicated in three files. This led to a bug where `ATRIndicator` appeared in available types but couldn't be looked up because mixed-case keys weren't matched after `.lower()` normalization. Adding a new indicator requires editing 5+ files, and there's no consistent pattern between the two systems despite similar needs.

## Goals

1. **Zero-touch registration**: Adding a new indicator or membership function should require only creating the file — no registry edits, no imports to add elsewhere
2. **Case-insensitive by design**: Any reasonable variant (`ATR`, `atr`, `ATRIndicator`, `atrindicator`) should resolve to the same type
3. **Single source of truth**: One place defines each type's existence, parameters, and metadata
4. **Consistent patterns**: Indicators and fuzzy membership functions use the same registry mechanism
5. **Required parameter schemas**: Every type must declare its parameters via a `Params` class for full introspection
6. **Delete v2 fuzzy code**: Complete the v3 migration by removing all v2 config and dual-mode logic
7. **Updated skills**: Refresh the `technical-indicators` and `fuzzy-logic-engine` skills to reflect new patterns

## Non-Goals (Out of Scope)

1. **Changing indicator computation logic**: We're fixing registration/lookup, not rewriting how RSI or MACD compute values
2. **Adding new indicators or membership functions**: This is infrastructure cleanup, not feature addition
3. **Backward compatibility for type names**: We can break existing strategies and fix them separately
4. **Auto-discovery via module scanning**: We're using `__init_subclass__`, not filesystem scanning
5. **Changing strategy YAML format**: The v3 format stays the same; only internal lookup changes

## User Experience

### Adding a New Indicator (After)

Create one file:

```python
# ktrdr/indicators/awesome_indicator.py
from ktrdr.indicators.base_indicator import BaseIndicator

class AwesomeIndicator(BaseIndicator):
    """Computes the Awesome Oscillator."""

    class Params(BaseIndicator.Params):
        fast_period: int = Field(default=5, ge=1, description="Fast MA period")
        slow_period: int = Field(default=34, ge=1, description="Slow MA period")

    def __init__(self, fast_period: int = 5, slow_period: int = 34):
        self.fast_period = fast_period
        self.slow_period = slow_period

    def compute(self, df: pd.DataFrame) -> pd.Series:
        # ... implementation ...
```

That's it. No registry edits. The indicator is automatically available as:
- `awesome` (canonical)
- `awesomeindicator`
- `AwesomeIndicator`
- `AWESOME`
- Any case variant

### Adding a New Membership Function (After)

Create one file:

```python
# ktrdr/fuzzy/sigmoid_mf.py
from ktrdr.fuzzy.membership import MembershipFunction

class SigmoidMF(MembershipFunction):
    """S-shaped membership function."""

    class Params(MembershipFunction.Params):
        center: float = Field(..., description="Inflection point")
        slope: float = Field(default=1.0, gt=0, description="Steepness")

    def __init__(self, parameters: list[float]):
        # parameters = [center, slope]
        ...

    def evaluate(self, x) -> float:
        # ... implementation ...
```

Automatically available as `sigmoid`, `sigmoidmf`, `SigmoidMF`, etc.

### Using in Strategy YAML (Unchanged)

```yaml
indicators:
  awesome_5_34:
    type: awesome          # Works
    fast_period: 5
    slow_period: 34

  rsi_14:
    type: RSIIndicator     # Also works (case-insensitive)
    period: 14

fuzzy_sets:
  rsi_momentum:
    indicator: rsi_14
    oversold: [0, 20, 35]  # Shorthand still works
    custom:
      type: sigmoid        # New MF type works immediately
      parameters: [50, 0.5]
```

### Querying Available Types

```python
from ktrdr.indicators import INDICATOR_REGISTRY
from ktrdr.fuzzy import MEMBERSHIP_REGISTRY

# List all indicators
INDICATOR_REGISTRY.list_types()  # ['adx', 'aroon', 'atr', 'awesome', ...]

# Get indicator class
cls = INDICATOR_REGISTRY.get('atr')  # ATRIndicator

# Get parameter schema
schema = INDICATOR_REGISTRY.get_params_schema('atr')  # Pydantic model

# Check if type exists
'macd' in INDICATOR_REGISTRY  # True
```

## Key Decisions

### Decision 1: Shared `TypeRegistry` Base Class

**Choice**: Create a generic `TypeRegistry[T]` class that both indicators and membership functions use.

**Alternatives considered**:
- Separate implementations for each system (rejected: duplication)
- Module scanning at import time (rejected: too magical, import order issues)

**Rationale**: Single implementation ensures consistent behavior. Generic typing provides type safety. Both systems have identical needs (register types, lookup by name, list available).

### Decision 2: `__init_subclass__` for Auto-Registration

**Choice**: Types auto-register when their class is defined via `__init_subclass__`.

**Alternatives considered**:
- Explicit decorator `@register_indicator` (rejected: still requires action per type)
- Module scanning (rejected: import-time magic)

**Rationale**: `__init_subclass__` is standard Python, well-understood, and requires zero explicit registration code. Test mocks can be excluded by checking module path.

### Decision 3: Canonical Name Derivation

**Choice**: Canonical name derived by lowercasing class name and stripping common suffixes (`Indicator`, `MF`).

```python
ATRIndicator -> "atr"
BollingerBandsIndicator -> "bollingerbands"
TriangularMF -> "triangular"
GaussianMF -> "gaussian"
```

**Alternatives considered**:
- Require explicit `name` class attribute (rejected: boilerplate)
- Use full lowercase class name (rejected: `atrindicator` is awkward)

**Rationale**: Most natural names. `type: atr` reads better than `type: atrindicator`.

### Decision 4: Required `Params` Nested Class

**Choice**: Every indicator/membership function must define a `Params` class inheriting from `BaseModel`.

```python
class RSIIndicator(BaseIndicator):
    class Params(BaseIndicator.Params):
        period: int = Field(default=14, ge=2, le=100)
        source: str = Field(default="close")
```

**Alternatives considered**:
- Optional schemas (rejected: incomplete introspection)
- Auto-derive from `__init__` signature (rejected: can't express constraints)

**Rationale**: Full introspection for agent-generated strategies, API documentation, and validation. The `Params` class is the single source of truth for what parameters a type accepts.

### Decision 5: Delete V2 Fuzzy Code Entirely

**Choice**: Remove all v2 config models, dual-mode logic in `FuzzyEngine`, and related code.

**Alternatives considered**:
- Keep v2 for backward compatibility (rejected: Karl confirmed no BC needed)
- Deprecation warnings first (rejected: unnecessary complexity)

**Rationale**: v2 was supposed to be deleted during v3 migration. Keeping it adds ~700 lines of dead code and dual-mode complexity. Clean break is simpler.

### Decision 6: Aliases via Class Attribute

**Choice**: Types can declare aliases via an optional `_aliases` class attribute.

```python
class BollingerBandsIndicator(BaseIndicator):
    _aliases = ["bbands", "bollinger"]
```

**Alternatives considered**:
- Decorator parameter (rejected: requires decorator)
- Separate alias registry (rejected: splits definition)

**Rationale**: Keeps all type metadata in one place. Most types won't need aliases; those that do can declare them simply.

## Resolved Questions

1. **Test class filtering**: Check `cls.__module__` for test paths. Implementation will determine exact approach.

2. **Migration path**: Create a one-time script to update all strategy files with new canonical type names.

3. **Circular import handling**: To be resolved in architecture — likely by moving registry to a separate module with no dependencies.

4. **Base `Params` class fields**: Each indicator declares ALL its params explicitly. No shared base fields. This is more verbose but clearer — `source` appears in most indicators but some have multiple sources or none.

5. **Multi-output indicator metadata**: Keep `get_output_names()` classmethod separate from `Params`. Params are constructor inputs; output names are computation outputs.
