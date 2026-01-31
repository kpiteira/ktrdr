---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 3: Fuzzy System Migrated

**Branch:** `feature/type-registry-m3`
**Builds on:** M1
**Goal:** Membership functions use registry, v2 code deleted

## E2E Validation

### Test: fuzzy/migration-complete

**Location:** `tests/unit/fuzzy/test_fuzzy_migration_complete.py`

**Success Criteria:**
- [ ] config.py and migration.py do not exist in ktrdr/fuzzy/
- [ ] MEMBERSHIP_REGISTRY importable from ktrdr.fuzzy
- [ ] All 3 MF types registered (triangular, trapezoidal, gaussian)
- [ ] Case-insensitive lookup works
- [ ] Invalid params raise ConfigurationError
- [ ] V2 config rejected with clear error
- [ ] FuzzyEngine v3 mode works

---

## Task 3.1: Add `__init_subclass__` to MembershipFunction

**File:** `ktrdr/fuzzy/membership.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**Implementation:**
```python
import inspect
from pydantic import BaseModel, ValidationError
from ktrdr.core.type_registry import TypeRegistry
from ktrdr.errors import ConfigurationError

MEMBERSHIP_REGISTRY: TypeRegistry["MembershipFunction"] = TypeRegistry("membership function")

class MembershipFunction(ABC):
    class Params(BaseModel):
        parameters: list[float]

    _aliases: list[str] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if inspect.isabstract(cls):
            return

        module = cls.__module__
        if module.startswith("tests.") or ".tests." in module:
            return

        name = cls.__name__
        if name.endswith("MF"):
            name = name[:-2]
        canonical = name.lower()

        aliases = [cls.__name__.lower()]
        if cls._aliases:
            aliases.extend(cls._aliases)

        MEMBERSHIP_REGISTRY.register(cls, canonical, aliases)

    def __init__(self, parameters: list[float]):
        try:
            validated = self.Params(parameters=parameters)
        except ValidationError as e:
            raise ConfigurationError(
                f"Invalid parameters for {self.__class__.__name__}",
                error_code="MF-InvalidParameters",
                details={"validation_errors": e.errors()}
            ) from e
        self._init_from_params(validated.parameters)

    @abstractmethod
    def _init_from_params(self, parameters: list[float]) -> None:
        pass
```

**Acceptance Criteria:**
- [ ] MEMBERSHIP_REGISTRY exists
- [ ] Base class has __init_subclass__
- [ ] Validation wraps errors in ConfigurationError

---

## Task 3.2: Add Params to TriangularMF, TrapezoidalMF, GaussianMF

**File:** `ktrdr/fuzzy/membership.py`
**Type:** CODING
**Estimated time:** 1 hour

**Implementation:**
```python
class TriangularMF(MembershipFunction):
    class Params(MembershipFunction.Params):
        @field_validator("parameters")
        @classmethod
        def validate_parameters(cls, v):
            if len(v) != 3:
                raise ValueError("Triangular requires 3 parameters [a, b, c]")
            a, b, c = v
            if not (a <= b <= c):
                raise ValueError("Must satisfy a <= b <= c")
            return v

    def _init_from_params(self, parameters: list[float]) -> None:
        self.a, self.b, self.c = parameters
```

**Acceptance Criteria:**
- [ ] All 3 MFs have Params with validators
- [ ] All 3 in MEMBERSHIP_REGISTRY
- [ ] Invalid params raise ConfigurationError

---

## Task 3.3: Update FuzzyEngine to use registry

**File:** `ktrdr/fuzzy/engine.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**Changes:**
- Delete _initialize_membership_functions (v2 path)
- Delete is_v3_format detection logic
- Replace if/elif dispatch with MEMBERSHIP_REGISTRY.get_or_raise()
- Add clear error for non-dict config

**Acceptance Criteria:**
- [ ] No v2 code paths
- [ ] Uses MEMBERSHIP_REGISTRY
- [ ] Non-v3 config raises ConfigurationError

---

## Task 3.4: Update MultiTimeframeFuzzyEngine

**File:** `ktrdr/fuzzy/multi_timeframe_engine.py`
**Type:** CODING
**Estimated time:** 30 min

**Changes:**
- Replace hardcoded MF dispatch with registry lookup

**Acceptance Criteria:**
- [ ] Uses MEMBERSHIP_REGISTRY
- [ ] Tests pass

---

## Task 3.5: Delete v2 fuzzy files

**Files to delete:**
- `ktrdr/fuzzy/config.py`
- `ktrdr/fuzzy/migration.py`

**Verification:**
```bash
git grep -l "from ktrdr.fuzzy.config" -- "*.py" || echo "No config imports"
git grep -l "FuzzyConfigLoader" -- "*.py" || echo "No FuzzyConfigLoader usage"
```

**Acceptance Criteria:**
- [ ] Both files deleted
- [ ] No remaining imports

---

## Task 3.6: Update `__init__.py` exports

**File:** `ktrdr/fuzzy/__init__.py`
**Type:** CODING
**Estimated time:** 15 min

**Acceptance Criteria:**
- [ ] `from ktrdr.fuzzy import MEMBERSHIP_REGISTRY` works
- [ ] No v2 exports

---

## Task 3.7: Execute M3 E2E Test

**Type:** VALIDATION

**E2E Test:**
```bash
uv run python -c "
from ktrdr.fuzzy import MEMBERSHIP_REGISTRY
from ktrdr.fuzzy.membership import TriangularMF
from ktrdr.errors import ConfigurationError

types = MEMBERSHIP_REGISTRY.list_types()
assert set(types) == {'triangular', 'trapezoidal', 'gaussian'}

for name in ['triangular', 'Triangular', 'TRIANGULAR', 'triangularmf']:
    assert MEMBERSHIP_REGISTRY.get(name) is not None

try:
    TriangularMF([1, 2])  # Wrong count
    assert False
except ConfigurationError:
    pass

print('M3 E2E PASSED')
"

test ! -f ktrdr/fuzzy/config.py && echo 'config.py deleted'
test ! -f ktrdr/fuzzy/migration.py && echo 'migration.py deleted'
```

**Acceptance Criteria:**
- [ ] E2E test passes
- [ ] `make test-unit` passes
- [ ] `make quality` passes
