# Training Service Unified Architecture - Implementation Plan

**Parent Documents**:
- [01-analysis.md](./01-analysis.md)
- [02-requirements.md](./02-requirements.md)
- [03-architecture.md](./03-architecture.md)

**Status**: Ready for Implementation
**Version**: 1.0
**Date**: 2025-01-05

---

## Overview

This document breaks down the implementation of the unified training architecture into discrete, testable tasks following **Test-Driven Development (TDD)** principles.

**Key Architecture Components**:
- `TrainingExecutor`: Environment-agnostic training logic (consolidates duplicates)
- `ExecutionModeSelector`: Intelligent mode selection with health checks and fallback
- Result callback mechanism: Host service posts results back to backend
- Compression and retry: Robust model transfer with gzip compression

**Implementation Philosophy**:
- **TDD-first**: Write tests before implementation
- **Incremental**: Small, mergeable changes
- **Quality gates**: `make test-unit` + `make quality` before every commit
- **Non-breaking**: Preserve existing functionality until cutover

---

## Branching Strategy

We'll use a **single long-lived feature branch** with **direct commits** for all work.

### Setup (One Time)

```bash
# Start from main
git checkout main
git pull origin main

# Create and push feature branch
git checkout -b feat/unified-training-architecture
git push -u origin feat/unified-training-architecture
```

### Daily Workflow

**For every task** (simple approach):

```bash
# 1. Make sure you're on feature branch
git checkout feat/unified-training-architecture
git pull origin feat/unified-training-architecture

# 2. Work on task (following TDD)
#    - Write tests
#    - Implement code
#    - Run make test-unit && make quality

# 3. Commit directly to feature branch
git add <files>
git commit -m "test: add tests for TrainingExecutor device detection"

git add <files>
git commit -m "feat(training): implement device detection in TrainingExecutor

- Checks MPS, CUDA, falls back to CPU
- Logs selected device
- Configures model.to(device)

Refs: #123"

# 4. Push regularly (at least daily)
git push origin feat/unified-training-architecture
```

### Branch Lifecycle

```
main (protected)
 └── feat/unified-training-architecture (all work happens here)
      ├── commit: test: add executor tests
      ├── commit: feat: implement executor
      ├── commit: test: add selector tests
      ├── commit: feat: implement selector
      └── ... (all tasks as sequential commits)

When complete:
  → Pull Request: feat/unified-training-architecture → main
  → Review, approve, squash & merge
  → Delete feat/unified-training-architecture
```

### Key Principles

1. **One branch**: All work on `feat/unified-training-architecture`
2. **Small commits**: Commit after each TDD cycle (test, then implementation)
3. **Push frequently**: At least once per day, ideally after each task
4. **Quality gates**: MUST pass before every commit
5. **No sub-branches**: Keep it simple, linear history

### When to Commit

```bash
# Good commit rhythm (example from Phase 1, Task 1.1):

git commit -m "test: add TrainingExecutor initialization tests"
# ~5-10 minutes later
git commit -m "feat(training): implement TrainingExecutor initialization"

git commit -m "test: add device detection tests (CPU, MPS, CUDA)"
# ~10-15 minutes later
git commit -m "feat(training): implement device detection logic"

git commit -m "test: add data loading tests"
# ~30-45 minutes later
git commit -m "feat(training): implement data loading step"

# ... continue for each step
```

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**: `test`, `feat`, `fix`, `refactor`, `docs`, `chore`
**Scope**: `training`, `api`, `host-service`, `tests`
**Subject**: Imperative mood, lowercase, no period

**Examples**:
```bash
git commit -m "test: add ExecutionModeSelector health check tests"

git commit -m "feat(training): implement mode selection with fallback

- Health check host service with 2s timeout
- Fallback to local when host unavailable
- Raise error when GPU required but unavailable

Closes #123"

git commit -m "fix(host-service): correct gzip compression byte encoding

Issue was using wrong encoding after compression.
Now properly base64-encodes compressed bytes.

Fixes #456"
```

### What NOT to Do

❌ **Don't create sub-branches** - adds complexity
❌ **Don't batch commits** - commit after each TDD cycle
❌ **Don't commit broken code** - quality gates must pass
❌ **Don't squash locally** - keep clean history, squash on merge to main

---

## Quality Gates (MANDATORY)

**Before EVERY commit**:

```bash
# 1. Run unit tests (must complete in <2s)
make test-unit

# 2. Run quality checks (lint, format, typecheck)
make quality

# 3. If both pass, commit
git add .
git commit -m "feat(training): descriptive message

- Specific change 1
- Specific change 2

🤖 Generated with Claude Code"
```

**If tests fail**: Fix before committing (no exceptions)
**If quality fails**: Fix formatting/typing before committing

---

## Test-Driven Development Approach

### TDD Cycle (Red-Green-Refactor)

For EVERY task:

1. **RED**: Write failing test first
   ```bash
   # Create test file
   touch tests/unit/training/test_new_feature.py
   # Write test that fails
   make test-unit  # Should fail
   ```

2. **GREEN**: Write minimal code to pass
   ```bash
   # Implement feature
   # Run tests until they pass
   make test-unit  # Should pass
   ```

3. **REFACTOR**: Clean up code
   ```bash
   # Improve implementation
   # Ensure tests still pass
   make test-unit  # Should still pass
   make quality   # Should pass
   ```

4. **COMMIT**: Save progress
   ```bash
   git add .
   git commit -m "test: add test for feature X"
   git add .
   git commit -m "feat: implement feature X"
   ```

### Testing Standards

**Unit Tests**:
- **Speed**: Must complete in <2 seconds total
- **Coverage**: Aim for >80% on new code
- **Isolation**: Mock external dependencies (HTTP, file system, database)
- **Clarity**: Descriptive test names, clear assertions

**Integration Tests** (when needed):
- Test component interactions
- Use real dependencies where practical
- Mark with `@pytest.mark.integration`

---

## Phase 1: Foundation Layer (TDD-First)

**Objective**: Build core components with zero impact on existing code

**Duration**: 3-4 days

**Branch**: `feature/unified-training-architecture`

---

### TASK-1.1: Create TrainingExecutor Foundation

**Objective**: Extract and consolidate training logic into environment-agnostic executor

**Branch**: `feat/unified-training-architecture`

**Files**:
- `ktrdr/training/executor.py` (NEW)
- `tests/unit/training/test_executor.py` (NEW)

**TDD Steps**:

1. **Write test for initialization** (RED)
   ```python
   def test_executor_initialization():
       executor = TrainingExecutor(config={...})
       assert executor.config is not None
       assert executor.model_storage is not None
   ```

2. **Implement initialization** (GREEN)
   ```python
   class TrainingExecutor:
       def __init__(self, config, progress_callback=None):
           self.config = config
           self.model_storage = ModelStorage()
   ```

3. **Write test for device detection** (RED)
   ```python
   def test_device_detection_cpu_only(monkeypatch):
       # Mock PyTorch backends to return False
       executor = TrainingExecutor(config={...})
       assert executor.device == "cpu"

   def test_device_detection_mps_available(monkeypatch):
       # Mock MPS available
       executor = TrainingExecutor(config={...})
       assert executor.device == "mps"
   ```

4. **Implement device detection** (GREEN)
   ```python
   def _detect_device(self):
       if torch.backends.mps.is_available():
           return "mps"
       elif torch.cuda.is_available():
           return "cuda"
       return "cpu"
   ```

5. **Continue TDD for each pipeline step**:
   - Data loading
   - Indicator calculation
   - Fuzzy generation
   - Feature engineering
   - Label generation
   - Model training
   - Evaluation
   - Model saving

**Key Methods** (implement via TDD):
```python
class TrainingExecutor:
    def __init__(self, config, progress_callback=None, cancellation_token=None)
    def execute(self, symbols, timeframes, start_date, end_date, **kwargs) -> dict

    # Private methods (test indirectly through execute)
    def _detect_device(self) -> str
    def _load_data(self, ...) -> dict
    def _calculate_indicators(self, ...) -> dict
    def _generate_fuzzy(self, ...) -> dict
    def _engineer_features(self, ...) -> tuple
    def _generate_labels(self, ...) -> np.ndarray
    def _split_data(self, ...) -> tuple
    def _create_model(self, ...) -> torch.nn.Module
    def _train_model(self, ...) -> dict
    def _evaluate_model(self, ...) -> dict
    def _calculate_importance(self, ...) -> dict
    def _save_model(self, ...) -> str
    def _build_results(self, ...) -> dict
```

**What to Extract**:
- Source: `ktrdr/training/train_strategy.py` (StrategyTrainer methods)
- Also reference: `training-host-service/services/training_service.py`
- Consolidate: Take best implementation from each

**Acceptance Criteria**:
- [ ] TrainingExecutor detects hardware (CPU/MPS/CUDA) correctly
- [ ] Can execute full training pipeline end-to-end
- [ ] Progress callback invoked at each step
- [ ] Cancellation token checked periodically
- [ ] Model saved via ModelStorage
- [ ] Returns standardized result dict
- [ ] **Zero knowledge of execution environment** (local vs host)
- [ ] All tests pass (`make test-unit`)
- [ ] Code quality passes (`make quality`)
- [ ] Test coverage >80%

**Commit Strategy**:
```bash
# Commit after each TDD cycle
git commit -m "test: add device detection tests"
git commit -m "feat(training): implement device detection"
git commit -m "test: add data loading tests"
git commit -m "feat(training): implement data loading"
# ... etc for each step
```

**Estimated**: 2 days

---

### TASK-1.2: Create ExecutionModeSelector

**Objective**: Intelligent mode selection with health checks and fallback

**Branch**: `feat/unified-training-architecture`

**Files**:
- `ktrdr/training/execution_mode_selector.py` (NEW)
- `tests/unit/training/test_execution_mode_selector.py` (NEW)

**TDD Steps**:

1. **Test: Default mode from env var** (RED)
   ```python
   def test_default_mode_from_env(monkeypatch):
       monkeypatch.setenv("TRAINING_DEFAULT_MODE", "local")
       selector = ExecutionModeSelector()
       assert selector.default_mode == "local"
   ```

2. **Implement: Read env var** (GREEN)
   ```python
   def __init__(self):
       self.default_mode = os.getenv("TRAINING_DEFAULT_MODE", "auto")
   ```

3. **Test: Health check success** (RED)
   ```python
   @pytest.mark.asyncio
   async def test_health_check_success(mock_http_client):
       mock_http_client.get.return_value.status_code = 200
       selector = ExecutionModeSelector()
       assert await selector._is_host_available() == True
   ```

4. **Implement: Health check** (GREEN)
   ```python
   async def _is_host_available(self):
       try:
           async with httpx.AsyncClient() as client:
               response = await client.get(f"{self.host_url}/health", timeout=2.0)
               return response.status_code == 200
       except:
           return False
   ```

5. **Test: Mode selection logic** (RED)
   ```python
   @pytest.mark.asyncio
   async def test_select_local_when_requested():
       selector = ExecutionModeSelector()
       mode = await selector.select_mode(requested_mode="local")
       assert mode == "local"

   @pytest.mark.asyncio
   async def test_select_host_with_fallback(mock_health_check):
       mock_health_check.return_value = False  # Host unavailable
       selector = ExecutionModeSelector()
       mode = await selector.select_mode(requested_mode="host", require_gpu=False)
       assert mode == "local"  # Fallback

   @pytest.mark.asyncio
   async def test_error_when_gpu_required_host_unavailable(mock_health_check):
       mock_health_check.return_value = False
       selector = ExecutionModeSelector()
       with pytest.raises(ExecutionModeError):
           await selector.select_mode(requested_mode="host", require_gpu=True)
   ```

6. **Implement: Selection logic** (GREEN)

**Key Methods**:
```python
class ExecutionModeSelector:
    def __init__(self, default_mode="auto")
    async def select_mode(self, requested_mode=None, require_gpu=False) -> str
    async def _is_host_available(self) -> bool
    def set_default_mode(self, mode: str) -> None
```

**Acceptance Criteria**:
- [ ] Reads default mode from TRAINING_DEFAULT_MODE env var
- [ ] Health checks host service with 2s timeout
- [ ] Selects "local" when requested
- [ ] Selects "host" when requested and available
- [ ] Falls back to "local" when host unavailable (if GPU not required)
- [ ] Raises error when GPU required but host unavailable
- [ ] Auto mode selects based on requirements and availability
- [ ] All tests pass (`make test-unit`)
- [ ] Code quality passes (`make quality`)
- [ ] Test coverage >85%

**Commit Strategy**:
```bash
git commit -m "test: add execution mode selector tests"
git commit -m "feat(training): implement execution mode selector"
```

**Estimated**: 1 day

---

### TASK-1.3: Add Result Callback Endpoint

**Objective**: Backend endpoint to receive training results from host service

**Branch**: `feat/unified-training-architecture`

**Files**:
- `ktrdr/api/endpoints/training.py` (MODIFY - add endpoint)
- `ktrdr/api/services/training_service.py` (MODIFY - add method)
- `tests/unit/api/test_training_endpoints.py` (MODIFY - add tests)

**TDD Steps**:

1. **Test: Endpoint receives results** (RED)
   ```python
   @pytest.mark.asyncio
   async def test_receive_results_endpoint(test_client):
       payload = {
           "session_id": "test-session",
           "model_state_dict_b64": "base64-encoded-data",
           "compression": "gzip",
           "training_metrics": {...},
           "test_metrics": {...},
           "config": {...},
           "feature_names": [...],
           "feature_importance": {...}
       }
       response = await test_client.post("/api/v1/trainings/results", json=payload)
       assert response.status_code == 200
   ```

2. **Implement: Endpoint** (GREEN)
   ```python
   @router.post("/results")
   async def receive_training_results(...):
       # Implementation
   ```

3. **Test: Model decompression** (RED)
   ```python
   def test_model_decompression():
       # Create compressed model
       model_bytes = create_test_model_bytes()
       compressed = gzip.compress(model_bytes)
       compressed_b64 = base64.b64encode(compressed).decode()

       # Call service method
       result = await service.receive_training_results(
           session_id="test",
           model_state_dict_b64=compressed_b64,
           compression="gzip",
           ...
       )

       # Verify model saved
       assert result["success"] == True
       assert "model_path" in result
   ```

4. **Implement: Decompression and saving** (GREEN)

**Key Methods**:
```python
# In TrainingService
async def receive_training_results(
    self,
    session_id: str,
    model_state_dict_b64: str,
    compression: str,
    training_metrics: dict,
    test_metrics: dict,
    config: dict,
    feature_names: list,
    feature_importance: dict,
) -> dict
```

**Acceptance Criteria**:
- [ ] Endpoint accepts POST at /api/v1/trainings/results
- [ ] Validates session_id exists
- [ ] Decompresses gzip-compressed model
- [ ] Deserializes PyTorch state dict
- [ ] Saves model via ModelStorage
- [ ] Updates operation status to completed
- [ ] Returns success with model_path
- [ ] Handles errors gracefully (400, 404, 500)
- [ ] All tests pass (`make test-unit`)
- [ ] Code quality passes (`make quality`)
- [ ] Test coverage >80%

**Commit Strategy**:
```bash
git commit -m "test: add result callback endpoint tests"
git commit -m "feat(training): add result callback endpoint"
```

**Estimated**: 1 day

---

## Phase 2: Integration Layer

**Objective**: Wire new components into existing orchestration

**Duration**: 2-3 days

**Branch**: `feature/unified-training-architecture` (merge sub-branches first)

---

### TASK-2.1: Integrate ExecutionModeSelector into TrainingService

**Objective**: Replace env var logic with ExecutionModeSelector

**Files**:
- `ktrdr/api/services/training_service.py` (MODIFY)
- `ktrdr/training/training_manager.py` (MODIFY)
- `tests/unit/api/test_training_service.py` (MODIFY)

**TDD Steps**:

1. **Test: Service uses selector** (RED)
   ```python
   @pytest.mark.asyncio
   async def test_service_uses_mode_selector(mock_selector):
       mock_selector.select_mode.return_value = "local"
       service = TrainingService()
       await service.start_training(
           symbols=["EURUSD"],
           strategy_name="test",
           execution_mode="auto"
       )
       mock_selector.select_mode.assert_called_once_with(
           requested_mode="auto",
           require_gpu=False
       )
   ```

2. **Implement: Inject selector into service** (GREEN)

3. **Test: Mode selection logged** (RED)
   ```python
   def test_selected_mode_logged(caplog):
       # Verify log message shows selected mode
   ```

4. **Implement: Logging** (GREEN)

**Acceptance Criteria**:
- [ ] TrainingService initializes ExecutionModeSelector
- [ ] start_training() accepts optional execution_mode parameter
- [ ] Selector used to determine execution mode
- [ ] Selected mode logged for observability
- [ ] Fallback behavior works correctly
- [ ] Backward compatible (no breaking changes)
- [ ] All existing tests still pass
- [ ] New tests pass (`make test-unit`)
- [ ] Code quality passes (`make quality`)

**Estimated**: 1 day

---

### TASK-2.2: Add Config Endpoint for Default Mode

**Objective**: Allow runtime configuration of default execution mode

**Files**:
- `ktrdr/api/endpoints/training.py` (MODIFY - add endpoint)
- `tests/unit/api/test_training_endpoints.py` (MODIFY)

**TDD Steps**:

1. **Test: GET config returns current default** (RED)
   ```python
   @pytest.mark.asyncio
   async def test_get_training_config(test_client):
       response = await test_client.get("/api/v1/trainings/config")
       assert response.status_code == 200
       assert "default_execution_mode" in response.json()
   ```

2. **Implement: GET endpoint** (GREEN)

3. **Test: PUT config updates default** (RED)
   ```python
   @pytest.mark.asyncio
   async def test_update_default_mode(test_client):
       response = await test_client.put(
           "/api/v1/trainings/config",
           json={"default_execution_mode": "host"}
       )
       assert response.status_code == 200
       assert response.json()["new_default"] == "host"
   ```

4. **Implement: PUT endpoint** (GREEN)

**Acceptance Criteria**:
- [ ] GET /api/v1/trainings/config returns current default
- [ ] PUT /api/v1/trainings/config updates default
- [ ] Validates mode values ("auto", "local", "host")
- [ ] Returns previous and new default in response
- [ ] Changes persist for session lifetime
- [ ] All tests pass (`make test-unit`)
- [ ] Code quality passes (`make quality`)

**Estimated**: 0.5 day

---

### TASK-2.3: Update LocalTrainingRunner to use TrainingExecutor

**Objective**: Replace StrategyTrainer with TrainingExecutor in local path

**Files**:
- `ktrdr/api/services/training/local_runner.py` (MODIFY)
- `tests/unit/api/services/training/test_local_runner.py` (MODIFY)

**TDD Steps**:

1. **Test: LocalRunner uses TrainingExecutor** (RED)
   ```python
   @pytest.mark.asyncio
   async def test_local_runner_uses_executor(mock_executor):
       runner = LocalTrainingRunner(
           context=context,
           progress_bridge=bridge,
           cancellation_token=token,
       )
       await runner.run()
       mock_executor.execute.assert_called_once()
   ```

2. **Implement: Replace StrategyTrainer** (GREEN)
   ```python
   # In LocalTrainingRunner
   self._executor = TrainingExecutor(
       config=config,
       progress_callback=self._build_progress_callback(),
       cancellation_token=self._cancellation_token,
   )

   raw_result = await asyncio.to_thread(self._executor.execute, ...)
   ```

3. **Test: Progress callback wired correctly** (RED)
   ```python
   def test_progress_callback_invoked(mock_bridge):
       # Verify bridge receives progress updates
   ```

4. **Implement: Progress wiring** (GREEN)

**Acceptance Criteria**:
- [ ] LocalRunner instantiates TrainingExecutor
- [ ] Progress callback passed to executor
- [ ] Cancellation token passed to executor
- [ ] Results aggregated correctly
- [ ] All existing functionality preserved
- [ ] Integration tests pass
- [ ] All tests pass (`make test-unit`)
- [ ] Code quality passes (`make quality`)

**Estimated**: 1 day

---

## Phase 3: Host Service Integration

**Objective**: Update host service to use TrainingExecutor and post results back

**Duration**: 2-3 days

**Branch**: `feature/unified-training-architecture`

---

### TASK-3.1: Update Host Service to use TrainingExecutor

**Objective**: Replace host service training logic with TrainingExecutor

**Files**:
- `training-host-service/services/training_service.py` (MODIFY)
- `training-host-service/requirements.txt` (MODIFY - ensure ktrdr package)
- `tests/unit/host/test_training_service.py` (MODIFY)

**TDD Steps**:

1. **Test: Host service uses TrainingExecutor** (RED)
   ```python
   @pytest.mark.asyncio
   async def test_host_service_uses_executor(mock_executor):
       service = TrainingService()
       session = await service.create_session(config)
       # Verify executor instantiated with correct params
   ```

2. **Implement: Replace custom training loop** (GREEN)
   ```python
   # In _run_real_training
   executor = TrainingExecutor(
       config=session.config,
       progress_callback=lambda p, m, **d: session.update_progress(p, m, **d),
       cancellation_token=session.cancellation_token,
   )

   result = executor.execute(
       symbols=symbols,
       timeframes=timeframes,
       ...
   )
   ```

3. **Test: Progress updates session state** (RED)
   ```python
   def test_progress_updates_session():
       # Verify session.update_progress called
   ```

4. **Implement: Progress wiring** (GREEN)

**Acceptance Criteria**:
- [ ] Host service imports TrainingExecutor from ktrdr package
- [ ] Custom training loop removed
- [ ] TrainingExecutor instantiated with session config
- [ ] Progress callback updates session state
- [ ] Hardware detection works (finds MPS on Mac)
- [ ] Training completes successfully
- [ ] All tests pass
- [ ] Code quality passes

**Estimated**: 1 day

---

### TASK-3.2: Implement Result Posting with Compression

**Objective**: Host service POSTs results back to backend after training

**Files**:
- `training-host-service/services/training_service.py` (MODIFY)
- `tests/unit/host/test_result_posting.py` (NEW)

**TDD Steps**:

1. **Test: Model compression** (RED)
   ```python
   def test_model_compression():
       model_bytes = create_test_model()
       compressed = compress_model(model_bytes)
       assert len(compressed) < len(model_bytes)
       assert gzip.decompress(compressed) == model_bytes
   ```

2. **Implement: Compression** (GREEN)
   ```python
   def compress_model(model_state_dict):
       buffer = io.BytesIO()
       torch.save(model_state_dict, buffer)
       model_bytes = buffer.getvalue()
       compressed = gzip.compress(model_bytes)
       return base64.b64encode(compressed).decode()
   ```

3. **Test: Result posting** (RED)
   ```python
   @pytest.mark.asyncio
   async def test_post_results_to_backend(mock_http):
       await post_results(
           callback_url="http://backend/api/v1/trainings/results",
           session_id="test",
           model_state_dict=...,
           ...
       )
       mock_http.post.assert_called_once()
       payload = mock_http.post.call_args[1]["json"]
       assert payload["compression"] == "gzip"
   ```

4. **Implement: Posting** (GREEN)

5. **Test: Retry with exponential backoff** (RED)
   ```python
   @pytest.mark.asyncio
   async def test_retry_on_failure(mock_http):
       mock_http.post.side_effect = [
           httpx.HTTPError("Network error"),
           httpx.HTTPError("Network error"),
           httpx.Response(200, json={"success": True})
       ]
       await post_results_with_retry(...)
       assert mock_http.post.call_count == 3
   ```

6. **Implement: Retry logic** (GREEN)
   ```python
   async def _post_results_with_retry(self, callback_url, **payload):
       max_attempts = 3
       backoff = 1.0

       for attempt in range(1, max_attempts + 1):
           try:
               async with httpx.AsyncClient() as client:
                   response = await client.post(callback_url, json=payload)
                   response.raise_for_status()
                   return
           except httpx.HTTPError as e:
               if attempt >= max_attempts:
                   logger.error(f"Failed after {attempt} attempts")
               else:
                   await asyncio.sleep(backoff)
                   backoff = min(backoff * 2, 8.0)
   ```

**Acceptance Criteria**:
- [ ] Model serialized and compressed with gzip
- [ ] Compression ratio logged for observability
- [ ] POST request sent to callback_url
- [ ] Retry with exponential backoff (1s, 2s, 4s, max 8s)
- [ ] After 3 failures, log error but don't crash
- [ ] Results remain in session state if posting fails
- [ ] All tests pass
- [ ] Code quality passes

**Estimated**: 1.5 days

---

### TASK-3.3: Add Callback URL to Training Start Request

**Objective**: Backend passes callback URL when starting host training

**Files**:
- `ktrdr/api/services/training/host_session.py` (MODIFY)
- `ktrdr/training/training_adapter.py` (MODIFY)
- `tests/unit/api/services/training/test_host_session.py` (MODIFY)

**TDD Steps**:

1. **Test: Callback URL included in request** (RED)
   ```python
   @pytest.mark.asyncio
   async def test_callback_url_in_request(mock_adapter):
       manager = HostSessionManager(...)
       await manager.start_session()

       # Verify adapter called with callback_url
       call_args = mock_adapter.train_multi_symbol_strategy.call_args
       assert "callback_url" in call_args[1]
       assert call_args[1]["callback_url"] == "http://backend:8000/api/v1/trainings/results"
   ```

2. **Implement: Add callback_url parameter** (GREEN)

**Acceptance Criteria**:
- [ ] HostSessionManager constructs callback_url from config
- [ ] Callback URL passed to adapter
- [ ] Adapter includes in HTTP POST to host service
- [ ] Host service receives and stores callback_url in session
- [ ] All tests pass
- [ ] Code quality passes

**Estimated**: 0.5 day

---

## Phase 4: End-to-End Testing & Cleanup

**Objective**: Validate complete flows, remove deprecated code

**Duration**: 2 days

**Branch**: `feature/unified-training-architecture`

---

### TASK-4.1: End-to-End Integration Tests

**Objective**: Test complete flows in both execution modes

**Files**:
- `tests/integration/training/test_local_training_flow.py` (NEW)
- `tests/integration/training/test_host_training_flow.py` (NEW)

**Test Scenarios**:

1. **Local Training Flow**:
   - Start training request
   - Training executes in-process
   - Model saved to models/ directory
   - Strategy status updates to "trained"
   - Can load and use trained model

2. **Host Service Training Flow**:
   - Start training request with execution_mode="host"
   - Host service receives request
   - Training executes on host
   - Results posted back to backend
   - Model saved to models/ directory
   - Strategy status updates to "trained"

3. **Fallback Scenario**:
   - Request with execution_mode="host"
   - Host service unavailable
   - Falls back to local
   - Training succeeds

4. **GPU Required Scenario**:
   - Request with require_gpu=True
   - Host service unavailable
   - Training fails with appropriate error

**Acceptance Criteria**:
- [ ] Local flow test passes end-to-end
- [ ] Host flow test passes end-to-end
- [ ] Fallback test passes
- [ ] GPU required test passes
- [ ] Models saved correctly in all scenarios
- [ ] Strategy status correct in all scenarios
- [ ] All integration tests pass
- [ ] Code quality passes

**Estimated**: 1 day

---

### TASK-4.2: Remove Deprecated Code

**Objective**: Clean up old implementations after successful migration

**Files**:
- `ktrdr/training/train_strategy.py` (MODIFY - mark deprecated or remove)
- `training-host-service/services/training_service.py` (already updated)

**Steps**:

1. **Verify all tests pass with new code**
   ```bash
   make test-unit
   make test-integration
   ```

2. **Mark StrategyTrainer as deprecated**
   ```python
   class StrategyTrainer:
       """DEPRECATED: Use TrainingExecutor instead.

       This class will be removed in version 2.0.
       """
       def __init__(self):
           warnings.warn(
               "StrategyTrainer is deprecated. Use TrainingExecutor.",
               DeprecationWarning,
               stacklevel=2
           )
   ```

3. **Update documentation**
   - Update CLAUDE.md to reference TrainingExecutor
   - Update training README if exists

4. **Create removal ticket** for next release

**Acceptance Criteria**:
- [ ] StrategyTrainer marked deprecated
- [ ] Deprecation warnings shown when used
- [ ] All references updated to TrainingExecutor
- [ ] Documentation updated
- [ ] All tests pass
- [ ] Code quality passes

**Estimated**: 0.5 day

---

### TASK-4.3: Update Logging to Structured Format

**Objective**: Ensure consistent numbered-step logging in TrainingExecutor

**Files**:
- `ktrdr/training/executor.py` (MODIFY)
- `tests/unit/training/test_executor_logging.py` (NEW)

**TDD Steps**:

1. **Test: Log format** (RED)
   ```python
   def test_logging_format(caplog):
       executor = TrainingExecutor(...)
       executor.execute(...)

       # Verify logs contain numbered steps
       logs = [r.message for r in caplog.records]
       assert "Step 1: Loading market data" in logs
       assert "Step 2: Calculating technical indicators" in logs
   ```

2. **Implement: Structured logging** (GREEN)
   ```python
   def _log_step(self, step_num, message, **details):
       logger.info(f"Step {step_num}: {message}")
       for key, value in details.items():
           logger.debug(f"  {key}: {value}")
   ```

**Acceptance Criteria**:
- [ ] All major steps logged with numbers (Step 1-12)
- [ ] Sub-steps logged with indentation
- [ ] Details logged at DEBUG level
- [ ] Log format consistent with requirements
- [ ] Tests verify log output
- [ ] All tests pass
- [ ] Code quality passes

**Estimated**: 0.5 day

---

## Phase 5: Documentation & Deployment

**Objective**: Document changes, prepare for merge

**Duration**: 1 day

**Branch**: `feature/unified-training-architecture`

---

### TASK-5.1: Update Documentation

**Files**:
- `CLAUDE.md` (UPDATE)
- `training-host-service/README.md` (UPDATE)
- `docs/architecture/training/README.md` (UPDATE)

**Updates**:

1. **CLAUDE.md**:
   - Update training architecture section
   - Reference TrainingExecutor
   - Update common commands

2. **Host Service README**:
   - Explain TrainingExecutor usage
   - Document callback mechanism
   - Update deployment instructions

3. **Architecture README**:
   - Mark as implemented
   - Add links to code

**Acceptance Criteria**:
- [ ] All documentation updated
- [ ] Code examples accurate
- [ ] Architecture diagrams match implementation
- [ ] READMEs clear and helpful

**Estimated**: 0.5 day

---

### TASK-5.2: Create Pull Request

**Objective**: Prepare comprehensive PR for review

**PR Description Template**:

```markdown
# Training Service Unified Architecture

## Summary
Implements the unified training architecture as designed in docs/architecture/training/.

**Key Changes**:
- Consolidates duplicate training logic into TrainingExecutor
- Adds intelligent execution mode selection with fallback
- Implements host service result callback mechanism
- Adds gzip compression for model transfer

## Changes

### New Components
- `TrainingExecutor`: Environment-agnostic training core
- `ExecutionModeSelector`: Intelligent mode selection
- Result callback endpoint: `/api/v1/trainings/results`

### Modified Components
- `LocalTrainingRunner`: Now uses TrainingExecutor
- `HostSessionManager`: Adds callback URL support
- Host service: Uses TrainingExecutor, posts results back

### Deprecated
- `StrategyTrainer`: Marked deprecated (to be removed in v2.0)

## Testing

**Unit Tests**: All pass (< 2s)
```bash
make test-unit
```

**Integration Tests**: All pass
```bash
make test-integration
```

**Code Quality**: All pass
```bash
make quality
```

**Coverage**: >80% on new code

## Breaking Changes
None - fully backward compatible

## Migration Guide
See docs/architecture/training/README.md

## Checklist
- [x] All tests pass
- [x] Code quality checks pass
- [x] Documentation updated
- [x] Integration tests added
- [x] TDD approach followed
- [x] Small, focused commits
- [x] No breaking changes
```

**Acceptance Criteria**:
- [ ] PR created with comprehensive description
- [ ] All CI checks pass
- [ ] Code reviewed by at least one team member
- [ ] Documentation reviewed
- [ ] Approved for merge

**Estimated**: 0.5 day

---

## Quality Checklist (MANDATORY)

Before considering this implementation complete:

### Code Quality
- [ ] `make test-unit` passes (< 2s)
- [ ] `make quality` passes (lint, format, typecheck)
- [ ] Test coverage >80% on new code
- [ ] No pylint warnings
- [ ] Type hints on all public methods

### Architecture
- [ ] No code duplication
- [ ] Clear separation of concerns
- [ ] Dependencies point inward
- [ ] Components are testable in isolation

### Testing
- [ ] TDD approach followed for all tasks
- [ ] Unit tests for all new code
- [ ] Integration tests for flows
- [ ] Edge cases covered
- [ ] Error cases tested

### Documentation
- [ ] Code is self-documenting
- [ ] Complex logic has comments
- [ ] Architecture docs updated
- [ ] README files updated
- [ ] Examples are accurate

### Backward Compatibility
- [ ] No breaking changes to APIs
- [ ] Deprecated code marked clearly
- [ ] Migration path documented
- [ ] Existing tests still pass

---

## Risk Management

### High Risk Areas

1. **TrainingExecutor Consolidation**
   - **Risk**: Bugs introduced during consolidation
   - **Mitigation**: TDD, comprehensive tests, gradual rollout

2. **Host Service Communication**
   - **Risk**: Network failures, timeouts
   - **Mitigation**: Retry logic, fallback, extensive error handling

3. **Model Transfer**
   - **Risk**: Corruption, size limits
   - **Mitigation**: Compression, validation, checksums (HTTP)

### Rollback Plan

If issues arise after merge:

1. **Immediate**: Revert PR
   ```bash
   git revert <merge-commit>
   ```

2. **Investigation**: Identify root cause
   - Check logs
   - Review test results
   - Reproduce locally

3. **Fix Forward**: Create hotfix branch
   ```bash
   git checkout -b hotfix/training-issue
   # Fix issue
   # Test thoroughly
   # Create new PR
   ```

---

## Timeline Estimate

**Total Duration**: 10-12 days

| Phase | Tasks | Duration |
|-------|-------|----------|
| Phase 1: Foundation | 1.1, 1.2, 1.3 | 4 days |
| Phase 2: Integration | 2.1, 2.2, 2.3 | 2.5 days |
| Phase 3: Host Service | 3.1, 3.2, 3.3 | 3 days |
| Phase 4: Testing & Cleanup | 4.1, 4.2, 4.3 | 2 days |
| Phase 5: Docs & Deployment | 5.1, 5.2 | 1 day |
| **Buffer** | Testing, reviews, fixes | 2 days |

**Total**: ~14 days (2-3 weeks)

---

## Success Metrics

**Code Metrics**:
- Lines of code reduced by >40%
- Test coverage >80%
- Zero code duplication
- All quality checks pass

**Functional Metrics**:
- Both execution modes work correctly
- Models saved in all scenarios
- Strategy status accurate
- Fallback works reliably

**Performance Metrics**:
- Training time ≤ 5% slower than before
- Test suite still completes in < 2s
- No memory leaks

**User Experience**:
- Clear error messages
- Helpful logging
- Transparent mode selection

---

**Status**: Ready for Implementation
**Next**: Begin TASK-1.1 (TrainingExecutor Foundation)
