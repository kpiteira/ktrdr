# Training Service Unified Architecture - Requirements

**Date**: 2025-01-05
**Status**: Requirements Approved
**Priority**: High
**Previous**: [01-analysis.md](./01-analysis.md)
**Next**: [03-architecture.md](./03-architecture.md)

---

## Overview

This document defines the requirements for unifying the KTRDR training architecture into a single, coherent system that eliminates code duplication while supporting both local (Docker container) and remote (host service) execution modes.

---

## R1: Unified Training Executor

**Priority**: CRITICAL
**Goal**: Single source of truth for training logic used by both execution paths.

### Requirements

1.1. **Create TrainingExecutor Class**
   - Location: `ktrdr/training/executor.py`
   - Contains ALL training logic (data loading, indicators, fuzzy, features, labels, training, evaluation, saving)
   - Must be **synchronous** (not async) - current pattern is correct
   - Both backend and host service use the same TrainingExecutor **code/class** (not instance)

1.2. **TrainingExecutor Responsibilities**
   - Data loading via DataManager
   - Indicator calculation via IndicatorEngine
   - Fuzzy membership generation via FuzzyEngine
   - Feature engineering via FuzzyNeuralProcessor
   - Label generation via ZigZagLabeler
   - Model creation via MLPTradingModel
   - Training loop execution via ModelTrainer
   - **Model saving via ModelStorage** ← CRITICAL
   - Result aggregation

1.3. **Design Constraints**
   - Must support both CPU and GPU execution
   - Must accept progress callback for real-time updates
   - Must support cancellation via `CancellationToken`
   - Must use `logger.info()` for all logging (not `print()`)

1.4. **Integration Points**
   - Backend: `LocalTrainingRunner` wraps `TrainingExecutor` via `asyncio.to_thread()`
   - Host Service: Uses `TrainingExecutor` directly (imports from `ktrdr` package)

### Success Criteria

- ✅ Training logic exists in exactly ONE place
- ✅ Zero duplication between backend and host service
- ✅ Both execution paths produce identical results
- ✅ Both paths save models correctly

---

## R2: Logging Standardization and Quality

**Priority**: HIGH
**Goal**: Maintain the quality and structure of backend logging across both execution paths.

### Requirements

2.1. **Technical Standard**
   - All logging uses `logger.info()` / `logger.warning()` / `logger.error()`
   - NO use of `print()` statements
   - Structured log messages with consistent format

2.2. **Quality Standard** (Primary Concern)
   - **Maintain backend's numbered step structure**: "Step 1: Loading market data", "Step 2: Calculating indicators", etc.
   - **Preserve hierarchical progress reporting**: Main steps and indented sub-steps
   - **Detailed progress information**: What's being processed, counts, status
   - **Clear phase transitions**: When moving from one major step to another

2.3. **Example Structure**
   ```python
   logger.info("Step 1: Loading market data for all symbols")
   for symbol in symbols:
       logger.debug(f"  Loading data for {symbol}")
       logger.debug(f"    {symbol}: {data_count} bars loaded")

   logger.info("Step 2: Calculating technical indicators")
   logger.debug(f"  Calculated {len(indicators)} indicators")
   ```

2.4. **Logging Levels**
   - Major steps: `logger.info()`
   - Sub-steps and details: `logger.debug()`
   - Warnings: `logger.warning()`
   - Errors: `logger.error()`

### Success Criteria

- ✅ Both backend and host service produce identical log structure
- ✅ Users can follow training progress clearly in both modes
- ✅ Numbered steps and hierarchy maintained
- ✅ No use of print() statements anywhere

---

## R3: Runtime Execution Mode Selection

**Priority**: HIGH
**Goal**: Flexible execution mode selection with intelligent fallback.

### Requirements

#### R3.1: Default Mode via Environment Variable (Startup)

```bash
# In .env or docker-compose.yml:
TRAINING_DEFAULT_MODE=auto  # Options: "auto" | "local" | "host"
```

**Behavior**:
- `auto`: Intelligently select based on availability and requirements
- `local`: Always use Docker container (CPU)
- `host`: Always use host service (GPU)

#### R3.2: Dynamic Mode Override Endpoint (Runtime)

```python
PUT /api/v1/trainings/config
{
    "default_execution_mode": "host"  # Changes default for future requests
}
```

**Behavior**:
- Changes the system-wide default mode
- Persists until changed again or service restart
- Returns current and previous configuration

#### R3.3: Per-Request Mode Override

```python
POST /api/v1/trainings/start
{
    "symbols": ["EURUSD"],
    "strategy_name": "trend_follower",
    "execution_mode": "auto",  # OPTIONAL - defaults to current system default
    # ... other params
}
```

**Behavior**:
- If `execution_mode` provided: Use that mode for this request only
- If `execution_mode` omitted: Use current system default
- **Does NOT change the system default**

**Note**: "auto" means intelligent selection (see R3.4), not "use current default"

#### R3.4: Intelligent Fallback Logic

```python
class ExecutionModeSelector:
    def select_mode(self, requested: str, require_gpu: bool = False) -> str:
        """
        Selection logic:

        1. If requested == "host":
           - Check host service health
           - If available: return "host"
           - If unavailable AND require_gpu: raise error
           - If unavailable AND !require_gpu: warn + return "local"

        2. If requested == "local":
           - Always return "local"

        3. If requested == "auto":
           - If require_gpu AND host_available: return "host"
           - If require_gpu AND !host_available: raise error
           - If !require_gpu: prefer "local" (faster startup)
        """
```

### Success Criteria

- ✅ Default mode set via environment variable at startup
- ✅ Can change default via API endpoint
- ✅ Can override per request via optional parameter
- ✅ Falls back gracefully when host service unavailable
- ✅ Fails loudly when GPU required but unavailable

---

## R4: Model Persistence & Result Transfer

**Priority**: CRITICAL
**Goal**: Ensure trained models are saved and accessible regardless of execution mode.

### Requirements

#### R4.1: Backend is Source of Truth

- Backend decides where models are stored
- Backend manages model versioning via ModelStorage
- Backend updates strategy status after model saved
- Host service NEVER saves models directly

#### R4.2: Host Service Posts Results Back

**Current flow**:
```
Backend → Host Service: POST /training/start
Backend → Host Service: GET /training/status/{session_id} (polling)
```

**Required new flow**:
```
Backend → Host Service: POST /training/start (with callback_url)
Host Service: Executes training
Host Service → Backend: POST {callback_url} (when complete)
Backend: Saves model using ModelStorage
Backend: Updates strategy status
```

#### R4.3: Training Start Request Enhancement

```python
POST /training/start (to host service)
{
    "session_id": "...",
    "model_configuration": {...},
    "training_configuration": {...},
    "data_configuration": {...},
    "gpu_configuration": {...},
    "callback_url": "http://backend:8000/api/v1/trainings/results"  # NEW
}
```

**Rationale**: With multiple potential training host services, each training request must specify where to send results.

#### R4.4: New Backend Endpoint

```python
@router.post("/trainings/results")
async def receive_training_results(
    session_id: str,
    model_state_dict: bytes,  # Serialized model weights
    training_metrics: dict,
    test_metrics: dict,
    feature_names: list[str],
    feature_importance: dict,
    config: dict,
    per_symbol_metrics: Optional[dict] = None,
):
    """
    Receive training results from host service via HTTP POST.

    Flow:
    1. Validate the session_id matches an active operation
    2. Deserialize the model state dict
    3. Save complete model using ModelStorage.save_model()
    4. Update operation status to "completed"
    5. Update strategy status to "trained"
    6. Return success acknowledgment
    """
```

#### R4.5: Host Service Modification

```python
# In training-host-service/services/training_service.py
async def _run_real_training(self, session: TrainingSession):
    # ... existing training loop ...

    # NEW: After successful training
    # 1. Serialize and compress model (per D2: gzip compression)
    import io
    import gzip
    import base64

    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer)
    model_bytes = buffer.getvalue()

    # Compress with gzip (typical 3-5x reduction)
    compressed_bytes = gzip.compress(model_bytes)
    compressed_b64 = base64.b64encode(compressed_bytes).decode()

    # 2. Extract callback URL from session config
    callback_url = session.config.get("callback_url")
    if not callback_url:
        logger.error("No callback_url provided in config")
        return

    # 3. POST results back to backend with retry (per D1)
    await self._post_results_with_retry(
        callback_url=callback_url,
        session_id=session.session_id,
        model_state_dict_b64=compressed_b64,
        training_metrics={...},
        test_metrics={...},
        feature_names=feature_names,
        feature_importance=feature_importance,
        config=session.config,
    )

async def _post_results_with_retry(self, callback_url: str, **payload):
    """POST results with exponential backoff retry."""
    max_attempts = 3
    backoff = 1.0
    max_backoff = 8.0

    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    callback_url,
                    json={
                        **payload,
                        "compression": "gzip",
                    }
                )
                response.raise_for_status()
                logger.info(f"Results posted successfully: {response.status_code}")
                return
        except httpx.HTTPError as e:
            if attempt >= max_attempts:
                logger.error(
                    f"Failed to post results after {attempt} attempts. "
                    f"Backend may be unavailable."
                )
                # Results remain in session state
            else:
                logger.warning(f"Retry {attempt}/{max_attempts} after {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
```

### Success Criteria

- ✅ Host service receives callback_url in training start request
- ✅ Host service POSTs results to callback_url when training completes
- ✅ Backend receives results and saves model via ModelStorage
- ✅ Strategy status updates to "trained" after model saved
- ✅ Model files exist in `models/{strategy}/{symbol}_{timeframe}_vN/`

---

## R5: Progress Callback Mechanism

**Priority**: MEDIUM
**Goal**: Unified progress tracking interface that works differently in each execution mode.

### Requirements

5.1. **Unified Callback Interface**

TrainingExecutor accepts a progress callback with consistent signature:

```python
def progress_callback(phase: str, message: str, **details):
    """
    Called during training to report progress.

    Args:
        phase: Training phase ("data_loading", "training", "evaluating", etc.)
        message: Human-readable progress message
        **details: Additional structured data (epoch, loss, accuracy, etc.)
    """
```

5.2. **Execution Mode-Specific Implementations**

The callback does **different things** depending on execution mode:

**Local Mode**:
```python
def local_progress_callback(phase, message, **details):
    # Update backend's GenericProgressManager (already exists)
    progress_manager.update(phase=phase, message=message, **details)
    # This updates the operation status in OperationsService
```

**Host Service Mode**:
```python
def host_progress_callback(phase, message, **details):
    # Update TrainingSession state (host service internal state)
    session.update_progress(phase=phase, message=message, **details)
    # This state is polled by backend via GET /training/status/{session_id}
```

5.3. **Key Difference**

- **Local mode**: Progress updates go directly to OperationsService
- **Host service mode**: Progress updates go to host service session state, which backend polls

This is necessary because:
- Local execution happens in backend's process (direct access to OperationsService)
- Host service execution happens remotely (backend must poll for updates)

### Success Criteria

- ✅ TrainingExecutor accepts progress callback
- ✅ Local mode updates backend's OperationsService directly
- ✅ Host service mode updates session state for polling
- ✅ Both modes provide same progress information to users

---

## Dependencies and Assumptions

### Dependencies

1. **Host Service Must Install ktrdr Package**
   - To use TrainingExecutor, DataManager, IndicatorEngine, etc.
   - Already true in current implementation

2. **HTTP Communication**
   - Backend → Host Service: Already established
   - Host Service → Backend: NEW requirement for result posting

3. **Model Serialization**
   - Must serialize PyTorch model state dicts
   - Use standard torch.save() / torch.load()

### Assumptions

1. **Single Backend Instance**
   - Callback URL points to single backend API
   - Future: Could support load-balanced backends

2. **Network Reliability**
   - Host service can reliably POST to backend
   - Retries may be needed for network failures

3. **Security**
   - Backend trusts host service (both on localhost initially)
   - Future: Authentication/authorization may be needed

---

## Success Criteria (Overall)

The unified architecture is successful when:

1. ✅ **Zero Code Duplication**: Training logic exists in ONE place (`TrainingExecutor`)
2. ✅ **Both Paths Save Models**: Local and host service both result in saved models via `ModelStorage`
3. ✅ **Strategies Show "Trained"**: After successful training, `/strategies/` endpoint shows `status="trained"`
4. ✅ **Logging Quality Maintained**: Both execution paths produce structured, numbered progress logs
5. ✅ **Runtime Mode Selection**: Users can choose execution mode per request with optional parameter
6. ✅ **Intelligent Fallback**: System auto-selects local if host service unavailable
7. ✅ **Result Transfer Works**: Host service successfully POSTs trained models back to backend

---

## Design Decisions (Approved)

### D1: Error Handling for Result Posting

**Decision**: Retry with exponential backoff + log errors

If host service completes training but fails to POST results to backend:

1. **Retry with exponential backoff** (up to 3 attempts)
   - Initial retry delay: 1 second
   - Backoff multiplier: 2x
   - Max retry delay: 8 seconds

2. **Log error as backend availability issue** after all retries fail
   - Host service logs the failure
   - Keeps results in session state (available via GET /status)
   - Backend can detect timeout and query status endpoint

**Rationale**: Network issues are transient; retries solve most cases. If backend is truly down, it's a backend problem, not training failure.

### D2: Model Size Limits

**Decision**: Compress models with gzip before POSTing

Implementation:
```python
import gzip
import base64

# Serialize and compress
model_bytes = torch.save(model.state_dict(), ...)
compressed = gzip.compress(model_bytes)
compressed_b64 = base64.b64encode(compressed).decode()

# POST to backend
await client.post(callback_url, json={
    "model_state_dict_b64": compressed_b64,
    "compression": "gzip",  # Tell backend to decompress
    ...
})
```

**Rationale**: Simple, effective, widely supported. Typical compression ratio: 3-5x reduction.

---

**Status**: Requirements Approved
**Next**: Create architecture design document
