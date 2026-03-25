# Test: cli/performance

**Purpose:** Validate CLI startup performance: `ktrdr --help` in < 100ms
**Duration:** ~10 seconds (multiple runs for averaging)
**Category:** CLI / Restructure

---

## Pre-Flight Checks

**Required modules:**
- None (this tests cold startup, no backend needed)

**Test-specific checks:**
- [ ] uv available
- [ ] ktrdr package installed

---

## Execution Steps

### 1. Measure Help Startup Time (5 runs)

**Command:**
```bash
for i in {1..5}; do
  START=$(python3 -c "import time; print(time.time())")
  uv run ktrdr --help > /dev/null 2>&1
  END=$(python3 -c "import time; print(time.time())")
  DURATION=$(echo "$END - $START" | bc)
  echo "Run $i: ${DURATION}s"
done
```

**Expected:**
- All runs complete
- Duration captured for each

### 2. Calculate Average

**Command:**
```bash
TOTAL=0
for i in {1..5}; do
  START=$(python3 -c "import time; print(time.time())")
  uv run ktrdr --help > /dev/null 2>&1
  END=$(python3 -c "import time; print(time.time())")
  DURATION=$(echo "$END - $START" | bc)
  TOTAL=$(echo "$TOTAL + $DURATION" | bc)
done
AVG=$(echo "scale=3; $TOTAL / 5" | bc)
echo "Average startup time: ${AVG}s"
```

**Expected:**
- Average < 0.5s (500ms) - acceptable
- Target: < 0.1s (100ms) - ideal

### 3. Check for Heavy Imports at Module Load

**Command:**
```bash
# Time the Python import of CLI module
uv run python -c "
import time
start = time.time()
from ktrdr.cli import commands
end = time.time()
print(f'CLI import time: {(end-start)*1000:.1f}ms')
"
```

**Expected:**
- Import time < 200ms
- No pandas/tensorflow loaded at import time

### 4. Verify No Heavy Deps in --help Path

**Command:**
```bash
# Check what gets imported during --help
uv run python -c "
import sys
initial_modules = set(sys.modules.keys())
from ktrdr.cli.commands import app  # Import main CLI
final_modules = set(sys.modules.keys())
new_modules = final_modules - initial_modules

# Check for heavy modules
heavy = ['pandas', 'numpy', 'tensorflow', 'torch', 'opentelemetry']
found_heavy = [m for m in heavy if any(m in mod for mod in new_modules)]
if found_heavy:
    print(f'WARNING: Heavy modules loaded: {found_heavy}')
else:
    print('OK: No heavy modules loaded at import')
"
```

**Expected:**
- No heavy modules (pandas, numpy, tensorflow, torch) loaded during help

---

## Success Criteria

- [ ] `ktrdr --help` completes successfully
- [ ] Average startup time < 500ms (acceptable threshold)
- [ ] Target: < 100ms (ideal, if lazy imports implemented)
- [ ] CLI module import < 200ms
- [ ] No heavy dependencies loaded for --help

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Consistent timing** — No outliers > 2x average
- [ ] **Help actually works** — Not just exiting immediately
- [ ] **Warm cache** — Run twice, second should be similar (not just cache warming)

---

## Troubleshooting

**If startup > 1s:**
- **Cause:** Eager imports of heavy modules
- **Cure:** Convert to lazy imports (inside functions)

**If heavy modules detected:**
- **Cause:** Module-level imports
- **Cure:** Move imports inside functions that need them

**If inconsistent timing:**
- **Cause:** System load variation
- **Cure:** Run more iterations, take median

---

## Notes

**Lazy Import Pattern:**
```python
# Bad - loaded at module import
import pandas as pd

def my_command():
    df = pd.DataFrame(...)

# Good - loaded only when needed
def my_command():
    import pandas as pd
    df = pd.DataFrame(...)
```

This pattern is critical for fast CLI startup.

---

## Evidence to Capture

- Individual run times (5 measurements)
- Average startup time
- CLI module import time
- List of modules loaded during import
