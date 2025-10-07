# Training Service Unified Architecture - Implementation Plan

**Parent Documents**:

- [01-analysis.md](./01-analysis.md)
- [02-requirements.md](./02-requirements.md)
- [03-architecture.md](./03-architecture.md)
- [05-migration-strategy.md](./05-migration-strategy.md)

**Status**: Ready for Implementation
**Version**: 2.0 (Complete Rewrite)
**Date**: 2025-01-06

---

## Overview

This document breaks down the implementation using **TRUE Progressive Refactoring** - extracting and validating one piece at a time, continuously testing end-to-end.

**What's Different from v1.0**:

- ❌ **OLD**: Build entire TrainingExecutor, then flip a switch
- ✅ **NEW**: Extract one method at a time, test continuously, always working system

**Key Principle**: Every single commit leaves the system in a working, testable state.

---

## Implementation Philosophy

### The Progressive Extraction Pattern

1. **Pick ONE method** from StrategyTrainer
2. **Extract to new module** (preserve exact logic)
3. **Add comprehensive tests** (unit + integration)
4. **Update StrategyTrainer** to call extracted method
5. **Test end-to-end** (full training must work)
6. **Commit** (working system)
7. **Repeat** for next method

### Continuous Testing Strategy

**Every commit must pass**:

```bash
# 1. Unit tests
make test-unit

# 2. Integration tests
make test-integration

# 3. END-TO-END TRAINING TEST (CRITICAL - NEW!)
make test-e2e-training

# 4. Quality checks
make quality
```

### End-to-End Training Test (Autonomous Validation)

**NEW**: Automated test that runs full training pipeline with REAL strategy

```python
# tests/e2e/test_training_pipeline.py

@pytest.mark.e2e
@pytest.mark.slow
def test_full_training_pipeline_local():
    """
    End-to-end test: Full training pipeline from API to model save.

    This test MUST pass after every extraction/refactoring.
    If it fails, the refactoring broke something.

    Uses REAL proven strategy (neuro_mean_reversion.yaml) with minimal dataset.
    """
    # Setup: Small test dataset
    symbols = ["EURUSD"]
    timeframes = ["1h"]
    start_date = "2024-01-01"
    end_date = "2024-01-07"  # Just 1 week for speed

    # Load REAL proven strategy (not a test mock!)
    strategy_path = "strategies/neuro_mean_reversion.yaml"
    strategy_config = load_strategy_config(strategy_path)

    # Execute training
    result = train_strategy(
        symbols=symbols,
        timeframes=timeframes,
        start_date=start_date,
        end_date=end_date,
        strategy_config=strategy_config,
        execution_mode="local",
    )

    # Validate results
    assert result["success"] == True
    assert os.path.exists(result["model_path"])
    assert result["test_metrics"]["accuracy"] > 0.5  # Sanity check

    # Validate model can be loaded and used
    model = load_model(result["model_path"])
    assert model is not None

    # Validate predictions work
    test_data = load_test_data(symbols[0], timeframes[0])
    predictions = model.predict(test_data)
    assert len(predictions) > 0

@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.requires_host_service
def test_full_training_pipeline_host():
    """
    End-to-end test: Full training via host service.

    This validates host service integration works.
    """
    # Same as above but execution_mode="host"
    # Requires host service running
    ...

@pytest.mark.e2e
def test_training_pipeline_with_cancellation():
    """Test that cancellation works end-to-end."""
    ...

@pytest.mark.e2e
def test_training_pipeline_with_progress():
    """Test that progress reporting works end-to-end."""
    ...
```

**Run Frequency**:

- After EVERY extraction/refactoring
- Before EVERY commit
- In CI/CD pipeline

**Performance Target**:

- < 2 minutes for local e2e test
- Use minimal dataset (1 week, 1 symbol)
- Use REAL strategy configuration (validates all real code paths)
- Reduce epochs if needed for speed (e.g., 5-10 epochs instead of 100)
- Focus on correctness, not training quality

**Why Use Real Strategy (neuro_mean_reversion.yaml)**:

- ✅ Tests actual production code paths (not mocked logic)
- ✅ Validates real indicator calculations, fuzzy logic, feature engineering
- ✅ Catches issues that simplified test strategy would miss
- ✅ If neuro_mean_reversion works, all strategies should work
- ✅ No need to maintain separate test-only strategy configuration

---

## Progressive Extraction Plan

### Phase 1: Foundation Infrastructure (1 week)

**Goal**: Set up testing infrastructure and extract first non-training method

#### TASK 1.1: Create End-to-End Test Infrastructure

**Objective**: Set up automated e2e testing before any refactoring

**Files**:

- `tests/e2e/test_training_pipeline.py` (NEW)
- `tests/e2e/conftest.py` (NEW - shared fixtures)
- `Makefile` (MODIFY - add `test-e2e-training` target)

**Tasks**:

1. Create e2e test using **real** `strategies/neuro_mean_reversion.yaml`
2. Override epochs to 5-10 for speed (config override in test)
3. Add Makefile target: `test-e2e-training`
4. Document how to run e2e tests locally
5. Ensure test passes with CURRENT code (baseline)

**Strategy Configuration Override**:

```python
# Load real strategy, override for speed
strategy_config = load_strategy_config("strategies/neuro_mean_reversion.yaml")

# Override training config for fast e2e test
strategy_config["training"]["epochs"] = 5  # Instead of 100
strategy_config["training"]["batch_size"] = 64  # Keep reasonable size
# All other settings remain from real strategy
```

**Acceptance Criteria**:

- [ ] `make test-e2e-training` runs and passes with current code
- [ ] Test uses **real** neuro_mean_reversion.yaml strategy
- [ ] Test completes in < 2 minutes
- [ ] Test validates model saved and loadable
- [ ] Test validates predictions work
- [ ] CI integration documented

**Why First**: We need automated validation BEFORE we start extracting code.

**Estimated**: 2 days

---

#### TASK 1.2: Extract Device Detection (First Extraction)

**Objective**: Extract simplest method to validate progressive pattern

**Current State** (in StrategyTrainer):

```python
class StrategyTrainer:
    def _detect_device(self):
        if torch.backends.mps.is_available():
            return "mps"
        elif torch.cuda.is_available():
            return "cuda"
        return "cpu"
```

**New State**:

```python
# ktrdr/training/device_detection.py (NEW)
def detect_training_device() -> str:
    """Detect best available device for training."""
    if torch.backends.mps.is_available():
        return "mps"
    elif torch.cuda.is_available():
        return "cuda"
    return "cpu"

# ktrdr/training/train_strategy.py (MODIFIED)
from ktrdr.training.device_detection import detect_training_device

class StrategyTrainer:
    def _detect_device(self):
        # Now just calls extracted function
        return detect_training_device()
```

**Testing Strategy**:

1. **Unit test extracted function**:

```python
# tests/unit/training/test_device_detection.py
def test_device_detection_cpu(monkeypatch):
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert detect_training_device() == "cpu"

def test_device_detection_mps(monkeypatch):
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)
    assert detect_training_device() == "mps"
```

2. **Run e2e test**:

```bash
make test-e2e-training  # MUST STILL PASS
```

3. **Commit**:

```bash
git add ktrdr/training/device_detection.py tests/unit/training/test_device_detection.py
git commit -m "refactor(training): extract device detection to standalone function

- Extracted _detect_device logic to device_detection.py
- StrategyTrainer now calls extracted function
- All tests pass including e2e

Verified: make test-unit && make test-e2e-training"
```

**Acceptance Criteria**:

- [ ] New module `device_detection.py` created
- [ ] Unit tests pass (>90% coverage)
- [ ] StrategyTrainer updated to use extracted function
- [ ] **E2E test still passes** (CRITICAL)
- [ ] All existing tests pass
- [ ] Code quality passes

**Estimated**: 1 day

---

#### TASK 1.3: Extract Data Loading Logic

**Objective**: Extract data loading to standalone module

**Current State**: `StrategyTrainer._load_data()`

**New State**:

```python
# ktrdr/training/data_loading.py (NEW)
from ktrdr.data.data_manager import DataManager

def load_training_data(
    symbols: list[str],
    timeframes: list[str],
    start_date: str,
    end_date: str,
    data_mode: str = "local",
) -> dict[str, Any]:
    """Load market data for training."""
    # Extract exact logic from StrategyTrainer._load_data
    ...

# ktrdr/training/train_strategy.py (MODIFIED)
from ktrdr.training.data_loading import load_training_data

class StrategyTrainer:
    def _load_data(self, symbols, timeframes, start_date, end_date):
        return load_training_data(symbols, timeframes, start_date, end_date, self.data_mode)
```

**Testing**:

1. Unit tests for `load_training_data()`
2. Mock DataManager for fast tests
3. **Run e2e test - must pass**
4. Commit

**Acceptance Criteria**:

- [ ] `data_loading.py` created with unit tests
- [ ] StrategyTrainer uses extracted function
- [ ] **E2E test passes**
- [ ] All existing tests pass

**Estimated**: 1 day

---

#### TASK 1.4: Extract Indicator Calculation

**Objective**: Extract indicator calculation logic

**Pattern**: Same as 1.3 - extract, test, validate e2e, commit

**Estimated**: 1 day

---

#### TASK 1.5: Extract Fuzzy Generation

**Objective**: Extract fuzzy membership generation logic

**Pattern**: Same as 1.3 - extract, test, validate e2e, commit

**Estimated**: 1 day

---

### Phase 2: Feature Engineering & Labels (1 week)

Continue progressive extraction pattern:

- TASK 2.1: Extract feature engineering
- TASK 2.2: Extract label generation
- TASK 2.3: Extract train/test split

Each follows same pattern: extract → test → e2e validate → commit

---

### Phase 3: Model Creation & Training (1 week)

#### TASK 3.1: Extract Model Creation

**Objective**: Extract model architecture creation

**Challenge**: This is tightly coupled to ModelTrainer

**Approach**: Extract configuration logic, keep ModelTrainer unchanged

---

#### TASK 3.2: Create Progress Callback Wrapper (CAREFUL!)

**Objective**: Add step-level progress reporting WITHOUT changing ModelTrainer signature

**Current**: ModelTrainer callback: `(epoch, total_epochs, metrics)`

**New**: Wrapper that adds step context

```python
# ktrdr/training/progress_integration.py (NEW)
from ktrdr.async_infrastructure.progress import GenericProgressManager

class TrainingProgressIntegrator:
    """
    Integrates ModelTrainer's epoch/batch progress with GenericProgressManager's step progress.

    CRITICAL: Does NOT change ModelTrainer's callback signature!
    """

    def __init__(self, progress_manager: GenericProgressManager, step_number: int = 7):
        self.progress_manager = progress_manager
        self.step_number = step_number

    def create_callback(self) -> Callable[[int, int, dict], None]:
        """
        Create callback for ModelTrainer.

        Returns callback with EXACT signature ModelTrainer expects.
        """
        def callback(epoch: int, total_epochs: int, metrics: dict[str, float]) -> None:
            # Report nested progress within current step
            self.progress_manager.update_step_progress(
                step_current=epoch,
                step_total=total_epochs,
                message=f"Epoch {epoch}/{total_epochs}",
                context={
                    "epoch": epoch,
                    "total_epochs": total_epochs,
                    "metrics": metrics,
                },
            )
        return callback
```

**Usage in StrategyTrainer**:

```python
# Before
trainer = ModelTrainer(config, progress_callback=self.progress_callback)

# After
integrator = TrainingProgressIntegrator(self.progress_manager, step_number=7)
trainer = ModelTrainer(config, progress_callback=integrator.create_callback())
```

**Testing**:

1. Unit test: Verify wrapper preserves signature
2. Integration test: Verify progress updates flow correctly
3. **E2E test: Verify progress reported during training**
4. Commit

**Acceptance Criteria**:

- [ ] Wrapper created and tested
- [ ] StrategyTrainer updated to use wrapper
- [ ] Progress visible in e2e test
- [ ] **E2E test passes**
- [ ] ModelTrainer signature unchanged

**Estimated**: 2 days

---

#### TASK 3.3: Extract Model Training Orchestration

**Objective**: Extract the logic AROUND ModelTrainer, not ModelTrainer itself

**Pattern**: Extract, test, e2e validate, commit

**Estimated**: 1 day

---

### Phase 4: Post-Training Steps (1 week)

- TASK 4.1: Extract model evaluation
- TASK 4.2: Extract feature importance
- TASK 4.3: Extract model saving
- TASK 4.4: Extract result building

Each: extract → test → e2e validate → commit

---

### Phase 5: Consolidation into TrainingExecutor (1 week)

**NOW** we create TrainingExecutor - but it just orchestrates the extracted functions!

#### TASK 5.1: Create TrainingExecutor Shell

**Objective**: Create TrainingExecutor that calls all extracted functions

```python
# ktrdr/training/executor.py (NEW)
from ktrdr.training.device_detection import detect_training_device
from ktrdr.training.data_loading import load_training_data
from ktrdr.training.indicator_calculation import calculate_indicators
# ... import all extracted functions

class TrainingExecutor:
    """
    Consolidated training executor using extracted, battle-tested functions.

    This class does NOT reimplement anything - it orchestrates extracted functions.
    """

    def __init__(self, config, progress_callback=None, cancellation_token=None):
        self.config = config
        self.progress_callback = progress_callback
        self.cancellation_token = cancellation_token
        self.device = detect_training_device()

    def execute(self, symbols, timeframes, start_date, end_date, **kwargs):
        """Execute training pipeline using extracted functions."""
        # Step 1: Load data
        data = load_training_data(symbols, timeframes, start_date, end_date)

        # Step 2: Calculate indicators
        indicators = calculate_indicators(data, self.config["strategy_config"])

        # Step 3: Generate fuzzy
        fuzzy = generate_fuzzy_members(indicators, self.config["strategy_config"])

        # ... continue with all extracted functions

        return results
```

**Testing**:

1. Unit test: TrainingExecutor.execute() calls all functions
2. **E2E test with TrainingExecutor directly**
3. Compare results: StrategyTrainer vs TrainingExecutor (should be identical)
4. Commit

**Acceptance Criteria**:

- [ ] TrainingExecutor created
- [ ] Uses ALL extracted functions
- [ ] **E2E test passes with TrainingExecutor**
- [ ] Side-by-side comparison: results match StrategyTrainer exactly

**Estimated**: 2 days

---

#### TASK 5.2: Add Feature Flag to StrategyTrainer

**Objective**: StrategyTrainer can delegate to TrainingExecutor

```python
# ktrdr/training/train_strategy.py
class StrategyTrainer:
    def train_multi_symbol_strategy(self, **kwargs):
        # Feature flag check
        if os.getenv("USE_TRAINING_EXECUTOR", "false").lower() == "true":
            # Delegate to TrainingExecutor
            executor = TrainingExecutor(
                config=self.config,
                progress_callback=self.progress_callback,
                cancellation_token=self.cancellation_token,
            )
            return executor.execute(**kwargs)
        else:
            # Original implementation (calls extracted functions)
            return self._original_train(**kwargs)
```

**Testing**:

1. **E2E test with flag OFF** - uses extracted functions directly
2. **E2E test with flag ON** - uses TrainingExecutor
3. **Compare results** - must be identical
4. Commit

**Acceptance Criteria**:

- [ ] Feature flag implemented
- [ ] Both paths tested
- [ ] Results identical
- [ ] **E2E tests pass both ways**

**Estimated**: 1 day

---

### Phase 6: Host Service Integration (1 week)

#### TASK 6.1: Update Host Service to Use Extracted Functions

**Objective**: Host service uses same extracted functions

**Current**: Host service has duplicate logic

**New**: Host service imports and uses extracted functions

**Pattern**: Replace one function at a time, test after each

**Estimated**: 3 days

---

#### TASK 6.2: Add Result Callback Endpoint

**Objective**: Backend can receive results from host service

**Pattern**: Add endpoint, test, commit

**Estimated**: 2 days

---

### Phase 7: Gradual Rollout (3-4 weeks)

**NOW** we do the gradual rollout from migration strategy doc:

- Week 1: Canary (10% with `USE_TRAINING_EXECUTOR=true`)
- Week 2-3: Expanded (50%)
- Week 4: Full (100%)

**Quality Gates**: See [05-migration-strategy.md](./05-migration-strategy.md)

---

### Phase 8: Cleanup (1 week)

- Remove feature flag
- Remove old StrategyTrainer implementation
- Keep only TrainingExecutor

---

## Testing Strategy Summary

### Test Pyramid

```
        E2E Tests (Few, Slow, High Value)
       /                                \
      Integration Tests (Some, Medium)
     /                                  \
    Unit Tests (Many, Fast, Low-Level)
```

### Test Frequency

| Test Type | When to Run | Duration | Purpose |
|-----------|-------------|----------|---------|
| **Unit** | After every change | < 2s | Validate individual functions |
| **Integration** | After every extraction | < 30s | Validate components work together |
| **E2E Training** | After every commit | < 2min | Validate FULL pipeline works |
| **E2E Host** | Before rollout phase | < 5min | Validate host service integration |

### Autonomous Test Execution

```bash
# Developer workflow
./scripts/test-extraction.sh

# This script runs:
# 1. make test-unit
# 2. make test-integration
# 3. make test-e2e-training
# 4. make quality
#
# If ALL pass: "✅ Safe to commit"
# If ANY fail: "❌ Extraction broke something - do NOT commit"
```

### CI/CD Integration

```yaml
# .github/workflows/training-refactoring.yml
name: Training Refactoring Tests

on:
  push:
    branches: [feat/progressive-training-refactor]
    paths:
      - 'ktrdr/training/**'
      - 'tests/**'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run unit tests
        run: make test-unit
      - name: Run integration tests
        run: make test-integration
      - name: Run e2e training tests
        run: make test-e2e-training
      - name: Quality checks
        run: make quality
```

---

## Timeline

| Phase | Duration | Key Milestone | E2E Tests |
|-------|----------|---------------|-----------|
| **Phase 1: Foundation** | 1 week | E2E test infrastructure + 5 extractions | ✅ Pass after EACH |
| **Phase 2: Features** | 1 week | 3 more extractions | ✅ Pass after EACH |
| **Phase 3: Model** | 1 week | 3 extractions + progress integration | ✅ Pass after EACH |
| **Phase 4: Post-Training** | 1 week | 4 extractions | ✅ Pass after EACH |
| **Phase 5: Consolidation** | 1 week | TrainingExecutor created, feature flag added | ✅ Pass both paths |
| **Phase 6: Host Service** | 1 week | Host service uses extracted functions | ✅ Pass local + host |
| **Phase 7: Rollout** | 3-4 weeks | Progressive rollout with monitoring | ✅ Continuous validation |
| **Phase 8: Cleanup** | 1 week | Remove legacy code | ✅ Final validation |
| **Total** | **10-11 weeks** | Truly progressive, always working | ✅ Tested continuously |

---

## Quality Gates

**After EVERY extraction**:

- ✅ Unit tests pass (extracted function)
- ✅ Integration tests pass
- ✅ **E2E training test passes** (CRITICAL - proves nothing broke)
- ✅ Code quality passes
- ✅ No performance regression (< 10% slower)

**Before moving to next phase**:

- ✅ All extractions in phase complete
- ✅ All tests passing
- ✅ Code review approved
- ✅ Documentation updated

**Before rollout phase**:

- ✅ TrainingExecutor produces identical results to StrategyTrainer
- ✅ Host service integration tested
- ✅ Performance benchmarks meet targets
- ✅ Side-by-side comparison validates equivalence

---

## Key Differences from v1.0

| Aspect | v1.0 (WRONG) | v2.0 (CORRECT) |
|--------|--------------|----------------|
| **Approach** | Build everything, then flip switch | Extract one piece at a time |
| **Testing** | Test at end | Test after EVERY extraction |
| **System State** | Broken during development | **Always working** |
| **Rollback** | Revert entire branch | Revert single commit |
| **Validation** | Manual testing | **Automated e2e tests** |
| **Commits** | Few large commits | Many small commits |
| **Risk** | High (big bang) | Low (incremental) |

---

## Success Criteria

- ✅ Every commit leaves system in working state
- ✅ E2E tests run and pass after every extraction
- ✅ Can deploy to production at ANY point (with feature flag)
- ✅ TrainingExecutor produces identical results to StrategyTrainer
- ✅ Host service integration validated automatically
- ✅ Zero production incidents during rollout
- ✅ Clear rollback path at every stage

---

**Status**: Ready for Implementation (TRUE Progressive Refactoring)
**Next**: TASK 1.1 - Create E2E Test Infrastructure
**Remember**: Test continuously, extract incrementally, never break the build
