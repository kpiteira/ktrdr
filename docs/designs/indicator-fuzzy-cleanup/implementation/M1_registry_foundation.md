---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 1: Registry Foundation

**Branch:** `feature/type-registry-m1`
**Goal:** Prove the TypeRegistry pattern works end-to-end with RSI indicator

## E2E Validation

### Test: indicators/registry-rsi-validation

**Location:** `tests/unit/indicators/test_registry_rsi_validation.py`
**Purpose:** Validate TypeRegistry pattern with RSI as proof of concept

**Success Criteria:**
- [ ] INDICATOR_REGISTRY exists with get, list_types, get_params_schema methods
- [ ] 'rsi' in list_types()
- [ ] All case variants (RSI, rsi, RSIIndicator, rsiindicator) resolve to RSIIndicator
- [ ] get_params_schema('rsi') returns Pydantic model with period, source fields
- [ ] RSI() with defaults creates instance with period=14, source='close'
- [ ] RSI(period=-1) raises DataError with error_code
- [ ] IndicatorEngine creates RSI for all type name variants
- [ ] Engine.compute() produces valid RSI column

---

## Task 1.1: Create TypeRegistry generic class

**File:** `ktrdr/core/type_registry.py` (new)
**Type:** CODING
**Estimated time:** 1-2 hours

**Description:**
Create generic `TypeRegistry[T]` class with case-insensitive lookup, registration, and schema introspection.

**Implementation:**
```python
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class TypeRegistry(Generic[T]):
    def __init__(self, name: str):
        self._name = name  # For error messages
        self._types: dict[str, type[T]] = {}
        self._canonical: set[str] = set()  # Track canonical names vs aliases

    def register(self, cls: type[T], canonical: str, aliases: list[str] | None = None) -> None:
        # Check collision, store canonical and aliases
        for name in [canonical] + (aliases or []):
            if name in self._types:
                raise ValueError(f"Cannot register {cls.__name__} as '{name}': already registered to {self._types[name].__name__}")
        self._types[canonical] = cls
        self._canonical.add(canonical)
        for alias in (aliases or []):
            self._types[alias] = cls

    def get(self, name: str) -> type[T] | None:
        return self._types.get(name.lower())

    def get_or_raise(self, name: str) -> type[T]:
        cls = self.get(name)
        if cls is None:
            available = sorted(self._canonical)
            raise ValueError(f"Unknown {self._name} type '{name}'. Available: {available}")
        return cls

    def list_types(self) -> list[str]:
        return sorted(self._canonical)

    def get_params_schema(self, name: str) -> type[BaseModel] | None:
        cls = self.get(name)
        return getattr(cls, "Params", None) if cls else None

    def __contains__(self, name: str) -> bool:
        return self.get(name) is not None
```

**Tests:** `tests/unit/core/test_type_registry.py`
- test_register_and_lookup
- test_case_insensitive_lookup
- test_aliases_work
- test_collision_raises
- test_get_or_raise_lists_available
- test_list_types_excludes_aliases

**Acceptance Criteria:**
- [ ] TypeRegistry class exists
- [ ] All unit tests pass
- [ ] Case-insensitive lookup works
- [ ] Collision detection fails fast

---

## Task 1.2: Add `__init_subclass__` to BaseIndicator

**File:** `ktrdr/indicators/base_indicator.py` (modify)
**Type:** CODING
**Estimated time:** 1-2 hours

**Description:**
Add auto-registration hook. Create INDICATOR_REGISTRY instance. Add base Params class. Wrap Pydantic errors in DataError.

**Implementation:**
```python
import inspect
from pydantic import BaseModel, ValidationError
from ktrdr.core.type_registry import TypeRegistry
from ktrdr.errors import DataError

INDICATOR_REGISTRY: TypeRegistry["BaseIndicator"] = TypeRegistry("indicator")

class BaseIndicator(ABC):
    class Params(BaseModel):
        pass

    _aliases: list[str] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if inspect.isabstract(cls):
            return

        module = cls.__module__
        if module.startswith("tests.") or ".tests." in module:
            return

        name = cls.__name__
        if name.endswith("Indicator"):
            name = name[:-9]
        canonical = name.lower()

        aliases = [cls.__name__.lower()]
        if cls._aliases:
            aliases.extend(cls._aliases)

        INDICATOR_REGISTRY.register(cls, canonical, aliases)

    def __init__(self, **kwargs):
        try:
            validated = self.Params(**kwargs)
        except ValidationError as e:
            raise DataError(
                f"Invalid parameters for {self.__class__.__name__}",
                error_code="INDICATOR-InvalidParameters",
                details={"validation_errors": e.errors()}
            ) from e

        for field_name in validated.model_fields:
            setattr(self, field_name, getattr(validated, field_name))

        # Store params dict for backward compatibility
        self.params = {field_name: getattr(validated, field_name)
                       for field_name in validated.model_fields}
```

**Tests:** `tests/unit/indicators/test_base_indicator.py`
- test_concrete_subclass_registers
- test_abstract_subclass_skipped
- test_test_class_skipped
- test_canonical_name_derivation
- test_init_validates_via_params
- test_init_sets_attributes

**Acceptance Criteria:**
- [ ] INDICATOR_REGISTRY exists and is importable
- [ ] Concrete subclasses auto-register
- [ ] Abstract classes don't register
- [ ] Test classes don't register
- [ ] Invalid params raise DataError

---

## Task 1.3: Add Params to RSIIndicator

**File:** `ktrdr/indicators/rsi_indicator.py` (modify)
**Type:** CODING
**Estimated time:** 30 min

**Description:**
Add Params class to RSI as proof of concept.

**Implementation:**
```python
from pydantic import Field

class RSIIndicator(BaseIndicator):
    class Params(BaseIndicator.Params):
        period: int = Field(default=14, ge=2, le=100, description="RSI lookback period")
        source: str = Field(default="close", description="Price source column")

    # Remove explicit __init__ — inherited from BaseIndicator
    # Keep compute() unchanged
```

**Tests:** Existing RSI tests should still pass, plus new registry tests

**Acceptance Criteria:**
- [ ] RSI has Params class
- [ ] RSI appears in registry as 'rsi', 'rsiindicator'
- [ ] Existing tests pass

---

## Task 1.4: Update IndicatorEngine with registry fallback

**File:** `ktrdr/indicators/indicator_engine.py` (modify)
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Try INDICATOR_REGISTRY first, fall back to BUILT_IN_INDICATORS for non-migrated indicators.

**Implementation:**
```python
from ktrdr.indicators.base_indicator import INDICATOR_REGISTRY

def _create_indicator(self, definition):
    # Try registry first
    cls = INDICATOR_REGISTRY.get(definition.type)
    if cls is not None:
        return cls(**definition.params)

    # Fallback during migration
    cls = BUILT_IN_INDICATORS.get(definition.type.lower())
    if cls is not None:
        return cls(**definition.params)

    available = sorted(set(INDICATOR_REGISTRY.list_types()) | set(BUILT_IN_INDICATORS.keys()))
    raise ValueError(f"Unknown indicator type '{definition.type}'. Available: {available}")
```

**Acceptance Criteria:**
- [ ] RSI created via registry
- [ ] Non-migrated indicators work via fallback
- [ ] Existing tests pass

---

## Task 1.5: Update `__init__.py` exports

**File:** `ktrdr/indicators/__init__.py` (modify)
**Type:** CODING
**Estimated time:** 15 min

**Description:**
Export INDICATOR_REGISTRY from package.

**Acceptance Criteria:**
- [ ] `from ktrdr.indicators import INDICATOR_REGISTRY` works
- [ ] 'rsi' in INDICATOR_REGISTRY

---

## Task 1.6: Execute M1 E2E Test

**Type:** VALIDATION
**Estimated time:** 10 min

**E2E Test:**
```bash
uv run python -c "
from ktrdr.indicators import INDICATOR_REGISTRY
from ktrdr.errors import DataError

# Verify RSI registered
assert 'rsi' in INDICATOR_REGISTRY

# Verify case variants
for v in ['rsi', 'RSI', 'RSIIndicator', 'rsiindicator']:
    assert INDICATOR_REGISTRY.get(v).__name__ == 'RSIIndicator'

# Verify Params schema
schema = INDICATOR_REGISTRY.get_params_schema('rsi')
assert 'period' in schema.model_fields

# Verify invalid params raise DataError
RSI = INDICATOR_REGISTRY.get('rsi')
try:
    RSI(period=-1)
    assert False
except DataError as e:
    assert 'validation_errors' in e.details

print('M1 E2E PASSED')
"
```

**Acceptance Criteria:**
- [ ] E2E test passes
- [ ] `make test-unit` passes
- [ ] `make quality` passes
