---
design: docs/designs/backtesting-pipeline-refactor/DESIGN.md
architecture: docs/designs/backtesting-pipeline-refactor/ARCHITECTURE.md
---

# M4: Worker Consolidation + Cleanup

## Goal

Consolidate the duplicated fresh/resume code in `BacktestWorker`. Remove dead code. Add documentation to preserved-but-decoupled components (`DecisionOrchestrator`, `DecisionEngine`, `BaseNeuralModel`, `ModelStorage`). Validate with a full research cycle.

## Tasks

### Task 4.1: Consolidate worker fresh/resume code

**File(s):** `ktrdr/backtesting/backtest_worker.py`
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
`_execute_backtest_work()` (275 lines) and `_execute_resumed_backtest_work()` (190 lines) share ~80% of their code: operation creation, bridge setup, checkpoint infrastructure, engine creation, result handling, cancellation handling. Extract the shared logic into a single `_run_backtest()` method.

**Implementation Notes:**

Shared infrastructure to extract:
1. **Bridge creation**: Lines 308-320 (fresh) and 558-570 (resume) — identical
2. **Checkpoint setup**: Lines 329-395 (fresh) and 573-607 (resume) — almost identical, resume uses `create_checkpoint_callback()` shared method
3. **Engine creation + run**: Lines 397-428 (fresh) and 609-645 (resume) — similar, resume adds `resume_from_context()` call and `resume_start_bar` parameter
4. **Result handling**: Lines 430-453 (fresh) and 647-671 (resume) — identical
5. **Cancellation handling**: Lines 455-518 (fresh) and 673-709 (resume) — fresh has inline checkpoint save, resume uses shared `save_cancellation_checkpoint()`

Proposed structure:
```python
async def _execute_backtest_work(self, operation_id, request):
    """Fresh backtest — prepare config and delegate."""
    # Parse request → BacktestConfig + original_request dict
    config = self._build_config(request)
    original_request = self._build_original_request(request)
    await self._operations_service.create_operation(operation_id, ...)
    await self._operations_service.start_operation(operation_id, ...)
    await self._run_backtest(operation_id, config, original_request)

async def _execute_resumed_backtest_work(self, operation_id, context):
    """Resumed backtest — restore context and delegate."""
    config = self._build_config_from_context(context)
    original_request = context.original_request
    await self.adopt_and_start_operation(operation_id)
    await self._run_backtest(operation_id, config, original_request, resume_context=context)

async def _run_backtest(self, operation_id, config, original_request, resume_context=None):
    """Shared backtest execution with bridge, checkpoints, and error handling."""
    bridge = self._create_bridge(operation_id, config)
    checkpoint_service, checkpoint_callback, last_state = self._setup_checkpoints(operation_id, original_request)

    try:
        engine = BacktestingEngine(config=config)
        if resume_context:
            engine.resume_from_context(resume_context)

        cancellation_token = self._operations_service.get_cancellation_token(operation_id)
        results = await asyncio.to_thread(
            engine.run,
            bridge=bridge,
            cancellation_token=cancellation_token,
            checkpoint_callback=checkpoint_callback,
            resume_start_bar=resume_context.start_bar if resume_context else None,
        )

        await self._complete_backtest(operation_id, results, checkpoint_service)
    except CancellationError:
        await self._handle_cancellation(operation_id, bridge, checkpoint_service, last_state, ...)
    except Exception as e:
        await self._operations_service.fail_operation(operation_id, str(e))
        raise
```

- The fresh path's inline `checkpoint_callback` should be migrated to use the same `create_checkpoint_callback()` shared method that resume already uses
- The fresh path's inline cancellation checkpoint save should use `save_cancellation_checkpoint()` like resume does
- `asyncio.CancelledError` and `CancellationError` handlers can be combined since they do the same thing

**Testing Requirements:**
- [ ] Fresh backtest via `_execute_backtest_work` still works (mock engine, verify operation lifecycle)
- [ ] Resumed backtest via `_execute_resumed_backtest_work` still works
- [ ] Existing `test_backtest_worker_checkpoint.py` tests pass
- [ ] Existing `test_backtest_worker_resume.py` tests pass
- [ ] Checkpoint callback correctly saves on interval

**Acceptance Criteria:**
- [ ] No duplicated error handling blocks
- [ ] Shared `_run_backtest()` (or equivalent) handles both fresh and resume
- [ ] Both paths use the same checkpoint infrastructure
- [ ] All worker tests pass

---

### Task 4.2: Remove dead code from backtesting module

**File(s):** `ktrdr/backtesting/engine.py`, `ktrdr/backtesting/__init__.py`
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Remove dead code that accumulated in the backtesting module. After M3, several things are no longer needed.

**Implementation Notes:**

Items to remove or clean:
1. **`model_loader.py`** — if not already deleted in M1 (depends on whether DecisionOrchestrator was the only user). After M3, no code imports it. Delete the file.
2. **`__init__.py` exports** — remove `ModelLoader` from exports if present. Add `ModelBundle` and `DecisionFunction` to exports.
3. **`engine.py` leftovers** — after M3 rewrite, verify no commented-out code remains:
   - Remove `self.progress_callback` (legacy, replaced by ProgressBridge)
   - Remove `_print_summary()` method (verbose output, not needed in worker context)
   - Remove `verbose` config handling throughout
4. **`backtesting_service.py`** — after M1 moved static utilities, verify the delegating stubs are minimal. If no external code calls `BacktestingService.is_v3_model()` directly (only through the new `ModelBundle` path), the stubs can be simplified or removed.

**Testing Requirements:**
- [ ] No import errors after removals
- [ ] `from ktrdr.backtesting import ModelBundle, DecisionFunction` works
- [ ] All unit tests pass

**Acceptance Criteria:**
- [ ] `model_loader.py` deleted
- [ ] No commented-out code blocks in engine.py
- [ ] Module exports updated
- [ ] All tests pass

---

### Task 4.3: Document preserved-but-decoupled components

**File(s):** `ktrdr/decision/orchestrator.py`, `ktrdr/decision/engine.py`, `ktrdr/neural/models/base_model.py`, `ktrdr/training/model_storage.py`
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Add clear documentation to components that are preserved in the codebase but no longer used by the backtesting pipeline. Without this documentation, future developers will wonder why two decision-making systems exist and may accidentally re-couple them.

**Implementation Notes:**

Per the ARCHITECTURE.md documentation requirements table:

**`ktrdr/decision/orchestrator.py`** — Add module-level docstring:
```python
"""Decision orchestrator for paper and live trading modes.

NOTE: As of the backtesting pipeline refactor, this module is NOT used by
the backtesting pipeline. Backtesting uses BacktestingEngine → ModelBundle +
DecisionFunction + FeatureCache directly, bypassing this orchestrator.

This orchestrator remains for future paper/live trading modes where:
- Real-time feature computation is needed (_compute_features_realtime)
- Multi-symbol model management is needed (_load_model_for_symbol)
- Orchestrator-level risk overrides are needed (_apply_orchestrator_logic)

The refactor was motivated by:
- Triple model loading (3 separate torch.load calls per backtest init)
- Triple position tracking (PositionManager, DecisionEngine, PositionState)
- Circular dependency (decision → backtesting_service for static utilities)
See docs/designs/backtesting-pipeline-refactor/DESIGN.md for full context.
"""
```

**`ktrdr/decision/engine.py`** — Add module-level docstring:
```python
"""Decision engine for paper and live trading modes.

NOTE: As of the backtesting pipeline refactor, this module is NOT used by
the backtesting pipeline. Backtesting uses DecisionFunction (stateless,
position passed as input) instead of this stateful engine.

This engine remains for future paper/live trading modes where:
- Stateful position tracking per engine instance is desired
- The prepare_features → FuzzyNeuralProcessor pipeline is needed

The backtesting refactor replaced this with DecisionFunction because:
- Position-as-input eliminates sync bugs between PositionManager and engine
- Stateless design simplifies checkpoint/resume
See docs/designs/backtesting-pipeline-refactor/ARCHITECTURE.md for details.
"""
```

**`ktrdr/neural/models/base_model.py`** — Add comment on `load_model()`:
```python
def load_model(self, path: str):
    """Load model from disk.

    NOTE: The backtesting pipeline does NOT use this method. Backtesting
    loads models via ModelBundle.load() which uses torch.load() with
    map_location="cpu" and weights_only=True directly. This method is
    used by the training pipeline and future paper/live trading.
    """
```

**`ktrdr/training/model_storage.py`** — Add comment on `load_model()`:
```python
# NOTE: Backtesting loads models via ModelBundle.load() (state dict only,
# map_location="cpu"). This method is used by training pipeline internals
# and future paper/live trading modes.
```

**Testing Requirements:**
- [ ] No functional changes — documentation only
- [ ] All tests pass (sanity check)

**Acceptance Criteria:**
- [ ] All four files have clear documentation explaining the decoupling
- [ ] Documentation references the design doc for full context
- [ ] No functional code changes in this task
- [ ] All tests pass

---

### Task 4.4: M4 Validation — full E2E research cycle (the original bug)

**File(s):** Tests, Docker containers
**Type:** VALIDATION
**Estimated time:** 2 hours

**Description:**
Validate the full refactored backtesting pipeline with an end-to-end research cycle. **This is the test that motivated the entire refactor.** A research agent designs a strategy, trains it on MPS (Apple Silicon), and backtests it on a CPU-only Docker worker. The original bug was that this backtest failed with `torch.UntypedStorage(): Storage device not recognized: mps`. If this test passes, the refactor is proven.

**Validation Steps:**
1. Run `uv run pytest tests/unit/backtesting/ -x -q` — all pass
2. Run `make quality` — clean
3. Restart workers to pick up code changes:
   ```bash
   docker compose -f docker-compose.sandbox.yml restart backtest-worker-1
   ```
4. Verify worker starts cleanly:
   ```bash
   docker compose -f docker-compose.sandbox.yml logs --tail=20 backtest-worker-1
   ```
   Look for: successful startup, worker registration, no import errors
5. Run a CLI backtest to validate the standalone path:
   ```bash
   uv run ktrdr backtest run mean_reversion_momentum_v1 EURUSD 1h \
     --start-date 2024-03-01 --end-date 2024-04-01
   ```
   Verify: completes successfully, produces trade results, model loaded on CPU
6. Checkpoint resume test (if feasible):
   - Start a long backtest
   - Cancel it mid-way
   - Resume and verify it completes
   - Compare final results — PnL should match a full uninterrupted run
7. **THE ULTIMATE E2E TEST — the original bug reproduction:**
   ```bash
   uv run ktrdr research -m haiku -f "Design a multi-timeframe strategy using RSI and Bollinger Bands on 1h and 5m data for EURUSD"
   ```
   This triggers the full agent cycle: design → train (MPS) → backtest (CPU Docker) → assess.
   - Training must complete successfully (model saved with MPS tensors)
   - **Backtesting must complete** — this is where the original `mps` device error occurred
   - Assessment must produce valid results
   - The research operation reaches COMPLETED status
8. Grep the codebase for any remaining orchestrator imports in backtesting:
   ```bash
   grep -r "DecisionOrchestrator" ktrdr/backtesting/
   grep -r "from.*decision.*orchestrator" ktrdr/backtesting/
   grep -r "self.orchestrator" ktrdr/backtesting/
   ```
   All should return zero results.

**Acceptance Criteria:**
- [ ] All unit tests pass
- [ ] Quality gates clean
- [ ] Worker starts without errors after code update
- [ ] CLI backtest completes successfully
- [ ] No `DecisionOrchestrator` references in backtesting module
- [ ] Model loaded on CPU in Docker container (the original MPS bug is fixed)
- [ ] **Full research cycle completes: agent designs, trains (MPS), backtests (CPU Docker), assesses — the exact scenario that originally failed**
