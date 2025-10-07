# Training Architecture Interface Contracts

## Overview

This document specifies the **exact interfaces** for all training components. These contracts are **immutable** - any changes require careful consideration of downstream impacts.

**Purpose**: Prevent signature mismatches, ensure consistent behavior, enable safe refactoring.

**Key Principle**: Interfaces are contracts. Break them at your own peril.

---

## Table of Contents

1. [TrainingExecutor Interface](#trainingexecutor-interface)
2. [Progress Callback Interface](#progress-callback-interface)
3. [CancellationToken Interface](#cancellationtoken-interface)
4. [ExecutionModeSelector Interface](#executionmodeselector-interface)
5. [TrainingResult Interface](#trainingresult-interface)
6. [Host Service API Contract](#host-service-api-contract)
7. [Backend Callback API Contract](#backend-callback-api-contract)

---

## TrainingExecutor Interface

### Class Definition

```python
from typing import Any, Callable, Optional
from ktrdr.async_infrastructure.cancellation import CancellationToken

ProgressCallbackType = Callable[[int, int, dict[str, float]], None]

class TrainingExecutor:
    """
    Environment-agnostic training executor.

    This is the core training implementation that consolidates logic from
    StrategyTrainer and host service. It has ZERO knowledge of where it runs
    (local vs host vs cloud).

    Key Design Decisions:
    - Progress callback signature matches ModelTrainer exactly (no adapters)
    - Cancellation token checked frequently (<100ms latency)
    - All steps logged with structured format
    - Hardware detection automatic (MPS > CUDA > CPU)
    """

    def __init__(
        self,
        config: dict[str, Any],
        progress_callback: Optional[ProgressCallbackType] = None,
        cancellation_token: Optional[CancellationToken] = None,
        model_storage: Optional["ModelStorage"] = None,
    ) -> None:
        """
        Initialize training executor.

        Args:
            config: Training configuration dict with keys:
                - strategy_config: Strategy parameters
                - training_config: Training hyperparameters (epochs, batch_size, etc.)
                - model_config: Model architecture parameters
            progress_callback: Optional callback for progress updates.
                Signature MUST match ModelTrainer: (epoch: int, total_epochs: int, metrics: dict)
            cancellation_token: Optional token for cancellation support
            model_storage: Optional model storage (defaults to global instance)

        Raises:
            ValueError: If config missing required keys
        """

    def execute(
        self,
        symbols: list[str],
        timeframes: list[str],
        start_date: str,
        end_date: str,
        validation_split: float = 0.2,
        data_mode: str = "local",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Execute complete training pipeline.

        This is the main entry point. It orchestrates:
        1. Data loading
        2. Indicator calculation
        3. Fuzzy member generation
        4. Feature engineering
        5. Label generation
        6. Train/test split
        7. Model creation
        8. Model training (with progress callbacks)
        9. Model evaluation
        10. Feature importance calculation
        11. Model saving
        12. Result building

        Args:
            symbols: List of trading symbols (e.g., ["EURUSD", "GBPUSD"])
            timeframes: List of timeframes (e.g., ["1h", "4h"])
            start_date: Training start date (format: "YYYY-MM-DD")
            end_date: Training end date (format: "YYYY-MM-DD")
            validation_split: Fraction of data for validation (default: 0.2)
            data_mode: Data source mode ("local", "ib", "csv")
            **kwargs: Additional parameters (reserved for future use)

        Returns:
            dict with keys:
                - success: bool
                - model_path: str (path to saved model)
                - model_id: str (unique model identifier)
                - training_metrics: dict (loss, accuracy over epochs)
                - test_metrics: dict (final test performance)
                - feature_names: list[str]
                - feature_importance: dict[str, float]
                - config: dict (full training configuration)
                - metadata: dict (execution details)

        Raises:
            CancellationError: If cancellation requested
            TrainingError: If training fails (data, model, convergence issues)
            ValueError: If parameters invalid

        Thread Safety:
            - This method is synchronous and NOT thread-safe
            - Call from async context using: await asyncio.to_thread(executor.execute, ...)
            - Progress callback invoked on calling thread

        Cancellation:
            - Cancellation token checked every batch (<100ms latency)
            - Raises CancellationError immediately when cancelled
            - Partial state may be saved (implementation detail)
        """
```

### Method Signatures (Private)

```python
# These are implementation details but documented for consistency

def _detect_device(self) -> str:
    """Detect best available hardware: 'mps' > 'cuda' > 'cpu'"""

def _load_data(
    self,
    symbols: list[str],
    timeframes: list[str],
    start_date: str,
    end_date: str,
    data_mode: str,
) -> dict[str, Any]:
    """Load market data for symbols and timeframes."""

def _calculate_indicators(
    self,
    data: dict[str, Any],
    strategy_config: dict[str, Any],
) -> dict[str, Any]:
    """Calculate technical indicators based on strategy config."""

def _generate_fuzzy(
    self,
    data: dict[str, Any],
    strategy_config: dict[str, Any],
) -> dict[str, Any]:
    """Generate fuzzy membership values for indicators."""

def _engineer_features(
    self,
    data: dict[str, Any],
) -> tuple[np.ndarray, list[str]]:
    """Engineer features from indicators and fuzzy values."""

def _generate_labels(
    self,
    data: dict[str, Any],
    strategy_config: dict[str, Any],
) -> np.ndarray:
    """Generate training labels based on strategy logic."""

def _split_data(
    self,
    X: np.ndarray,
    y: np.ndarray,
    validation_split: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Split data into train/test sets."""

def _create_model(
    self,
    input_dim: int,
    model_config: dict[str, Any],
) -> torch.nn.Module:
    """Create PyTorch model based on config."""

def _train_model(
    self,
    model: torch.nn.Module,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    training_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Train model and return metrics.

    CRITICAL: Progress callback passed UNCHANGED to ModelTrainer.
    No adapter, no wrapper, exact signature preservation.
    """

def _evaluate_model(
    self,
    model: torch.nn.Module,
    X_test: np.ndarray,
    y_test: np.ndarray,
) -> dict[str, float]:
    """Evaluate model on test set."""

def _calculate_importance(
    self,
    model: torch.nn.Module,
    X_test: np.ndarray,
    y_test: np.ndarray,
    feature_names: list[str],
) -> dict[str, float]:
    """Calculate feature importance using permutation."""

def _save_model(
    self,
    model: torch.nn.Module,
    config: dict[str, Any],
    metadata: dict[str, Any],
) -> str:
    """Save model via ModelStorage and return path."""

def _build_results(
    self,
    model_path: str,
    model_id: str,
    training_metrics: dict[str, Any],
    test_metrics: dict[str, float],
    feature_names: list[str],
    feature_importance: dict[str, float],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Build standardized result dictionary."""
```

---

## Progress Callback Interface

### Signature

```python
ProgressCallbackType = Callable[[int, int, dict[str, float]], None]

def progress_callback(
    epoch: int,
    total_epochs: int,
    metrics: dict[str, float],
) -> None:
    """
    Progress callback invoked during training.

    CRITICAL CONTRACT: This signature MUST match ModelTrainer exactly.
    Never create adapters or wrappers that change this signature.

    Args:
        epoch: Current epoch number (1-indexed)
        total_epochs: Total number of epochs
        metrics: Training metrics for current epoch
            - train_loss: float
            - train_accuracy: float
            - val_loss: float (if validation enabled)
            - val_accuracy: float (if validation enabled)
            - learning_rate: float (current LR)
            - batch_time: float (avg time per batch in seconds)

    Returns:
        None

    Frequency:
        - Called once per epoch (after epoch completes)
        - Called once per N batches (adaptive throttling, target ~300ms intervals)

    Thread Safety:
        - Invoked on training thread (same thread as execute())
        - Callback must be thread-safe if updating shared state

    Error Handling:
        - Exceptions in callback are caught and logged
        - Training continues despite callback errors
        - Do NOT raise exceptions in callback

    Example Usage:
        def my_callback(epoch: int, total_epochs: int, metrics: dict[str, float]) -> None:
            print(f"Epoch {epoch}/{total_epochs}: loss={metrics['train_loss']:.4f}")

        executor = TrainingExecutor(
            config=config,
            progress_callback=my_callback,  # Direct pass-through, no wrapper
        )
    """
```

### Common Pitfalls

```python
# ❌ WRONG - Creating adapter that changes signature
def wrapper_callback(epoch, total_epochs, metrics):
    # This changes the signature downstream!
    bridge.on_progress("training", f"Epoch {epoch}", epoch=epoch, ...)

trainer = ModelTrainer(progress_callback=wrapper_callback)  # BREAKS!

# ✅ CORRECT - Pass through unchanged
trainer = ModelTrainer(progress_callback=original_callback)

# ✅ CORRECT - If you need adaptation, do it OUTSIDE ModelTrainer
def my_callback(epoch, total_epochs, metrics):
    # Original signature preserved for ModelTrainer
    bridge.on_progress(...)  # Adaptation happens here

executor = TrainingExecutor(progress_callback=my_callback)
```

---

## CancellationToken Interface

### Protocol Definition

```python
from typing import Protocol

class CancellationToken(Protocol):
    """
    Protocol for cancellation support.

    This is a runtime protocol - any object implementing these methods
    can be used as a cancellation token.

    Design Philosophy:
    - Check frequently (<100ms latency requirement)
    - Lightweight check (is_cancelled property)
    - Cooperative cancellation (callee checks, caller cancels)
    """

    def is_cancelled(self) -> bool:
        """
        Check if cancellation has been requested.

        MUST be a lightweight operation (<1ms).
        Called frequently (every batch, every epoch).

        Returns:
            True if cancellation requested, False otherwise
        """

    def cancel(self, reason: str = "Operation cancelled") -> None:
        """
        Request cancellation.

        This is non-blocking - just sets a flag.
        Actual cancellation happens when is_cancelled() checked.

        Args:
            reason: Human-readable cancellation reason (for logging)
        """

    async def wait_for_cancellation(self) -> None:
        """
        Async wait until cancellation requested.

        Used for monitoring tasks that should stop when cancelled.

        Example:
            async def monitor():
                await token.wait_for_cancellation()
                print("Cancelled!")
        """

    @property
    def is_cancelled_requested(self) -> bool:
        """
        Property alias for is_cancelled().

        Some code prefers property syntax.
        MUST return same value as is_cancelled().
        """
```

### Usage Pattern

```python
# In TrainingExecutor.execute():
for epoch in range(1, total_epochs + 1):
    # Check at start of each epoch
    if self.cancellation_token and self.cancellation_token.is_cancelled():
        raise CancellationError(f"Training cancelled at epoch {epoch}")

    for batch_idx, (X_batch, y_batch) in enumerate(train_loader):
        # Check frequently during epoch (adaptive stride)
        if batch_idx % batch_stride == 0:
            if self.cancellation_token and self.cancellation_token.is_cancelled():
                raise CancellationError(f"Training cancelled at batch {batch_idx}")

        # ... training step ...
```

### Implementation Example

```python
import asyncio
from dataclasses import dataclass

@dataclass
class SimpleCancellationToken:
    """Simple implementation of CancellationToken protocol."""

    _cancelled: bool = False
    _reason: str = ""

    def is_cancelled(self) -> bool:
        return self._cancelled

    def cancel(self, reason: str = "Operation cancelled") -> None:
        self._cancelled = True
        self._reason = reason

    async def wait_for_cancellation(self) -> None:
        while not self._cancelled:
            await asyncio.sleep(0.1)

    @property
    def is_cancelled_requested(self) -> bool:
        return self._cancelled
```

---

## ExecutionModeSelector Interface

### Class Definition

```python
from typing import Literal

ExecutionMode = Literal["local", "host", "auto"]

class ExecutionModeSelector:
    """
    Intelligent execution mode selection with health checks and fallback.

    Decides where training should run based on:
    - User preference (requested_mode)
    - GPU requirements
    - Host service availability
    - System capabilities
    """

    def __init__(
        self,
        default_mode: ExecutionMode = "auto",
        host_service_url: str = "http://localhost:5002",
        health_check_timeout: float = 2.0,
    ) -> None:
        """
        Initialize mode selector.

        Args:
            default_mode: Default mode when not specified ("auto", "local", "host")
            host_service_url: URL of training host service
            health_check_timeout: Timeout for health checks in seconds
        """

    async def select_mode(
        self,
        requested_mode: Optional[ExecutionMode] = None,
        require_gpu: bool = False,
    ) -> ExecutionMode:
        """
        Select execution mode intelligently.

        Selection Logic:
        1. If requested_mode == "local": return "local"
        2. If requested_mode == "host":
           a. Health check host service
           b. If available: return "host"
           c. If unavailable and require_gpu: raise ExecutionModeError
           d. If unavailable and not require_gpu: return "local" (fallback)
        3. If requested_mode == "auto":
           a. Check if GPU required
           b. Health check host service
           c. Select best available mode

        Args:
            requested_mode: User-requested mode (None = use default)
            require_gpu: Whether GPU is required for this training

        Returns:
            Selected mode: "local" or "host"

        Raises:
            ExecutionModeError: If GPU required but host unavailable

        Examples:
            # Simple local execution
            mode = await selector.select_mode("local")
            assert mode == "local"

            # Host with fallback
            mode = await selector.select_mode("host", require_gpu=False)
            # Returns "host" if available, "local" otherwise

            # GPU required, no fallback
            try:
                mode = await selector.select_mode("host", require_gpu=True)
            except ExecutionModeError:
                print("Host unavailable and GPU required - cannot proceed")
        """

    async def _is_host_available(self) -> bool:
        """
        Health check host service.

        Returns:
            True if host service healthy, False otherwise

        Implementation:
            - GET {host_service_url}/health
            - Timeout: self.health_check_timeout
            - Success: status_code == 200
        """

    def set_default_mode(self, mode: ExecutionMode) -> None:
        """
        Update default execution mode.

        Args:
            mode: New default mode

        Raises:
            ValueError: If mode not in ("auto", "local", "host")
        """
```

---

## TrainingResult Interface

### Result Dictionary Structure

```python
TrainingResult = dict[str, Any]  # Structure defined below

def execute(...) -> TrainingResult:
    """
    Returns a standardized result dictionary.

    REQUIRED KEYS (always present):
    {
        "success": bool,              # True if training completed
        "model_path": str,            # Path to saved model file
        "model_id": str,              # Unique model identifier (UUID)
        "training_metrics": {         # Metrics during training
            "epochs": list[int],      # [1, 2, 3, ...]
            "train_loss": list[float],# Loss per epoch
            "train_accuracy": list[float],  # Accuracy per epoch
            "val_loss": list[float],  # Validation loss per epoch
            "val_accuracy": list[float],    # Validation accuracy per epoch
        },
        "test_metrics": {             # Final test set metrics
            "loss": float,            # Test loss
            "accuracy": float,        # Test accuracy
            "precision": float,       # Precision (if classification)
            "recall": float,          # Recall (if classification)
            "f1_score": float,        # F1 score (if classification)
        },
        "feature_names": list[str],   # List of feature names
        "feature_importance": dict[str, float],  # Feature importance scores
        "config": {                   # Full training configuration
            "strategy_config": dict,  # Strategy parameters
            "training_config": dict,  # Training hyperparameters
            "model_config": dict,     # Model architecture
            "data_config": dict,      # Data loading configuration
        },
        "metadata": {                 # Execution metadata
            "start_time": str,        # ISO 8601 timestamp
            "end_time": str,          # ISO 8601 timestamp
            "duration_seconds": float,# Total training time
            "device": str,            # "cpu", "mps", "cuda"
            "symbols": list[str],     # Training symbols
            "timeframes": list[str],  # Training timeframes
            "start_date": str,        # Training start date
            "end_date": str,          # Training end date
            "total_samples": int,     # Total data samples
            "training_samples": int,  # Training set size
            "test_samples": int,      # Test set size
        },
    }

    OPTIONAL KEYS (may be present):
    {
        "error": str,                 # Error message if success=False
        "warnings": list[str],        # Non-fatal warnings
        "checkpoints": list[str],     # Saved checkpoint paths
        "early_stopped": bool,        # Whether early stopping triggered
        "early_stop_epoch": int,      # Epoch where early stopping occurred
    }
    """
```

### Validation

```python
def validate_training_result(result: dict[str, Any]) -> bool:
    """
    Validate training result structure.

    Raises:
        ValueError: If result missing required keys or invalid structure
    """
    required_keys = {
        "success", "model_path", "model_id", "training_metrics",
        "test_metrics", "feature_names", "feature_importance",
        "config", "metadata"
    }

    missing = required_keys - set(result.keys())
    if missing:
        raise ValueError(f"Training result missing keys: {missing}")

    if not isinstance(result["success"], bool):
        raise ValueError("success must be bool")

    if result["success"] and not result["model_path"]:
        raise ValueError("model_path required when success=True")

    # ... additional validation ...

    return True
```

---

## Host Service API Contract

### POST /training/start

**Request**:
```python
{
    "model_configuration": {
        "strategy_config": str,       # Strategy name or path
        "symbols": list[str],         # Trading symbols
        "timeframes": list[str],      # Timeframes
        "model_type": str,            # "mlp", "lstm", "transformer"
        "multi_symbol": bool,         # Multi-symbol training
    },
    "training_configuration": {
        "validation_split": float,    # 0.0-1.0
        "start_date": str,            # "YYYY-MM-DD"
        "end_date": str,              # "YYYY-MM-DD"
        "data_mode": str,             # "local", "ib", "csv"
        "epochs": int,                # Optional: default from strategy
        "batch_size": int,            # Optional: default from strategy
        "learning_rate": float,       # Optional: default from strategy
    },
    "data_configuration": {
        "symbols": list[str],         # Same as model_configuration
        "timeframes": list[str],      # Same as model_configuration
        "data_source": str,           # Same as data_mode
    },
    "gpu_configuration": {
        "enable_gpu": bool,           # Whether to use GPU
        "memory_fraction": float,     # GPU memory fraction (0.0-1.0)
        "mixed_precision": bool,      # Use mixed precision training
    },
    "callback_url": str,              # OPTIONAL: URL to POST results (NEW)
}
```

**Response** (immediate):
```python
{
    "session_id": str,                # Unique session identifier
    "status": "queued",               # Initial status
    "message": str,                   # Human-readable message
}
```

**Status Codes**:
- `200 OK`: Training session created
- `400 Bad Request`: Invalid configuration
- `500 Internal Server Error`: Server error

---

### GET /training/status/{session_id}

**Response**:
```python
{
    "session_id": str,
    "status": str,                    # "queued", "running", "completed", "failed", "stopped", "cancelled"
    "progress": {
        "current_epoch": int,         # Current epoch (1-indexed)
        "total_epochs": int,          # Total epochs
        "current_batch": int,         # Current batch within epoch
        "total_batches": int,         # Total batches per epoch
        "elapsed_time": float,        # Seconds since start
        "estimated_remaining": float, # Estimated seconds remaining
    },
    "metrics": {
        "train_loss": float,          # Current training loss
        "train_accuracy": float,      # Current training accuracy
        "val_loss": float,            # Current validation loss
        "val_accuracy": float,        # Current validation accuracy
    },
    "resource_usage": {               # Optional: system resource usage
        "gpu_used": bool,
        "gpu_name": str,
        "gpu_utilization_percent": float,
        "gpu_memory_used_mb": float,
        "gpu_memory_total_mb": float,
    },
    "result": dict | None,            # TrainingResult (if status == "completed")
    "error": str | None,              # Error message (if status == "failed")
}
```

**Status Codes**:
- `200 OK`: Status retrieved
- `404 Not Found`: Session not found

---

### POST /training/stop

**Request**:
```python
{
    "session_id": str,
    "save_checkpoint": bool,          # Whether to save checkpoint before stopping
}
```

**Response**:
```python
{
    "session_id": str,
    "status": "stopped",              # New status
    "message": str,
    "checkpoint_path": str | None,    # If save_checkpoint=True
}
```

**Status Codes**:
- `200 OK`: Stop request accepted
- `404 Not Found`: Session not found
- `409 Conflict`: Session already stopped/completed

---

## Backend Callback API Contract

### POST /api/v1/trainings/results

**Purpose**: Host service POSTs training results back to backend after completion.

**Request**:
```python
{
    "session_id": str,                    # Training session ID
    "model_state_dict_b64": str,          # Base64-encoded model state dict
    "compression": str,                   # "gzip", "none"
    "training_metrics": {                 # Training metrics
        "epochs": list[int],
        "train_loss": list[float],
        "train_accuracy": list[float],
        "val_loss": list[float],
        "val_accuracy": list[float],
    },
    "test_metrics": {                     # Test metrics
        "loss": float,
        "accuracy": float,
        "precision": float,
        "recall": float,
        "f1_score": float,
    },
    "config": dict[str, Any],             # Full training config
    "feature_names": list[str],           # Feature names
    "feature_importance": dict[str, float], # Feature importance scores
    "metadata": dict[str, Any],           # Execution metadata
}
```

**Model Serialization Process**:
```python
# Host service (sender):
import torch
import gzip
import base64
import io

# 1. Serialize model state dict
buffer = io.BytesIO()
torch.save(model.state_dict(), buffer)
model_bytes = buffer.getvalue()

# 2. Compress with gzip
compressed = gzip.compress(model_bytes)

# 3. Base64 encode for JSON
model_state_dict_b64 = base64.b64encode(compressed).decode('utf-8')

# 4. POST to backend
payload = {
    "session_id": session_id,
    "model_state_dict_b64": model_state_dict_b64,
    "compression": "gzip",
    ...
}
```

**Model Deserialization Process**:
```python
# Backend (receiver):
import torch
import gzip
import base64
import io

# 1. Base64 decode
compressed = base64.b64decode(payload["model_state_dict_b64"])

# 2. Decompress
if payload["compression"] == "gzip":
    model_bytes = gzip.decompress(compressed)
else:
    model_bytes = compressed

# 3. Deserialize PyTorch state dict
buffer = io.BytesIO(model_bytes)
state_dict = torch.load(buffer, map_location="cpu")

# 4. Load into model
model = create_model_from_config(payload["config"])
model.load_state_dict(state_dict)

# 5. Save via ModelStorage
model_path = model_storage.save(model, metadata=payload["metadata"])
```

**Response**:
```python
{
    "success": bool,
    "message": str,
    "model_path": str,                    # Path where model saved
    "model_id": str,                      # Model identifier
}
```

**Status Codes**:
- `200 OK`: Results received and model saved
- `400 Bad Request`: Invalid payload or decompression failed
- `404 Not Found`: Session not found
- `500 Internal Server Error`: Model save failed

**Retry Logic** (Host Service):
```python
async def _post_results_with_retry(
    self,
    callback_url: str,
    payload: dict[str, Any],
    max_attempts: int = 3,
) -> None:
    """
    POST results with exponential backoff retry.

    Retry schedule: 1s, 2s, 4s (max 8s)
    """
    backoff = 1.0

    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(callback_url, json=payload)
                response.raise_for_status()
                logger.info(f"Results posted successfully on attempt {attempt}")
                return
        except httpx.HTTPError as e:
            if attempt >= max_attempts:
                logger.error(f"Failed to post results after {attempt} attempts: {e}")
                # Don't raise - results remain in session state for recovery
            else:
                logger.warning(f"Attempt {attempt} failed, retrying in {backoff}s: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 8.0)
```

---

## Interface Evolution Guidelines

### When Can You Change an Interface?

**NEVER** change an interface without:
1. Understanding all callers and callees
2. Updating all implementations simultaneously
3. Updating all tests
4. Documenting the change
5. Considering backward compatibility

### Adding Optional Parameters

✅ **SAFE**:
```python
# Before
def execute(self, symbols: list[str], timeframes: list[str]) -> dict:
    pass

# After (adding optional parameter at end)
def execute(
    self,
    symbols: list[str],
    timeframes: list[str],
    new_param: Optional[str] = None,  # Default value required
) -> dict:
    pass
```

### Adding Required Parameters

❌ **BREAKING**:
```python
# Before
def execute(self, symbols: list[str]) -> dict:
    pass

# After
def execute(
    self,
    symbols: list[str],
    required_new_param: str,  # BREAKS all existing callers!
) -> dict:
    pass
```

**Instead**: Use optional parameter with default:
```python
def execute(
    self,
    symbols: list[str],
    new_param: str = "default_value",
) -> dict:
    if new_param == "default_value":
        logger.warning("new_param not provided, using default")
    pass
```

### Changing Return Types

❌ **BREAKING**:
```python
# Before
def execute(self) -> dict:
    return {"success": True}

# After
def execute(self) -> TrainingResult:  # Different type!
    return TrainingResult(success=True)
```

**Instead**: Extend dict structure:
```python
# Before
def execute(self) -> dict:
    return {"success": True}

# After (backward compatible)
def execute(self) -> dict:
    return {
        "success": True,
        "new_field": "value",  # Additional field, old code ignores
    }
```

---

## Testing Interface Contracts

### Unit Tests

```python
import pytest
from ktrdr.training.executor import TrainingExecutor

class TestTrainingExecutorInterface:
    """Test interface contract, not implementation."""

    def test_init_signature(self):
        """Verify __init__ accepts correct parameters."""
        executor = TrainingExecutor(
            config={},
            progress_callback=None,
            cancellation_token=None,
            model_storage=None,
        )
        assert executor is not None

    def test_execute_signature(self):
        """Verify execute() accepts correct parameters."""
        executor = TrainingExecutor(config={})

        # Should accept all required parameters
        result = executor.execute(
            symbols=["EURUSD"],
            timeframes=["1h"],
            start_date="2024-01-01",
            end_date="2024-12-31",
            validation_split=0.2,
            data_mode="local",
        )

        # Should return dict with required keys
        assert isinstance(result, dict)
        assert "success" in result
        assert "model_path" in result

    def test_progress_callback_signature(self):
        """Verify progress callback receives correct arguments."""
        calls = []

        def callback(epoch: int, total_epochs: int, metrics: dict[str, float]):
            calls.append((epoch, total_epochs, metrics))

        executor = TrainingExecutor(config={}, progress_callback=callback)
        # ... trigger training ...

        # Verify callback invoked with correct signature
        assert len(calls) > 0
        epoch, total_epochs, metrics = calls[0]
        assert isinstance(epoch, int)
        assert isinstance(total_epochs, int)
        assert isinstance(metrics, dict)

    def test_cancellation_token_protocol(self):
        """Verify cancellation token follows protocol."""
        from ktrdr.async_infrastructure.cancellation import SimpleCancellationToken

        token = SimpleCancellationToken()

        # Protocol methods
        assert hasattr(token, "is_cancelled")
        assert hasattr(token, "cancel")
        assert hasattr(token, "wait_for_cancellation")
        assert hasattr(token, "is_cancelled_requested")

        # Behavior
        assert token.is_cancelled() == False
        token.cancel("test")
        assert token.is_cancelled() == True
```

### Integration Tests

```python
@pytest.mark.integration
async def test_host_service_api_contract():
    """Test host service API follows contract."""
    async with httpx.AsyncClient() as client:
        # Start training
        response = await client.post(
            "http://localhost:5002/training/start",
            json={
                "model_configuration": {
                    "strategy_config": "test",
                    "symbols": ["EURUSD"],
                    "timeframes": ["1h"],
                    "model_type": "mlp",
                    "multi_symbol": False,
                },
                "training_configuration": {
                    "validation_split": 0.2,
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                    "data_mode": "local",
                },
                # ... rest of config ...
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response contract
        assert "session_id" in data
        assert "status" in data
        assert data["status"] == "queued"

        session_id = data["session_id"]

        # Check status
        response = await client.get(f"http://localhost:5002/training/status/{session_id}")
        assert response.status_code == 200
        status_data = response.json()

        # Verify status contract
        assert "session_id" in status_data
        assert "status" in status_data
        assert "progress" in status_data
```

---

## Conclusion

These interface contracts are **immutable guardrails**. They prevent:
- Signature mismatches (callback errors)
- Type confusion (device errors)
- Integration failures (missing keys)
- Breaking changes (backward incompatibility)

**Before changing any interface**:
1. Read this document
2. Understand why the interface exists
3. Identify all impacted code
4. Update everything simultaneously
5. Test thoroughly

**Remember**: Interfaces are contracts. Break them carefully, or not at all.
