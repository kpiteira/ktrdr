# E2E Test: indicators/registry-migration-complete

**Purpose:** Validate the M2 indicator registry migration is complete: old factory files deleted, all 31 indicators use Params classes, registry is the sole source of truth

**Duration:** ~30s (Python introspection, no API calls or external dependencies)

**Category:** Indicators / Architecture / Migration

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
# Expected indicator count
EXPECTED_COUNT = 31

# Files that must NOT exist
DELETED_FILES = [
    "ktrdr/indicators/indicator_factory.py",
    "ktrdr/indicators/schemas.py",
]
```

**Why this data:**
- 31 types is the corrected count after audit (not 39 from original estimate)
- Names are canonical (class name minus "Indicator" suffix, lowercase)
- Deleted files represent the old factory pattern being replaced

---

## Execution Steps

### Phase 1: File Deletion Verification

#### 1.1 Verify indicator_factory.py Deleted

**Command:**
```bash
if [ -f "ktrdr/indicators/indicator_factory.py" ]; then
  echo "FAIL: indicator_factory.py still exists"
  exit 1
else
  echo "OK: indicator_factory.py deleted"
fi
```

**Expected:**
- Output: "OK: indicator_factory.py deleted"
- Exit code: 0

#### 1.2 Verify schemas.py Deleted

**Command:**
```bash
if [ -f "ktrdr/indicators/schemas.py" ]; then
  echo "FAIL: schemas.py still exists"
  exit 1
else
  echo "OK: schemas.py deleted"
fi
```

**Expected:**
- Output: "OK: schemas.py deleted"
- Exit code: 0

---

### Phase 2: Registry Count and Types

#### 2.1 Verify Registry Contains Exactly 31 Types

**Command:**
```bash
uv run python -c "
from ktrdr.indicators import INDICATOR_REGISTRY, ensure_all_registered

count = ensure_all_registered()
print(f'Registered types: {count}')

if count != 31:
    print(f'FAIL: Expected 31 types, got {count}')
    print(f'Types: {sorted(INDICATOR_REGISTRY.list_types())}')
    exit(1)
print('OK: Exactly 31 types registered')
"
```

**Expected:**
- Output includes: "Registered types: 31"
- Output includes: "OK: Exactly 31 types registered"
- Exit code: 0

---

### Phase 3: Params Class Validation

#### 3.1 Verify All Types Have Params Inheriting from BaseModel

**Command:**
```bash
uv run python -c "
from pydantic import BaseModel
from ktrdr.indicators import INDICATOR_REGISTRY, ensure_all_registered
from ktrdr.indicators.base_indicator import BaseIndicator

ensure_all_registered()

failures = []

for type_name in INDICATOR_REGISTRY.list_types():
    cls = INDICATOR_REGISTRY.get(type_name)

    if not hasattr(cls, 'Params'):
        failures.append(f'{type_name}: Missing Params class')
        continue

    if not issubclass(cls.Params, BaseModel):
        failures.append(f'{type_name}: Params does not inherit from BaseModel')
        continue

    if cls.Params is BaseIndicator.Params:
        failures.append(f'{type_name}: Uses base Params (not customized)')
        continue

if failures:
    print('FAILURES:')
    for f in failures:
        print(f'  - {f}')
    exit(1)

print('OK: All indicator types have valid Params classes')
"
```

**Expected:**
- Output: "OK: All indicator types have valid Params classes"
- Exit code: 0

---

### Phase 4: Case-Insensitive Lookup

#### 4.1 Verify Case-Insensitive Lookup Works for All Types

**Command:**
```bash
uv run python -c "
from ktrdr.indicators import INDICATOR_REGISTRY, ensure_all_registered

ensure_all_registered()

failures = []
types = INDICATOR_REGISTRY.list_types()

for type_name in types:
    for variant in [type_name.lower(), type_name.upper(), type_name.title()]:
        if INDICATOR_REGISTRY.get(variant) is None:
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
- Output: "OK: Case-insensitive lookup works for all 31 types"
- Exit code: 0

---

### Phase 5: IndicatorEngine Clean of BUILT_IN_INDICATORS

#### 5.1 Verify No BUILT_IN_INDICATORS References in IndicatorEngine

**Command:**
```bash
uv run python -c "
import inspect
from ktrdr.indicators.indicator_engine import IndicatorEngine

source_file = inspect.getfile(IndicatorEngine)
with open(source_file, 'r') as f:
    source = f.read()

if 'BUILT_IN_INDICATORS' in source:
    lines = source.split('\n')
    print('FAIL: BUILT_IN_INDICATORS found in indicator_engine.py:')
    for i, line in enumerate(lines, 1):
        if 'BUILT_IN_INDICATORS' in line:
            print(f'  Line {i}: {line.strip()}')
    exit(1)

print('OK: No BUILT_IN_INDICATORS references in IndicatorEngine')
"
```

**Expected:**
- Output: "OK: No BUILT_IN_INDICATORS references in IndicatorEngine"
- Exit code: 0

---

### Phase 6: Default Instantiation

#### 6.1 Verify All Indicators Instantiate with Default Params

**Command:**
```bash
uv run python -c "
from ktrdr.indicators import INDICATOR_REGISTRY, ensure_all_registered

ensure_all_registered()

failures = []

for type_name in INDICATOR_REGISTRY.list_types():
    cls = INDICATOR_REGISTRY.get(type_name)
    try:
        instance = cls()
    except Exception as e:
        failures.append(f'{type_name}: {type(e).__name__}: {e}')

if failures:
    print('FAILURES:')
    for f in failures:
        print(f'  - {f}')
    exit(1)

print(f'OK: All {len(INDICATOR_REGISTRY.list_types())} indicators instantiate with defaults')
"
```

**Expected:**
- Output: "OK: All 31 indicators instantiate with defaults"
- Exit code: 0

---

## Success Criteria

All must pass for test to pass:

- [ ] `indicator_factory.py` does NOT exist in `ktrdr/indicators/`
- [ ] `schemas.py` does NOT exist in `ktrdr/indicators/`
- [ ] `INDICATOR_REGISTRY` contains exactly 31 canonical types
- [ ] All 31 types have a `Params` class that:
  - Exists on the indicator class
  - Inherits from `pydantic.BaseModel`
  - Is NOT the base `BaseIndicator.Params` (must be customized)
- [ ] Case-insensitive lookup works for all 31 types (lowercase, UPPERCASE, MixedCase)
- [ ] `indicator_engine.py` source contains zero references to `BUILT_IN_INDICATORS`
- [ ] All 31 indicators instantiate successfully with no parameters (using defaults)

---

## Sanity Checks

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Registry count == 31 | != 31 fails | Missing or duplicate registrations |
| Params validation >= 31 | < 31 fails | Some indicators not migrated |
| Instantiation >= 31 | < 31 fails | Broken defaults or missing required params |
| Python exits 0 | != 0 fails | Runtime errors in validation code |

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| indicator_factory.py exists | CODE_BUG | Delete file, verify git history |
| schemas.py exists | CODE_BUG | Delete file, verify git history |
| Registry count != 31 | CODE_BUG | Compare expected vs actual list, find missing |
| Params missing/wrong inheritance | CODE_BUG | Update indicator class to add Params |
| Case lookup fails | CODE_BUG | Check TypeRegistry.register() aliases |
| BUILT_IN_INDICATORS in engine | CODE_BUG | Remove import and references |
| Instantiation fails | CODE_BUG | Fix Params defaults or required fields |
| Import error | CONFIGURATION | Check ktrdr installation, circular imports |

---

## Troubleshooting

**If registry count is wrong:**
- Check `ktrdr/indicators/__init__.py` for completeness of `_INDICATOR_MODULES` list
- Debug: `uv run python -c "from ktrdr.indicators import INDICATOR_REGISTRY, ensure_all_registered; ensure_all_registered(); print(sorted(INDICATOR_REGISTRY.list_types()))"`

**If Params inheritance fails:**
- Add `class Params(BaseIndicator.Params):` with appropriate fields
- Reference: See `ktrdr/indicators/rsi_indicator.py` for pattern

**If BUILT_IN_INDICATORS found:**
- Replace with `INDICATOR_REGISTRY.get()` or `INDICATOR_REGISTRY.get_or_raise()`

**If instantiation fails:**
- Ensure all Params fields have sensible defaults
- Debug: `uv run python -c "from ktrdr.indicators import INDICATOR_REGISTRY, ensure_all_registered; ensure_all_registered(); cls = INDICATOR_REGISTRY.get('rsi'); print(cls.Params.model_fields)"`
