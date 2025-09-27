# Training Service Orchestrator Migration

## Background
- Training today mixes bespoke async wiring with direct `OperationsService` usage, custom `asyncio.create_task`, and synchronous PyTorch loops. Host-service routing lives in `TrainingManager`, while API endpoints and CLI clients manually juggle progress updates and cancellation semantics.
- The new async foundation (`ServiceOrchestrator`, `GenericProgressManager`, unified cancellation) already powers the Dummy service and central operations endpoints. Training is the last major service still bypassing it, which prevents consistent progress UX, complicates cancellation, and duplicates infra code.
- Local training runs entirely inside the API container via `StrategyTrainer`/`ModelTrainer`; GPU-accelerated training is proxied to `training-host-service` through `TrainingAdapter` → HTTPX. Both paths must surface fine-grained progress (epochs/batches) and honor cancellations without sacrificing throughput.

## Goals
- Treat training as a first-class `ServiceOrchestrator` client: API endpoints should only invoke TrainingService methods and return operation handles.
- Preserve feature parity (strategy validation, host/local routing, analytics outputs, model storage) while simplifying threading/async logic.
- Provide smooth, high-resolution progress that the CLI can render ( epochs, batches, ETA ), whether work runs locally or remotely.
- Ensure cancellation is propagated promptly to PyTorch loops or the host service, with predictable teardown and status updates.
- Reduce coupling between the API layer and `OperationsService`; consolidate error handling, retries, and diagnostics under the orchestrator.

## Architecture Overview

### Sequence (happy path)
1. CLI issues `POST /trainings/start`; FastAPI endpoint resolves singleton `TrainingService`.
2. `TrainingService.start_training()` validates config, then calls `self.start_managed_operation(...)`, passing an async `operation_func` plus metadata/total steps.
3. `ServiceOrchestrator` creates an `OperationInfo`, initializes a `GenericProgressManager`, and spawns `_managed_operation_wrapper` inside a dedicated worker thread.
4. Inside the wrapper, `TrainingService._execute_training_operation()` builds a `TrainingOperationContext`, acquires the unified cancellation token, and decides between local or host execution.
5. Execution path emits structured progress events → `TrainingProgressBridge`, which updates the shared `GenericProgressManager`. Main loop tasks translate those into `OperationProgress` rows via the existing operations service.
6. On completion (or cancellation/error) the wrapper writes final status/result summary back to `OperationsService`, which drives the CLI display and post-run analytics.

## Component Responsibilities
- **TrainingService(ServiceOrchestrator[TrainingAdapter])**
  - Owns env detection (`USE_TRAINING_HOST_SERVICE`), adapter lifecycle, and orchestrator hooks.
  - Exposes high-level methods (`start_training`, `cancel_training_session`, `get_model_performance`, etc.) that rely on operations registry rather than manual task tracking.
- **TrainingOperationContext** (dataclass)
  - Captures operation_id, resolved strategy config/path, symbol/timeframe lists, training hyperparameters, analytics flags, start/end ranges, host/local mode, and convenience handles (progress bridge, cancellation token).
- **TrainingProgressBridge**
  - Converts domain events into `GenericProgressState` updates.
  - Tracks totals (epochs, batches, bars) and builds human-readable messages (e.g., `Epoch 3/50 · Batch 120/640`), ensures throttling (e.g., batches every N iterations), and adds contextual metadata for CLI (current symbol, timeframe, host session id when relevant).
- **LocalTrainingRunner**
  - Wraps `StrategyTrainer`/`ModelTrainer`. Injects a cancellation-aware progress callback that checks `token.is_cancelled()` and raises `CancellationError` to unwind quickly. Collects metrics, analytics artefacts, and model paths for the result summary.
- **HostSessionManager**
  - Starts remote training via `TrainingAdapter.train_multi_symbol_strategy`, stores `session_id`, and spawns a polling coroutine that:
    - Periodically calls `get_training_status(session_id)`.
    - Feeds progress snapshots to the `TrainingProgressBridge`.
    - Handles cancellation by calling `stop_training(session_id)` and awaiting confirmation.
    - Bridges remote metrics/result payloads into the final summary.
- **ResultAggregator**
  - Normalizes outputs (train/test metrics, analytics files, checkpoints) so `OperationsService.result_summary` has consistent keys consumed by `/trainings/{task_id}/performance` and model save/load routes.

## Execution Modes

### Local (in-container)
- Validate and load strategy YAML (docker + host path fallback) before creating the operation; store derived metadata (epochs, model type) in `OperationMetadata.parameters`.
- Start managed operation with `total_steps = epochs` (fallback to 1 if unknown). Optionally set `items_total` to total batches or bars when known.
- Inside `LocalTrainingRunner`:
  - Pre-flight data fetch or preprocessing can emit progress “steps” (e.g., data loading, indicator calc) via incremental step numbers before entering epochs.
  - PyTorch loop leverages injected callback to update batches (coalesced) and check cancellation every batch.
  - Upon completion, assemble metrics, confusion stats, file paths (model, analytics) for result summary. Persist model via `ModelStorage` as today.

### Host Service (GPU)
- After starting managed operation, call adapter `train_multi_symbol_strategy`. Response contains `session_id`; update progress to indicate remote execution startup and store `session_id` inside both `TrainingOperationContext` and operation metadata.
- Launch polling loop (interval configurable, e.g., 2–5s) that:
  - Fetches status, converts remote `progress_percent`/epoch data into local progress states.
  - Surfaces GPU utilization metrics as part of `context` for `GenericProgressState`, so CLI can optionally display them.
  - Terminates when status ∈ {`completed`, `failed`, `stopped`}.
- On cancellation request, the polling loop triggers `stop_training(session_id)` and waits for status change before completing with a cancellation result.
- Final summary merges host-reported metrics, checkpoints, and optional download links into operation result.

## Progress & Cancellation
- `TrainingProgressBridge` exposes simple hooks: `on_phase(name)`, `on_epoch(epoch, total, metrics)`, `on_batch(epoch, batch, total_batches, metrics)`, `on_remote_snapshot(snapshot_dict)`.
- Bridge uses `GenericProgressManager.update_progress()` with:
  - `step` = epoch index (1-based), `total_steps` = total epochs.
  - `items_processed` = total batches or bars processed so far; `items_total` if known.
  - `context` includes `current_item` (e.g., `Batch 120/640`), `epoch_metrics`, `host_session_id`, GPU stats, warnings.
  - Derived percentage = epoch progress + intra-epoch batch fraction.
- Cancellation token is read at the top of each bridge call; if cancelled, raise `CancellationError`. For remote mode, bridge instructs `HostSessionManager` to fire the stop call.
- Errors bubble through `ServiceOrchestrator` which already handles progress finalization and marks the operation failed with message in `OperationProgress.context['error']`.

## Operations & Data Contracts
- **OperationMetadata.parameters**
  - `{ strategy_name, symbols, timeframes, epochs, use_host_service, session_id?, analytics_enabled, training_mode (local|host), gpu_required? }`.
- **OperationProgress**
  - `percentage`: derived float.
  - `current_step`: human-readable string (phase/epoch summary).
  - `steps_completed/steps_total`: epoch tracking (or pre-training phases counted as steps 0..N).
  - `items_processed/items_total`: batches/bars processed when available.
  - `current_item`: batch detail or high-level status (e.g., `Polling host session...`).
  - `context`: JSON-safe dict with `epoch_metrics`, `host_status`, `gpu_usage`, `warnings`, `phase`.
- **Result Summary Format** (shared by both execution modes):
  - `training_metrics` (final losses/accuracies, epochs_completed, training_time_minutes, early_stopped).
  - `validation_metrics` / `test_metrics` (mirrors current API shape).
  - `resource_usage` (GPU/system stats snapshot if available).
  - `artifacts` (model_path, analytics_dir, checkpoints, session_logs?).
  - `session_info` (host session id, start/end timestamps, cancellation_reason).

## API and CLI Touchpoints
- `ktrdr/api/endpoints/training.py` simplifies to thin orchestration: instantiate service (singleton like Dummy), call `service.start_training(...)`, return its dict response.
- `/operations` endpoints remain untouched—they already surface the progress and status produced by the orchestrator.
- CLI (`async_model_commands.py`) keeps polling `OperationsService`; richer `context` fields allow optional enhancements (GPU stats, per-epoch metrics) without breaking compatibility.
- Cancellation flows through `/operations/{id}/cancel`, which now signals the same unified cancellation coordinator the training service reads.

## Migration Plan
1. **Foundation refactor**
   - Convert `TrainingService` into `ServiceOrchestrator` subclass; inject adapter, remove direct `OperationsService` dependency from constructor; wire helpers (context builder, progress bridge, local/host runners).
   - Update API endpoint to use new interface; adjust dependency injection accordingly.
2. **Local execution integration**
   - Implement `TrainingProgressBridge` + local runner; thread cancellation checks into `StrategyTrainer`/`ModelTrainer` via injected callbacks; ensure result summary parity.
   - Verify CLI progress with local run, including cancellation mid-epoch.
3. **Host-service execution**
   - Add `HostSessionManager` polling & cancellation logic; enrich metadata and progress contexts with remote session info.
   - Handle remote completion/failure payloads and align result summary schema with local mode.
4. **Ancillary updates**
   - Adapt `get_model_performance`, `save_trained_model`, and related endpoints/tests to new `OperationInfo` layout (e.g., ensure they read updated result summary keys).
   - Update documentation & diagnostics (`/health`, orchestrator config introspection) to report new structure.
5. **Cleanup**
   - Retire obsolete training-specific async helpers; consolidate duplicated logging/error handling under orchestrator patterns.

## Testing Strategy
- Unit tests for `TrainingProgressBridge` covering local epoch/batch updates, throttling, cancellation detection, and remote snapshot conversion.
- Async integration tests that simulate:
  - Local training (mocked `StrategyTrainer`) verifying progress timeline, cancellation response time, and final summary structure.
  - Host service polling (mock `TrainingAdapter` responses) ensuring polling cadence, cancellation triggers remote stop, and errors propagate.
- Regression tests for API endpoints (`/trainings/start`, `/trainings/{id}/performance`, `/models/save`) validating response schemas and error handling.
- CLI smoke tests (Vitest or Typer integration) to ensure progress rendering remains stable with enriched context.

## Risks & Open Questions
- **PyTorch loop responsiveness**: ensuring cancellation checks (likely via callback every batch) do not degrade throughput. May need configurable batch stride for checks.
- **Host polling load**: choose interval/backoff that balances responsiveness with HTTP overhead; consider server-sent events in future.
- **Result schema compatibility**: confirm downstream consumers (analytics, model registry) tolerate unified summary fields; document any new keys.
- **Analytics artefacts**: decide whether to push additional progress info (e.g., `training_analytics` paths) directly into progress context or defer to result summary.
- **Threading nuances**: verify that running synchronous training inside orchestrator thread does not starve progress callbacks; if needed, offload heavy phases to `asyncio.to_thread` within the worker loop.

