---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 2: Lazy Torch Imports

**Goal:** Break the import chain so backend can start without torch installed.

**Branch:** `feature/container-optimization`

**Builds on:** M1 (dependency cleanup)

---

## E2E Validation

### Success Criteria

The backend must be able to import and start without torch in the environment.

```bash
# Create a test environment without torch
uv sync --no-dev  # Install core deps only, no --extra ml

# This MUST succeed (currently fails)
python -c "from ktrdr.api.main import app; print('SUCCESS: backend imports without torch')"
```

### Import Chain to Break

```
api/main.py
  → api/endpoints/training.py
    → api/services/training_service.py (imports ModelLoader, ModelStorage)
      → backtesting/model_loader.py (import torch at line 6)
      → training/model_storage.py (import torch at line 10)

api/endpoints/strategies.py
  → training/model_storage.py (import torch)
```

### Verification

- [ ] `python -c "from ktrdr.api.main import app"` works without torch
- [ ] All unit tests still pass with torch installed
- [ ] Workers still function correctly

---

## Task 2.1: Remove Unused Imports from training_service.py

**File(s):** `ktrdr/api/services/training_service.py`
**Type:** CODING
**Estimated time:** 20 min

**Task Categories:** Wiring/DI

**Description:**
Remove the ModelLoader and ModelStorage imports that are instantiated but never used.

**Current code (lines ~25-28):**
```python
from ktrdr.backtesting.model_loader import ModelLoader
from ktrdr.training.model_storage import ModelStorage
```

**Evidence these are unused:**
- Research confirmed: `ModelLoader()` and `ModelStorage()` created in `__init__()` but no methods ever call them
- Backend is pure orchestration — it dispatches to workers, doesn't load models

**Implementation Notes:**
- Remove the import statements
- Remove any instantiation in `__init__()`
- Remove any instance variables (`self.model_loader`, `self.model_storage`)
- Do NOT remove other imports or functionality

**Testing Requirements:**

*Unit Tests:*
- Existing TrainingService tests must pass
- No new tests needed (removing unused code)

*Smoke Test:*
```bash
# Verify imports removed
grep -n "ModelLoader\|ModelStorage" ktrdr/api/services/training_service.py && echo "FAIL: imports still present" || echo "SUCCESS"
```

**Acceptance Criteria:**
- [ ] No `ModelLoader` import in training_service.py
- [ ] No `ModelStorage` import in training_service.py
- [ ] No `self.model_loader` or `self.model_storage` in class
- [ ] Existing tests pass

---

## Task 2.2: Lazy Import in strategies.py

**File(s):** `ktrdr/api/endpoints/strategies.py`
**Type:** CODING
**Estimated time:** 20 min

**Task Categories:** Wiring/DI

**Description:**
Move ModelStorage import inside the function that uses it.

**Current code (line ~60):**
```python
from ktrdr.training.model_storage import ModelStorage
```

**Target pattern:**
```python
# Remove module-level import

# Inside list_strategies() or wherever it's used:
def list_strategies(...):
    from ktrdr.training.model_storage import ModelStorage
    storage = ModelStorage()
    # ... rest of function
```

**Implementation Notes:**
- Find where ModelStorage is actually used in this file
- Move import inside that function
- This is called "lazy import" — import happens at function call time, not module load time

**Testing Requirements:**

*Unit Tests:*
- Existing strategies endpoint tests must pass

*Integration Tests:*
```bash
# Verify endpoint still works
curl http://localhost:8000/api/v1/strategies | head -c 200
```

*Smoke Test:*
```bash
# Verify no module-level ModelStorage import
head -100 ktrdr/api/endpoints/strategies.py | grep "from ktrdr.training.model_storage" && echo "FAIL" || echo "SUCCESS"
```

**Acceptance Criteria:**
- [ ] No module-level ModelStorage import in strategies.py
- [ ] Import moved inside function(s) that use it
- [ ] Endpoint still functions correctly

---

## Task 2.3: Lazy Imports in model_loader.py and model_storage.py

**File(s):**
- `ktrdr/backtesting/model_loader.py`
- `ktrdr/training/model_storage.py`

**Type:** CODING
**Estimated time:** 45 min

**Task Categories:** Wiring/DI

**Description:**
Move `import torch` inside functions that actually need it.

**model_loader.py current (line 6):**
```python
import torch
```

**model_storage.py current (line 10):**
```python
import torch
```

**Target pattern:**
```python
# At module level: NO torch import

def load_model(path: str):
    import torch  # Lazy import
    return torch.load(path)

def save_model(model, path: str):
    import torch  # Lazy import
    torch.save(model, path)
```

**Implementation Notes:**
- Move `import torch` inside EVERY function that uses torch
- For type hints, use string annotations: `def func() -> "torch.nn.Module":`
- Or use TYPE_CHECKING block if needed for complex types
- The import cost is negligible — Python caches imported modules

**Functions to check in model_loader.py:**
- `load_model()` — uses torch.load
- Any function returning torch.nn.Module

**Functions to check in model_storage.py:**
- `save()` — uses torch.save
- `load()` — uses torch.load
- Any function accessing torch.__version__

**Testing Requirements:**

*Unit Tests:*
- Existing model_loader tests must pass
- Existing model_storage tests must pass

*Smoke Test:*
```bash
# Verify no module-level torch import
head -20 ktrdr/backtesting/model_loader.py | grep "^import torch" && echo "FAIL" || echo "SUCCESS"
head -20 ktrdr/training/model_storage.py | grep "^import torch" && echo "FAIL" || echo "SUCCESS"
```

**Acceptance Criteria:**
- [ ] No module-level `import torch` in model_loader.py
- [ ] No module-level `import torch` in model_storage.py
- [ ] All functions that need torch import it internally
- [ ] Type hints use strings or TYPE_CHECKING
- [ ] All existing tests pass

---

## Task 2.4: Verify Import Chain is Broken

**File(s):** None (verification task)
**Type:** VALIDATION
**Estimated time:** 15 min

**Task Categories:** Configuration

**Description:**
Verify that the backend can now import without torch.

**Test Script:**
```python
#!/usr/bin/env python
"""Verify backend imports work without torch."""
import sys

# Remove torch from available modules if present
for mod in list(sys.modules.keys()):
    if 'torch' in mod:
        del sys.modules[mod]

# Block torch imports
class TorchBlocker:
    def find_module(self, name, path=None):
        if name == 'torch' or name.startswith('torch.'):
            return self
    def load_module(self, name):
        raise ImportError(f"BLOCKED: {name} - backend should not import torch!")

sys.meta_path.insert(0, TorchBlocker())

# Now try to import the backend
try:
    from ktrdr.api.main import app
    print("SUCCESS: Backend imports without torch!")
    sys.exit(0)
except ImportError as e:
    if "BLOCKED" in str(e):
        print(f"FAIL: Backend still imports torch!")
        print(f"  {e}")
        sys.exit(1)
    raise
```

**Implementation Notes:**
- Run this test in a clean environment
- If it fails, trace which import is still pulling in torch

**Testing Requirements:**

*E2E Test:*
```bash
# Save script and run
python /tmp/verify_no_torch.py
```

**Acceptance Criteria:**
- [ ] Verification script passes
- [ ] `from ktrdr.api.main import app` works without torch
- [ ] All unit tests still pass (with torch available)
- [ ] All changes committed

---

## Milestone 2 Completion Checklist

- [ ] Task 2.1: Unused imports removed from training_service.py
- [ ] Task 2.2: Lazy import in strategies.py
- [ ] Task 2.3: Lazy imports in model_loader.py and model_storage.py
- [ ] Task 2.4: Import chain verified broken
- [ ] All unit tests pass: `make test-unit`
- [ ] Quality gates pass: `make quality`
- [ ] Backend imports without torch
- [ ] All changes committed
- [ ] M1 functionality still works (no regressions)
