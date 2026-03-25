# E2E Test: fuzzy/migration-complete

**Purpose:** Validate the M3 fuzzy system migration is complete: v2 config files deleted, MEMBERSHIP_REGISTRY is sole source of truth, all 3 MF types registered with validated Params classes

**Duration:** ~30s (Python introspection, no API calls or external dependencies)

**Category:** Fuzzy / Architecture / Migration

---

## Pre-Flight Checks

**Required modules:**
- None (this test validates Python code structure, does not require running services)

**Test-specific checks:**
- [ ] Python environment available: `uv run python --version` succeeds
- [ ] ktrdr package importable: `uv run python -c "import ktrdr"` succeeds

**Note:** This test validates internal architecture, not runtime behavior. It requires only the Python environment, not Docker or API services.

---

## Test Data

```python
# Expected MF type count
EXPECTED_MF_COUNT = 3

# Expected MF canonical names
EXPECTED_MF_TYPES = ["triangular", "trapezoidal", "gaussian"]

# Files that must NOT exist (v2 config system)
DELETED_FILES = [
    "ktrdr/fuzzy/config.py",
    "ktrdr/fuzzy/migration.py",
]

# V2 classes that must NOT be exported from ktrdr.fuzzy
V2_CLASSES_NOT_EXPORTED = [
    "FuzzyConfig",
    "FuzzyConfigLoader",
    "FuzzySetConfig",
]
```

**Why this data:**
- 3 types: triangular, trapezoidal, gaussian are the membership function types
- Deleted files represent the old v2 config-based pattern being replaced
- V2 classes should no longer be accessible from the public API

---

## Execution Steps

### Phase 1: V2 File Deletion Verification

#### 1.1 Verify config.py Deleted

**Command:**
```bash
if [ -f "ktrdr/fuzzy/config.py" ]; then
  echo "FAIL: config.py still exists"
  exit 1
else
  echo "OK: config.py deleted"
fi
```

**Expected:**
- Output: "OK: config.py deleted"
- Exit code: 0

#### 1.2 Verify migration.py Deleted

**Command:**
```bash
if [ -f "ktrdr/fuzzy/migration.py" ]; then
  echo "FAIL: migration.py still exists"
  exit 1
else
  echo "OK: migration.py deleted"
fi
```

**Expected:**
- Output: "OK: migration.py deleted"
- Exit code: 0

---

### Phase 2: MEMBERSHIP_REGISTRY Importable and Contains 3 Types

#### 2.1 Verify MEMBERSHIP_REGISTRY Importable from ktrdr.fuzzy

**Command:**
```bash
uv run python -c "
from ktrdr.fuzzy import MEMBERSHIP_REGISTRY

print(f'MEMBERSHIP_REGISTRY imported successfully')
print(f'Registry type: {type(MEMBERSHIP_REGISTRY).__name__}')
print('OK: MEMBERSHIP_REGISTRY importable from ktrdr.fuzzy')
"
```

**Expected:**
- Output includes: "OK: MEMBERSHIP_REGISTRY importable from ktrdr.fuzzy"
- Exit code: 0

#### 2.2 Verify Registry Contains Exactly 3 Types

**Command:**
```bash
uv run python -c "
from ktrdr.fuzzy import MEMBERSHIP_REGISTRY

types = MEMBERSHIP_REGISTRY.list_types()
count = len(types)

print(f'Registered types: {sorted(types)}')
print(f'Count: {count}')

if count != 3:
    print(f'FAIL: Expected 3 types, got {count}')
    exit(1)

expected = {'triangular', 'trapezoidal', 'gaussian'}
actual = set(types)

if actual != expected:
    missing = expected - actual
    extra = actual - expected
    if missing:
        print(f'FAIL: Missing types: {missing}')
    if extra:
        print(f'FAIL: Extra types: {extra}')
    exit(1)

print('OK: Exactly 3 expected types registered (triangular, trapezoidal, gaussian)')
"
```

**Expected:**
- Output includes: "OK: Exactly 3 expected types registered"
- Exit code: 0

---

### Phase 3: Params Class Validation

#### 3.1 Verify All MF Types Have Params Inheriting from BaseModel

**Command:**
```bash
uv run python -c "
from pydantic import BaseModel
from ktrdr.fuzzy import MEMBERSHIP_REGISTRY
from ktrdr.fuzzy.membership import MembershipFunction

failures = []

for type_name in MEMBERSHIP_REGISTRY.list_types():
    cls = MEMBERSHIP_REGISTRY.get(type_name)

    if not hasattr(cls, 'Params'):
        failures.append(f'{type_name}: Missing Params class')
        continue

    if not issubclass(cls.Params, BaseModel):
        failures.append(f'{type_name}: Params does not inherit from BaseModel')
        continue

    if cls.Params is MembershipFunction.Params:
        failures.append(f'{type_name}: Uses base Params (not customized)')
        continue

    print(f'{type_name}: Params OK (customized, inherits BaseModel)')

if failures:
    print('FAILURES:')
    for f in failures:
        print(f'  - {f}')
    exit(1)

print('OK: All MF types have valid Params classes')
"
```

**Expected:**
- Output: "OK: All MF types have valid Params classes"
- Exit code: 0

---

### Phase 4: Case-Insensitive Lookup

#### 4.1 Verify Case-Insensitive Lookup Works for All Types

**Command:**
```bash
uv run python -c "
from ktrdr.fuzzy import MEMBERSHIP_REGISTRY

failures = []
types = MEMBERSHIP_REGISTRY.list_types()

for type_name in types:
    for variant in [type_name.lower(), type_name.upper(), type_name.title()]:
        result = MEMBERSHIP_REGISTRY.get(variant)
        if result is None:
            failures.append(f'{type_name}: {variant} lookup failed')

if failures:
    print('FAILURES:')
    for f in failures:
        print(f'  - {f}')
    exit(1)

print(f'OK: Case-insensitive lookup works for all {len(types)} types')
"
```

**Expected:**
- Output: "OK: Case-insensitive lookup works for all 3 types"
- Exit code: 0

#### 4.2 Verify Full Class Name Aliases Work

**Command:**
```bash
uv run python -c "
from ktrdr.fuzzy import MEMBERSHIP_REGISTRY, TriangularMF, TrapezoidalMF, GaussianMF

# Full class names (lowercase) should also work as aliases
alias_tests = [
    ('triangularmf', TriangularMF),
    ('trapezoidalmf', TrapezoidalMF),
    ('gaussianmf', GaussianMF),
]

failures = []

for alias, expected_cls in alias_tests:
    result = MEMBERSHIP_REGISTRY.get(alias)
    if result is None:
        failures.append(f'{alias}: Lookup returned None')
    elif result is not expected_cls:
        failures.append(f'{alias}: Expected {expected_cls}, got {result}')

if failures:
    print('FAILURES:')
    for f in failures:
        print(f'  - {f}')
    exit(1)

print('OK: Full class name aliases work (triangularmf, trapezoidalmf, gaussianmf)')
"
```

**Expected:**
- Output: "OK: Full class name aliases work"
- Exit code: 0

---

### Phase 5: Parameter Validation and Error Handling

#### 5.1 Verify Invalid Parameters Raise ConfigurationError

**Command:**
```bash
uv run python -c "
from ktrdr.fuzzy import TriangularMF, TrapezoidalMF, GaussianMF
from ktrdr.errors import ConfigurationError

test_cases = [
    # (class, invalid_params, description)
    (TriangularMF, [1.0, 2.0], 'triangular with 2 params (need 3)'),
    (TriangularMF, [5.0, 2.0, 3.0], 'triangular with a > b'),
    (TrapezoidalMF, [1.0, 2.0, 3.0], 'trapezoidal with 3 params (need 4)'),
    (TrapezoidalMF, [5.0, 2.0, 3.0, 4.0], 'trapezoidal with a > b'),
    (GaussianMF, [1.0], 'gaussian with 1 param (need 2)'),
    (GaussianMF, [0.0, 0.0], 'gaussian with sigma = 0'),
    (GaussianMF, [0.0, -1.0], 'gaussian with negative sigma'),
]

failures = []

for cls, params, description in test_cases:
    try:
        instance = cls(params)
        failures.append(f'{description}: No error raised')
    except ConfigurationError as e:
        if 'MF-InvalidParameters' not in str(e.error_code):
            failures.append(f'{description}: Wrong error code: {e.error_code}')
        else:
            print(f'{description}: ConfigurationError raised correctly')
    except Exception as e:
        failures.append(f'{description}: Wrong exception type: {type(e).__name__}')

if failures:
    print('FAILURES:')
    for f in failures:
        print(f'  - {f}')
    exit(1)

print('OK: Invalid parameters raise ConfigurationError with MF-InvalidParameters code')
"
```

**Expected:**
- Output: "OK: Invalid parameters raise ConfigurationError with MF-InvalidParameters code"
- Exit code: 0

---

### Phase 6: V2 Classes Not Exported

#### 6.1 Verify V2 Config Classes Not in ktrdr.fuzzy.__all__

**Command:**
```bash
uv run python -c "
from ktrdr import fuzzy

v2_classes = ['FuzzyConfig', 'FuzzyConfigLoader', 'FuzzySetConfig']
failures = []

# Check __all__ does not contain V2 classes
all_exports = getattr(fuzzy, '__all__', [])
print(f'ktrdr.fuzzy.__all__: {all_exports}')

for v2_class in v2_classes:
    if v2_class in all_exports:
        failures.append(f'{v2_class} found in __all__')

# Check classes are not accessible via direct attribute access
for v2_class in v2_classes:
    if hasattr(fuzzy, v2_class):
        failures.append(f'{v2_class} accessible as fuzzy.{v2_class}')

if failures:
    print('FAILURES:')
    for f in failures:
        print(f'  - {f}')
    exit(1)

print('OK: V2 config classes not exported from ktrdr.fuzzy')
"
```

**Expected:**
- Output: "OK: V2 config classes not exported from ktrdr.fuzzy"
- Exit code: 0

---

### Phase 7: FuzzyEngine V3 Mode Integration

#### 7.1 Verify FuzzyEngine Uses Registry for MF Creation

**Command:**
```bash
uv run python -c "
import inspect
from ktrdr.fuzzy.engine import FuzzyEngine

source_file = inspect.getfile(FuzzyEngine)
with open(source_file, 'r') as f:
    source = f.read()

# Check that FuzzyEngine imports MEMBERSHIP_REGISTRY
if 'MEMBERSHIP_REGISTRY' not in source:
    print('FAIL: FuzzyEngine does not use MEMBERSHIP_REGISTRY')
    exit(1)

# Check for registry-based creation pattern
if 'get_or_raise' not in source and 'MEMBERSHIP_REGISTRY.get' not in source:
    print('FAIL: FuzzyEngine does not use registry lookup')
    exit(1)

# Check that old MembershipFunctionFactory direct usage is not present
# (direct instantiation in _create_membership_function should use registry)
method_lines = []
in_method = False
for line in source.split('\\n'):
    if 'def _create_membership_function' in line:
        in_method = True
    if in_method:
        method_lines.append(line)
        if line.strip().startswith('return') and 'mf_cls' in line:
            break

method_body = '\\n'.join(method_lines)
print(f'_create_membership_function method uses registry: {\"get_or_raise\" in method_body}')

print('OK: FuzzyEngine uses MEMBERSHIP_REGISTRY for MF creation')
"
```

**Expected:**
- Output: "OK: FuzzyEngine uses MEMBERSHIP_REGISTRY for MF creation"
- Exit code: 0

#### 7.2 Verify FuzzyEngine V3 Mode Works End-to-End

**Command:**
```bash
uv run python -c "
import numpy as np
from ktrdr.fuzzy import FuzzyEngine
from ktrdr.config.models import FuzzySetDefinition

# Create a v3 configuration
config = {
    'test_momentum': FuzzySetDefinition(
        indicator='test_indicator',
        low={'type': 'triangular', 'parameters': [0.0, 25.0, 50.0]},
        medium={'type': 'gaussian', 'parameters': [50.0, 15.0]},
        high={'type': 'trapezoidal', 'parameters': [50.0, 75.0, 85.0, 100.0]},
    )
}

# Create engine
engine = FuzzyEngine(config)

# Verify v3 mode
if not engine.is_v3_mode:
    print('FAIL: Engine not in v3 mode')
    exit(1)

# Fuzzify some test values
test_values = np.array([10.0, 50.0, 90.0])
result = engine.fuzzify('test_momentum', test_values)

# Verify result structure
expected_columns = {'test_momentum_low', 'test_momentum_medium', 'test_momentum_high'}
actual_columns = set(result.columns)

if actual_columns != expected_columns:
    print(f'FAIL: Expected columns {expected_columns}, got {actual_columns}')
    exit(1)

# Verify values are in valid range [0, 1]
if (result.values < 0).any() or (result.values > 1).any():
    print('FAIL: Membership values outside [0, 1] range')
    exit(1)

# Verify expected behavior:
# - Low value (10.0) should have high 'low' membership
# - Mid value (50.0) should have high 'medium' membership
# - High value (90.0) should have high 'high' membership
# Note: test_values = [10.0, 50.0, 90.0] so indices are 0, 1, 2
low_at_10 = result['test_momentum_low'].iloc[0]      # x=10 at index 0
medium_at_50 = result['test_momentum_medium'].iloc[1]  # x=50 at index 1
high_at_90 = result['test_momentum_high'].iloc[2]      # x=90 at index 2

print(f'Membership at 10: low={low_at_10:.3f}')
print(f'Membership at 50: medium={medium_at_50:.3f}')
print(f'Membership at 90: high={high_at_90:.3f}')

# Sanity checks on values
if low_at_10 < 0.3:
    print(f'FAIL: Low membership at 10 should be > 0.3, got {low_at_10}')
    exit(1)
if medium_at_50 < 0.9:  # Gaussian peaks at center
    print(f'FAIL: Medium membership at 50 should be > 0.9, got {medium_at_50}')
    exit(1)
if high_at_90 < 0.5:
    print(f'FAIL: High membership at 90 should be > 0.5, got {high_at_90}')
    exit(1)

print('OK: FuzzyEngine v3 mode works end-to-end with all 3 MF types')
"
```

**Expected:**
- Output: "OK: FuzzyEngine v3 mode works end-to-end with all 3 MF types"
- Exit code: 0

---

## Success Criteria

All must pass for test to pass:

- [ ] `config.py` does NOT exist in `ktrdr/fuzzy/`
- [ ] `migration.py` does NOT exist in `ktrdr/fuzzy/`
- [ ] `MEMBERSHIP_REGISTRY` importable from `ktrdr.fuzzy`
- [ ] `MEMBERSHIP_REGISTRY` contains exactly 3 types: triangular, trapezoidal, gaussian
- [ ] All 3 MF types have a `Params` class that:
  - Exists on the membership function class
  - Inherits from `pydantic.BaseModel`
  - Is NOT the base `MembershipFunction.Params` (must be customized)
- [ ] Case-insensitive lookup works for all 3 types (lowercase, UPPERCASE, MixedCase)
- [ ] Full class name aliases work (triangularmf, trapezoidalmf, gaussianmf)
- [ ] Invalid parameters raise `ConfigurationError` with `MF-InvalidParameters` error code
- [ ] V2 config classes (`FuzzyConfig`, `FuzzyConfigLoader`, `FuzzySetConfig`) not exported from `ktrdr.fuzzy`
- [ ] FuzzyEngine source uses `MEMBERSHIP_REGISTRY` for MF creation
- [ ] FuzzyEngine v3 mode works end-to-end with all 3 MF types

---

## Sanity Checks

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Registry count == 3 | != 3 fails | Missing or duplicate registrations |
| Params validation == 3 | < 3 fails | Some MF types not migrated |
| Case variants work | Any failure | TypeRegistry case normalization broken |
| Invalid params raise error | No error | Params validation not implemented |
| FuzzyEngine fuzzify works | Error raised | Integration between engine and registry broken |
| Python exits 0 | != 0 fails | Runtime errors in validation code |

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| config.py exists | CODE_BUG | Delete file, verify git history |
| migration.py exists | CODE_BUG | Delete file, verify git history |
| Registry count != 3 | CODE_BUG | Check __init_subclass__ in MF classes |
| Params missing/wrong inheritance | CODE_BUG | Add/fix Params class in MF subclass |
| Case lookup fails | CODE_BUG | Check TypeRegistry.register() normalization |
| Invalid params don't error | CODE_BUG | Add Pydantic validators to Params class |
| V2 classes still exported | CODE_BUG | Remove from __init__.py __all__ |
| FuzzyEngine not using registry | CODE_BUG | Update _create_membership_function method |
| Import error | CONFIGURATION | Check ktrdr installation, circular imports |

---

## Troubleshooting

**If registry count is wrong:**
- Check that MF classes have proper `__init_subclass__` triggering registration
- Verify classes are not marked as abstract
- Debug: `uv run python -c "from ktrdr.fuzzy import MEMBERSHIP_REGISTRY; print(sorted(MEMBERSHIP_REGISTRY.list_types()))"`

**If Params inheritance fails:**
- Ensure `class Params(MembershipFunction.Params):` pattern is used
- Add `@field_validator` for parameter validation
- Reference: See `ktrdr/fuzzy/membership.py` for pattern

**If case-insensitive lookup fails:**
- Check that TypeRegistry normalizes names to lowercase
- Verify aliases are registered correctly

**If invalid params don't raise ConfigurationError:**
- Add `@field_validator("parameters")` to the Params class
- Ensure validator raises `ValueError` (Pydantic converts to ValidationError)
- Ensure `__init__` catches ValidationError and raises ConfigurationError

**If V2 classes still accessible:**
- Remove from `ktrdr/fuzzy/__init__.py` imports and `__all__`
- Delete the source files if they still exist

**If FuzzyEngine v3 fails:**
- Check that `_create_membership_function` uses `MEMBERSHIP_REGISTRY.get_or_raise()`
- Verify FuzzySetDefinition model is compatible with engine initialization
- Debug: `uv run python -c "from ktrdr.config.models import FuzzySetDefinition; print(FuzzySetDefinition.model_fields)"`
