---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 4: Cleanup

**Branch:** `feature/type-registry-m4`
**Builds on:** M2, M3
**Goal:** Consistent exceptions, no dead code

## E2E Validation

**Success Criteria:**
- [ ] No ValueError in indicator param validation
- [ ] No _validate_params calls in compute() methods
- [ ] No assert isinstance in FuzzyEngine
- [ ] No [CRITICAL BUG] in codebase
- [ ] No dead get_name() method
- [ ] Invalid params raise DataError

---

## Task 4.1: Remove redundant validation from indicators

**Files:** adx, ad_line, cmf, donchian_channels, fisher_transform, keltner_channels, supertrend, zigzag
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Old _validate_params methods with ValueError are now redundant — Params handles validation. Remove or simplify.

**Acceptance Criteria:**
- [ ] No raise ValueError for param validation
- [ ] Tests pass

---

## Task 4.1b: Remove double validation in compute() methods

**Files:** bollinger_bands and others (audit needed)
**Type:** CODING
**Estimated time:** 1 hour

**Pattern to find:**
```python
def compute(self, data):
    validated_params = self._validate_params(self.params)  # REMOVE THIS
```

**Verification:**
```bash
grep -rn "_validate_params" ktrdr/indicators/*.py | grep -v "def _validate_params"
```

**Acceptance Criteria:**
- [ ] No _validate_params calls in compute()
- [ ] Tests pass

---

## Task 4.2: Replace assert statements in FuzzyEngine

**File:** `ktrdr/fuzzy/engine.py`
**Type:** CODING
**Estimated time:** 30 min

**Change from:**
```python
assert isinstance(config, dict)
```

**To:**
```python
if not isinstance(config, dict):
    raise ConfigurationError(
        f"FuzzyEngine config must be dict, got {type(config).__name__}",
        error_code="FUZZY-InvalidConfigType"
    )
```

**Acceptance Criteria:**
- [ ] No assert isinstance in engine.py
- [ ] Type errors raise ConfigurationError
- [ ] Works same with python -O

---

## Task 4.3: Fix [CRITICAL BUG] workaround

**File:** `ktrdr/indicators/williams_r_indicator.py`
**Type:** MIXED (research + coding)
**Estimated time:** 1-2 hours

**Current state:** Lines 114-142 log "[CRITICAL BUG]" and silently fix DataFrame → Series conversion.

**Actions:**
1. Trace callers to find why data['high'] returns DataFrame
2. Fix root cause or add explicit handling without scary log
3. Remove workaround

**Acceptance Criteria:**
- [ ] Root cause identified
- [ ] Proper fix (not workaround)
- [ ] No "[CRITICAL BUG]" in codebase

---

## Task 4.4: Remove dead code

**Files:** Various
**Type:** CODING
**Estimated time:** 30 min

**Items:**
- `BollingerBandsIndicator.get_name()` — unused method
- Unused imports in modified files

**Acceptance Criteria:**
- [ ] No dead get_name() method
- [ ] No unused imports

---

## Task 4.5: Execute M4 E2E Test

**Type:** VALIDATION

**E2E Test:**
```bash
# Static checks
result=$(grep -rn "raise ValueError" ktrdr/indicators/*.py | grep -v __pycache__ | grep -v indicator_engine | wc -l)
[ "$result" -eq 0 ] && echo "OK: No ValueError" || echo "FAIL: $result ValueError found"

result=$(grep -rn "_validate_params" ktrdr/indicators/*.py | grep -v "def _validate_params" | wc -l)
[ "$result" -eq 0 ] && echo "OK: No double validation" || echo "FAIL: $result double validation"

grep -n "assert isinstance" ktrdr/fuzzy/engine.py && echo "FAIL: assert found" || echo "OK: No assert"

grep -r "CRITICAL BUG" ktrdr/ --include="*.py" && echo "FAIL: CRITICAL BUG found" || echo "OK: No CRITICAL BUG"

grep -n "def get_name" ktrdr/indicators/bollinger_bands_indicator.py && echo "FAIL: dead method" || echo "OK: No dead get_name"

# Runtime check
uv run python -c "
from ktrdr.indicators import INDICATOR_REGISTRY
from ktrdr.errors import DataError

for name in ['adx', 'cmf', 'keltner']:
    cls = INDICATOR_REGISTRY.get(name)
    try:
        cls(period=-1)
    except DataError:
        print(f'OK: {name} raises DataError')
    except ValueError:
        print(f'FAIL: {name} raises ValueError')
"

echo "M4 E2E complete"
```

**Acceptance Criteria:**
- [ ] All static checks pass
- [ ] Runtime checks pass
- [ ] `make test-unit` passes
- [ ] `make quality` passes
