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

### TASK-3.2: Cleanup and Documentation

#### Plan

**Objective**: Mark deprecated code, update documentation to reflect new architecture, and document performance optimizations.

**Why**: Clean up transition artifacts, provide clear migration path, document lessons learned.

**What Changes**:
- Mark `StrategyTrainer` as deprecated:
  - Add `@deprecated` warning
  - Document migration path to orchestrators
  - Keep functional for backward compatibility (Phase 3 will remove)
- Update architecture documentation:
  - Mark TrainingPipeline methods as implemented
  - Document orchestrators
  - Add performance optimization notes
- Create PERFORMANCE.md:
  - Document 29× speedup from removing sleep
  - Explain throttling strategy
  - Provide configuration guidance
- Update README/relevant docs:
  - Reflect new architecture
  - Update training examples

**Architectural Decisions**:
1. **Deprecate, don't delete** → Gives users time to migrate
2. **Document performance wins** → Helps others avoid similar mistakes
3. **Clear migration path** → Users know how to update their code

**Risks & Mitigations**:
- **Risk**: Users miss deprecation warning
  - **Mitigation**: Warning logged on every use
- **Risk**: Documentation gets out of sync
  - **Mitigation**: Update all references in single commit

**Dependencies**: TASK-2.1 and TASK-3.1 (orchestrators must exist for migration)

**Estimated Effort**: 0.5 days

#### Acceptance Criteria

**Code Deprecation**:
- [ ] StrategyTrainer marked @deprecated
  - [ ] warnings.warn() called in __init__
  - [ ] Docstring updated with migration guide
  - [ ] Still functional (backward compatible)
- [ ] No broken references in codebase
  - [ ] All imports still work
  - [ ] Deprecation warning appears in tests

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

### TASK-3.3: Manual E2E Validation (Karl Leads)

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
