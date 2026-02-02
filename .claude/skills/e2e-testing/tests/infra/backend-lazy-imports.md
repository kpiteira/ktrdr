# Test: infra/backend-lazy-imports

**Purpose:** Validate that the Backend API can be imported and started without torch being eagerly loaded into sys.modules
**Duration:** ~30s (subprocess isolation + API health check)
**Category:** Infrastructure / Container Optimization (M2)

---

## Pre-Flight Checks

**Required modules:**
- None (this test validates import behavior, not runtime functionality)

**Test-specific checks:**
- [ ] uv available
- [ ] ktrdr package installed
- [ ] Python can import subprocess module

---

## Background

This test validates the M2 Container Optimization milestone: making torch imports lazy so the backend API container can run without ML dependencies in most scenarios.

**Why this matters:**
- Backend container image can be ~500MB smaller without torch/CUDA
- Faster container startup times
- Memory savings when ML features aren't needed
- Enables right-sized container images per deployment role

**What "lazy imports" means:**
- torch is NOT imported at module load time
- torch is only imported when ML-specific functionality is called
- API health check, data endpoints, operations endpoints all work without torch

---

## Test Data

No test data required - this test validates import behavior.

---

## Execution Steps

### 1. Verify torch Exists in Environment (Baseline)

**Command:**
```bash
uv run python -c "
import sys
# Verify torch is available (for comparison)
try:
    import torch
    print(f'BASELINE: torch is available (version {torch.__version__})')
    del sys.modules['torch']  # Clean up
    print('BASELINE: torch successfully imported and removed')
except ImportError:
    print('BASELINE: torch not installed (test still valid - verifies no import attempts)')
"
```

**Expected:**
- Either "torch is available" (torch installed) OR "torch not installed"
- Both outcomes are valid for this test

**Why:** Establishes baseline - if torch is NOT installed and API imports fail, that's a CODE_BUG. If torch IS installed and appears in sys.modules after API import, that's also a CODE_BUG (eager import).

---

### 2. Import API Module and Check sys.modules (Core Test)

**Command:**
```bash
uv run python -c "
import sys

# Capture initial modules BEFORE any ktrdr imports
initial_modules = set(sys.modules.keys())
initial_torch = 'torch' in initial_modules
print(f'BEFORE: torch in sys.modules = {initial_torch}')

# Import the API application (this is what uvicorn does)
from ktrdr.api.main import app

# Check what was imported
final_modules = set(sys.modules.keys())
new_modules = final_modules - initial_modules

# Check for torch and related modules
torch_modules = [m for m in new_modules if m.startswith('torch')]
final_torch = 'torch' in final_modules

print(f'AFTER: torch in sys.modules = {final_torch}')
print(f'AFTER: torch-related modules imported = {len(torch_modules)}')

if torch_modules:
    print(f'FAIL: torch modules loaded during API import: {torch_modules[:10]}')
    sys.exit(1)
else:
    print('PASS: No torch modules loaded during API import')
    sys.exit(0)
"
```

**Expected:**
- "PASS: No torch modules loaded during API import"
- Exit code 0

**Evidence to Capture:**
- BEFORE/AFTER torch status
- List of torch modules if any (for debugging)

---

### 3. Verify API App is Functional (Not Just Importable)

**Command:**
```bash
uv run python -c "
import sys

# Import API
from ktrdr.api.main import app

# Verify it's a FastAPI application
from fastapi import FastAPI
assert isinstance(app, FastAPI), 'app is not a FastAPI instance'

# Check routes exist (proves app was properly initialized)
route_paths = [route.path for route in app.routes]
assert '/api/v1/health' in route_paths or any('/health' in p for p in route_paths), \
    'Health endpoint not found in routes'

# Check torch still not loaded
torch_loaded = 'torch' in sys.modules
print(f'API app initialized successfully')
print(f'Route count: {len(route_paths)}')
print(f'torch loaded after app init: {torch_loaded}')

if torch_loaded:
    print('FAIL: torch loaded during app initialization')
    sys.exit(1)
else:
    print('PASS: API app functional without torch')
    sys.exit(0)
"
```

**Expected:**
- "PASS: API app functional without torch"
- Route count > 10 (proves app fully initialized)

---

### 4. Check Heavy Module Imports (Extended Validation)

**Command:**
```bash
uv run python -c "
import sys

initial_modules = set(sys.modules.keys())

# Import API
from ktrdr.api.main import app

final_modules = set(sys.modules.keys())
new_modules = final_modules - initial_modules

# Check for heavy ML modules that should be lazy
heavy_modules = {
    'torch': [],
    'tensorflow': [],
    'jax': [],
    'sklearn': [],  # Some sklearn is OK for fuzzy, but not at import time
}

for prefix in heavy_modules:
    matches = [m for m in new_modules if m.startswith(prefix)]
    heavy_modules[prefix] = matches

# Report findings
print('Heavy module analysis:')
problems = []
for prefix, matches in heavy_modules.items():
    if matches:
        print(f'  {prefix}: {len(matches)} modules loaded')
        problems.append(prefix)
    else:
        print(f'  {prefix}: not loaded (OK)')

if problems:
    print(f'FAIL: Heavy modules loaded at import: {problems}')
    sys.exit(1)
else:
    print('PASS: No heavy ML modules loaded at import')
    sys.exit(0)
"
```

**Expected:**
- "PASS: No heavy ML modules loaded at import"
- torch: not loaded (OK)
- tensorflow: not loaded (OK)

---

### 5. Verify Running API Server Works (Integration Check)

This step requires Docker to be running. Skip if Docker is not available.

**Command:**
```bash
# Load sandbox config if present
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Check if Docker/API is running
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$API_PORT/api/v1/health" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    echo "API server responding on port $API_PORT"

    # Make actual health check request
    RESPONSE=$(curl -s "http://localhost:$API_PORT/api/v1/health")
    echo "Health response: $RESPONSE"

    # Verify response contains expected fields
    if echo "$RESPONSE" | grep -q '"status"'; then
        echo "PASS: Running API server responds to health check"
    else
        echo "FAIL: Health response missing status field"
        exit 1
    fi
else
    echo "SKIP: API server not running (HTTP $HTTP_CODE) - import tests still valid"
    echo "NOTE: Start Docker with 'docker compose up' to test running server"
fi
```

**Expected:**
- Either "PASS: Running API server responds to health check" (Docker running)
- OR "SKIP: API server not running" (acceptable - import tests still valid)

---

## Success Criteria

All must pass:

- [ ] `from ktrdr.api.main import app` succeeds without error
- [ ] torch NOT in sys.modules after API import
- [ ] API app is a valid FastAPI instance with routes
- [ ] No torch-related modules loaded at import time
- [ ] No other heavy ML modules (tensorflow, jax) loaded at import time

---

## Sanity Checks

**CRITICAL:** These catch false positives

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Route count > 10 | < 10 fails | API not fully initialized |
| App is FastAPI instance | Not FastAPI fails | Wrong module imported |
| Test duration > 0.5s | < 0.5s fails | Test skipped or cached |
| new_modules count > 50 | < 50 fails | Import not actually executed |

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| `from ktrdr.api.main import app` raises ImportError | CODE_BUG | Eager import somewhere in chain - trace with `python -v` |
| torch in sys.modules after import | CODE_BUG | Find eager import with `grep -r "import torch" ktrdr/api` |
| API app has no routes | CODE_BUG | Check create_application() for errors |
| Test passes but health check fails | ENVIRONMENT | Docker not running or API crashed |
| ModuleNotFoundError for torch | CONFIGURATION | torch not installed (OK if test passes otherwise) |

---

## Troubleshooting

**If torch appears in sys.modules:**
- **Cause:** Eager import somewhere in the API import chain
- **Diagnosis:** Run `python -v -c "from ktrdr.api.main import app" 2>&1 | grep torch`
- **Cure:** Convert the eager import to lazy import (inside function)

**If API import fails with ImportError:**
- **Cause:** Code assumes torch is always available
- **Diagnosis:** Check the full traceback
- **Cure:** Wrap torch imports in try/except or move inside functions

**If route count is low:**
- **Cause:** Some routers failed to initialize
- **Diagnosis:** Check logs for import errors
- **Cure:** Fix the failing router imports

---

## Evidence to Capture

- sys.modules snapshot (torch-related only)
- Route count after API init
- Heavy module analysis results
- Health check response (if Docker running)
- Full traceback if import fails

---

## Implementation Notes

### Why subprocess/fresh Python is critical

The test MUST run in a fresh Python process because:
1. Once torch is imported, it cannot be fully unloaded
2. Previous imports in the same session pollute sys.modules
3. uv run provides process isolation automatically

### Known lazy import patterns in codebase

The following files already use lazy imports (from code review):
- `ktrdr/api/services/training_service.py` - imports ModelStorage inside methods
- `ktrdr/api/services/training/local_orchestrator.py` - imports torch inside methods

### Files to watch for eager imports

These files import torch and must NOT be imported at API load time:
- `ktrdr/training/*.py` (all training modules)
- `ktrdr/neural/models/*.py` (all neural network models)
- `ktrdr/backtesting/model_loader.py`
- `ktrdr/decision/engine.py`

### Testing the test

To verify this test is working correctly, temporarily add `import torch` at the top of `ktrdr/api/main.py` and confirm the test fails.

---

## Related Tests

- `cli/performance` - Similar sys.modules checking for CLI startup
- `training/smoke` - Validates training works (uses torch, but lazily)
