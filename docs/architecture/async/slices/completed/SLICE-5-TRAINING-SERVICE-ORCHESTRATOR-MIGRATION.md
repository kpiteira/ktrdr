# SLICE 5: TRAINING SERVICE ORCHESTRATOR MIGRATION – IMPLEMENTATION PLAN (REVISION 2)

This slice follows the architecture defined in `docs/architecture/async/training_service_orchestrator_design.md`. Tasks below mirror the design doc’s components: shared context, progress bridge, local runner, host-session manager, result aggregation, and the final cleanup that retires bespoke async/sync wiring. Each task is structured so a contributor can work end-to-end (with TDD and full-suite validation) and update the single draft PR on branch `feature/training-service-orchestrator`.

**Per-task quality gates:**
- Write or update tests first (unit + integration as applicable).
- Run `uv run make test-unit` and `uv run make quality` before committing.
- Push branch and update the draft PR checklist/progress log after each task.

---

## Task 5.1 – Orchestrator Foundation & Context Layer
**Goal:** Move `TrainingService` onto `ServiceOrchestrator`, introduce shared context helpers, and keep behaviour identical.

1. **TrainingOperationContext** (`ktrdr/api/services/training/context.py`)
   - Dataclass fields exactly as in design doc (`operation_id`, `strategy_path`, symbols/timeframes, date range, training config, analytics flags, adapter mode, optional `session_id`, derived totals, metadata payload).
   - Factory `build_training_context(...)` handles strategy YAML discovery (Docker + host path), validation, metadata assembly, and determines total epochs/batches (when available).
   - **Tests:** `tests/api/services/training/test_context.py` covering success path, missing strategy file, malformed config, metadata content.

2. **Orchestrator-aware TrainingService scaffold**
   - Refactor `TrainingService` to subclass `ServiceOrchestrator[TrainingAdapter]` while keeping external API the same.
   - `start_training` now: build context → call `start_managed_operation(...)` with placeholder executor (`legacy_local_task_adapter` reused temporarily).
   - Retain current behaviour of `/trainings/start` and downstream endpoints; no progress enhancements yet.
   - **Tests:** extend existing FastAPI tests (`tests/api/endpoints/test_training.py`) to assert returned payload, ensure operation created via operations service.

3. **Progress bridge stub** (`ktrdr/api/services/training/progress_bridge.py`)
   - Introduce `TrainingProgressBridge` compatible with `GenericProgressManager` but with stub methods (`on_phase`, `on_epoch`, etc.) that simply log + update minimal progress (0%, 100%). Detailed progress comes in later tasks.
   - **Tests:** `tests/api/services/training/test_progress_bridge.py` verifying start/complete flows and compatibility with `ServiceOrchestrator.update_operation_progress`.

4. **Dependency wiring cleanup**
   - Update `ktrdr/api/endpoints/training.py` to obtain orchestrator instance without manually threading `OperationsService`.
   - Adjust CLI tests or fixtures if they instantiate the old service.

5. **Acceptance:** All new tests pass, `/trainings/start` end-to-end smoke test green, behaviour matches pre-refactor (no progress delta yet).

---

## Task 5.2 – Refactor Local Execution Path (No Feature Re-implementation)
**Goal:** Replace bespoke async/sync code for local training with the orchestrator-native flow while reusing existing training logic. Focus on wiring and progress/cancellation; no algorithmic rewrite.

1. **Progress bridge full implementation**
   - Flesh out `TrainingProgressBridge` to map phases from design doc: data prep → epoch loop → cleanup.
   - Compute percentage using context totals, send `GenericProgressState` updates (with `current_step`, `items_processed`, context metadata).
   - Throttle batch updates (e.g., default every N batches configurable via context).
   - **Tests:** Extend progress bridge tests for percentage math, context fields, throttling.

2. **LocalTrainingRunner (refactor wrapper)**
   - Create `ktrdr/api/services/training/local_runner.py`. This is a thin orchestration layer around existing `StrategyTrainer`/`ModelTrainer`—not a rewrite of training logic.
   - Responsibilities: emit `bridge.on_phase(...)`, call `StrategyTrainer` with injected callbacks, capture outputs (metrics, artefacts), and return result summary skeleton.
   - **Tests:** Mock `StrategyTrainer` to ensure callbacks/cancellation flow works; confirm metrics forwarded correctly.

3. **Inject callbacks into existing training classes**
   - Update `StrategyTrainer` / `ModelTrainer` to accept optional callback hooks for epoch/batch (already partially exist). Ensure they call the provided callback and check `cancellation_token.is_cancelled()` each stride.
   - Avoid adding new computation—just thread the orchestrator-provided hooks.
   - **Tests:** Update `tests/training/test_model_trainer.py` and `test_strategy_trainer.py` to assert callbacks invoked and cancellation raises the expected exception.

4. **TrainingService integration**
   - In orchestrator-managed operation, detect `use_host_service=False` → instantiate `LocalTrainingRunner` with context + cancellation token + progress bridge.
   - Remove the old `_start_training_via_manager_async` coroutine and the manual `asyncio.create_task`/`OperationsService.update_progress` wiring; rely on orchestrator methods instead.
   - Ensure result summary matches previous structure to keep downstream endpoints stable (until Task 5.4).
   - **Integration tests:** asynchronous test starting a local training operation, verifying operations API receives progress events and cancellation halts within two batch strides.

5. **Acceptance:** Local mode now fully goes through orchestrator pipeline, legacy async code paths removed, progress visible in `/operations/{id}`. No regression in training results or endpoints.

---

## Task 5.3 – Host Service Integration & Remote Progress/Cancellation
**Goal:** Align host-based execution with orchestrator infrastructure, including bridging remote progress and updating the host service itself to emit finer updates and honour cancellation promptly.

1. **HostSessionManager** (`ktrdr/api/services/training/host_session.py`)
   - Methods per design doc: `start_session`, `poll_session`, `cancel_session`.
   - Polling uses configurable interval/backoff, forwards snapshots to `TrainingProgressBridge.on_remote_snapshot`.
   - Handles network errors with retries capped; surfaces problems through progress context and final result.
   - **Tests:** Unit tests mocking `TrainingAdapter` responses (normal completion, cancellation, failure).

2. **TrainingProgressBridge remote snapshot support**
   - Implement `on_remote_snapshot(snapshot)` converting host payload (percentage, epoch, gpu stats) into `GenericProgressState` updates with consistent context keys.
   - Ensure remote updates mesh with local progress semantics (same `steps_total`, etc.).
   - **Tests:** Extend bridge tests for remote mode, including GPU metadata.

3. **Update training-host-service**
   - Modify `training-host-service/services/training_service.py` and `/endpoints/training.py` to:
     - Emit granular progress snapshots (epochs/batches/resource usage) accessible via status endpoint, matching the fields consumed by bridge.
     - Honour cancellation: ensure `stop_training` flips session flag quickly, training loop checks `session.stop_requested` each batch/epoch, and status reflects “stopped”.
     - Surface reasons/errors in status payload.
   - **Tests:** Add/adjust host-service tests (e.g., `tests/services/test_training_service.py`) to cover new progress fields and cancellation path.

4. **TrainingService wiring**
   - When `adapter.use_host_service` is true: use `HostSessionManager` in orchestrator operation.
   - Store `session_id` in context and `OperationMetadata.parameters`; inject into progress context for CLI visibility.
   - Ensure final result summary includes remote metrics/checkpoints (placeholder aggregator until Task 5.4).
   - **Integration tests:** Mocked host adapter returning status payloads; verify polling, cancellation, and final summary.

5. **Acceptance:** Host mode now feeds rich progress into operations, cancellation requests propagate to host service, and host service unit/integration tests cover new behaviour.

---

## Task 5.4 – Unified Result Aggregation & Downstream Consumers
**Goal:** Standardise result summaries across modes and adapt API/CLI consumers without re-implementing training logic.

1. **ResultAggregator** (`ktrdr/api/services/training/result_aggregator.py`)
   - Functions: `from_local_run(context, metrics, artefacts, resource_usage)`, `from_host_run(context, payload)`.
   - Ensures consistent keys: `training_metrics`, `validation_metrics`, `test_metrics`, `resource_usage`, `artifacts`, `session_info`.
   - **Tests:** `tests/api/services/training/test_result_aggregator.py` verifying structure for both modes and handling missing analytics.

2. **Integrate aggregator into TrainingService**
   - Local runner returns raw metrics → aggregator builds final summary before `operations_service.complete_operation`.
   - Host session manager uses aggregator on final status payload.

3. **Downstream API adjustments (refactor, not rewrite)**
   - `/trainings/{task_id}/performance`, `/models/save`, `/models/{name}/load` updated to read aggregated fields instead of bespoke result structures.
   - Preserve existing response schemas; only internal data extraction changes.
   - **Tests:** Update endpoint tests to assert compatibility; add regression for analytics-enabled run.

4. **CLI alignment**
   - `ktrdr/cli/async_model_commands.py`: use new progress context fields (epoch info, GPU stats) for display while remaining backward-compatible if fields missing.
   - **Tests:** Adjust CLI integration tests to confirm output includes new context when available.

5. **Acceptance:** Unified result schema consumed everywhere; CLI shows richer info; no behavioural regressions.

---

## Task 5.5 – Cleanup, Legacy Removal, and Documentation
**Goal:** Remove obsolete async/sync scaffolding, polish observability, and document the new architecture and migration steps.

1. **Code cleanup**
   - Delete redundant methods/files replaced by orchestrator: `_start_training_via_manager_async`, manual progress callbacks, direct `OperationsService` calls in training service.
   - Remove unused imports/config tied to old flow.
   - Ensure `TrainingManager` (if still needed) delegates appropriately or refactor per design doc decision (if training manager becomes thin orchestrator wrapper, adjust accordingly).
   - **Tests:** Rely on prior suites; ensure nothing broken after deletions.

2. **Diagnostics enhancements**
   - Expand `TrainingService.health_check` to expose orchestrator config (mode, adapter stats, active session ids) and verify via unit tests.
   - Add logging around cancellation latency, bridge anomalies (e.g., if progress falls back to stub).

3. **Documentation updates**
   - Update `docs/architecture/async/training_service_orchestrator_design.md` with actual implementation notes, component diagrams/screens.
   - Record migration steps and cleanup summary in `docs/architecture/async/tasks/README.md` (link to Slice 5 doc).
   - If host service behaviour changed significantly, note it in `training-host-service/README.md`.

4. **Final QA sweep**
   - Run full `uv run make test-unit`, targeted integration/integration tests, manual smoke tests for both local and host flows (start, progress observation, cancellation, completion).
   - Document results in draft PR, highlight any residual risks or follow-ups.

5. **Acceptance:** Legacy async code retired, documentation matches state, diagnostics improved, full suite green. Draft PR ready for stakeholder review.

---

**Post-slice**
- After stakeholder validation, convert draft PR to “Ready for Review”, summarising each task, their test outputs, and linking updated docs.
