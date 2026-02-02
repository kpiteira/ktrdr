# Handoff: M2 - Lazy Torch Imports

## Task 2.1 Complete: Remove Unused Imports from training_service.py

**What was done:**
- Removed `ModelLoader` import and `self.model_loader` (confirmed unused)
- Made `ModelStorage` import lazy (inside methods, not module level)
- Removed `model_loader_ready` and `model_storage_ready` from health_check

**DEVIATION FROM PLAN:**
The task description said both ModelLoader and ModelStorage were "unused", but
ModelStorage IS used by `load_trained_model()` and `list_trained_models()` API
endpoints. Instead of removing it entirely, we made the import lazy which still
achieves the goal of breaking the torch import chain.

**Gotcha:**
- `tests/api/test_training_service.py` was already broken before this change
  (patching non-existent `TrainingManager`). Updated the fixture but some tests
  still fail due to missing mocks for the distributed architecture.

**Next Task Notes:**
Task 2.2 does the same lazy import pattern for `strategies.py`. Same approach:
find where ModelStorage is used, move import inside that function.

## Task 2.2 Complete: Lazy Import in strategies.py

**What was done:**
- Removed module-level `from ktrdr.training.model_storage import ModelStorage`
- Moved import inside `list_strategies()` function

**Next Task Notes:**
Task 2.3 does lazy imports for torch itself in `model_loader.py` and `model_storage.py`.
These files have `import torch` at module level which needs to move inside functions.

## Task 2.3 Complete: Lazy Imports in model_loader.py and model_storage.py

**What was done:**
- model_loader.py: Added TYPE_CHECKING block for torch, string annotations for type hints
- model_storage.py: Added TYPE_CHECKING block, lazy imports in save_model() and load_model()

**Pattern used:**
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import torch

def save_model(self, model: "torch.nn.Module", ...):
    import torch  # Lazy import
    torch.save(...)
```

**Next Task Notes:**
Task 2.4 is VALIDATION - verifies the import chain is broken by testing that
`from ktrdr.api.main import app` works without torch available.

## Task 2.4 Complete: VALIDATION PASSED ✅

**E2E Test Result:** ✅ PASSED

**What was tested:**
- Verified that `from ktrdr.api.main import app` loads without torch
- Checked `sys.modules` for any torch-related modules

**Result:**
- 0 torch modules loaded during API import
- Import chain successfully broken

**Root Cause (from earlier failed attempt):**

The import chain was:
1. `backtesting/__init__.py` → imports from `engine.py`
2. `engine.py` line 16: `from ..decision.base import Signal`
3. This triggers `decision/__init__.py` to load (Python loads parent `__init__` first)
4. `decision/__init__.py` had: `from .engine import DecisionEngine`
5. `decision/engine.py` line 7: `import torch`

**Fix Applied:**

Made `decision/__init__.py` use `__getattr__` for lazy loading of torch-dependent classes:

```python
# Base classes load immediately (no torch dependency)
from .base import Position, Signal, TradingDecision

def __getattr__(name: str):
    """Lazy loading for torch-dependent modules."""
    if name == "DecisionEngine":
        from .engine import DecisionEngine
        return DecisionEngine
    if name == "DecisionOrchestrator":
        from .orchestrator import DecisionOrchestrator
        return DecisionOrchestrator
    # ... etc
```

Now when `backtesting/engine.py` imports `from ..decision.base import Signal`:
1. `decision/__init__.py` loads
2. Only `from .base import Position, Signal, TradingDecision` runs
3. `decision/base.py` has NO torch imports
4. Chain is broken!

**All M2 Tasks Complete:**
- Task 2.1: training_service.py lazy imports ✅
- Task 2.2: strategies.py lazy imports ✅
- Task 2.3: model_loader.py and model_storage.py lazy imports ✅
- Task 2.4: Validation passed ✅

**Tests:** 5135 passed, quality checks pass

---

## Additional Bugs Found During Full E2E Validation

After the basic import chain test passed, running actual training/backtest E2E tests
revealed additional bugs that needed fixing:

### Bug 1: Model Loading - input_size Null

**Symptom:** "Model not built" error on every bar during backtest
**Cause:** `metadata.json` had `"input_size": null` after training
**Fix:** Updated `base_model.py` to infer input_size from:
1. `features.json` (has `feature_count`)
2. Model weights (first layer shape)

### Bug 2: Model Loading - Config Structure Mismatch

**Symptom:** `KeyError: 'architecture'` during model load
**Cause:** `model_storage.py` saves FULL strategy config to `config.json`, but
`MLPTradingModel.build_model()` expects just the model section
**Fix:** Updated `base_model.py` to extract "model" section if present:
```python
if "model" in loaded_config and "architecture" not in loaded_config:
    self.config = loaded_config["model"]
else:
    self.config = loaded_config
```

### Bug 3: Missing jinja2 Dependency

**Symptom:** Backend unhealthy - "jinja2 must be installed to use Jinja2Templates"
**Fix:** Added `jinja2>=3.1.0` to pyproject.toml

### Bug 4: Dockerfile.dev Missing ML Extras

**Symptom:** Training workers fail - "No module named 'torch'"
**Cause:** `uv sync --frozen --no-install-project` doesn't include optional extras
**Fix:** Changed to `uv sync --frozen --no-install-project --extra ml`

### E2E Test Updates

Updated test recipes for meaningful validation:
- **training/smoke**: 1h timeframe, 1 year range → ~5,600 samples
- **backtest/smoke**: 1h timeframe, 6 months → ~2,800 bars, 58 trades

**Final Validation Results:**
- 0 torch modules on API import (lazy loading works)
- Training E2E: PASS (5,661 samples, model created)
- Backtest E2E: PASS (58 trades executed, completed in 4.1s)
