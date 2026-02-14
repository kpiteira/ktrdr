---
design: docs/designs/backtesting-pipeline-refactor/DESIGN.md
architecture: docs/designs/backtesting-pipeline-refactor/ARCHITECTURE.md
---

# M1: ModelBundle + map_location Fix

## Goal

Create `ModelBundle` as the single model loading point for backtesting. Fix the `map_location="cpu"` bug on the legacy path. Move metadata utilities from `BacktestingService`. Delete `ModelLoader`.

## Tasks

### Task 1.1: Fix base_model.py map_location (the original bug)

**File(s):** `ktrdr/neural/models/base_model.py`
**Type:** CODING
**Estimated time:** 30 minutes

**Description:**
Add `map_location="cpu"` to `torch.load()` at line 343. This is the root cause of the MPS device error. Even though the backtesting pipeline will stop using this path after M3, it must be correct for any future callers (paper/live trading, direct model inspection).

**Implementation Notes:**
- Line 343: `model_state = torch.load(load_dir / "model.pt", weights_only=True)` → add `map_location="cpu"`
- Add inline comment: "CPU mapping ensures models trained on MPS/CUDA load on any device"
- This is a one-line fix but critical for correctness

**Testing Requirements:**
- [ ] Existing `tests/unit/neural/` tests pass
- [ ] Unit test: load a model state dict that contains CPU tensors (smoke test for the parameter)

**Acceptance Criteria:**
- [ ] `torch.load` at base_model.py:343 includes `map_location="cpu"`
- [ ] All existing unit tests pass

---

### Task 1.2: Create ModelBundle class

**File(s):** `ktrdr/backtesting/model_bundle.py` (NEW)
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Create `ModelBundle` — a frozen dataclass that loads all model artifacts from disk in one call. This replaces the triple-load pattern. Loads `model.pt` (state dict, `weights_only=True`, `map_location="cpu"`), reads JSON metadata files, builds model architecture, and reconstructs `StrategyConfigurationV3` from metadata.

**Implementation Notes:**
- `@dataclass(frozen=True)` — immutable after creation
- `@classmethod def load(cls, model_path: str) -> "ModelBundle"` — the single entry point
- Move `reconstruct_config_from_metadata()` from `BacktestingService` (lines 536-619) — this is a config utility, not a service method
- Move `load_v3_metadata()` from `BacktestingService` (lines 465-494) — same reason
- Move `is_v3_model()` from `BacktestingService` (lines 496-508)
- Model building: read `model_config` from metadata, determine `input_size` from `features.json`, call `MLPTradingModel.build_model()` or equivalent factory
- Guard against non-v3 models: raise clear error if `metadata_v3.json` missing
- Lazy torch import: `import torch` inside `load()`, not at module level (keeps imports fast for modules that only need metadata)

**Pattern to follow:** `FeatureCache.__init__()` for how it receives `config` and `model_metadata` — `ModelBundle.load()` produces exactly these.

**Testing Requirements:**
- [ ] Test: `ModelBundle.load(valid_model_path)` returns frozen dataclass with model in eval mode
- [ ] Test: `ModelBundle.load(path_without_metadata_v3)` raises `FileNotFoundError` with clear message
- [ ] Test: `ModelBundle.load(path_with_corrupt_model_pt)` raises with clear error
- [ ] Test: `bundle.model` is in eval mode and on CPU device
- [ ] Test: `bundle.strategy_config` has required sections (indicators, fuzzy_sets, model, etc.)
- [ ] Test: frozen dataclass — assignment to `bundle.model` raises `FrozenInstanceError`

**Acceptance Criteria:**
- [ ] `ModelBundle.load()` performs exactly ONE `torch.load` call
- [ ] `torch.load` uses `map_location="cpu"` and `weights_only=True`
- [ ] Metadata loaded from JSON files only (no torch needed for metadata)
- [ ] `reconstruct_config_from_metadata` logic moved from `BacktestingService`
- [ ] All tests pass

---

### Task 1.3: Move metadata utilities from BacktestingService

**File(s):** `ktrdr/backtesting/backtesting_service.py`, `ktrdr/backtesting/model_bundle.py`
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
`BacktestingService` has three static methods that are config/metadata utilities, not service methods: `is_v3_model()`, `load_v3_metadata()`, `validate_v3_model()`, and `reconstruct_config_from_metadata()`. Move these to `ModelBundle` (or as standalone functions in `model_bundle.py`). Update all callers.

**Implementation Notes:**
- Callers to find and update:
  - `ktrdr/decision/orchestrator.py` lines 760-762 (`_check_v3_model` calls `BacktestingService.is_v3_model()`)
  - `ktrdr/decision/orchestrator.py` lines 776-786 (`_create_feature_cache` calls `BacktestingService.load_v3_metadata()` and `reconstruct_config_from_metadata()`)
  - Any tests that reference these static methods
- In `BacktestingService`, replace the moved methods with thin delegations that call the new location (backward compat for any external callers)
- This fixes the circular dependency: `decision/orchestrator.py` will import from `backtesting/model_bundle.py` (a data module) instead of `backtesting/backtesting_service.py` (an API service)

**Testing Requirements:**
- [ ] Existing tests that call `BacktestingService.is_v3_model()` etc. still pass
- [ ] `orchestrator.py` imports from `model_bundle` instead of `backtesting_service`

**Acceptance Criteria:**
- [ ] No direct `BacktestingService` import in `decision/orchestrator.py`
- [ ] Static methods delegated from `BacktestingService` to `model_bundle.py` functions
- [ ] All existing tests pass

---

### Task 1.4: Delete ModelLoader

**File(s):** `ktrdr/backtesting/model_loader.py` (DELETE), callers
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
`ModelLoader` is replaced by `ModelBundle`. Delete the file and update all callers. The only caller in the backtesting pipeline is `DecisionOrchestrator.__init__()` (line 144) — but since M3 will remove that dependency, this task only needs to ensure no OTHER callers exist, and remove the import from `__init__.py`.

**Implementation Notes:**
- Search for all imports of `ModelLoader` across the codebase
- `DecisionOrchestrator` still uses `ModelLoader` until M3 — if it's the only caller, we can defer deletion to M3. If there are other callers, update them now.
- Actually: check if `DecisionOrchestrator` is the ONLY user. If so, keep `model_loader.py` alive until M3 when the orchestrator is decoupled. Mark it with a deprecation comment instead.
- Remove from `ktrdr/backtesting/__init__.py` exports if present

**Testing Requirements:**
- [ ] No import errors after removal/deprecation
- [ ] Grep confirms no remaining imports of `ModelLoader` outside the orchestrator

**Acceptance Criteria:**
- [ ] `ModelLoader` either deleted or marked deprecated with comment pointing to `ModelBundle`
- [ ] No new code imports `ModelLoader`
- [ ] All tests pass

---

### Task 1.5: M1 Validation

**File(s):** Tests
**Type:** VALIDATION
**Estimated time:** 1 hour

**Description:**
Validate that `ModelBundle` correctly loads models in a CPU-only environment, specifically models trained on MPS (Apple Silicon).

**Validation Steps:**
1. Run `uv run pytest tests/unit/backtesting/ -x -q` — all pass
2. Run `make quality` — clean
3. Fast container test: execute `ModelBundle.load()` inside a Docker backtest worker container against an MPS-trained model:
   ```bash
   docker exec ktrdr-prod-backtest-worker-1-1 /app/.venv/bin/python -c "
   from ktrdr.backtesting.model_bundle import ModelBundle
   bundle = ModelBundle.load('/app/models/rhythm_dancer_multibeat_20250211/1h_v6')
   print(f'Model loaded: {bundle.model.__class__.__name__}')
   print(f'Features: {len(bundle.feature_names)}')
   print(f'Device: {next(bundle.model.parameters()).device}')
   "
   ```
4. Verify output shows: model loaded, feature count > 0, device = cpu

**Acceptance Criteria:**
- [ ] All unit tests pass
- [ ] Quality gates clean
- [ ] ModelBundle loads MPS-trained model inside CPU-only Docker container
- [ ] Model is on CPU device after loading
