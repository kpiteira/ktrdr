# Training Metrics Exposure for Agent Decision Making: Design

**Date**: 2025-01-17
**Status**: Design Phase
**Related**: [Problem Statement](./01-problem-statement.md)

---

## Executive Summary

**Problem**: Agents can see training progress but cannot assess training health or make intelligent decisions.

**Solution**: Expose complete training metrics history through the Operations API, stored alongside operation progress, accessible in real-time via new MCP client methods.

**Key Insight**: We already collect rich metrics (`ModelTrainer.history`) - we just need to **flow them through** the existing infrastructure to make them accessible to agents.

---

## Design Principles

1. **Leverage Existing Data**: ModelTrainer already collects all needed metrics
2. **Extend, Don't Replace**: Add metrics exposure without changing training logic
3. **Real-Time Access**: Metrics available during training, not just after
4. **Agent-Friendly**: Simple MCP interface for trend analysis
5. **Minimal Overhead**: Store efficiently, retrieve quickly

---

## High-Level Approach

### Current Flow (Progress Only)
```
ModelTrainer.train()
  ↓ (progress_callback)
TrainingProgressBridge
  ↓ (update progress)
GenericProgressManager
  ↓ (emit to callback)
OperationsService.update_progress()
  ↓ (store in DB)
Operation.progress = {...}
  ↓ (API)
Agent gets: {percentage: 65%, current epoch metrics}
```

### Proposed Flow (Progress + Metrics)
```
ModelTrainer.train()
  ↓ (progress_callback with FULL metrics)
TrainingProgressBridge
  ↓ (update progress AND metrics)
GenericProgressManager
  ↓ (emit progress + metrics separately)
OperationsService.update_progress() AND add_metrics()
  ↓ (store in DB)
Operation.progress = {...}
Operation.metrics = {epochs: [...], best_epoch: 35, ...}
  ↓ (API)
Agent gets:
  - GET /operations/{id} → progress
  - GET /operations/{id}/metrics → ALL epoch metrics + analysis
```

---

## Core Design: Metrics Storage

### Generic Metrics Field in Operation Model

**Location**: `ktrdr/api/models/operations.py`

```python
class Operation(BaseModel):
    # ... existing fields ...
    progress: OperationProgress  # Real-time execution status
    result: Optional[OperationResult] = None  # Final outcome

    # NEW: Domain-specific metrics (generic container)
    metrics: Optional[dict[str, Any]] = Field(
        None,
        description="Domain-specific metrics (structure varies by operation type)"
    )
```

**Design Rationale**: Use a generic `metrics` field instead of `training_metrics` to maintain separation of concerns. The Operation model should remain domain-agnostic, while different operation types (training, data loading, backtesting, live trading) can store their specific metrics in a structured format.

**Semantic Distinction**:

- **progress**: Real-time execution status (percentage, current step, items processed)
- **result**: Final outcome when complete (success/failure, high-level summary)
- **metrics**: Domain-specific performance and diagnostic data (collected during execution)

### Training Metrics Data Structure

For **training operations**, the `metrics` field will contain:

```python
# Stored as structured dict in operation.metrics
{
    "epochs": [
        {
            "epoch": 0,
            "train_loss": 0.8234,
            "train_accuracy": 0.65,
            "val_loss": 0.8912,
            "val_accuracy": 0.58,
            "learning_rate": 0.001,
            "duration": 12.5,
            "timestamp": "2025-01-17T10:00:00Z"
        },
        # ... more epochs ...
    ],

    # Computed analysis (updated on each epoch)
    "best_epoch": 35,
    "best_val_loss": 0.4123,
    "epochs_since_improvement": 8,
    "is_overfitting": false,
    "is_plateaued": false,

    # Training state
    "total_epochs_planned": 100,
    "total_epochs_completed": 43
}
```

**Schema Definition** (for validation, not enforced at Operation level):

```python
@dataclass
class EpochMetrics:
    """Metrics for a single epoch (matches ModelTrainer.TrainingMetrics)"""
    epoch: int
    train_loss: float
    train_accuracy: float
    val_loss: Optional[float] = None
    val_accuracy: Optional[float] = None
    learning_rate: float = 0.001
    duration: float = 0.0  # seconds
    timestamp: Optional[str] = None  # ISO format

# Note: This schema is used by TrainingService for validation,
# but Operation.metrics remains a generic dict to support all operation types
```

### Why This Design?

**Advantages**:

- ✅ **Generic & Extensible**: Works for training, data loading, backtesting, live trading
- ✅ **Separation of Concerns**: Operation model stays domain-agnostic
- ✅ **Type Flexibility**: Each service validates its own metrics structure
- ✅ **Queryable**: Agent can fetch metrics without full operation
- ✅ **Analyzed**: Pre-computed indicators save agent computation
- ✅ **Incremental**: Updates as each epoch completes
- ✅ **Efficient**: ~10KB per 100 epochs (negligible)

**Future Extensibility**:

```python
# Data loading operation
operation.metrics = {
    "segments_fetched": 8,
    "total_bars": 5000,
    "cache_hit_rate": 0.75,
    "fetch_durations": [1.2, 0.8, ...]
}

# Backtesting operation
operation.metrics = {
    "trades": [...],
    "win_rate": 0.65,
    "sharpe_ratio": 1.8,
    "max_drawdown": -0.15
}
```

**Alternatives Considered**:

❌ **Option A**: Separate `training_metrics`, `data_metrics`, `backtest_metrics` fields

- Pollutes Operation model with domain-specific fields
- Breaks separation of concerns
- Not extensible to new operation types

❌ **Option B**: Store in separate metrics table

- More complex (new table, queries, joins)
- Harder to keep in sync with operations
- Over-engineering for ~10KB of data

❌ **Option C**: Compute trends on every API call

- Wasteful (re-analyze every time)
- Slower response times
- Agent has to do analysis

❌ **Option D**: Store only in Operation.result (final)

- Not available during training
- Agent has to wait for completion
- Defeats purpose of real-time monitoring

---

## API Design

### New Endpoint: Get Training Metrics

```
GET /api/v1/operations/{operation_id}/metrics
```

**Response:**
```json
{
  "success": true,
  "data": {
    "operation_id": "op-training-123",
    "epochs": [
      {
        "epoch": 0,
        "train_loss": 0.8234,
        "train_accuracy": 0.65,
        "val_loss": 0.8912,
        "val_accuracy": 0.58,
        "learning_rate": 0.001,
        "duration": 12.5,
        "timestamp": "2025-01-17T10:00:00Z"
      },
      {
        "epoch": 1,
        "train_loss": 0.7123,
        "train_accuracy": 0.72,
        "val_loss": 0.7456,
        "val_accuracy": 0.68,
        "learning_rate": 0.001,
        "duration": 12.3,
        "timestamp": "2025-01-17T10:00:12Z"
      }
      // ... more epochs ...
    ],
    "best_epoch": 35,
    "best_val_loss": 0.4123,
    "epochs_since_improvement": 8,
    "is_overfitting": false,
    "is_plateaued": false,
    "total_epochs_planned": 100,
    "total_epochs_completed": 43
  }
}
```

**Use Cases:**
- ✅ Agent polls this every 30s to get latest metrics
- ✅ Agent analyzes trends to decide on early stopping
- ✅ Agent provides intelligent feedback to user

**Error Cases:**
```json
// Not a training operation
{
  "success": false,
  "error": "Operation op-data-123 is not a training operation"
}

// No metrics yet (training just started)
{
  "success": true,
  "data": {
    "operation_id": "op-training-123",
    "epochs": [],
    "total_epochs_planned": 100,
    "total_epochs_completed": 0
  }
}
```

### Enhanced: Include Metrics in Status Response

**Modify**: `GET /api/v1/operations/{operation_id}`

**Add optional query parameter**: `?include_metrics=true`

```json
{
  "success": true,
  "data": {
    "operation_id": "op-training-123",
    "type": "training",
    "status": "running",
    "progress": {
      "percentage": 43.0,
      "current_step": "Epoch 43/100",
      "context": {
        "epoch_index": 43,
        "epoch_metrics": {
          "train_loss": 0.4567,
          "val_loss": 0.5123
        }
      }
    },
    // NEW: Optional metrics inclusion (for training operations)
    "metrics": {
      "epochs": [...],  // If include_metrics=true
      "best_epoch": 35,
      "epochs_since_improvement": 8
    }
  }
}
```

**Rationale**: Allows fetching progress + metrics in one call if needed, but keeps them separate for efficiency.

---

## MCP Client Interface

### New Methods

**Location**: `mcp/src/clients/operations_client.py`

```python
class OperationsAPIClient(BaseAPIClient):
    # ... existing methods ...

    async def get_training_metrics(
        self,
        operation_id: str
    ) -> dict[str, Any]:
        """
        Get training metrics history for a training operation.

        Returns all epoch metrics, best epoch info, and trend indicators.

        Example:
            metrics = await client.get_training_metrics("op-training-123")
            if metrics["is_overfitting"]:
                await client.cancel_operation(operation_id)
        """
        return await self._request(
            "GET",
            f"/operations/{operation_id}/metrics"
        )

    async def get_operation_status(
        self,
        operation_id: str,
        include_metrics: bool = False
    ) -> dict[str, Any]:
        """
        Get operation status, optionally including training metrics.

        Args:
            operation_id: Operation ID
            include_metrics: If True, include full training metrics
                           (only applicable for training operations)
        """
        params = {}
        if include_metrics:
            params["include_metrics"] = "true"

        return await self._request(
            "GET",
            f"/operations/{operation_id}",
            params=params
        )
```

### Agent Usage Examples

```python
# Example 1: Monitor training health
async def monitor_training(operation_id: str):
    while True:
        metrics = await mcp.get_training_metrics(operation_id)

        # Check overfitting
        if metrics["is_overfitting"]:
            print("⚠️ Overfitting detected!")
            await mcp.cancel_operation(
                operation_id,
                reason="Overfitting: train_loss↓ val_loss↑"
            )
            break

        # Check plateau
        if metrics["epochs_since_improvement"] > 15:
            print(f"✅ Training plateaued. Best epoch: {metrics['best_epoch']}")
            await mcp.cancel_operation(
                operation_id,
                reason=f"Plateau: no improvement in 15 epochs, best was epoch {metrics['best_epoch']}"
            )
            break

        await asyncio.sleep(30)  # Poll every 30s

# Example 2: Analyze loss trajectory
async def analyze_loss_trend(operation_id: str):
    metrics = await mcp.get_training_metrics(operation_id)
    epochs = metrics["epochs"]

    if len(epochs) < 10:
        return "Not enough data yet"

    # Calculate recent trend
    recent_losses = [e["val_loss"] for e in epochs[-10:]]
    trend = "improving" if recent_losses[-1] < recent_losses[0] else "worsening"

    return f"Validation loss {trend} over last 10 epochs: {recent_losses[0]:.4f} → {recent_losses[-1]:.4f}"

# Example 3: Provide intelligent summary
async def training_summary(operation_id: str):
    status = await mcp.get_operation_status(operation_id, include_metrics=True)
    metrics = status["metrics"]  # Generic metrics field

    if not metrics or not metrics.get("epochs"):
        return "Training just started, no metrics yet"

    latest = metrics["epochs"][-1]
    summary = f"""
    Training Progress: Epoch {latest['epoch']}/{metrics['total_epochs_planned']}
    Current Loss: train={latest['train_loss']:.4f}, val={latest['val_loss']:.4f}
    Best Epoch: {metrics['best_epoch']} (val_loss={metrics['best_val_loss']:.4f})
    Status: {'⚠️ Overfitting' if metrics['is_overfitting'] else '✅ Healthy'}
    """
    return summary
```

---

## Data Flow Architecture

### 1. Metrics Collection (No Changes)

**ModelTrainer** already collects metrics:

```python
# Line ~482 in model_trainer.py
metrics = TrainingMetrics(
    epoch=epoch,
    train_loss=avg_train_loss,
    train_accuracy=train_accuracy,
    val_loss=val_loss,
    val_accuracy=val_accuracy,
    learning_rate=optimizer.param_groups[0]["lr"],
    duration=duration,
)
self.history.append(metrics)
```

### 2. Metrics Emission (ENHANCED)

**Progress Callback** needs to include full metrics:

```python
# In ModelTrainer.train() - line ~530
if self.progress_callback:
    epoch_metrics = {
        "epoch": epoch,
        "total_epochs": epochs,
        "progress_type": "epoch",

        # EXISTING: Current epoch summary
        "train_loss": avg_train_loss,
        "val_loss": val_loss,
        "train_accuracy": train_accuracy,
        "val_accuracy": val_accuracy,

        # NEW: Include full metrics object for storage
        "full_metrics": {
            "epoch": epoch,
            "train_loss": float(avg_train_loss),
            "train_accuracy": float(train_accuracy),
            "val_loss": float(val_loss) if val_loss else None,
            "val_accuracy": float(val_accuracy) if val_accuracy else None,
            "learning_rate": optimizer.param_groups[0]["lr"],
            "duration": duration,
        }
    }
    self.progress_callback(epoch, epochs, epoch_metrics)
```

### 3. Bridge Forwarding (ENHANCED)

**TrainingProgressBridge** forwards metrics to operations service:

```python
# In TrainingProgressBridge.on_epoch()
def on_epoch(self, epoch: int, total_epochs: int, metrics: dict):
    # ... existing progress update ...

    # NEW: Extract and store full metrics
    if "full_metrics" in metrics:
        epoch_metrics = metrics["full_metrics"]
        self._store_epoch_metrics(epoch_metrics)

def _store_epoch_metrics(self, epoch_metrics: dict) -> None:
    """Store epoch metrics in operations service."""
    if self._update_callback:
        # Call operations service to add metrics
        self._update_callback(
            operation_id=self._context.operation_id,
            metrics_update=epoch_metrics
        )
```

### 4. Operations Service Storage (NEW)

**OperationsService** stores metrics alongside operation:

```python
class OperationsService:
    async def add_metrics(
        self,
        operation_id: str,
        metrics_data: dict[str, Any]
    ) -> None:
        """
        Add domain-specific metrics to an operation.

        For training operations, metrics_data should contain epoch metrics.
        For other operation types, structure will vary.
        """
        operation = await self.get_operation(operation_id)

        # Initialize metrics dict if needed
        if operation.metrics is None:
            operation.metrics = {}

        # Handle training-specific metrics
        if operation.type == OperationType.TRAINING:
            await self._add_training_epoch_metrics(operation, metrics_data)
        else:
            # For other operation types, just store the metrics
            operation.metrics.update(metrics_data)

        # Persist to database
        await self._save_operation(operation)

    async def _add_training_epoch_metrics(
        self,
        operation: Operation,
        epoch_metrics: dict[str, Any]
    ) -> None:
        """Add epoch metrics to training operation and update analysis."""
        # Initialize training metrics structure if needed
        if "epochs" not in operation.metrics:
            operation.metrics["epochs"] = []
            operation.metrics["total_epochs_planned"] = epoch_metrics.get("total_epochs", 0)
            operation.metrics["total_epochs_completed"] = 0

        # Add epoch metrics
        operation.metrics["epochs"].append(epoch_metrics)
        operation.metrics["total_epochs_completed"] = len(operation.metrics["epochs"])

        # Update trend analysis
        self._update_training_metrics_analysis(operation.metrics)

    def _update_training_metrics_analysis(self, metrics: dict[str, Any]) -> None:
        """Update trend indicators based on current training metrics."""
        if not metrics.get("epochs"):
            return

        epochs = metrics["epochs"]

        # Find best epoch
        val_losses = [
            (i, e["val_loss"])
            for i, e in enumerate(epochs)
            if e.get("val_loss") is not None
        ]
        if val_losses:
            best_idx, best_loss = min(val_losses, key=lambda x: x[1])
            metrics["best_epoch"] = best_idx
            metrics["best_val_loss"] = best_loss
            metrics["epochs_since_improvement"] = len(epochs) - 1 - best_idx

        # Detect overfitting (simple heuristic)
        if len(epochs) >= 10:
            recent = epochs[-10:]
            train_trend = recent[-1]["train_loss"] < recent[0]["train_loss"]
            val_trend = (recent[-1].get("val_loss") or 0) > (recent[0].get("val_loss") or 0)
            metrics["is_overfitting"] = train_trend and val_trend

        # Detect plateau
        metrics["is_plateaued"] = metrics.get("epochs_since_improvement", 0) >= 10
```

### 5. API Endpoint (NEW)

```python
# ktrdr/api/endpoints/operations.py

@router.get(
    "/operations/{operation_id}/metrics",
    response_model=OperationMetricsResponse,
    tags=["Operations"],
    summary="Get operation metrics"
)
async def get_operation_metrics(
    operation_id: str,
    operations_service: OperationsService = Depends(get_operations_service)
) -> OperationMetricsResponse:
    """
    Get domain-specific metrics for an operation.

    For training operations: returns epoch metrics and trend analysis
    For data loading operations: returns segment info and cache stats
    For other operations: returns operation-specific metrics
    """
    operation = await operations_service.get_operation(operation_id)

    if operation.metrics is None:
        # No metrics yet (operation just started)
        return OperationMetricsResponse(
            success=True,
            data={
                "operation_id": operation_id,
                "operation_type": operation.type,
                "metrics": {}
            }
        )

    return OperationMetricsResponse(
        success=True,
        data={
            "operation_id": operation_id,
            "operation_type": operation.type,
            "metrics": operation.metrics
        }
    )
```

---

## Trend Detection Algorithms

### Overfitting Detection

**Heuristic**: Train loss decreasing while val loss increasing

```python
def detect_overfitting(epochs: List[EpochMetrics], window: int = 10) -> bool:
    """Detect overfitting in recent training window."""
    if len(epochs) < window:
        return False

    recent = epochs[-window:]

    # Calculate trends
    train_losses = [e.train_loss for e in recent]
    val_losses = [e.val_loss for e in recent if e.val_loss is not None]

    if len(val_losses) < window:
        return False  # Not enough validation data

    # Simple linear trend: last < first means decreasing
    train_decreasing = train_losses[-1] < train_losses[0]
    val_increasing = val_losses[-1] > val_losses[0]

    # Additional check: significant divergence
    train_improvement = (train_losses[0] - train_losses[-1]) / train_losses[0]
    val_degradation = (val_losses[-1] - val_losses[0]) / val_losses[0]

    # Overfitting if train improving >5% while val degrading >5%
    return train_decreasing and val_increasing and train_improvement > 0.05 and val_degradation > 0.05
```

### Plateau Detection

**Heuristic**: No val_loss improvement for N epochs

```python
def detect_plateau(epochs: List[EpochMetrics], patience: int = 10) -> bool:
    """Detect if training has plateaued."""
    val_losses = [
        (i, e.val_loss)
        for i, e in enumerate(epochs)
        if e.val_loss is not None
    ]

    if len(val_losses) < patience + 1:
        return False

    # Find best validation loss
    best_idx, best_loss = min(val_losses, key=lambda x: x[1])

    # Plateau if no improvement for 'patience' epochs
    epochs_since_best = len(epochs) - 1 - best_idx
    return epochs_since_best >= patience
```

### Divergence Detection

**Heuristic**: Loss increasing consistently

```python
def detect_divergence(epochs: List[EpochMetrics], window: int = 5) -> bool:
    """Detect if training is diverging (loss increasing)."""
    if len(epochs) < window:
        return False

    recent = epochs[-window:]
    train_losses = [e.train_loss for e in recent]

    # Diverging if train loss increased significantly
    loss_increase = (train_losses[-1] - train_losses[0]) / train_losses[0]
    return loss_increase > 0.2  # 20% increase is bad
```

---

## Performance Considerations

### Storage Overhead

**Per Epoch**: ~200 bytes (JSON)
```json
{
  "epoch": 42,
  "train_loss": 0.4567,
  "train_accuracy": 0.82,
  "val_loss": 0.5123,
  "val_accuracy": 0.75,
  "learning_rate": 0.0001,
  "duration": 12.5,
  "timestamp": "2025-01-17T10:00:00Z"
}
```

**100 Epochs**: ~20KB
**Typical Training**: < 50KB total

**Verdict**: Negligible - can store in Operation document directly.

### Retrieval Performance

**Query**: Single operation lookup by ID
**Data size**: < 50KB
**Network transfer**: < 100ms
**JSON parsing**: < 10ms

**Total**: < 200ms end-to-end (acceptable for agent polling)

### Computation Overhead

**Trend analysis** (per update):
- Find best epoch: O(n) where n = epochs (~100)
- Overfitting check: O(window) = O(10)
- Plateau check: O(n) = O(100)

**Total**: < 1ms (negligible)

**When to compute**:
- ✅ On each `add_training_metrics()` call (once per epoch)
- ❌ NOT on every API read (wasteful)

---

## What Stays the Same

**Critical**: This design **extends** existing infrastructure, doesn't replace it.

- ✓ Progress reporting continues as-is
- ✓ TrainingProgressBridge continues reporting progress
- ✓ GenericProgressManager unchanged
- ✓ ModelTrainer.train() logic unchanged
- ✓ Training pipeline unchanged
- ✓ Final results unchanged
- ✓ Analytics unchanged

**The existing training flow continues to work exactly as before!**

Metrics exposure is **additive** - we're just storing and exposing what was already being collected.

---

## Next Steps

See [03-architecture.md](./03-architecture.md) for detailed architecture and [04-implementation-plan.md](./04-implementation-plan.md) for implementation tasks.

---

**END OF DESIGN DOCUMENT**
