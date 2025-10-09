# Training Architecture Phase 1 - Implementation Plan

**Parent Documents**:
- [01-analysis.md](./01-analysis.md) - Problem identification
- [02-requirements.md](./02-requirements.md) - Requirements specification
- [03-architecture.md](./03-architecture.md) - Phase 1 architecture
- [03-architecture-phase2.md](./03-architecture-phase2.md) - Future improvements

**Status**: Ready for Implementation
**Version**: Phase 1 - Minimal Refactoring
**Date**: 2025-01-06

---

## Overview

This plan implements **Phase 1** of the training architecture refactoring: eliminating code duplication while preserving all current behavior.

### Key Principles

1. **Minimize Risk**: Change only what's necessary to eliminate duplication
2. **Preserve Behavior**: Keep async model, cancellation, progress mechanisms unchanged
3. **Test Continuously**: Equivalence tests are PRIMARY validation
4. **Incremental Progress**: Each task delivers testable value

### Branching Strategy

```bash
# Main development branch
feat/training-phase1-refactor

# Task-specific branches (optional, for large tasks)
feat/training-phase1-refactor/task-1.1-device-manager
feat/training-phase1-refactor/task-3.1-host-orchestrator
```

### Success Criteria

**Phase 1 is complete when**:
- ✅ Zero code duplication between local and host training paths
- ✅ All existing tests pass (unit, integration, e2e)
- ✅ Equivalence tests confirm identical behavior
- ✅ Host service saves models to shared ModelStorage
- ✅ No performance regression (< 5% difference)
- ✅ All async/cancellation behavior preserved exactly

---

## Phase 1: Foundation (Week 1)

### TASK-1.1: Create DeviceManager

**Objective**: Extract GPU detection logic to eliminate duplication

**Branch**: `feat/training-phase1-refactor` (main branch)

**Files**:
- `ktrdr/training/device_manager.py` (CREATE)
- `tests/unit/training/test_device_manager.py` (CREATE)

**Current State**:
- Host service: `training-host-service/services/training_service.py:104-122`
- Backend: Similar logic in various places

**New Design**:
```python
# ktrdr/training/device_manager.py
class DeviceManager:
    """Centralized GPU detection and device selection."""

    @staticmethod
    def detect_device() -> str:
        """Detect best available device (cuda, mps, cpu)."""
        # Extract exact logic from host service lines 104-122
        ...

    @staticmethod
    def get_device_info() -> dict[str, Any]:
        """Get detailed device information for logging/metrics."""
        ...
```

**Implementation Steps**:
1. Create `DeviceManager` class with exact logic from host service
2. Add comprehensive unit tests (mock torch.cuda, torch.backends.mps)
3. Update host service to use `DeviceManager`
4. Update backend training code to use `DeviceManager`
5. Run full test suite

**Acceptance Criteria**:
- [ ] DeviceManager detects CUDA correctly
- [ ] DeviceManager detects MPS correctly
- [ ] DeviceManager falls back to CPU correctly
- [ ] Host service uses DeviceManager
- [ ] Backend uses DeviceManager
- [ ] Unit test coverage > 95%
- [ ] All existing tests pass

**Testing Strategy**:
```bash
# Unit tests
uv run pytest tests/unit/training/test_device_manager.py -v

# Integration test (host service)
cd training-host-service && uv run pytest tests/ -v

# Full suite
make test-unit
```

**Commit Message**:
```
feat(training): create DeviceManager for centralized GPU detection

- Extract device detection logic to DeviceManager
- Eliminate duplication between host service and backend
- Add comprehensive unit tests for all device types

Tested:
- Unit tests: 95%+ coverage
- Host service integration tests pass
- Backend training tests pass
```

**Estimated Effort**: 1 day

---

### TASK-1.2: Create TrainingPipeline - Data Methods

**Objective**: Extract data loading/processing into pure functions

**Files**:
- `ktrdr/training/training_pipeline.py` (CREATE)
- `tests/unit/training/test_training_pipeline_data.py` (CREATE)

**Methods to Extract**:
```python
class TrainingPipeline:
    """Pure training work functions - no callbacks, no async."""

    @staticmethod
    def load_market_data(
        symbols: list[str],
        timeframes: list[str],
        start_date: str,
        end_date: str,
        data_source: str = "local"
    ) -> pd.DataFrame:
        """Load market data from data manager."""
        # Extract from local_runner.py and training_service.py
        ...

    @staticmethod
    def validate_data_quality(df: pd.DataFrame) -> dict[str, Any]:
        """Validate data has required columns and no major gaps."""
        ...
```

**Implementation Steps**:
1. Create `TrainingPipeline` class skeleton
2. Extract `load_market_data` from both paths (find common logic)
3. Extract `validate_data_quality` if it exists in both
4. Add unit tests with mocked DataManager
5. Update local_runner to call TrainingPipeline methods
6. Update host service to call TrainingPipeline methods

**Acceptance Criteria**:
- [ ] TrainingPipeline.load_market_data() works correctly
- [ ] TrainingPipeline.validate_data_quality() works correctly
- [ ] Unit tests cover all edge cases
- [ ] Local orchestrator uses TrainingPipeline
- [ ] Host service uses TrainingPipeline
- [ ] All existing tests pass

**Testing Strategy**:
```bash
# Unit tests
uv run pytest tests/unit/training/test_training_pipeline_data.py -v

# Integration tests
make test-integration

# Equivalence test (critical!)
uv run pytest tests/integration/training/test_training_equivalence.py -v
```

**Commit Message**:
```
feat(training): add TrainingPipeline data loading methods

- Create TrainingPipeline with load_market_data()
- Add data validation method
- Eliminate duplication in data loading logic

Tested:
- Unit tests for data methods
- Equivalence tests confirm identical behavior
- All integration tests pass
```

**Estimated Effort**: 2 days

---

### TASK-1.3: Create TrainingPipeline - Feature Engineering

**Objective**: Extract feature/label generation into pure functions

**Files**:
- `ktrdr/training/training_pipeline.py` (MODIFY)
- `tests/unit/training/test_training_pipeline_features.py` (CREATE)

**Methods to Extract**:
```python
class TrainingPipeline:
    # ... existing data methods ...

    @staticmethod
    def calculate_indicators(
        df: pd.DataFrame,
        strategy_config: dict[str, Any]
    ) -> pd.DataFrame:
        """Calculate technical indicators."""
        ...

    @staticmethod
    def generate_fuzzy_memberships(
        df: pd.DataFrame,
        strategy_config: dict[str, Any]
    ) -> pd.DataFrame:
        """Generate fuzzy membership values."""
        ...

    @staticmethod
    def create_features(
        df: pd.DataFrame,
        strategy_config: dict[str, Any]
    ) -> tuple[np.ndarray, list[str]]:
        """Create feature matrix and feature names."""
        ...

    @staticmethod
    def create_labels(
        df: pd.DataFrame,
        strategy_config: dict[str, Any]
    ) -> np.ndarray:
        """Create target labels."""
        ...
```

**Acceptance Criteria**:
- [ ] All feature engineering methods extracted
- [ ] Unit tests with real strategy config
- [ ] Local orchestrator uses pipeline methods
- [ ] Host service uses pipeline methods
- [ ] Equivalence tests pass (CRITICAL)

**Commit Message**:
```
feat(training): add TrainingPipeline feature engineering methods

- Extract indicator calculation
- Extract fuzzy membership generation
- Extract feature/label creation
- Eliminate feature engineering duplication

Tested: Equivalence tests confirm identical outputs
```

**Estimated Effort**: 2 days

---

### TASK-1.4: Create TrainingPipeline - Model Methods

**Objective**: Extract model creation/training/evaluation

**Files**:
- `ktrdr/training/training_pipeline.py` (MODIFY)
- `tests/unit/training/test_training_pipeline_model.py` (CREATE)

**Methods to Extract**:
```python
class TrainingPipeline:
    # ... existing methods ...

    @staticmethod
    def create_model(
        input_dim: int,
        output_dim: int,
        strategy_config: dict[str, Any],
        device: str
    ) -> nn.Module:
        """Create neural network model."""
        ...

    @staticmethod
    def train_model(
        model: nn.Module,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        training_config: dict[str, Any],
        device: str
    ) -> dict[str, Any]:
        """Train model and return metrics."""
        # NOTE: This is synchronous, no callbacks
        # Orchestrators will wrap this for progress reporting
        ...

    @staticmethod
    def evaluate_model(
        model: nn.Module,
        X_test: np.ndarray,
        y_test: np.ndarray,
        device: str
    ) -> dict[str, Any]:
        """Evaluate model on test set."""
        ...
```

**Key Design Decision**:
- `train_model()` is **synchronous** and takes no callbacks
- Progress reporting is orchestrator responsibility (they wrap this differently)
- This preserves current async model differences

**Acceptance Criteria**:
- [ ] Model methods extracted
- [ ] Unit tests for each method
- [ ] Equivalence tests confirm identical training results
- [ ] Performance benchmark (< 5% difference)

**Commit Message**:
```
feat(training): add TrainingPipeline model methods

- Extract model creation, training, evaluation
- Keep methods synchronous (orchestrators handle progress)
- Eliminate model logic duplication

Tested: Equivalence tests + performance benchmarks
```

**Estimated Effort**: 2 days

---

## Phase 2: Refactor Orchestrators (Week 2)

### TASK-2.1: Create LocalTrainingOrchestrator

**Objective**: Refactor local_runner to use TrainingPipeline

**Files**:
- `ktrdr/api/services/training/local_orchestrator.py` (CREATE, refactor from local_runner.py)
- `ktrdr/api/services/training/local_runner.py` (MODIFY - delegate to orchestrator)
- `tests/integration/training/test_local_orchestrator.py` (CREATE)

**Design**:
```python
# ktrdr/api/services/training/local_orchestrator.py
class LocalTrainingOrchestrator:
    """
    Orchestrate local training using TrainingPipeline.

    Responsibilities:
    - Progress reporting via ProgressBridge
    - Cancellation checking via CancellationToken
    - Wrapping TrainingPipeline in asyncio.to_thread()
    """

    def __init__(
        self,
        context: TrainingOperationContext,
        progress_bridge: TrainingProgressBridge,
        cancellation_token: CancellationToken | None
    ):
        self._context = context
        self._bridge = progress_bridge
        self._token = cancellation_token

    async def run(self) -> dict[str, Any]:
        """Execute training workflow using TrainingPipeline."""
        self._bridge.on_phase("initializing", message="Preparing training")

        # Load data (sync wrapped in thread)
        data = await asyncio.to_thread(
            TrainingPipeline.load_market_data,
            self._context.symbols,
            self._context.timeframes,
            self._context.start_date,
            self._context.end_date
        )

        # Calculate indicators
        self._bridge.on_phase("indicators", message="Calculating indicators")
        data = await asyncio.to_thread(
            TrainingPipeline.calculate_indicators,
            data,
            self._context.strategy_config
        )

        # ... continue with other TrainingPipeline methods ...

        # Train model (wrap in thread, poll for progress)
        self._bridge.on_phase("training", message="Training model")
        result = await self._train_model_with_progress(model, X_train, y_train, ...)

        return result

    async def _train_model_with_progress(self, ...) -> dict[str, Any]:
        """Wrap synchronous training with progress polling."""
        # Current implementation from local_runner
        # Uses progress_callback to bridge to ProgressBridge
        ...
```

**Key Preservation**:
- Keep `asyncio.to_thread()` wrapper pattern (don't change async model)
- Keep progress callback mechanism (ProgressBridge)
- Keep cancellation checking at same points

**Acceptance Criteria**:
- [ ] LocalTrainingOrchestrator uses all TrainingPipeline methods
- [ ] Progress reporting works identically
- [ ] Cancellation works identically
- [ ] Integration tests pass
- [ ] Equivalence tests confirm identical behavior

**Commit Message**:
```
refactor(training): create LocalTrainingOrchestrator

- Refactor local_runner to use TrainingPipeline
- Preserve asyncio.to_thread() wrapper pattern
- Preserve progress/cancellation mechanisms
- Zero behavior change

Tested: Equivalence tests confirm identical behavior
```

**Estimated Effort**: 2 days

---

### TASK-2.2: Integration Test Local Orchestrator

**Objective**: Comprehensive integration testing

**Files**:
- `tests/integration/training/test_local_orchestrator.py` (CREATE)
- `tests/integration/training/test_training_equivalence.py` (MODIFY - add orchestrator tests)

**Test Coverage**:
```python
@pytest.mark.integration
async def test_local_orchestrator_full_workflow():
    """Test complete training workflow via LocalTrainingOrchestrator."""
    # Setup context, progress bridge, cancellation token
    # Run training
    # Assert results are valid
    ...

@pytest.mark.integration
async def test_local_orchestrator_progress_reporting():
    """Verify progress updates flow correctly."""
    # Setup with progress callback
    # Run training
    # Assert all expected progress updates received
    ...

@pytest.mark.integration
async def test_local_orchestrator_cancellation():
    """Verify cancellation stops training gracefully."""
    # Setup with cancellation token
    # Start training
    # Cancel after 2 epochs
    # Assert training stopped and cleanup occurred
    ...

@pytest.mark.integration
async def test_equivalence_local_orchestrator_vs_old():
    """PRIMARY TEST: Confirm identical behavior to old local_runner."""
    # Run same training with old and new paths
    # Compare all outputs (model weights, metrics, feature importance)
    # Assert < 0.1% difference (account for random initialization)
    ...
```

**Acceptance Criteria**:
- [ ] All integration tests pass
- [ ] Equivalence test confirms < 0.1% difference
- [ ] Coverage > 90% for LocalTrainingOrchestrator
- [ ] Performance within 5% of baseline

**Commit Message**:
```
test(training): add comprehensive LocalTrainingOrchestrator tests

- Integration tests for full workflow
- Progress reporting verification
- Cancellation behavior tests
- Equivalence tests confirm identical behavior

All tests pass with < 0.1% difference from baseline
```

**Estimated Effort**: 1 day

---

## Phase 3: Refactor Host Service (Week 2-3)

### TASK-3.1: Create HostTrainingOrchestrator + Model Persistence

**Objective**: Refactor host service to use TrainingPipeline AND save models

**Files**:
- `ktrdr/api/services/training/host_orchestrator.py` (CREATE)
- `training-host-service/services/training_service.py` (MODIFY - delegate to orchestrator)
- `training-host-service/services/model_storage.py` (CREATE - wrapper for ktrdr.training.model_storage)
- `tests/integration/training/test_host_orchestrator.py` (CREATE)

**Critical Fix**: Host service must save models using shared ModelStorage

**Design**:
```python
# ktrdr/api/services/training/host_orchestrator.py
class HostTrainingOrchestrator:
    """
    Orchestrate host service training using TrainingPipeline.

    Responsibilities:
    - Progress reporting via TrainingSession updates
    - Cancellation checking via session.stop_requested
    - Direct async execution (no asyncio.to_thread wrapper)
    - Model persistence via shared ModelStorage
    """

    def __init__(
        self,
        session: TrainingSession,
        model_storage: ModelStorage  # NEW: Shared with backend
    ):
        self._session = session
        self._model_storage = model_storage

    async def run(self) -> dict[str, Any]:
        """Execute training workflow using TrainingPipeline."""
        self._update_progress("initializing", "Preparing training")

        # Load data (direct call, no thread wrapper)
        data = TrainingPipeline.load_market_data(
            self._session.symbols,
            self._session.timeframes,
            self._session.start_date,
            self._session.end_date
        )

        # ... continue with TrainingPipeline methods ...

        # Train model with progress updates
        self._update_progress("training", "Training model")
        result = await self._train_model_with_polling(model, X_train, y_train, ...)

        # CRITICAL: Save model using shared ModelStorage
        model_path = self._model_storage.save_model(
            model=model,
            strategy_name=self._session.strategy_name,
            metadata={
                "symbols": self._session.symbols,
                "timeframes": self._session.timeframes,
                "metrics": result["metrics"],
                "session_id": self._session.session_id,
            }
        )

        # Store model_path in session for backend retrieval
        self._session.artifacts["model_path"] = model_path

        return result

    def _update_progress(self, phase: str, message: str):
        """Update session progress (current mechanism)."""
        self._session.progress = {
            "phase": phase,
            "message": message,
            # ... existing progress fields ...
        }
```

**Host Service Integration**:
```python
# training-host-service/services/training_service.py
from ktrdr.training.model_storage import ModelStorage
from ktrdr.api.services.training.host_orchestrator import HostTrainingOrchestrator

class TrainingService:
    def __init__(self):
        # NEW: Initialize shared ModelStorage
        self.model_storage = ModelStorage(base_path="models/")  # Shared filesystem
        self.sessions: dict[str, TrainingSession] = {}

    async def _run_real_training(self, session_id: str):
        """Execute training using HostTrainingOrchestrator."""
        session = self.sessions[session_id]

        # Create orchestrator with shared model storage
        orchestrator = HostTrainingOrchestrator(
            session=session,
            model_storage=self.model_storage
        )

        try:
            result = await orchestrator.run()
            session.status = "completed"
            session.artifacts.update(result.get("artifacts", {}))
            # model_path is now in session.artifacts!
        except Exception as e:
            session.status = "failed"
            session.error = str(e)
```

**Shared Filesystem Assumption (Phase 1)**:
```python
# Backend and host service must have access to same models/ directory
# Examples of valid setups:
# 1. Same machine: Both access /Users/karl/ktrdr/models/
# 2. Docker volumes: Both mount same volume
# 3. Network filesystem: Both mount same NFS/SMB share
```

**Acceptance Criteria**:
- [ ] HostTrainingOrchestrator uses all TrainingPipeline methods
- [ ] Host service saves models to shared ModelStorage
- [ ] Backend can load models trained by host service
- [ ] model_path correctly returned to backend
- [ ] Progress updates work identically
- [ ] Cancellation works identically
- [ ] Integration tests pass
- [ ] Equivalence tests confirm identical behavior

**Commit Message**:
```
refactor(training): create HostTrainingOrchestrator with model persistence

- Refactor host service to use TrainingPipeline
- Add shared ModelStorage for model persistence
- Fix critical bug: host service now saves models
- Preserve direct async execution (no thread wrapper)
- Preserve progress/cancellation mechanisms

Tested: Equivalence tests + model persistence validation
```

**Estimated Effort**: 3 days

---

### TASK-3.2: Update TrainingSession Model

**Objective**: Ensure session model tracks model_path

**Files**:
- `training-host-service/models/training_session.py` (MODIFY)
- `tests/unit/training_host/test_training_session.py` (MODIFY)

**Changes**:
```python
# training-host-service/models/training_session.py
class TrainingSession:
    # ... existing fields ...

    artifacts: dict[str, Any] = field(default_factory=dict)
    # artifacts now includes:
    # - "model_path": "/path/to/saved/model.pth" (NEW)
    # - "feature_importance": {...}
    # - "training_history": {...}
```

**Acceptance Criteria**:
- [ ] TrainingSession.artifacts includes model_path
- [ ] Backend retrieves model_path correctly
- [ ] Unit tests verify model_path field

**Commit Message**:
```
feat(training-host): add model_path to TrainingSession artifacts

- Ensure host service returns model_path to backend
- Update session model to track model artifacts

Tested: Unit tests + integration tests
```

**Estimated Effort**: 0.5 days

---

### TASK-3.3: Integration Test Host Orchestrator

**Objective**: Comprehensive integration testing including model persistence

**Files**:
- `tests/integration/training/test_host_orchestrator.py` (CREATE)
- `tests/integration/training/test_training_equivalence.py` (MODIFY)

**Test Coverage**:
```python
@pytest.mark.integration
@pytest.mark.requires_shared_storage
async def test_host_orchestrator_full_workflow():
    """Test complete training workflow via HostTrainingOrchestrator."""
    # Setup session with shared model storage
    # Run training
    # Assert model saved to shared location
    # Assert backend can load model
    ...

@pytest.mark.integration
async def test_host_orchestrator_model_persistence():
    """Verify model persistence to shared ModelStorage."""
    # Run training on host service
    # Check model file exists in shared storage
    # Load model from backend side
    # Verify model works for inference
    ...

@pytest.mark.integration
async def test_equivalence_host_vs_local():
    """PRIMARY TEST: Confirm host and local produce identical results."""
    # Run same training locally and on host
    # Compare model weights, metrics, feature importance
    # Assert < 0.1% difference
    ...

@pytest.mark.integration
async def test_equivalence_host_new_vs_old():
    """Confirm new host orchestrator vs old host service."""
    # Run with old training_service._run_real_training
    # Run with new HostTrainingOrchestrator
    # Compare results
    # Assert < 0.1% difference
    ...
```

**Acceptance Criteria**:
- [ ] All integration tests pass
- [ ] Model persistence validated
- [ ] Equivalence tests confirm < 0.1% difference
- [ ] Performance within 5% of baseline

**Commit Message**:
```
test(training): add HostTrainingOrchestrator integration tests

- Full workflow tests including model persistence
- Equivalence tests vs local training
- Equivalence tests vs old host implementation

All tests pass with < 0.1% difference
```

**Estimated Effort**: 1.5 days

---

## Phase 4: Equivalence Testing (Week 3)

### TASK-4.1: Create Comprehensive Equivalence Test Suite

**Objective**: PRIMARY VALIDATION - Prove Phase 1 preserves all behavior

**Files**:
- `tests/integration/training/test_training_equivalence.py` (COMPREHENSIVE REWRITE)
- `tests/integration/training/fixtures/equivalence_strategies.py` (CREATE - test strategies)

**Test Matrix**:
```python
# Test all combinations:
# - Old local vs New local
# - Old host vs New host
# - New local vs New host
# - Multiple strategies
# - Multiple symbol/timeframe combinations

@pytest.mark.equivalence
@pytest.mark.parametrize("strategy", ["neuro_mean_reversion", "simple_ma_crossover"])
@pytest.mark.parametrize("execution", ["local_old", "local_new", "host_old", "host_new"])
async def test_training_equivalence_comprehensive(strategy, execution):
    """Comprehensive equivalence testing across all paths."""
    # Run training with specified strategy and execution path
    result = await run_training(strategy, execution)

    # Store results for comparison
    results_db[f"{strategy}_{execution}"] = result

    # Compare with baseline if exists
    if baseline := results_db.get(f"{strategy}_baseline"):
        assert_equivalent(result, baseline, tolerance=0.001)

def assert_equivalent(result1, result2, tolerance=0.001):
    """Assert two training results are equivalent within tolerance."""
    # Model weights (allow small numeric difference)
    assert_model_weights_close(result1["model"], result2["model"], rtol=tolerance)

    # Metrics (exact match for most, tolerance for floats)
    assert result1["metrics"]["accuracy"] == pytest.approx(
        result2["metrics"]["accuracy"], rel=tolerance
    )

    # Feature importance (order may differ slightly, check top features)
    assert_top_features_match(
        result1["feature_importance"],
        result2["feature_importance"],
        top_n=10
    )

    # Artifacts (model_path exists, loadable)
    assert os.path.exists(result1["model_path"])
    assert os.path.exists(result2["model_path"])

    # Both models produce similar predictions
    test_data = load_test_data()
    pred1 = result1["model"].predict(test_data)
    pred2 = result2["model"].predict(test_data)
    assert np.allclose(pred1, pred2, rtol=tolerance)
```

**Equivalence Report**:
```python
# Generate detailed comparison report
def generate_equivalence_report(results_db):
    """Generate detailed report comparing all execution paths."""
    report = {
        "summary": {
            "total_comparisons": len(results_db),
            "passed": count_passing_comparisons(),
            "failed": count_failing_comparisons(),
            "max_difference": calculate_max_difference(),
        },
        "details": [
            {
                "comparison": "local_old vs local_new",
                "strategy": "neuro_mean_reversion",
                "metrics_diff": {...},
                "weights_diff": 0.0003,
                "passed": True,
            },
            # ... more comparisons ...
        ]
    }
    return report
```

**Acceptance Criteria**:
- [ ] All equivalence tests pass (< 0.1% difference)
- [ ] Equivalence report generated
- [ ] Test coverage includes:
  - [ ] Multiple strategies (at least 2)
  - [ ] Both local and host execution
  - [ ] Old vs new implementations
  - [ ] Model weights comparison
  - [ ] Metrics comparison
  - [ ] Feature importance comparison
  - [ ] Prediction comparison

**Commit Message**:
```
test(training): comprehensive equivalence test suite

- Test all combinations of execution paths
- Compare old vs new implementations
- Validate < 0.1% difference in all outputs
- Generate detailed equivalence report

PRIMARY VALIDATION: All equivalence tests pass
```

**Estimated Effort**: 2 days

---

### TASK-4.2: Run Full Test Suite and Performance Benchmarks

**Objective**: Final validation before merge

**Testing Checklist**:
```bash
# 1. Unit tests
make test-unit
# Expected: All pass, > 90% coverage

# 2. Integration tests
make test-integration
# Expected: All pass

# 3. Equivalence tests (CRITICAL)
uv run pytest tests/integration/training/test_training_equivalence.py -v
# Expected: All pass with < 0.1% difference

# 4. Performance benchmarks
uv run pytest tests/performance/test_training_performance.py -v
# Expected: < 5% difference from baseline

# 5. E2E tests
make test-e2e
# Expected: All pass

# 6. Quality checks
make quality
# Expected: All pass
```

**Performance Benchmark**:
```python
@pytest.mark.performance
@pytest.mark.parametrize("execution", ["local_old", "local_new", "host_old", "host_new"])
def test_training_performance_benchmark(execution, benchmark):
    """Benchmark training performance across all paths."""
    def run_training():
        return train_strategy(
            strategy="neuro_mean_reversion",
            symbols=["EURUSD"],
            timeframes=["1h"],
            start_date="2024-01-01",
            end_date="2024-01-07",
            execution=execution
        )

    result = benchmark(run_training)

    # Assert no significant regression
    baseline = load_baseline_timing(execution.replace("_new", "_old"))
    assert result.stats["mean"] < baseline * 1.05  # Max 5% slower
```

**Acceptance Criteria**:
- [ ] All unit tests pass (> 90% coverage)
- [ ] All integration tests pass
- [ ] All equivalence tests pass (< 0.1% diff)
- [ ] Performance benchmarks pass (< 5% regression)
- [ ] All e2e tests pass
- [ ] Code quality passes (lint, format, typecheck)

**Commit Message**:
```
test(training): validate Phase 1 complete

- All unit tests pass (93% coverage)
- All integration tests pass
- Equivalence tests: < 0.1% difference
- Performance: < 2% regression
- All quality checks pass

Phase 1 validation complete - ready for merge
```

**Estimated Effort**: 1 day

---

## Phase 5: Documentation and Merge (Week 3)

### TASK-5.1: Update Documentation

**Objective**: Document new architecture and migration path

**Files**:
- `docs/architecture/training/03-architecture.md` (already updated)
- `ktrdr/training/README.md` (CREATE)
- `training-host-service/README.md` (UPDATE)
- `docs/development/testing-guide.md` (UPDATE - add equivalence testing)

**New Documentation**:
```markdown
# ktrdr/training/README.md

# Training System Architecture (Phase 1)

## Overview

The training system is built on three core components:

1. **TrainingPipeline**: Pure work functions (no callbacks, no async)
2. **LocalTrainingOrchestrator**: Local execution with asyncio.to_thread wrapper
3. **HostTrainingOrchestrator**: Host service execution with direct async

## Key Design Decisions

### Why Two Orchestrators?

We preserve the existing async models because:
- Local training wraps sync StrategyTrainer in asyncio.to_thread()
- Host service runs directly async (no thread wrapper needed)
- Unifying these would risk breaking existing behavior

### Why TrainingPipeline?

Eliminates ~70% code duplication while preserving orchestration differences.

## Usage

### Local Training
```python
from ktrdr.api.services.training.local_orchestrator import LocalTrainingOrchestrator

orchestrator = LocalTrainingOrchestrator(context, bridge, token)
result = await orchestrator.run()
```

### Host Training
```python
from ktrdr.api.services.training.host_orchestrator import HostTrainingOrchestrator

orchestrator = HostTrainingOrchestrator(session, model_storage)
result = await orchestrator.run()
```

## Testing

See [equivalence tests](../../tests/integration/training/test_training_equivalence.py) for validation that Phase 1 preserves all behavior.
```

**Acceptance Criteria**:
- [ ] All README files updated
- [ ] Architecture docs accurate
- [ ] Testing guide includes equivalence testing section
- [ ] Migration notes documented

**Commit Message**:
```
docs(training): update documentation for Phase 1 architecture

- Add ktrdr/training/README.md explaining new architecture
- Update host service README with model persistence info
- Update testing guide with equivalence testing section

All documentation reflects Phase 1 implementation
```

**Estimated Effort**: 1 day

---

### TASK-5.2: Create Pull Request

**Objective**: Merge Phase 1 to main

**PR Description Template**:
```markdown
# Training Architecture Phase 1 - Eliminate Duplication

## Summary

This PR implements Phase 1 of the training architecture refactoring, eliminating ~70% code duplication while preserving all existing behavior.

## Key Changes

### New Components
- **DeviceManager**: Centralized GPU detection
- **TrainingPipeline**: Pure work functions (data, features, model)
- **LocalTrainingOrchestrator**: Refactored local training (uses TrainingPipeline)
- **HostTrainingOrchestrator**: Refactored host training (uses TrainingPipeline)

### Critical Fix
- **Host service now saves models** via shared ModelStorage

### Preserved Behavior
- ✅ Async execution models (asyncio.to_thread for local, direct async for host)
- ✅ Progress reporting mechanisms (callback-based for local, polling for host)
- ✅ Cancellation propagation (in-memory token for local, HTTP flag for host)
- ✅ All existing functionality

## Testing

### Equivalence Tests (PRIMARY VALIDATION)
```
tests/integration/training/test_training_equivalence.py
- Old local vs New local: < 0.05% difference ✅
- Old host vs New host: < 0.08% difference ✅
- New local vs New host: < 0.1% difference ✅
```

### Test Coverage
- Unit tests: 93% coverage ✅
- Integration tests: All pass ✅
- E2E tests: All pass ✅
- Performance: < 2% regression ✅

### Quality Checks
- Lint: Pass ✅
- Format: Pass ✅
- Typecheck: Pass ✅

## Phase 2 Improvements

Phase 2 (future work) will address:
- Remote model transfer (for distributed deployment)
- Async pattern harmonization (if beneficial)
- Dynamic mode selection with health checks

See [03-architecture-phase2.md](docs/architecture/training/03-architecture-phase2.md) for details.

## Migration Notes

### Shared Filesystem Requirement
Backend and host service must access same `models/` directory in Phase 1.

Examples of valid setups:
- Same machine (both access `/Users/karl/ktrdr/models/`)
- Docker volumes (both mount same volume)
- Network filesystem (both mount same NFS/SMB share)

Phase 2 will add remote model transfer to eliminate this requirement.

## Checklist

- [x] All unit tests pass (> 90% coverage)
- [x] All integration tests pass
- [x] Equivalence tests pass (< 0.1% difference)
- [x] Performance benchmarks pass (< 5% regression)
- [x] Documentation updated
- [x] Code quality checks pass
```

**Review Checklist**:
- [ ] All tests pass in CI
- [ ] Code review approved
- [ ] Documentation reviewed
- [ ] Performance benchmarks reviewed
- [ ] Equivalence report reviewed

**Merge Strategy**:
1. Squash merge to main (or keep detailed commits if preferred)
2. Tag release: `v2.1.0-training-phase1`
3. Deploy to staging first
4. Monitor for any issues
5. Deploy to production

**Commit Message** (if squashing):
```
feat(training): Phase 1 - eliminate duplication, preserve behavior (#XX)

Major refactoring of training architecture:
- Extract shared TrainingPipeline (eliminates 70% duplication)
- Refactor local and host orchestrators to use pipeline
- Fix critical bug: host service now saves models
- Preserve all existing async/progress/cancellation behavior

Validated:
- Equivalence tests: < 0.1% difference from old implementation
- Performance: < 2% regression
- All tests pass (93% coverage)

See docs/architecture/training/ for detailed architecture.
```

**Estimated Effort**: 0.5 days

---

## Summary Timeline

| Phase | Tasks | Estimated Effort | Key Deliverables |
|-------|-------|------------------|------------------|
| **Phase 1: Foundation** | TASK-1.1 to 1.4 | 1 week | DeviceManager, TrainingPipeline (all methods) |
| **Phase 2: Orchestrators** | TASK-2.1 to 2.2 | 3 days | LocalTrainingOrchestrator + tests |
| **Phase 3: Host Service** | TASK-3.1 to 3.3 | 5 days | HostTrainingOrchestrator + model persistence + tests |
| **Phase 4: Validation** | TASK-4.1 to 4.2 | 3 days | Comprehensive equivalence tests + benchmarks |
| **Phase 5: Documentation** | TASK-5.1 to 5.2 | 1.5 days | Docs + PR |
| **Total** | 15 tasks | **2.5-3 weeks** | Zero duplication, zero behavior change |

---

## Risk Mitigation

### High-Risk Areas

1. **Model Persistence**: Host service saving models is new functionality
   - **Mitigation**: Extensive integration tests, verify file exists and loads correctly

2. **Equivalence Testing**: Must confirm < 0.1% difference
   - **Mitigation**: Comprehensive test matrix, detailed comparison report

3. **Performance Regression**: Training must not slow down significantly
   - **Mitigation**: Performance benchmarks, < 5% tolerance

### Rollback Plan

If issues discovered after merge:
1. Revert PR (single commit if squashed)
2. Re-test on branch
3. Fix and re-submit

If issues discovered in production:
1. Feature flag to disable new orchestrators (use old paths)
2. Fix on branch
3. Re-deploy

---

## Success Metrics

Phase 1 is successful if:

- ✅ **Zero duplication**: TrainingPipeline used by both orchestrators
- ✅ **Zero behavior change**: Equivalence tests pass (< 0.1% diff)
- ✅ **Zero performance regression**: < 5% difference in benchmarks
- ✅ **Models persist**: Host service saves models correctly
- ✅ **All tests pass**: Unit, integration, e2e, equivalence
- ✅ **Production stable**: No incidents after deployment

---

**Status**: Ready for Implementation
**Next**: TASK-1.1 - Create DeviceManager
**Template**: Based on [CLI-UNIFIED-OPERATIONS-IMPLEMENTATION.md](../cli/CLI-UNIFIED-OPERATIONS-IMPLEMENTATION.md)
