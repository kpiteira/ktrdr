# E2E Test: codebase/m4-cleanup-complete

**Purpose:** Validate M4 cleanup is complete: no legacy ValueError patterns, no dead code, no deprecated assert statements, invalid indicator params raise DataError

**Duration:** ~30s (static analysis + quick runtime validation, no API calls or external dependencies)

**Category:** Codebase / Architecture / Cleanup

---

## Pre-Flight Checks

**Required modules:**
- None (this test validates Python code structure and behavior, does not require running services)

**Test-specific checks:**
- [ ] Python environment available: `uv run python --version` succeeds
- [ ] ktrdr package importable: `uv run python -c "import ktrdr"` succeeds

**Note:** This test combines static code analysis with runtime validation. It requires only the Python environment, not Docker or API services.

---

## Test Data

```python
# Files that MUST NOT contain certain patterns
INDICATOR_FILES_NO_VALUEERROR = [
    # All indicator files EXCEPT indicator_engine.py and base_indicator.py
    # (those may have legitimate ValueError for internal use)
]

# Indicators to test with invalid parameters
INVALID_PARAM_TEST_CASES = [
    ("ADXIndicator", {"period": -1}, "negative period"),
    ("CMFIndicator", {"period": -1}, "negative period"),
    ("KeltnerChannelsIndicator", {"period": -1}, "negative period"),
]

# Patterns that must NOT exist
FORBIDDEN_PATTERNS = {
    "raise ValueError": "ktrdr/indicators/*.py (excluding indicator_engine.py)",
    "assert isinstance": "ktrdr/fuzzy/engine.py",
    "CRITICAL BUG": "ktrdr/**/*.py",
    "def get_name": "ktrdr/indicators/bollinger_bands_indicator.py",
}
```

**Why this data:**
- M4 migrated indicator validation to Pydantic Params classes, removing manual ValueError raises
- FuzzyEngine cleanup removed assert isinstance checks
- CRITICAL BUG markers should be resolved, not left in production code
- Dead get_name() method should be removed from BollingerBands

---

## Execution Steps

### Phase 1: No ValueError in Indicator Parameter Validation

#### 1.1 Verify No raise ValueError in Indicator Files (Excluding indicator_engine.py)

**Command:**
```bash
uv run python -c "
import os
import glob

# Find all indicator files (excluding engine, base, template)
indicator_dir = 'ktrdr/indicators'
exclude_files = ['indicator_engine.py', 'base_indicator.py', 'indicator_template.py', '__init__.py', 'categories.py']

failures = []

for filepath in glob.glob(f'{indicator_dir}/*.py'):
    filename = os.path.basename(filepath)
    if filename in exclude_files:
        continue

    with open(filepath, 'r') as f:
        content = f.read()

    # Check for raise ValueError
    if 'raise ValueError' in content:
        # Find line numbers for context
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if 'raise ValueError' in line:
                failures.append(f'{filename}:{i}: {line.strip()}')

if failures:
    print('FAIL: Found raise ValueError in indicator files:')
    for f in failures:
        print(f'  - {f}')
    exit(1)

print('OK: No raise ValueError in indicator files (M4 cleanup verified)')
"
```

**Expected:**
- Output: "OK: No raise ValueError in indicator files (M4 cleanup verified)"
- Exit code: 0

---

### Phase 2: No _validate_params Calls in compute() Methods

#### 2.1 Verify No _validate_params Called Inside compute()

**Command:**
```bash
uv run python -c "
import os
import glob
import re

indicator_dir = 'ktrdr/indicators'
exclude_files = ['indicator_engine.py', 'base_indicator.py', 'indicator_template.py', '__init__.py', 'categories.py']

failures = []

for filepath in glob.glob(f'{indicator_dir}/*.py'):
    filename = os.path.basename(filepath)
    if filename in exclude_files:
        continue

    with open(filepath, 'r') as f:
        content = f.read()

    # Find compute method bodies and check for _validate_params
    # This is a simple heuristic - looking for _validate_params after 'def compute'
    lines = content.split('\n')
    in_compute = False
    indent_level = 0

    for i, line in enumerate(lines, 1):
        if 'def compute(' in line:
            in_compute = True
            # Get indent level of def
            indent_level = len(line) - len(line.lstrip())
            continue

        if in_compute:
            # Check if we've exited compute method (another def at same indent)
            if line.strip() and not line.strip().startswith('#'):
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= indent_level and line.strip().startswith('def '):
                    in_compute = False
                    continue

            # Check for _validate_params call inside compute
            if '_validate_params' in line:
                failures.append(f'{filename}:{i}: {line.strip()}')

if failures:
    print('FAIL: Found _validate_params calls inside compute() methods:')
    for f in failures:
        print(f'  - {f}')
    exit(1)

print('OK: No _validate_params calls inside compute() methods (validation happens in __init__)')
"
```

**Expected:**
- Output: "OK: No _validate_params calls inside compute() methods"
- Exit code: 0

---

### Phase 3: No assert isinstance in FuzzyEngine

#### 3.1 Verify No assert isinstance in engine.py

**Command:**
```bash
uv run python -c "
with open('ktrdr/fuzzy/engine.py', 'r') as f:
    content = f.read()

if 'assert isinstance' in content:
    lines = content.split('\n')
    print('FAIL: Found assert isinstance in ktrdr/fuzzy/engine.py:')
    for i, line in enumerate(lines, 1):
        if 'assert isinstance' in line:
            print(f'  Line {i}: {line.strip()}')
    exit(1)

print('OK: No assert isinstance in FuzzyEngine (M4 cleanup verified)')
"
```

**Expected:**
- Output: "OK: No assert isinstance in FuzzyEngine (M4 cleanup verified)"
- Exit code: 0

---

### Phase 4: No CRITICAL BUG Markers in Codebase

#### 4.1 Verify No [CRITICAL BUG] Comments in ktrdr/

**Command:**
```bash
uv run python -c "
import os
import glob

failures = []

# Search recursively in ktrdr/
for filepath in glob.glob('ktrdr/**/*.py', recursive=True):
    with open(filepath, 'r') as f:
        content = f.read()

    if 'CRITICAL BUG' in content:
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if 'CRITICAL BUG' in line:
                rel_path = filepath
                failures.append(f'{rel_path}:{i}: {line.strip()[:80]}...')

if failures:
    print('FAIL: Found CRITICAL BUG markers in codebase:')
    for f in failures:
        print(f'  - {f}')
    exit(1)

print('OK: No CRITICAL BUG markers in codebase (all resolved)')
"
```

**Expected:**
- Output: "OK: No CRITICAL BUG markers in codebase (all resolved)"
- Exit code: 0

---

### Phase 5: No Dead get_name() Method in BollingerBands

#### 5.1 Verify No def get_name in bollinger_bands_indicator.py

**Command:**
```bash
uv run python -c "
with open('ktrdr/indicators/bollinger_bands_indicator.py', 'r') as f:
    content = f.read()

if 'def get_name' in content:
    lines = content.split('\n')
    print('FAIL: Found dead get_name() method in bollinger_bands_indicator.py:')
    for i, line in enumerate(lines, 1):
        if 'def get_name' in line:
            print(f'  Line {i}: {line.strip()}')
    exit(1)

print('OK: No dead get_name() method in BollingerBands (M4 cleanup verified)')
"
```

**Expected:**
- Output: "OK: No dead get_name() method in BollingerBands (M4 cleanup verified)"
- Exit code: 0

---

### Phase 6: Invalid Parameters Raise DataError (Not ValueError)

#### 6.1 Verify ADXIndicator with period=-1 Raises DataError

**Command:**
```bash
uv run python -c "
from ktrdr.indicators import INDICATOR_REGISTRY, ensure_all_registered
from ktrdr.errors import DataError

ensure_all_registered()

# Get ADXIndicator
ADXIndicator = INDICATOR_REGISTRY.get('adx')
if ADXIndicator is None:
    print('FAIL: ADXIndicator not found in registry')
    exit(1)

try:
    indicator = ADXIndicator(period=-1)
    print('FAIL: ADXIndicator with period=-1 did not raise an error')
    exit(1)
except DataError as e:
    if 'INDICATOR-InvalidParameters' in str(e.error_code):
        print(f'OK: ADXIndicator(period=-1) raises DataError with INDICATOR-InvalidParameters')
    else:
        print(f'FAIL: Wrong error code: {e.error_code}')
        exit(1)
except ValueError as e:
    print(f'FAIL: ADXIndicator(period=-1) raises ValueError instead of DataError: {e}')
    exit(1)
except Exception as e:
    print(f'FAIL: ADXIndicator(period=-1) raises unexpected {type(e).__name__}: {e}')
    exit(1)
"
```

**Expected:**
- Output: "OK: ADXIndicator(period=-1) raises DataError with INDICATOR-InvalidParameters"
- Exit code: 0

#### 6.2 Verify CMFIndicator with period=-1 Raises DataError

**Command:**
```bash
uv run python -c "
from ktrdr.indicators import INDICATOR_REGISTRY, ensure_all_registered
from ktrdr.errors import DataError

ensure_all_registered()

# Get CMFIndicator
CMFIndicator = INDICATOR_REGISTRY.get('cmf')
if CMFIndicator is None:
    print('FAIL: CMFIndicator not found in registry')
    exit(1)

try:
    indicator = CMFIndicator(period=-1)
    print('FAIL: CMFIndicator with period=-1 did not raise an error')
    exit(1)
except DataError as e:
    if 'INDICATOR-InvalidParameters' in str(e.error_code):
        print(f'OK: CMFIndicator(period=-1) raises DataError with INDICATOR-InvalidParameters')
    else:
        print(f'FAIL: Wrong error code: {e.error_code}')
        exit(1)
except ValueError as e:
    print(f'FAIL: CMFIndicator(period=-1) raises ValueError instead of DataError: {e}')
    exit(1)
except Exception as e:
    print(f'FAIL: CMFIndicator(period=-1) raises unexpected {type(e).__name__}: {e}')
    exit(1)
"
```

**Expected:**
- Output: "OK: CMFIndicator(period=-1) raises DataError with INDICATOR-InvalidParameters"
- Exit code: 0

#### 6.3 Verify KeltnerChannelsIndicator with period=-1 Raises DataError

**Command:**
```bash
uv run python -c "
from ktrdr.indicators import INDICATOR_REGISTRY, ensure_all_registered
from ktrdr.errors import DataError

ensure_all_registered()

# Get KeltnerChannelsIndicator
KeltnerChannelsIndicator = INDICATOR_REGISTRY.get('keltnerchannels')
if KeltnerChannelsIndicator is None:
    print('FAIL: KeltnerChannelsIndicator not found in registry')
    exit(1)

try:
    indicator = KeltnerChannelsIndicator(period=-1)
    print('FAIL: KeltnerChannelsIndicator with period=-1 did not raise an error')
    exit(1)
except DataError as e:
    if 'INDICATOR-InvalidParameters' in str(e.error_code):
        print(f'OK: KeltnerChannelsIndicator(period=-1) raises DataError with INDICATOR-InvalidParameters')
    else:
        print(f'FAIL: Wrong error code: {e.error_code}')
        exit(1)
except ValueError as e:
    print(f'FAIL: KeltnerChannelsIndicator(period=-1) raises ValueError instead of DataError: {e}')
    exit(1)
except Exception as e:
    print(f'FAIL: KeltnerChannelsIndicator(period=-1) raises unexpected {type(e).__name__}: {e}')
    exit(1)
"
```

**Expected:**
- Output: "OK: KeltnerChannelsIndicator(period=-1) raises DataError with INDICATOR-InvalidParameters"
- Exit code: 0

---

### Phase 7: Comprehensive Validation Across All Indicators

#### 7.1 Verify All Indicators with Negative Period Raise DataError

**Command:**
```bash
uv run python -c "
from ktrdr.indicators import INDICATOR_REGISTRY, ensure_all_registered
from ktrdr.errors import DataError

ensure_all_registered()

# Indicators that have a 'period' parameter
indicators_with_period = []
failures = []
successes = []

for type_name in INDICATOR_REGISTRY.list_types():
    cls = INDICATOR_REGISTRY.get(type_name)

    # Check if Params has a 'period' field
    if hasattr(cls, 'Params') and hasattr(cls.Params, 'model_fields'):
        if 'period' in cls.Params.model_fields:
            indicators_with_period.append(type_name)

            try:
                # Try to instantiate with negative period
                indicator = cls(period=-1)
                failures.append(f'{type_name}: No error raised for period=-1')
            except DataError as e:
                if 'INDICATOR-InvalidParameters' in str(e.error_code):
                    successes.append(type_name)
                else:
                    failures.append(f'{type_name}: Wrong error code: {e.error_code}')
            except ValueError as e:
                failures.append(f'{type_name}: Raises ValueError instead of DataError')
            except Exception as e:
                # Pydantic validation errors are OK if they get wrapped
                if 'ValidationError' in type(e).__name__:
                    failures.append(f'{type_name}: Raw ValidationError not wrapped in DataError')
                else:
                    failures.append(f'{type_name}: Unexpected error: {type(e).__name__}')

print(f'Tested {len(indicators_with_period)} indicators with period parameter')
print(f'Successes: {len(successes)}')

if failures:
    print('FAILURES:')
    for f in failures:
        print(f'  - {f}')
    exit(1)

print(f'OK: All {len(successes)} indicators with period parameter raise DataError for invalid values')
"
```

**Expected:**
- Output includes: "OK: All N indicators with period parameter raise DataError for invalid values"
- Exit code: 0

---

## Success Criteria

All must pass for test to pass:

- [ ] No `raise ValueError` in indicator files (excluding indicator_engine.py, base_indicator.py, indicator_template.py)
- [ ] No `_validate_params` calls inside `compute()` methods in indicators
- [ ] No `assert isinstance` in `ktrdr/fuzzy/engine.py`
- [ ] No `CRITICAL BUG` markers anywhere in `ktrdr/**/*.py`
- [ ] No `def get_name` method in `bollinger_bands_indicator.py`
- [ ] ADXIndicator(period=-1) raises DataError with INDICATOR-InvalidParameters
- [ ] CMFIndicator(period=-1) raises DataError with INDICATOR-InvalidParameters
- [ ] KeltnerChannelsIndicator(period=-1) raises DataError with INDICATOR-InvalidParameters
- [ ] All indicators with period parameter raise DataError for negative values

---

## Sanity Checks

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Indicators tested >= 15 | < 15 fails | Not enough indicators have period param or registry issue |
| All raise DataError | Any ValueError fails | Indicator not migrated to Pydantic Params pattern |
| Error code is INDICATOR-InvalidParameters | Wrong code fails | BaseIndicator wrapper not applied correctly |
| No raw ValidationError | ValidationError leaks fails | Pydantic error not wrapped in DataError |
| Python exits 0 | != 0 fails | Runtime errors in validation code |

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| raise ValueError found | CODE_BUG | Replace with DataError or remove (use Pydantic validation) |
| _validate_params in compute | CODE_BUG | Remove call; validation happens in __init__ via Params |
| assert isinstance in FuzzyEngine | CODE_BUG | Remove assert; use proper type checking if needed |
| CRITICAL BUG marker found | CODE_BUG | Investigate and fix the bug, remove marker |
| Dead get_name() method | CODE_BUG | Delete the method |
| ValueError instead of DataError | CODE_BUG | Ensure indicator uses Params class; check BaseIndicator wrapping |
| Wrong error code | CODE_BUG | Check BaseIndicator.__init__ error wrapping |
| ValidationError not wrapped | CODE_BUG | Fix BaseIndicator.__init__ to wrap Pydantic errors |
| Import error | CONFIGURATION | Check ktrdr installation, circular imports |

---

## Troubleshooting

**If raise ValueError found in indicator:**
- M4 pattern: All parameter validation should be in Params class using Pydantic Field constraints
- Replace: `if period < 2: raise ValueError(...)` with `period: int = Field(ge=2, ...)`
- BaseIndicator.__init__ wraps Pydantic ValidationError in DataError automatically

**If _validate_params found in compute():**
- compute() should not validate parameters; that happens in __init__
- Remove the call; params are already validated when indicator was instantiated

**If indicator raises ValueError instead of DataError:**
- Check that indicator defines `class Params(BaseIndicator.Params)` with Field constraints
- Check that indicator is instantiated without explicit name (new-style)
- Debug: `uv run python -c "from ktrdr.indicators.adx_indicator import ADXIndicator; print(ADXIndicator.Params.model_fields)"`

**If wrong error code returned:**
- BaseIndicator.__init__ should use error_code="INDICATOR-InvalidParameters"
- Check ktrdr/indicators/base_indicator.py lines 121-127

**If CRITICAL BUG marker found:**
- This indicates an unresolved known issue
- Read the context around the marker to understand the bug
- Fix the bug, then remove the marker

**If assert isinstance found:**
- Replace with explicit type checking if validation is needed
- Or remove if the assertion is redundant (Pydantic handles types)

---

## Notes for Implementation

- This test is purely static analysis + quick runtime checks
- No Docker or API services required
- Fast execution (~30s) suitable for frequent CI runs
- Template file (indicator_template.py) is excluded from static checks as it demonstrates the old pattern for documentation
- base_indicator.py and indicator_engine.py may legitimately use ValueError for internal errors
- The runtime tests specifically validate the DataError wrapping behavior for user-facing errors
