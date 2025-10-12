# Training Architecture Phase 2 - Implementation Plan

**Parent Documents**:
- [01-analysis.md](./01-analysis.md) - Problem identification
- [02-requirements.md](./02-requirements.md) - Requirements specification
- [03-architecture.md](./03-architecture.md) - Architecture design

**Status**: Ready for Implementation
**Version**: Phase 2 - Orchestrator Refactoring + Performance Optimization
**Date**: 2025-01-10

---

## Overview

This plan implements **Phase 2**: Creating orchestrators that use TrainingPipeline for all work, eliminating code duplication, and fixing critical performance bugs.

### Goals

1. **Create orchestrators** that use TrainingPipeline for all work
2. **Eliminate code duplication** between local and host training paths
3. **Fix critical performance bug** in host service (14-minute sleep overhead!)
4. **Preserve all behavior** - zero breaking changes
5. **Enable model persistence** in host service via shared filesystem

### Key Principles (from CLAUDE.md)

1. **Think Before You Code**: Understand root cause, consider architecture, propose solution
2. **Quality > Speed**: Taking time to do it right saves debugging time
3. **Test Everything**: If it's not tested, it's broken
4. **Refactor Fearlessly**: If the current design doesn't fit, change it

### Success Criteria

- ✅ Zero code duplication in training logic
- ✅ Both orchestrators use TrainingPipeline exclusively
- ✅ GPU training achieves FULL SPEED (remove 14-minute sleep overhead!)
- ✅ Progress updates remain frequent (every 10 batches)
- ✅ Cancellation remains responsive (< 50ms local, < 2.1s host)
- ✅ All manual E2E tests pass
- ✅ Models saved and loadable from both paths
- ✅ Performance within 1% of baseline

---

## Phase 2 Task Breakdown

### TASK-2.0: Extract Multi-Symbol Logic + Create High-Level Pipeline API

#### Plan

**Objective**: Move multi-symbol handling logic from StrategyTrainer to TrainingPipeline and create a high-level orchestration method.

**Why This First**:
- Both orchestrators depend on these methods
- Must be complete and tested before refactoring orchestrators
- Establishes pattern for avoiding "previous failed attempt trap"

**What Changes**:

- Extract multi-symbol data combining from StrategyTrainer (lines 1199-1255):
  - `combine_multi_symbol_data()` - Concatenates data from multiple symbols, preserving temporal order
  - **Symbol-agnostic design**: Strategies operate on patterns, not symbol names
  - **Temporal preservation**: Concatenates sequentially (AAPL all data → MSFT all data → etc.)
  - **Indicator resets**: Reset indicator state at symbol boundaries
  - **No symbol embeddings**: Model sees only technical indicators and fuzzy memberships
  - **No random sampling**: Uses ALL data, no data loss
- Create high-level `train_strategy()` method:
  - Orchestrates entire pipeline (load data → train → save model)
  - Accepts `progress_callback` and `cancellation_token` as parameters
  - **Passes them through to train_model()** - doesn't handle them (key to avoiding trap!)
  - Returns standardized result format
- Update StrategyTrainer to delegate to pipeline methods (backward compatibility)

**Architectural Decisions**:

1. **Strategies are symbol-agnostic** → Model learns patterns from indicators/price, not symbol names
2. **Multi-symbol = concatenate data** → Simple sequential concatenation preserves temporal order
3. **No symbol embeddings** → Model sees only technical indicators and fuzzy memberships
4. **Reset indicators at boundaries** → Each symbol's data is a separate time series
5. **High-level API passes callbacks/tokens through** → Orchestrators provide implementations
6. **Pipeline returns standardized format** → Eliminates need for result_aggregator.py
7. **StrategyTrainer delegates** → Preserves backward compat during transition

**Why This Avoids Previous Trap**:
- Previous attempt tried to UNIFY progress/cancellation mechanisms
- New approach: Pipeline ACCEPTS callbacks/tokens as parameters, PASSES THROUGH to train_model()
- Orchestrators provide DIFFERENT implementations (local vs host)
- Separation preserved, duplication eliminated

**Risks & Mitigations**:
- **Risk**: Extracting code might change behavior
  - **Mitigation**: Keep StrategyTrainer as wrapper, test both paths
- **Risk**: High-level API might not support all needs
  - **Mitigation**: Pass callbacks/tokens through, don't handle in pipeline
- **Risk**: Multi-symbol extraction could break edge cases
  - **Mitigation**: Comprehensive unit tests, existing tests must pass

**Dependencies**: None (foundation task)

**Estimated Effort**: 3 days

#### Acceptance Criteria

**Multi-Symbol Data Combining**:

- [ ] `combine_multi_symbol_data()` extracted and tested
  - [ ] Concatenates data sequentially (preserves temporal order within each symbol)
  - [ ] Returns combined features and labels only (no symbol_indices)
  - [ ] Uses ALL data from all symbols (no sampling/data loss)
  - [ ] Handles different sample counts per symbol (natural concatenation)
  - [ ] Documents indicator reset requirement at symbol boundaries
- [ ] Symbol-agnostic design verified
  - [ ] Uses regular `MLPTradingModel` (not MultiSymbolMLP)
  - [ ] Model receives only technical indicators and fuzzy memberships
  - [ ] No symbol names, indices, or embeddings anywhere in training
  - [ ] Strategy can be trained on any combination of symbols and used on any data

**High-Level API**:
- [ ] `train_strategy()` method created
  - [ ] Orchestrates all pipeline steps (load → process → train → save)
  - [ ] Accepts progress_callback parameter (optional)
  - [ ] Accepts cancellation_token parameter (optional)
  - [ ] Passes both through to train_model() without handling
  - [ ] Returns standardized result dict with:
    - [ ] model_path
    - [ ] training_metrics
    - [ ] test_metrics
    - [ ] artifacts (feature_importance, per_symbol_metrics)
    - [ ] model_info (parameters, architecture)
    - [ ] data_summary (symbols, timeframes, sample counts)
  - [ ] Works for single-symbol training
  - [ ] Works for multi-symbol training

**Testing & Validation**:
- [ ] Unit tests pass for all extracted methods
- [ ] Unit tests for train_strategy() cover:
  - [ ] Single-symbol path
  - [ ] Multi-symbol path
  - [ ] Progress callback invoked correctly
  - [ ] Cancellation token checked correctly
- [ ] StrategyTrainer still works (delegates to pipeline)
- [ ] Existing StrategyTrainer tests pass (no behavior change)

**Code Quality**:
- [ ] All methods have type hints
- [ ] All methods have clear docstrings explaining purpose
- [ ] Code follows existing TrainingPipeline patterns
- [ ] No debug print statements

#### Files Modified

- `ktrdr/training/training_pipeline.py` - Add 5 new methods
- `ktrdr/training/train_strategy.py` - Update to delegate to pipeline
- `tests/unit/training/test_training_pipeline_multi_symbol.py` - Create comprehensive tests

#### Reference Implementation

See [APPENDIX A](#appendix-a-task-20-reference-implementation) for complete code examples of:

- `combine_multi_symbol_data()` method (symbol-agnostic, temporal preservation)
- High-level `train_strategy()` method signature

---

### TASK-2.1: Create LocalTrainingOrchestrator

#### Plan

**Objective**: Create thin orchestrator that uses TrainingPipeline.train_strategy() for local training execution.

**Why**: Eliminates duplication by delegating all work to pipeline while preserving local-specific coordination (ProgressBridge, in-memory cancellation).

**What Changes**:
- Create `LocalTrainingOrchestrator` class:
  - Load strategy config from filesystem
  - Create progress callback adapter (TrainingPipeline → ProgressBridge)
  - Provide in-memory cancellation token
  - Call TrainingPipeline.train_strategy() via asyncio.to_thread()
  - Add session metadata to result
- Update `LocalTrainingRunner` to thin wrapper:
  - Instantiate LocalTrainingOrchestrator
  - Delegate run() to orchestrator
  - Maintain backward-compatible API
- Delete `result_aggregator.py`:
  - No longer needed (pipeline returns standardized format)
  - from_local_run() eliminated
  - from_host_run() eliminated

**Architectural Decisions**:
1. **Orchestrator loads config** → Strategy acquisition may differ by environment
2. **Progress adapter created by orchestrator** → Bridges pipeline callbacks to ProgressBridge
3. **LocalTrainingRunner becomes thin wrapper** → Maintains API compatibility
4. **Delete result_aggregator** → Pipeline standardizes output

**Key Preservation**:
- Keep `asyncio.to_thread()` wrapper (preserve async model)
- Keep ProgressBridge mechanism (preserve progress reporting)
- Keep in-memory CancellationToken (preserve cancellation)

**Risks & Mitigations**:
- **Risk**: Progress callback adapter might not translate correctly
  - **Mitigation**: Integration tests verify progress updates work
- **Risk**: Breaking LocalTrainingRunner API
  - **Mitigation**: Runner becomes thin wrapper, API unchanged

**Dependencies**: TASK-2.0 (requires train_strategy() method)

**Estimated Effort**: 2 days

#### Acceptance Criteria

**LocalTrainingOrchestrator**:
- [ ] Class created with correct initialization
  - [ ] Accepts context, progress_bridge, cancellation_token, model_storage
  - [ ] No other dependencies (delegates everything to pipeline)
- [ ] Strategy config loading works
  - [ ] Loads YAML from filesystem
  - [ ] Validates required sections
  - [ ] Returns parsed config dict
- [ ] Progress callback adapter works
  - [ ] Translates batch-level progress to bridge.on_batch()
  - [ ] Translates epoch-level progress to bridge.on_epoch()
  - [ ] Translates phase changes to bridge.on_phase()
- [ ] Cancellation token passed through correctly
  - [ ] In-memory token provided to pipeline
  - [ ] Training stops when token cancelled
- [ ] Result includes session metadata
  - [ ] operation_id, strategy_name, symbols, timeframes
  - [ ] use_host_service = false
  - [ ] resource_usage includes training_mode = "local"

**LocalTrainingRunner**:
- [ ] Updated to thin wrapper
  - [ ] Instantiates LocalTrainingOrchestrator
  - [ ] Delegates run() to orchestrator
  - [ ] API unchanged (backward compatible)

**Cleanup**:
- [ ] result_aggregator.py deleted
  - [ ] from_local_run() removed
  - [ ] from_host_run() removed
  - [ ] No references remain in codebase

**Testing**:
- [ ] Integration tests pass
  - [ ] test_local_orchestrator.py covers full flow
  - [ ] Progress updates verified
  - [ ] Cancellation verified
- [ ] Manual E2E test passes
  - [ ] `ktrdr models train` completes successfully
  - [ ] Progress visible in CLI
  - [ ] Model saved and loadable

**Code Quality**:
- [ ] Type hints on all methods
- [ ] Clear docstrings
- [ ] Follows existing service patterns

#### Files Modified

- `ktrdr/api/services/training/local_orchestrator.py` - CREATE
- `ktrdr/api/services/training/local_runner.py` - MODIFY (thin wrapper)
- `ktrdr/api/services/training/result_aggregator.py` - DELETE
- `tests/integration/training/test_local_orchestrator.py` - CREATE

#### Reference Implementation

See [APPENDIX B](#appendix-b-task-21-reference-implementation) for complete code examples of:
- LocalTrainingOrchestrator class
- Updated LocalTrainingRunner wrapper
- Progress callback adapter pattern

---

### TASK-3.1: Create HostTrainingOrchestrator + Fix Performance Bug

#### Plan

**Objective**: Create orchestrator for host service AND fix critical 14-minute sleep overhead that destroys GPU performance.

**Why**: Eliminates duplication by delegating to pipeline while preserving host-specific coordination (session-based progress/cancellation). **CRITICAL**: Removes artificial delays that make GPU 29× slower than it should be.

**What Changes**:
- **CRITICAL PERFORMANCE FIX**:
  - Delete `await asyncio.sleep(0.1)` from batch loop (line ~738) - wastes 13 minutes per 100 epochs!
  - Delete `await asyncio.sleep(0.5)` from epoch loop (line ~778) - wastes 50 seconds per 100 epochs!
  - Implement intelligent throttling: update every 10 batches (not every batch)
  - Result: 14 minutes overhead → 8ms overhead (105,000× faster!)
- Create `HostTrainingOrchestrator` class:
  - Extract config from TrainingSession
  - Create throttled progress callback (session.update_progress)
  - Create SessionCancellationToken (checks session.stop_requested)
  - Call TrainingPipeline.train_strategy() directly (no thread wrapper)
  - Add host metadata (GPU info, device type)
  - Save model via shared ModelStorage
- Update `training_service._run_real_training()`:
  - Instantiate HostTrainingOrchestrator
  - Delegate to orchestrator.run()
  - Delete entire inline training loop (lines 551-781)
  - Delete inline TradingModel definition (lines 635-658)

**Performance Analysis**:
```
BEFORE (broken):
- 78 batches/epoch × 100ms sleep = 7,800ms per epoch
- 100 epochs × 7.8s = 780 seconds = 13 minutes wasted on batch sleep
- 100 epochs × 500ms = 50 seconds wasted on epoch sleep
- TOTAL WASTE: ~14 minutes per 100-epoch training
- GPU training: 30s native + 14min overhead = 14.5 minutes

AFTER (fixed):
- 78 batches/epoch / 10 (throttle) = 8 updates/epoch
- 8 updates × 0.01ms = 0.08ms per epoch
- 100 epochs × 0.08ms = 8ms total overhead
- GPU training: 30s native + 8ms overhead = ~30 seconds
- SPEEDUP: 14.5 minutes → 30 seconds = 29× FASTER!
```

**Architectural Decisions**:
1. **Remove ALL sleep operations** → Sleep destroys performance, throttle by skipping instead
2. **Progress every 10 batches** → Balance between frequency and overhead
3. **Check cancellation every 5 batches** → Responsive (< 2.1s) with minimal overhead
4. **Direct async (no thread wrapper)** → Host service already async, no need for to_thread
5. **Session-based cancellation** → Check session.stop_requested flag
6. **Shared filesystem model storage** → Both services access same models/ directory

**Why This Fixes Performance**:
- Sleep operations add artificial 14-minute delay per training
- Throttling by skipping (not sleeping) has essentially zero overhead
- Progress updates are cheap (~0.01ms each)
- Cancellation checks are free (~0.001ms each)
- GPU can run at full speed (> 95% utilization)

**Risks & Mitigations**:
- **Risk**: Throttling might miss progress updates
  - **Mitigation**: Update every 10 batches is ~100ms intervals, smooth enough
- **Risk**: Less frequent cancellation checks
  - **Mitigation**: Every 5 batches = < 2.1s latency, acceptable
- **Risk**: Session-based token might not work
  - **Mitigation**: SessionCancellationToken implements CancellationToken interface

**Dependencies**: TASK-2.0 (requires train_strategy() method)

**Estimated Effort**: 3 days (including performance testing)

#### Acceptance Criteria

**HostTrainingOrchestrator**:
- [ ] Class created with correct initialization
  - [ ] Accepts session and model_storage
  - [ ] No other dependencies
- [ ] Config extraction works
  - [ ] Extracts symbols, timeframes, dates from session.config
  - [ ] Handles both single and multi-symbol
- [ ] Throttled progress callback works
  - [ ] Updates every 10 batches (not every batch)
  - [ ] NO sleep operations anywhere
  - [ ] Batch-level progress updates session
  - [ ] Epoch-level progress updates session
- [ ] SessionCancellationToken works
  - [ ] Checks session.stop_requested
  - [ ] Implements CancellationToken interface
  - [ ] Training stops when flag set
- [ ] Model persistence works
  - [ ] Saves model via ModelStorage
  - [ ] model_path in session.artifacts
  - [ ] Backend can load model from shared filesystem
- [ ] Host metadata included in result
  - [ ] GPU name and device type
  - [ ] gpu_used flag
  - [ ] session_id

**TrainingService Updates**:
- [ ] _run_real_training() simplified to thin wrapper
  - [ ] Instantiates HostTrainingOrchestrator
  - [ ] Delegates to orchestrator.run()
  - [ ] Updates session status correctly
- [ ] Inline training loop deleted (lines 551-781)
- [ ] Inline TradingModel deleted (lines 635-658)
- [ ] Both sleep operations deleted:
  - [ ] await asyncio.sleep(0.1) removed (line ~738)
  - [ ] await asyncio.sleep(0.5) removed (line ~778)

**Performance Verification**:
- [ ] GPU training completes in ~30 seconds (not 14 minutes!)
  - [ ] Measured with manual timing
  - [ ] Within 1% of baseline (no progress overhead)
- [ ] GPU utilization > 95% during training
  - [ ] Verified with Activity Monitor or nvidia-smi
  - [ ] No artificial delays slowing GPU
- [ ] Progress updates still frequent
  - [ ] Every 10 batches = ~100ms intervals
  - [ ] Visible in CLI
  - [ ] Smooth progress bar
- [ ] Cancellation responsive
  - [ ] Stops within 2.1 seconds
  - [ ] Session status updates to "cancelled"

**Testing**:
- [ ] Integration tests pass
  - [ ] test_host_orchestrator.py covers full flow
  - [ ] Progress throttling verified
  - [ ] No sleep operations in test execution
- [ ] Manual E2E test passes
  - [ ] `USE_TRAINING_HOST_SERVICE=true ktrdr models train` completes
  - [ ] Performance measured and documented
  - [ ] Model saved and loadable

**Code Quality**:
- [ ] No sleep operations anywhere in training code
- [ ] Throttling configuration documented
- [ ] Clear comments explaining performance decisions

#### Files Modified

- `ktrdr/api/services/training/host_orchestrator.py` - CREATE
- `training-host-service/services/training_service.py` - MODIFY (delete 300 lines!)
- `tests/integration/training/test_host_orchestrator.py` - CREATE

#### Reference Implementation

See [APPENDIX C](#appendix-c-task-31-reference-implementation) for complete code examples of:
- HostTrainingOrchestrator class with throttled progress
- SessionCancellationToken implementation
- Updated training_service._run_real_training() wrapper
- Performance optimization patterns

---

### TASK-3.2: Cleanup and Deletion of Deprecated Code

#### Plan

**Objective**: DELETE deprecated code and files that are no longer used after Phase 2 refactoring.

**Why**: Eliminate technical debt, ensure single source of truth, prevent confusion about which code to use. After thorough codebase analysis, this task removes ~1,800+ lines of deprecated code.

**CRITICAL FINDINGS FROM CODEBASE ANALYSIS**:

Based on exhaustive investigation, the following components MUST be deleted:

---

**DELETION #1: result_aggregator.py (255 lines) - DEFERRED TO TASK-3.3**

**File**: `ktrdr/api/services/training/result_aggregator.py`

**Status**: Used ONLY by HostSessionManager
**Reason for Deletion**: Task 3.3 will fix host service to return TrainingPipeline result directly

**IMPORTANT: DO NOT DELETE IN TASK-3.2!**
- Keep result_aggregator.py working during Task 3.2 cleanup
- This allows running both local and host training to verify everything works
- Delete ONLY after Task 3.3 is complete and verified (see Task 3.3 acceptance criteria)

**Why It Exists**:
- Host service status endpoint returns SESSION METADATA format
- TrainingPipeline returns TRAINING RESULT format
- result_aggregator transforms one into the other
- Task 3.3 fixes host service to store and return training result directly

**Dependencies**: Complete TASK-3.3 first (fix host service result storage), then delete this

---

**DELETION #2: train_strategy.py - StrategyTrainer class (1,417 lines)**

**File**: `ktrdr/training/train_strategy.py`

**Status**: ONLY used by TrainingAdapter local mode
**Reason for Deletion**: LocalTrainingOrchestrator and HostTrainingOrchestrator replace it

**What to Delete**:
- [ ] Delete `ktrdr/training/train_strategy.py` (entire file - 1,417 lines)
- [ ] Remove import from `ktrdr/training/__init__.py`
- [ ] Update all test files that import StrategyTrainer

**Evidence StrategyTrainer is Unused**:
- ✅ LocalTrainingOrchestrator uses TrainingPipeline directly (NOT StrategyTrainer)
- ✅ HostTrainingOrchestrator uses TrainingPipeline directly (NOT StrategyTrainer)
- ✅ TrainingService routes to orchestrators (NOT StrategyTrainer)
- ⚠️ ONLY TrainingAdapter local mode still uses it (lines 84-86, 282-292)

**Action**: First complete TrainingAdapter cleanup (see DELETION #3), then delete this file

---

**DELETION #3: TrainingAdapter Local Training Code (~200 lines)**

**File**: `ktrdr/training/training_adapter.py`

**Problem Found**: TrainingAdapter has deprecated local training code that BYPASSES LocalTrainingOrchestrator!

**What's Wrong**:
- Lines 82-86: Imports and instantiates StrategyTrainer for local mode
- Lines 273-292: Calls `self.local_trainer.train_multi_symbol_strategy()` directly
- This BYPASSES LocalTrainingOrchestrator entirely
- BUT: TrainingService DOES use LocalTrainingOrchestrator (correctly)
- Result: TrainingAdapter local code is NEVER CALLED (dead code!)

**Root Cause**:
- TrainingAdapter was designed BEFORE Phase 2 orchestrator refactoring
- It was a "dual-mode" adapter (local OR host)
- Phase 2 introduced orchestrators, so now:
  - Local mode: TrainingService → LocalTrainingOrchestrator ✅
  - Host mode: TrainingService → TrainingAdapter → Host Service ✅
- Adapter is now HOST-SERVICE-ONLY, but still has dead local code

**What to Delete**:
- [ ] Delete lines 82-87: StrategyTrainer import and instantiation
  ```python
  # DELETE THIS:
  if not use_host_service:
      from .train_strategy import StrategyTrainer
      self.local_trainer: Optional[StrategyTrainer] = StrategyTrainer()
  else:
      self.local_trainer = None
  ```
- [ ] Delete lines 273-292: Local training execution path
  ```python
  # DELETE THIS:
  else:
      # Use local training (existing behavior)
      logger.info(f"Starting local training for {symbols} on {timeframes}")

      if self.local_trainer is None:
          raise TrainingProviderError(...)

      return self.local_trainer.train_multi_symbol_strategy(...)
  ```
- [ ] Simplify `__init__` to require `use_host_service=True`
- [ ] Update tests using `TrainingAdapter(use_host_service=False)`

**After Cleanup, TrainingAdapter becomes**:
- Host-service-only communication layer
- No local training code
- Clear single responsibility

---

**DELETION #4: MultiSymbolMLPTradingModel class (~150 lines)**

**File**: `ktrdr/neural/models/mlp.py`

**Status**: ONLY used by StrategyTrainer (which is being deleted)
**Reason for Deletion**: Phase 2 architecture specifies symbol-agnostic design (NO embeddings)

**What to Delete**:
- [ ] Delete `MultiSymbolMLPTradingModel` class (lines 188+, ~150 lines)
- [ ] Delete `MultiSymbolMLP` nn.Module class (if exists)
- [ ] Delete any helper classes for symbol embeddings

**Evidence It's Unused**:
- ✅ Only imported in `train_strategy.py` (line 1274) - training code
- ✅ Only instantiated in `train_strategy.py` (line 1276) - during training
- ✅ NOT used in inference (backtesting/trading uses MLPTradingModel)
- ✅ Existing saved models are MLPTradingModel (model_type: "Sequential")
- ✅ NO imports in backtesting or trading code

**Architecture Decision** (from 03-architecture.md, Task 2.0):
- "NO symbol embeddings - Model sees only technical indicators and fuzzy memberships"
- "Strategies are symbol-agnostic"
- Multi-symbol training = sequential concatenation (AAPL all → MSFT all → etc.)
- Uses regular `MLPTradingModel`, not `MultiSymbolMLPTradingModel`

**Contradiction in Codebase**:
- Architecture doc says: NO embeddings
- Old code still has: MultiSymbolMLPTradingModel with embeddings
- Resolution: Architecture is correct, old code is deprecated

---

**DELETION SUMMARY**:

| File/Component | Lines | Status | Reason |
|----------------|-------|--------|--------|
| result_aggregator.py | 255 | **KEEP in 3.2, delete in 3.3** | Host service will return TrainingPipeline format |
| train_strategy.py | 1,417 | Delete in 3.2 (after adapter cleanup) | Replaced by orchestrators |
| TrainingAdapter local code | ~200 | Delete in 3.2 | Dead code bypassing orchestrators |
| MultiSymbolMLPTradingModel | ~150 | Delete in 3.2 (with train_strategy) | Contradicts symbol-agnostic architecture |
| **TOTAL (3.2)** | **~1,750** | **Delete in 3.2** | **Phase 2 complete, old code obsolete** |
| **TOTAL (3.3)** | **+255** | **Delete after verification** | **After harmonization verified** |
| **GRAND TOTAL** | **~2,000** | **Delete across 3.2 + 3.3** | **Eliminates all deprecated code** |

---

**DOCUMENTATION UPDATES**:

1. **Update 03-architecture.md**:
   - [ ] Mark TrainingPipeline methods as implemented
   - [ ] Document orchestrators as canonical training pattern
   - [ ] Remove all references to StrategyTrainer
   - [ ] Add performance optimization section
   - [ ] Clarify symbol-agnostic design (no embeddings)

2. **Update inline comments**:
   - [ ] Remove "TODO: delete StrategyTrainer" comments
   - [ ] Update code referencing old patterns

---

**ARCHITECTURAL DECISIONS**:

1. **DELETE, don't deprecate** → Phase 2 complete means old code should be removed
2. **Single source of truth** → Orchestrators + TrainingPipeline are the ONLY way
3. **Symbol-agnostic design** → NO embeddings, strategies work on any symbol
4. **Host adapter is host-only** → No local training code in adapter

---

**RISKS & MITIGATIONS**:

- **Risk**: Deleting StrategyTrainer breaks existing code
  - **Mitigation**: Only TrainingAdapter uses it; refactor adapter first (DELETION #3)
- **Risk**: Breaking change for external consumers
  - **Mitigation**: StrategyTrainer was internal-only; orchestrators are the public API
- **Risk**: Documentation gets out of sync
  - **Mitigation**: Update all references in same commit as deletion
- **Risk**: Deleting multi-symbol logic removes useful feature
  - **Mitigation**: Multi-symbol still supported via symbol-agnostic design (Task 2.0)

---

**DEPENDENCIES**:

- TASK-2.1 complete (LocalTrainingOrchestrator exists)
- TASK-3.1 complete (HostTrainingOrchestrator exists)
- **DO NOT** depend on TASK-3.3 (keep result_aggregator working for verification!)

**ESTIMATED EFFORT**: 1 day

#### Acceptance Criteria

**Code Deletion**:
- [ ] result_aggregator.py **KEPT** (do not delete!)
  - [ ] Verify it's still working for host training
  - [ ] Will be deleted in TASK-3.3 after verification
- [ ] StrategyTrainer DELETED
  - [ ] train_strategy.py removed from imports
  - [ ] TrainingAdapter refactored to use orchestrators
  - [ ] All tests updated
- [ ] Multi-symbol embedding code DELETED or CLARIFIED
  - [ ] Decision documented
  - [ ] If deleted: MultiSymbolMLPTradingModel removed
  - [ ] If kept: Architecture doc updated to explain embeddings

**Documentation Updates**:
- [ ] 03-architecture.md updated
  - [ ] TrainingPipeline methods marked implemented
  - [ ] Orchestrators documented
  - [ ] Performance optimization section added
- [ ] 04-implementation-plan.md updated
  - [ ] Phase 2 tasks marked complete
  - [ ] Actual vs estimated effort documented
- [ ] PERFORMANCE.md created
  - [ ] Documents 14-minute sleep bug
  - [ ] Explains throttling solution
  - [ ] Provides configuration examples
  - [ ] Shows before/after metrics
- [ ] README updated (if training examples exist)
  - [ ] Reflects new architecture
  - [ ] Shows orchestrator usage

**Code Quality**:
- [ ] All documentation clear and concise
- [ ] No broken links
- [ ] Consistent terminology

#### Files Modified

- `ktrdr/training/train_strategy.py` - Add deprecation warning
- `docs/architecture/training/03-architecture.md` - Update status
- `docs/architecture/training/04-implementation-plan.md` - Mark complete
- `docs/architecture/training/PERFORMANCE.md` - CREATE
- Relevant READMEs - Update if needed

#### Reference Implementation

See [APPENDIX D](#appendix-d-task-32-reference-implementation) for:
- Deprecation warning pattern
- PERFORMANCE.md content

---

### TASK-3.3: Fix Host Service Result Storage and Aggregation

#### Plan

**Objective**: Eliminate result_aggregator.py by fixing host service to store and return TrainingPipeline result format directly, following the architectural principle that TrainingPipeline is responsible for standardizing training output.

**Why This is Critical**: The current discrepancy between local and host result formats violates the "shared work, separate coordination" principle from 03-architecture.md. TrainingPipeline already returns standardized format—host service should preserve it, not transform it.

**Current Problem**:

```
LOCAL FLOW (Correct):
  LocalTrainingOrchestrator
    ↓ calls
  TrainingPipeline.train_strategy()
    ↓ returns
  {"model_path": ..., "training_metrics": {...}, "test_metrics": {...}, ...}
    ↓ adds session metadata
  LocalTrainingOrchestrator returns SAME FORMAT
    ↓
  TrainingService receives TrainingPipeline format ✅

HOST FLOW (Broken):
  HostTrainingOrchestrator
    ↓ calls
  TrainingPipeline.train_strategy()
    ↓ returns
  {"model_path": ..., "training_metrics": {...}, "test_metrics": {...}, ...}
    ↓ BUT THEN...
  TrainingSession stores progress/metrics in DIFFERENT FORMAT
    ↓
  Status endpoint returns SESSION METADATA (not training result!)
    ↓
  result_aggregator.from_host_run() transforms it BACK
    ↓
  TrainingService receives reconstructed format ❌
```

**Root Cause Analysis**:

1. **TrainingSession** (training-host-service/services/training_service.py:25-69) stores:
   - Progress tracking fields: `current_epoch`, `current_batch`, `metrics`
   - Session metadata: `status`, `message`, `error`
   - Resource managers: `gpu_manager`, `memory_manager`
   - **MISSING**: The actual TrainingPipeline result!

2. **Status endpoint** (training-host-service/services/training_service.py:~300) returns:
   - Session progress dict (not training result)
   - Metrics from session state (not from TrainingPipeline)
   - **MISSING**: `model_path`, `artifacts`, proper `test_metrics`

3. **HostSessionManager** (ktrdr/api/services/training/host_session.py:57) calls:
   - `from_host_run(context, host_snapshot)` to reconstruct result
   - This is architectural violation—TrainingPipeline already standardized it!

**Architectural Principle Violated**:

From 03-architecture.md:
> **TrainingPipeline Responsibility**: Execute pure training transformations, return standardized output
> **Orchestrator Responsibility**: Handle environment-specific coordination, add session metadata

**Current violation**: Host service discards TrainingPipeline output and reconstructs it later via result_aggregator.

---

**Solution Architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│ TrainingPipeline (Shared Work Logic)                       │
│ - Responsibility: Standardize training output format        │
│ - Returns: Complete training result with all metrics       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓ (returns standardized result)
         ┌─────────────────────────────┐
         │                             │
         ↓                             ↓
┌────────────────────┐        ┌────────────────────┐
│ LocalOrchestrator  │        │ HostOrchestrator   │
│ - Add session_info │        │ - Store in session │
│ - Return result    │        │ - Add session_id   │
└────────────────────┘        └────────┬───────────┘
         │                             │
         ↓                             ↓
    (returns result)         (session stores result)
                                      │
                                      ↓
                            ┌──────────────────────┐
                            │ Status Endpoint      │
                            │ - Return stored      │
                            │   training result    │
                            │ - Add status/progress│
                            └──────────┬───────────┘
                                      │
                                      ↓
                            ┌──────────────────────┐
                            │ HostSessionManager   │
                            │ - Return snapshot    │
                            │   directly (NO       │
                            │   aggregation!)      │
                            └──────────────────────┘
```

**Key Insight**: Host service should store the TrainingPipeline result AS-IS, then return it when status = "completed". No transformation needed!

---

**What Changes**:

**CHANGE #1: TrainingSession stores training result**

File: `training-host-service/services/training_service.py`

Add field to store complete training result:

```python
class TrainingSession:
    def __init__(self, session_id: str, config: dict[str, Any]):
        # ... existing fields ...

        # NEW: Store complete training result from TrainingPipeline
        self.training_result: Optional[dict[str, Any]] = None
```

**CHANGE #2: HostTrainingOrchestrator stores result in session**

File: `training-host-service/orchestrator.py` (lines 185-205)

```python
# After TrainingPipeline.train_strategy() returns:
result = await loop.run_in_executor(...)

# Add host metadata (keep existing)
result["resource_usage"] = {...}
result["session_id"] = self._session.session_id

# NEW: Store complete result in session
self._session.training_result = result

# Update session status
self._session.status = "completed"
self._session.message = "Training completed successfully"

return result
```

**CHANGE #3: Status endpoint returns training result when complete**

File: `training-host-service/services/training_service.py` (status endpoint)

```python
def get_session_status(self, session_id: str) -> dict[str, Any]:
    """Get detailed status of a training session."""
    if session_id not in self.sessions:
        raise Exception(f"Session {session_id} not found")

    session = self.sessions[session_id]

    # NEW: If training complete, return the actual training result
    if session.status == "completed" and session.training_result:
        return {
            **session.training_result,  # TrainingPipeline format!
            "session_id": session_id,
            "status": session.status,
            "start_time": session.start_time.isoformat(),
            "last_updated": session.last_updated.isoformat(),
        }

    # Otherwise return progress (for "running" status)
    return {
        "session_id": session_id,
        "status": session.status,
        "progress": session.get_progress_dict(),
        "metrics": {"current": session.metrics, "best": session.best_metrics},
        "resource_usage": session.get_resource_usage(),
        "start_time": session.start_time.isoformat(),
        "last_updated": session.last_updated.isoformat(),
        "error": session.error,
    }
```

**CHANGE #4: HostSessionManager returns snapshot directly**

File: `ktrdr/api/services/training/host_session.py` (line 51-57)

```python
async def run(self) -> dict[str, Any]:
    """Start the host session and poll until completion."""
    await self.start_session()
    host_snapshot = await self.poll_session()

    # NEW: Return snapshot directly (NO aggregation!)
    # When status=completed, snapshot IS the TrainingPipeline result
    return host_snapshot
```

**CHANGE #5: Delete result_aggregator.py** (FINAL STEP - after verification)

After above changes are complete and verified working, delete result_aggregator:

- [ ] Delete `ktrdr/api/services/training/result_aggregator.py`
- [ ] Remove import from `ktrdr/api/services/training/__init__.py`
- [ ] Remove import from `ktrdr/api/services/training/host_session.py`
- [ ] Delete test file `tests/unit/api/services/training/test_result_aggregator.py`

**IMPORTANT**: This is the LAST step. Do not delete until all verification tests pass!

---

**Architectural Benefits**:

1. **Single Source of Truth**: TrainingPipeline is THE authoritative source of result format
2. **No Duplication**: Result format defined once, used everywhere
3. **Local/Host Equivalence**: Both paths return identical structure
4. **Simplified Code**: Remove 255 lines of transformation logic
5. **Principle Compliance**: Shared work (pipeline), separate coordination (orchestrators)

---

**Testing Strategy**:

1. **Unit test**: TrainingSession stores and retrieves training_result
2. **Integration test**: Status endpoint returns correct format when completed
3. **E2E test**: Full training flow returns identical format to local
4. **Comparison test**: Assert local and host results have same schema

---

**Verification Logging**:

To enable easy verification that local and host training return harmonized results, add structured logging at key points:

**LOG #1: LocalTrainingOrchestrator result structure (ktrdr/api/services/training/local_orchestrator.py)**

```python
async def run(self) -> dict[str, Any]:
    # ... training execution ...

    result["session_info"] = {
        "operation_id": self._context.operation_id,
        "strategy_name": self._context.strategy_name,
        # ...
    }

    # NEW: Log result structure for verification
    logger.info("=" * 80)
    logger.info("LOCAL TRAINING RESULT STRUCTURE")
    logger.info(f"  Keys: {list(result.keys())}")
    logger.info(f"  model_path: {result.get('model_path')}")
    logger.info(f"  training_metrics keys: {list(result.get('training_metrics', {}).keys())}")
    logger.info(f"  test_metrics keys: {list(result.get('test_metrics', {}).keys())}")
    logger.info(f"  artifacts keys: {list(result.get('artifacts', {}).keys())}")
    logger.info(f"  session_info keys: {list(result.get('session_info', {}).keys())}")
    logger.info("=" * 80)

    return result
```

**LOG #2: HostTrainingOrchestrator result before storing (training-host-service/orchestrator.py)**

```python
async def run(self) -> dict[str, Any]:
    # ... training execution ...

    result["resource_usage"] = {...}
    result["session_id"] = self._session.session_id

    # NEW: Log result structure BEFORE storing in session
    logger.info("=" * 80)
    logger.info("HOST TRAINING RESULT STRUCTURE (before storing)")
    logger.info(f"  Keys: {list(result.keys())}")
    logger.info(f"  model_path: {result.get('model_path')}")
    logger.info(f"  training_metrics keys: {list(result.get('training_metrics', {}).keys())}")
    logger.info(f"  test_metrics keys: {list(result.get('test_metrics', {}).keys())}")
    logger.info(f"  artifacts keys: {list(result.get('artifacts', {}).keys())}")
    logger.info(f"  resource_usage keys: {list(result.get('resource_usage', {}).keys())}")
    logger.info("=" * 80)

    # Store in session
    self._session.training_result = result

    return result
```

**LOG #3: Status endpoint when returning completed result (training-host-service/services/training_service.py)**

```python
def get_session_status(self, session_id: str) -> dict[str, Any]:
    session = self.sessions[session_id]

    if session.status == "completed" and session.training_result:
        result = {
            **session.training_result,
            "session_id": session_id,
            "status": session.status,
            # ...
        }

        # NEW: Log result structure being returned
        logger.info("=" * 80)
        logger.info(f"STATUS ENDPOINT RETURNING COMPLETED RESULT (session {session_id})")
        logger.info(f"  Keys: {list(result.keys())}")
        logger.info(f"  model_path: {result.get('model_path')}")
        logger.info(f"  training_metrics keys: {list(result.get('training_metrics', {}).keys())}")
        logger.info(f"  test_metrics keys: {list(result.get('test_metrics', {}).keys())}")
        logger.info(f"  artifacts keys: {list(result.get('artifacts', {}).keys())}")
        logger.info(f"  session_id: {result.get('session_id')}")
        logger.info("=" * 80)

        return result
```

**LOG #4: HostSessionManager final result (ktrdr/api/services/training/host_session.py)**

```python
async def run(self) -> dict[str, Any]:
    await self.start_session()
    host_snapshot = await self.poll_session()

    # NEW: Log final result structure
    logger.info("=" * 80)
    logger.info("HOST SESSION MANAGER FINAL RESULT")
    logger.info(f"  Keys: {list(host_snapshot.keys())}")
    logger.info(f"  model_path: {host_snapshot.get('model_path')}")
    logger.info(f"  training_metrics keys: {list(host_snapshot.get('training_metrics', {}).keys())}")
    logger.info(f"  test_metrics keys: {list(host_snapshot.get('test_metrics', {}).keys())}")
    logger.info(f"  artifacts keys: {list(host_snapshot.get('artifacts', {}).keys())}")
    logger.info(f"  session_id: {host_snapshot.get('session_id')}")
    logger.info(f"  status: {host_snapshot.get('status')}")
    logger.info("=" * 80)

    return host_snapshot
```

**Verification Test Script**:

Create a test script that runs identical training on both paths and compares logs:

```bash
#!/bin/bash
# verify_result_harmonization.sh

echo "=== Running LOCAL training ==="
ktrdr models train \
  --strategy config/strategies/example.yaml \
  --symbols AAPL \
  --timeframes 1d \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  2>&1 | tee local_training.log

echo ""
echo "=== Running HOST training ==="
USE_TRAINING_HOST_SERVICE=true ktrdr models train \
  --strategy config/strategies/example.yaml \
  --symbols AAPL \
  --timeframes 1d \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  2>&1 | tee host_training.log

echo ""
echo "=== Extracting result structures ==="
grep -A 10 "LOCAL TRAINING RESULT STRUCTURE" local_training.log > local_structure.txt
grep -A 10 "HOST SESSION MANAGER FINAL RESULT" host_training.log > host_structure.txt

echo ""
echo "=== Comparison ==="
echo "LOCAL structure:"
cat local_structure.txt
echo ""
echo "HOST structure:"
cat host_structure.txt

echo ""
echo "=== VERIFICATION ==="
echo "Both should have identical keys:"
echo "  - model_path"
echo "  - training_metrics"
echo "  - test_metrics"
echo "  - artifacts"
echo "  - model_info"
echo "  - data_summary"
echo "  - session_info (local) / session_id (host)"
echo "  - resource_usage"
```

**Expected Log Output** (harmonized):

```
================================================================================
LOCAL TRAINING RESULT STRUCTURE
  Keys: ['model_path', 'training_metrics', 'test_metrics', 'artifacts', 'model_info', 'data_summary', 'session_info', 'resource_usage']
  model_path: /path/to/model.pt
  training_metrics keys: ['final_train_loss', 'final_val_loss', 'final_train_accuracy', ...]
  test_metrics keys: ['test_accuracy', 'test_loss', 'precision', 'recall', 'f1_score']
  artifacts keys: ['feature_importance', 'per_symbol_metrics']
  session_info keys: ['operation_id', 'strategy_name', 'symbols', 'timeframes', ...]
================================================================================

================================================================================
HOST SESSION MANAGER FINAL RESULT
  Keys: ['model_path', 'training_metrics', 'test_metrics', 'artifacts', 'model_info', 'data_summary', 'resource_usage', 'session_id', 'status', 'start_time', 'last_updated']
  model_path: /path/to/model.pt
  training_metrics keys: ['final_train_loss', 'final_val_loss', 'final_train_accuracy', ...]
  test_metrics keys: ['test_accuracy', 'test_loss', 'precision', 'recall', 'f1_score']
  artifacts keys: ['feature_importance', 'per_symbol_metrics']
  session_id: abc-123-def
  status: completed
================================================================================
```

**Success Criteria**:
- [ ] Both logs show identical core keys (model_path, training_metrics, test_metrics, artifacts)
- [ ] Training metrics have same structure (final_train_loss, final_val_loss, etc.)
- [ ] Test metrics have same structure (test_accuracy, precision, recall, f1_score)
- [ ] model_path exists in both
- [ ] Only difference: local has session_info, host has session_id/status/timestamps

**Manual Verification Required**:
- [ ] Run `verify_result_harmonization.sh` script
- [ ] Compare local_structure.txt and host_structure.txt
- [ ] Verify both trainings completed successfully
- [ ] Confirm log output shows harmonized results
- [ ] **ONLY AFTER verification passes, proceed to delete result_aggregator.py**

---

**Risks & Mitigations**:

- **Risk**: Status endpoint returns different structure during polling vs completion
  - **Mitigation**: Document this behavior; polling returns progress, completion returns result
- **Risk**: Breaking change for any code parsing status response
  - **Mitigation**: This is internal API; only HostSessionManager uses it
- **Risk**: Training result might be large for session storage
  - **Mitigation**: Results are small (< 10KB typically); acceptable for in-memory storage

---

**Dependencies**:

- TASK-3.1 complete (HostTrainingOrchestrator exists)
- TrainingPipeline returns standardized format (TASK-2.0 complete)

**Estimated Effort**: 0.5 days (straightforward refactoring)

#### Acceptance Criteria

**TrainingSession**:
- [ ] Add `training_result` field to store complete result
- [ ] Field is Optional[dict[str, Any]]
- [ ] Initially None, set when training completes

**HostTrainingOrchestrator**:
- [ ] Stores TrainingPipeline result in session.training_result
- [ ] Result stored BEFORE setting status = "completed"
- [ ] Result includes all fields from TrainingPipeline

**Status Endpoint**:
- [ ] Returns training_result when status = "completed"
- [ ] Returns progress dict when status = "running"
- [ ] Includes session metadata in both cases
- [ ] Schema documented clearly

**HostSessionManager**:
- [ ] Returns host snapshot directly (no aggregation)
- [ ] No longer calls from_host_run()
- [ ] Result matches LocalTrainingOrchestrator format

**Result Aggregator Deletion** (FINAL STEP):
- [ ] **WAIT**: Verify harmonization works first using verification script
- [ ] Run both local and host training with same parameters
- [ ] Confirm logs show identical result structures
- [ ] **THEN** delete `ktrdr/api/services/training/result_aggregator.py`
- [ ] Remove import from `ktrdr/api/services/training/__init__.py`
- [ ] Remove import from `ktrdr/api/services/training/host_session.py`
- [ ] Delete test file `tests/unit/api/services/training/test_result_aggregator.py`
- [ ] No references remain

**Schema Validation**:
- [ ] Local and host results have identical schema
- [ ] Both include: model_path, training_metrics, test_metrics, artifacts, model_info
- [ ] Both include session_info (orchestrator-added)
- [ ] Integration test verifies schema equivalence

**Code Quality**:
- [ ] Clear comments explaining dual-mode status endpoint
- [ ] Type hints on training_result field
- [ ] Documentation updated

#### Files Modified

- `training-host-service/services/training_service.py` - Add training_result field, update status endpoint, add verification logging
- `training-host-service/orchestrator.py` - Store result in session, add verification logging
- `ktrdr/api/services/training/local_orchestrator.py` - Add verification logging
- `ktrdr/api/services/training/host_session.py` - Remove from_host_run() call, add verification logging
- `verify_result_harmonization.sh` - CREATE (verification script)
- `ktrdr/api/services/training/result_aggregator.py` - DELETE (AFTER verification passes!)
- `ktrdr/api/services/training/__init__.py` - Remove import (AFTER verification)
- `tests/unit/api/services/training/test_result_aggregator.py` - DELETE (AFTER verification)

---

### TASK-3.4: Manual E2E Validation (Karl Leads)

#### Plan

**Objective**: Validate Phase 2 preserves all behavior and achieves performance goals through comprehensive manual testing.

**Why**: Automated tests can't catch everything. Manual testing by Karl ensures real-world usage works and performance targets are met.

**What To Test**:
1. **Local Training** (single-symbol)
2. **Local Training** (multi-symbol)
3. **Host Service Training** (GPU performance verification)
4. **Performance Benchmark** (measure overhead)
5. **Cancellation Test** (verify responsiveness)
6. **Model Loading Test** (verify interoperability)

**Success Criteria**:
- All 6 test scenarios pass
- Performance targets met
- No regressions in functionality
- Models from both paths interchangeable

**Dependencies**: All other Phase 2 tasks complete

**Estimated Effort**: 1 day

#### Acceptance Criteria

**Test Scenario 1: Local Training (Single Symbol)**
- [ ] Command runs successfully:
  ```bash
  ktrdr models train --strategy config/strategies/example.yaml \
    --symbols AAPL --timeframes 1d \
    --start-date 2024-01-01 --end-date 2024-12-31
  ```
- [ ] Progress updates visible and smooth
- [ ] Training completes without errors
- [ ] Model saved to models/ directory
- [ ] Model file exists and has reasonable size

**Test Scenario 2: Local Training (Multi-Symbol)**
- [ ] Command runs successfully:
  ```bash
  ktrdr models train --strategy config/strategies/example.yaml \
    --symbols AAPL MSFT GOOGL --timeframes 1d \
    --start-date 2024-01-01 --end-date 2024-12-31
  ```
- [ ] All symbols' data used (no sampling/data loss)
- [ ] Temporal order preserved within each symbol
- [ ] Symbol-agnostic model (no embeddings)

**Test Scenario 3: Host Service Training (GPU Performance)**
- [ ] Command runs successfully:
  ```bash
  USE_TRAINING_HOST_SERVICE=true ktrdr models train \
    --strategy config/strategies/example.yaml \
    --symbols AAPL --timeframes 1d \
    --start-date 2024-01-01 --end-date 2024-12-31
  ```
- [ ] Training completes in ~30 seconds (not 14 minutes!)
  - [ ] Measured with `time` command
  - [ ] Within 1% of baseline
- [ ] GPU utilization > 95% during training
  - [ ] Verified with Activity Monitor or nvidia-smi
  - [ ] No long idle periods
- [ ] Progress updates visible in CLI
- [ ] Model saved and loadable

**Test Scenario 4: Performance Benchmark**
- [ ] Baseline measured (training without overhead)
- [ ] Phase 2 measured (training with orchestrators)
- [ ] Overhead < 1% (target exceeded)
- [ ] Results documented

**Test Scenario 5: Cancellation Test**
- [ ] Start training in background
- [ ] Cancel after 10 seconds via CLI
- [ ] Local training stops within 50ms
- [ ] Host training stops within 2.1s
- [ ] Status updates to "cancelled"
- [ ] Resources cleaned up properly

**Test Scenario 6: Model Loading Test**
- [ ] List models with `ktrdr models list`
- [ ] Load model trained locally
- [ ] Load model trained on host service
- [ ] Both models generate predictions
- [ ] Predictions are reasonable (not NaN/inf)

**Performance Targets Met**:
- [ ] Training overhead < 1% (measured)
- [ ] GPU training ~30s for 100 epochs (measured)
- [ ] Progress frequency every 10 batches (~100ms)
- [ ] Cancellation latency: < 50ms local, < 2.1s host
- [ ] GPU utilization > 95%

**Cross-Validation**:
- [ ] Models from local and host are interchangeable
- [ ] Both produce similar accuracy/loss (within 5%)
- [ ] Both save same metadata format
- [ ] Both work with backtesting

**Edge Cases**:
- [ ] Cancellation mid-epoch works
- [ ] Cancellation mid-batch works
- [ ] Out of memory handled gracefully (if testable)
- [ ] Invalid config rejected with clear error

#### Testing Commands

See [APPENDIX E](#appendix-e-task-33-testing-commands) for complete testing script.

---

## Summary Timeline

| Task | Estimated | Key Deliverables |
|------|-----------|------------------|
| TASK-2.0 | 3 days | Multi-symbol methods + high-level API |
| TASK-2.1 | 2 days | LocalTrainingOrchestrator |
| TASK-3.1 | 3 days | HostTrainingOrchestrator + 29× speedup! |
| TASK-3.2 | 0.5 days | Deprecation + docs |
| TASK-3.3 | 1 day | Manual E2E validation |
| **Total** | **9.5 days** | **Zero duplication, full GPU speed** |

---

## Risk Mitigation

### High-Risk Areas

1. **Performance Regression**
   - Risk: Orchestrators add overhead
   - Mitigation: Benchmark before/after, manual timing
   - Target: < 1% overhead

2. **Behavioral Differences**
   - Risk: Orchestrators behave differently than StrategyTrainer
   - Mitigation: Manual E2E testing, StrategyTrainer stays as fallback
   - Target: All tests pass

3. **Progress/Cancellation**
   - Risk: Callback adapters don't translate correctly
   - Mitigation: Integration tests, manual verification
   - Target: Same responsiveness as before

### Rollback Plan

If critical issues discovered:
1. Revert orchestrator commits
2. StrategyTrainer still works (delegates to pipeline)
3. Fix issues on branch
4. Re-test and re-deploy

---

## Success Metrics

Phase 2 is successful when:

1. ✅ **Zero Duplication**: All training logic in TrainingPipeline
2. ✅ **Full GPU Speed**: 29× faster than broken version, within 1% of baseline
3. ✅ **Both Orchestrators Working**: Local and host use same pipeline
4. ✅ **Progress Preserved**: Updates every 10 batches (~100ms)
5. ✅ **Cancellation Preserved**: < 50ms local, < 2.1s host
6. ✅ **Models Interchangeable**: Both paths produce same format
7. ✅ **Manual E2E Tests Pass**: All 6 scenarios validated

---

## Appendices

### APPENDIX A: TASK-2.0 Reference Implementation

#### Multi-Symbol Data Combiner (Symbol-Agnostic)

```python
@staticmethod
def combine_multi_symbol_data(
    all_symbols_features: dict[str, torch.Tensor],
    all_symbols_labels: dict[str, torch.Tensor],
    symbols: list[str],
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Combine features and labels from multiple symbols sequentially, preserving temporal order.

    DESIGN PRINCIPLE: Strategies are symbol-agnostic. A trading strategy operates on
    patterns in technical indicators and price action, not on symbol names. The model
    learns "when RSI is oversold AND MACD crosses up, buy" - this pattern is universal
    across all symbols.

    TEMPORAL PRESERVATION: Concatenates data sequentially (AAPL all → MSFT all → TSLA all)
    to preserve time series order within each symbol. This is critical for learning
    temporal patterns.

    INDICATOR RESETS: Caller must reset indicator state (moving averages, etc.) at
    symbol boundaries since each symbol's data is a separate time series. Concatenating
    AAPL's last day with MSFT's first day doesn't represent continuous time.

    NO DATA LOSS: Uses ALL data from all symbols - no sampling, no random selection.

    Args:
        all_symbols_features: Dict mapping symbol to features tensor
        all_symbols_labels: Dict mapping symbol to labels tensor
        symbols: List of symbol names in order

    Returns:
        Tuple of (combined_features, combined_labels)
        Note: No symbol_indices returned - strategies are symbol-agnostic
    """
    combined_features_list = []
    combined_labels_list = []

    for symbol in symbols:
        # Concatenate sequentially - preserves temporal order
        combined_features_list.append(all_symbols_features[symbol])
        combined_labels_list.append(all_symbols_labels[symbol])

    # Concatenate all symbols (AAPL all data, then MSFT all data, etc.)
    combined_features = torch.cat(combined_features_list, dim=0)
    combined_labels = torch.cat(combined_labels_list, dim=0)

    # NO SHUFFLE - temporal order is critical for time series
    # NO SYMBOL_INDICES - strategies don't care about symbol names
    return combined_features, combined_labels
```

#### High-Level Train Strategy Method (Signature)

```python
@staticmethod
def train_strategy(
    symbols: list[str],
    timeframes: list[str],
    strategy_config: dict[str, Any],
    start_date: str,
    end_date: str,
    model_storage: ModelStorage,
    data_mode: str = "local",
    progress_callback=None,        # ← Orchestrator provides
    cancellation_token=None,       # ← Orchestrator provides
    data_manager: Optional[DataManager] = None,
) -> dict[str, Any]:
    """
    Complete training pipeline from data to trained model.

    Orchestrates all steps: load data → indicators → fuzzy → features →
    labels → train → evaluate → save. Returns standardized result.

    Key: progress_callback and cancellation_token are PASSED THROUGH
    to train_model(), not handled here. This avoids the trap of trying
    to unify progress/cancellation mechanisms.

    Args:
        symbols: Trading symbols to train on
        timeframes: Timeframes for multi-timeframe training
        strategy_config: Complete strategy configuration
        start_date: Start date for training data
        end_date: End date for training data
        model_storage: ModelStorage instance for saving
        data_mode: Data loading mode ('local', 'tail', 'backfill')
        progress_callback: Optional progress callback (orchestrator-provided)
        cancellation_token: Optional cancellation token (orchestrator-provided)
        data_manager: Optional DataManager instance

    Returns:
        Standardized result dict with model_path, metrics, artifacts
    """
    # Implementation orchestrates all pipeline methods
    # See full code in task implementation
```

### APPENDIX B: TASK-2.1 Reference Implementation

#### LocalTrainingOrchestrator Class Structure

```python
class LocalTrainingOrchestrator:
    """Orchestrate local training using TrainingPipeline."""

    def __init__(
        self,
        context: TrainingOperationContext,
        progress_bridge: TrainingProgressBridge,
        cancellation_token: CancellationToken | None,
        model_storage: ModelStorage,
    ):
        self._context = context
        self._bridge = progress_bridge
        self._token = cancellation_token
        self._model_storage = model_storage

    async def run(self) -> dict[str, Any]:
        """Execute training via TrainingPipeline."""
        # 1. Load config
        config = self._load_strategy_config(self._context.strategy_path)

        # 2. Create progress adapter
        progress_callback = self._create_progress_callback()

        # 3. Call pipeline (in thread)
        result = await asyncio.to_thread(
            TrainingPipeline.train_strategy,
            symbols=self._context.symbols,
            timeframes=self._context.timeframes,
            strategy_config=config,
            # ... other params ...
            progress_callback=progress_callback,  # ← Adapter
            cancellation_token=self._token,       # ← Local token
        )

        # 4. Add session metadata
        return {**result, "session_info": {...}}

    def _create_progress_callback(self):
        """Create adapter from TrainingPipeline to ProgressBridge."""
        def callback(epoch, total_epochs, metrics):
            if metrics.get("progress_type") == "batch":
                self._bridge.on_batch(epoch, metrics["batch"], ...)
            elif metrics.get("progress_type") == "epoch":
                self._bridge.on_epoch(epoch, total_epochs, ...)
        return callback
```

### APPENDIX C: TASK-3.1 Reference Implementation

#### HostTrainingOrchestrator with Throttling

```python
class HostTrainingOrchestrator:
    """Orchestrate host service training with throttled progress."""

    # Performance tuning constants
    PROGRESS_UPDATE_FREQUENCY = 10  # Update every 10 batches
    CANCELLATION_CHECK_FREQUENCY = 5  # Check every 5 batches

    def __init__(self, session: TrainingSession, model_storage: ModelStorage):
        self._session = session
        self._model_storage = model_storage

    async def run(self) -> dict[str, Any]:
        """Execute training via TrainingPipeline."""
        # Create throttled progress callback
        progress_callback = self._create_throttled_progress_callback()

        # Create session-based cancellation token
        cancellation_token = SessionCancellationToken(self._session)

        # Call pipeline (direct - no thread wrapper)
        result = TrainingPipeline.train_strategy(
            # ... params ...
            progress_callback=progress_callback,  # ← Throttled
            cancellation_token=cancellation_token, # ← Session-based
        )

        # Add host metadata
        device_info = DeviceManager.get_device_info()
        return {
            **result,
            "resource_usage": {
                "gpu_used": device_info["device_type"] != "cpu",
                "gpu_name": device_info.get("device_name"),
            }
        }

    def _create_throttled_progress_callback(self):
        """Create throttled callback - NO SLEEP OPERATIONS!"""
        def callback(epoch, total_epochs, metrics):
            if metrics.get("progress_type") == "batch":
                batch = metrics["batch"]
                # Throttle: only update every N batches
                if batch % self.PROGRESS_UPDATE_FREQUENCY == 0:
                    self._session.update_progress(epoch, batch, metrics)
                # NO SLEEP! Throttling by skipping, not sleeping
            elif metrics.get("progress_type") == "epoch":
                # Always update on epoch completion
                self._session.update_progress(epoch, 0, metrics)
        return callback


class SessionCancellationToken(CancellationToken):
    """Cancellation token that checks session flag."""

    def __init__(self, session):
        self._session = session

    def is_cancelled(self) -> bool:
        return self._session.stop_requested
```

### APPENDIX D: TASK-3.2 Reference Implementation

#### StrategyTrainer Deprecation

```python
import warnings

class StrategyTrainer:
    """
    Strategy training orchestrator.

    DEPRECATED: This class is deprecated and will be removed in a future version.
    Use LocalTrainingOrchestrator or HostTrainingOrchestrator instead.

    Migration:
    - For local training: Use LocalTrainingOrchestrator
    - For host training: Use HostTrainingOrchestrator
    - Both use TrainingPipeline for work logic
    """

    def __init__(self, models_dir: str = "models"):
        warnings.warn(
            "StrategyTrainer is deprecated and will be removed in a future version. "
            "Use LocalTrainingOrchestrator or HostTrainingOrchestrator instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        # ... rest of init
```

#### PERFORMANCE.md Content Outline

```markdown
# Training Performance Optimizations

## Critical Fix: Sleep Operations Removed

Previous host service had ~14 minutes of artificial delays per 100 epochs.

**Problem**:
- `await asyncio.sleep(0.1)` after every batch (13 min waste)
- `await asyncio.sleep(0.5)` after every epoch (50s waste)

**Solution**:
- Throttle by skipping updates, not sleeping
- Update every 10 batches instead of every batch
- NO SLEEP operations anywhere

**Results**:
- GPU training: 14.5 minutes → 30 seconds (29× faster!)
- Progress overhead: 14 minutes → 8ms (negligible)

## Configuration

```python
# Throttling configuration
PROGRESS_UPDATE_FREQUENCY = 10  # Update every N batches
CANCELLATION_CHECK_FREQUENCY = 5  # Check every N batches
```

## Best Practices

1. NEVER use sleep() in training loops
2. Throttle by skipping, not sleeping
3. Progress updates are cheap (~0.01ms)
4. Cancellation checks are free (~0.001ms)
```

### APPENDIX E: TASK-3.3 Testing Commands

```bash
#!/bin/bash
# Phase 2 E2E Testing Script

echo "=== Test 1: Local Training (Single Symbol) ==="
ktrdr models train \
  --strategy config/strategies/example.yaml \
  --symbols AAPL \
  --timeframes 1d \
  --start-date 2024-01-01 \
  --end-date 2024-12-31

echo "=== Test 2: Local Training (Multi-Symbol) ==="
ktrdr models train \
  --strategy config/strategies/example.yaml \
  --symbols AAPL MSFT GOOGL \
  --timeframes 1d \
  --start-date 2024-01-01 \
  --end-date 2024-12-31

echo "=== Test 3: Host Service Training (Performance) ==="
time USE_TRAINING_HOST_SERVICE=true ktrdr models train \
  --strategy config/strategies/example.yaml \
  --symbols AAPL \
  --timeframes 1d \
  --start-date 2024-01-01 \
  --end-date 2024-12-31

echo "=== Test 6: Model Loading ==="
ktrdr models list
ktrdr models test <model-name> --symbol AAPL --timeframe 1d
```

---

**End of Implementation Plan**
**Ready to begin TASK-2.0**
