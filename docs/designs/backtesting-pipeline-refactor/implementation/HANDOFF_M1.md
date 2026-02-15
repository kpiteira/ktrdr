# Handoff: M1 — ModelBundle + map_location Fix

## Status: Complete

## What Was Done

### Task 1.1: Fix base_model.py map_location
- Added `map_location="cpu"` to `torch.load()` at `ktrdr/neural/models/base_model.py:344`
- Added inline comment explaining why
- Tests: `TestBaseModelMapLocation` in `tests/unit/core/test_neural_foundation.py` (skip when torch unavailable)

### Task 1.2: Create ModelBundle class
- Created `ktrdr/backtesting/model_bundle.py` with:
  - `ModelBundle` frozen dataclass with `load()` classmethod
  - `is_v3_model()` standalone function
  - `load_v3_metadata()` standalone function
  - `reconstruct_config_from_metadata()` standalone function
  - `_build_model()` helper
- Lazy torch import: metadata operations (JSON) don't require torch; `import torch` happens only at weight-loading time
- Tests: 18 tests in `tests/unit/backtesting/test_model_bundle.py` (all pass without torch via sys.modules mock)

### Task 1.3: Move metadata utilities from BacktestingService
- `BacktestingService.is_v3_model()`, `load_v3_metadata()`, `validate_v3_model()`, `reconstruct_config_from_metadata()` now delegate to `model_bundle.py` functions
- `ktrdr/decision/orchestrator.py` updated to import from `model_bundle` instead of `backtesting_service` — fixes the circular dependency
- All existing BacktestingService tests continue to pass via delegation

### Task 1.4: Deprecate ModelLoader
- Added deprecation docstring to `model_loader.py` pointing to `ModelBundle`
- `ModelLoader` kept in codebase because `DecisionOrchestrator` still uses it (will be removed in M3)
- `__init__.py` updated: `ModelBundle` added to exports, `ModelLoader` lazy-load kept with deprecation comment

## Files Changed

| File | Change |
|------|--------|
| `ktrdr/neural/models/base_model.py` | Added `map_location="cpu"` to `torch.load` |
| `ktrdr/backtesting/model_bundle.py` | **NEW** — ModelBundle + utility functions |
| `ktrdr/backtesting/backtesting_service.py` | Static methods now delegate to model_bundle.py |
| `ktrdr/backtesting/__init__.py` | Added ModelBundle export |
| `ktrdr/backtesting/model_loader.py` | Added deprecation docstring |
| `ktrdr/decision/orchestrator.py` | Imports from model_bundle instead of backtesting_service |
| `tests/unit/backtesting/test_model_bundle.py` | **NEW** — 18 tests |
| `tests/unit/core/test_neural_foundation.py` | Added `TestBaseModelMapLocation`, `pytest.importorskip` |

## Test Results

- **165 backtesting unit tests pass** (13 pre-existing failures from missing torch)
- **4816 total unit tests pass** (22 pre-existing failures from torch/training_host)
- Lint: clean
- Format: clean
- Typecheck: pre-existing torch import-not-found errors only

## Gotchas / Notes for M2

1. **torch not in base venv**: The `ml` optional dependency group has torch. Tests that need torch must use `pytest.importorskip("torch")` or mock via `sys.modules`. The `test_model_bundle.py` `TestModelBundleLoad` class shows the sys.modules pattern.

2. **ModelBundle.load() model config fallback**: If `config.json` is missing from the model directory, ModelBundle uses a default MLP config `{"type": "mlp", "architecture": {"hidden_layers": [64, 32]}}`. This works because the state_dict load will fail if the architecture doesn't match, giving a clear error.

3. **Docker validation passed**: `ModelBundle.load()` tested inside CPU-only Docker backtest worker container with synthetic v3 model. Model loads on CPU, eval mode confirmed, inference produces correct output shape, frozen dataclass prevents mutation.

4. **DecisionOrchestrator still imports ModelLoader**: The orchestrator at `ktrdr/decision/orchestrator.py:11` still does `from ..backtesting.model_loader import ModelLoader`. This is intentional — the orchestrator is used for paper/live trading paths. M3 will decouple it.
