# Training Service Architecture - Problem Analysis

**Date**: 2025-01-05
**Status**: Analysis Complete
**Next**: Requirements Definition

---

## Executive Summary

Analysis of the KTRDR training service reveals **four critical architectural issues** that impact training reliability, code maintainability, and user experience. This document focuses on **analysis only** - requirements and solutions are in separate documents.

---

## Issue #1: Logging Quality and Consistency

### Current State

**Backend Training** ([ktrdr/training/train_strategy.py](ktrdr/training/train_strategy.py)):
- Uses `print()` statements for progress output
- **Well-structured numbered steps**: "1. Loading market data...", "2. Calculating indicators...", etc.
- Clear hierarchical progress with indented sub-steps
- Detailed information about what's happening at each stage
- Example:
  ```python
  print("\n1. Loading market data for all symbols...")
  for symbol in symbols:
      print(f"  Loading data for {symbol}...")
      print(f"    {symbol}: {data_count} bars")
  ```

**Host Service Training** ([training-host-service/services/training_service.py](training-host-service/services/training_service.py)):
- Uses `logger.info()` for logging
- **Generic, unstructured messages**: "Starting training for session {session_id}"
- No clear step numbering or hierarchy
- Progress tracking exists via `session.update_progress()` but not reflected in logs
- Example:
  ```python
  logger.info(f"Starting training for session {session.session_id}")
  logger.info(f"Total training data points: {total_data_points}")
  ```

### Impact Analysis

1. **Visibility Gap**: Backend provides clear, structured progress; host service provides generic messages
2. **User Experience**: Users see detailed step-by-step progress locally but minimal information remotely
3. **Debugging Difficulty**: Different log formats make it hard to correlate issues between execution paths
4. **Quality Regression**: Host service logs are objectively worse quality than backend logs

### Root Cause

The host service was developed as a separate service without adopting the backend's well-designed logging structure. The focus was on technical implementation (session management, GPU access) rather than maintaining the user-facing quality of progress reporting.

---

## Issue #2: Code Duplication

### Quantitative Analysis

| Aspect | Backend ([train_strategy.py](ktrdr/training/train_strategy.py)) | Host Service ([training_service.py](training-host-service/services/training_service.py)) |
|--------|---------------------------|--------------------------------|
| **Lines of Code** | ~1,500 lines | ~1,000 lines |
| **Data Loading** | Uses DataManager directly | Reimplements with DataManager |
| **Indicators** | Uses IndicatorEngine | Reimplements with IndicatorEngine |
| **Fuzzy Logic** | Uses FuzzyEngine | Reimplements with FuzzyEngine |
| **Feature Engineering** | Uses FuzzyNeuralProcessor | Simplified feature preparation |
| **Labels** | Uses ZigZagLabeler | Simplified label generation |
| **Training Loop** | Uses ModelTrainer class | Custom training loop |
| **Model Saving** | ✅ Calls ModelStorage.save_model() | ❌ Does NOT save models |
| **Progress Tracking** | print() statements | session.update_progress() |
| **GPU Support** | CPU fallback | GPU-first with MPS/CUDA detection |

### Duplication Breakdown

**Identical Logic (~80% duplication)**:
1. Data loading workflow
2. Indicator calculation sequence
3. Fuzzy membership generation
4. Feature engineering approach
5. Label generation strategy
6. Basic training loop structure

**Different Implementations**:
1. **Model Training**:
   - Backend: Uses `ModelTrainer` class with proper structure
   - Host: Custom loop directly in `_run_real_training()`

2. **Model Saving** (CRITICAL):
   - Backend: Line 495 calls `self.model_storage.save_model(...)`
   - Host: NO model saving code exists

3. **GPU Handling**:
   - Backend: CPU-only (Docker limitation)
   - Host: MPS/CUDA detection with fallback

### Impact Analysis

1. **Maintenance Burden**: Bug fixes and features must be implemented twice
2. **Divergence Risk**: Already diverged on model saving; will continue to drift
3. **Testing Overhead**: Need separate test suites for identical logic
4. **Quality Inconsistency**: Backend uses proper abstractions (ModelTrainer), host has ad-hoc code

---

## Issue #3: Rigid Service Selection

### Current Implementation

Service selection happens at **initialization time** via environment variables:

**Configuration Location**: [ktrdr/training/training_manager.py:43](ktrdr/training/training_manager.py#L43)

```python
def _initialize_training_adapter(self) -> TrainingAdapter:
    env_enabled = os.getenv("USE_TRAINING_HOST_SERVICE", "").lower()

    if env_enabled in ("true", "1", "yes"):
        use_host_service = True
        host_service_url = os.getenv("TRAINING_HOST_SERVICE_URL", "http://localhost:5002")
    else:
        use_host_service = False
        host_service_url = None

    return TrainingAdapter(use_host_service=use_host_service, ...)
```

### Limitations

1. **No Runtime Override**: Cannot choose execution mode per training request
2. **No Dynamic Switching**: Requires container restart to change modes
3. **No Fallback**: If host service is down, training fails instead of falling back to local
4. **No User Control**: API clients cannot specify their preference
5. **No Health Awareness**: Doesn't check if host service is actually available

### Current Behavior

```
Startup:
  ├─ Read USE_TRAINING_HOST_SERVICE env var
  ├─ Create TrainingAdapter(use_host_service=True/False)
  └─ LOCKED for lifetime of process

Training Request:
  ├─ Uses whatever mode was set at startup
  ├─ No ability to override
  └─ No fallback if chosen mode fails
```

---

## Issue #4: Model Persistence Failure (CRITICAL)

### The Problem

**Observed Behavior**: Host service training completes successfully (100 epochs, good metrics) but strategies remain marked as "untrained" in the UI.

### Root Cause Analysis

#### 1. Host Service Missing Save Step

**Evidence**: [training-host-service/services/training_service.py](training-host-service/services/training_service.py)
- Method `_run_real_training()` runs complete training loop
- Updates progress and metrics ✅
- **Never imports ModelStorage** ❌
- **Never calls save_model()** ❌
- Model exists in memory, then is discarded when session ends

Search results for "ModelStorage" in host service: **0 matches**
Search results for "save_model" in host service: **0 matches**

#### 2. Strategy Status Determination

**Location**: [ktrdr/api/endpoints/strategies.py:119-122](ktrdr/api/endpoints/strategies.py#L119)

```python
all_models = model_storage.list_models(strategy_name)

if all_models:
    training_status = "trained"
```

**Logic**: Checks `models/` directory for saved model files. Since host service never saves, directory is empty, status stays "untrained".

#### 3. Backend Does Save (Correctly)

**Location**: [ktrdr/training/train_strategy.py:495](ktrdr/training/train_strategy.py#L495)

```python
model_path = self.model_storage.save_model(
    model=model,
    strategy_name=strategy_name,
    symbol=symbol,
    timeframe=primary_timeframe,
    config=model_config,
    training_metrics=training_results,
    feature_names=feature_names,
    feature_importance=feature_importance,
    scaler=feature_scaler,
)
```

Backend training works correctly because it includes this save step.

### Actual Execution Flow

```
User Request:
  └─> POST /trainings/start
       └─> TrainingService.start_training()
           └─> Execution mode = "host" (via env var)
               └─> HostSessionManager.run()
                   └─> POST to host service /training/start
                       └─> Host service creates session
                           └─> _run_real_training() executes
                               ├─ Loads data ✅
                               ├─ Calculates indicators ✅
                               ├─ Generates fuzzy memberships ✅
                               ├─ Engineers features ✅
                               ├─ Generates labels ✅
                               ├─ Trains model (100 epochs) ✅
                               ├─ Updates metrics ✅
                               └─ Returns success ✅
                           ❌ Model NOT saved to disk
                           ❌ Model discarded
                       ← Backend receives "completed" status
                   ← HostSessionManager polls until complete
               ← Backend updates operation status
           ← Training marked successful
       ← User notified: training complete

User checks strategy status:
  └─> GET /strategies/
       └─> ModelStorage.list_models(strategy_name)
           └─> Checks models/{strategy}/
               ❌ Directory empty or nonexistent
           ← Returns []
       ← Strategy status = "untrained"
```

### Impact

1. **User Confusion**: Training shows "success" but strategy shows "untrained"
2. **Wasted Resources**: GPU time spent training models that are discarded
3. **Broken Workflow**: Cannot proceed to backtesting or deployment
4. **Data Loss**: Training metrics and model weights lost

---

## System Architecture Overview

### Current Flow (Dual Implementation)

```
┌─────────────────────────────────────────────────────────────────┐
│ API Layer                                                        │
│  POST /trainings/start                                          │
│  └─> TrainingService.start_training()                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Service Orchestration Layer                                      │
│  TrainingService (ServiceOrchestrator)                          │
│  ├─ TrainingManager                                             │
│  └─ TrainingAdapter (reads env var at init)                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
┌───────────────────────────┐    ┌──────────────────────────────┐
│ Local Training Path       │    │ Host Service Path            │
│ (Docker Container)        │    │ (Native - Port 5002)         │
│                           │    │                              │
│ LocalTrainingRunner       │    │ HostSessionManager           │
│ └─> StrategyTrainer       │    │ └─> HTTP POST /training/start│
│     └─> train_strategy.py│    │     └─> training_service.py  │
│         (1,500 lines)     │    │         (1,000 lines)        │
│                           │    │                              │
│ ✅ Saves to ModelStorage │    │ ❌ Does NOT save models      │
└───────────────────────────┘    └──────────────────────────────┘
```

### Result Flow Analysis

**Current Backend → Host Service Communication**:

1. **Start Training**:
   ```
   Backend → Host Service: POST /training/start
   Response: {"session_id": "...", "status": "started"}
   ```

2. **Poll Status** (repeatedly):
   ```
   Backend → Host Service: GET /training/status/{session_id}
   Response: {
     "status": "running",
     "progress": {"epoch": 50, "total_epochs": 100, ...},
     "metrics": {"current": {...}, "best": {...}}
   }
   ```

3. **Final Status**:
   ```
   Backend → Host Service: GET /training/status/{session_id}
   Response: {
     "status": "completed",
     "metrics": {...}
   }
   ```

**What's Missing**: No mechanism to retrieve trained model or persist it.

---

## Technical Findings

### Docker GPU Access Investigation

**Test Results**:
```bash
# Host machine (macOS):
$ python -c "import torch; print(torch.backends.mps.is_available())"
> True  # MPS available natively

# Docker container:
$ docker exec ktrdr-backend python -c "import torch; print(torch.backends.mps.is_available())"
> False  # MPS NOT available in Docker

# Docker PyTorch version:
$ docker exec ktrdr-backend python -c "import torch; print(torch.__version__)"
> 2.8.0+cpu  # CPU-only build
```

**Conclusion**: Docker on macOS runs in a Linux VM and cannot access Metal/MPS. Host service architecture is **necessary** for GPU acceleration on Mac.

### Async/Sync Pattern Analysis

**Current Implementation** ([ktrdr/api/services/training/local_runner.py:41](ktrdr/api/services/training/local_runner.py#L41)):

```python
async def run(self) -> dict[str, Any]:
    """Run the synchronous training workflow in a worker thread."""
    raw_result = await asyncio.to_thread(self._execute_training)
    # ...

def _execute_training(self) -> dict[str, Any]:
    # Calls synchronous StrategyTrainer.train_multi_symbol_strategy()
    return self._trainer.train_multi_symbol_strategy(...)
```

**Pattern**:
- Training logic is **synchronous** (StrategyTrainer has no `async def`)
- Wrapped via `asyncio.to_thread()` for async API compatibility
- This is architecturally correct

---

## File References

### Critical Files Analyzed

1. **[ktrdr/training/train_strategy.py](ktrdr/training/train_strategy.py)** (~1,500 lines)
   - Backend training implementation
   - Uses print() for progress
   - Saves models via ModelStorage ✅

2. **[training-host-service/services/training_service.py](training-host-service/services/training_service.py)** (~1,000 lines)
   - Host service training implementation
   - Uses logger for progress
   - Does NOT save models ❌

3. **[ktrdr/training/training_manager.py](ktrdr/training/training_manager.py)**
   - Initializes TrainingAdapter based on env vars
   - No runtime mode selection

4. **[ktrdr/api/endpoints/strategies.py](ktrdr/api/endpoints/strategies.py)**
   - Determines training status by checking ModelStorage
   - Correctly shows "untrained" when models missing

5. **[ktrdr/training/model_storage.py](ktrdr/training/model_storage.py)**
   - Handles model persistence and versioning
   - Used by backend ✅, NOT used by host service ❌

---

## Summary of Findings

### Critical Issues (Must Fix)

1. **Model Persistence Failure**: Host service training succeeds but models not saved
2. **Code Duplication**: 80% of training logic duplicated across two implementations

### Important Issues (Should Fix)

3. **Logging Quality Degradation**: Host service logs are less detailed/structured than backend
4. **Rigid Service Selection**: No runtime override or fallback mechanism

### Technical Constraints (Design Considerations)

5. **Docker Cannot Access GPU**: Host service architecture required for GPU on Mac
6. **Sync Training Pattern**: Current async wrapping pattern is correct

---

**Status**: Analysis Complete
**Next Document**: [02-requirements.md](./02-requirements.md)
