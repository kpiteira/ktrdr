# Training Metrics Exposure for Agent Decision Making: Architecture

**Date**: 2025-01-17
**Status**: Architecture Phase
**Related**: [Problem Statement](./01-problem-statement.md), [Design](./02-design.md)

---

## Executive Summary

This document defines the technical architecture for exposing training metrics to AI agents through the Operations API. The solution **extends existing infrastructure** (Operation model, TrainingProgressBridge, OperationsService) to store and serve historical metrics alongside real-time progress.

**Core Approach**: Flow epoch metrics through the existing progress callback system, store them in the generic `Operation.metrics` field, and expose via new API endpoint.

**Key Design**: Works identically for **both local and host service training** - the metrics collection point is in `ModelTrainer`, which is common to both paths.

---

## Current Architecture

### Training Execution Modes

KTRDR supports two training modes:

```
┌──────────────────────────────────────────────────────────────┐
│ Training Request (API or CLI)                                │
└──────────────────────────────────────────────────────────────┘
                          │
                          ├─ USE_TRAINING_HOST_SERVICE=false
                          │  (Local Training)
                          ▼
         ┌────────────────────────────────────────┐
         │ Docker Container (API)                 │
         │  ┌──────────────────────────────────┐ │
         │  │ LocalTrainingOrchestrator        │ │
         │  │  - Creates TrainingProgressBridge│ │
         │  │  - Calls TrainingPipeline        │ │
         │  └──────────────────────────────────┘ │
         │                │                       │
         │                ▼                       │
         │  ┌──────────────────────────────────┐ │
         │  │ TrainingPipeline                 │ │
         │  │  - Orchestrates data prep        │ │
         │  │  - Calls ModelTrainer.train()    │ │
         │  └──────────────────────────────────┘ │
         │                │                       │
         │                ▼                       │
         │  ┌──────────────────────────────────┐ │
         │  │ ModelTrainer                     │ │
         │  │  - Training loop                 │ │
         │  │  - Collects epoch metrics        │ │
         │  │  - Emits progress callbacks      │ │
         │  └──────────────────────────────────┘ │
         └────────────────────────────────────────┘

                          │
                          ├─ USE_TRAINING_HOST_SERVICE=true
                          │  (Host Service Training - for GPU)
                          ▼
         ┌────────────────────────────────────────┐
         │ Docker Container (API)                 │
         │  ┌──────────────────────────────────┐ │
         │  │ TrainingService                  │ │
         │  │  - Forwards request to host      │ │
         │  └──────────────────────────────────┘ │
         └────────────────────────────────────────┘
                          │
                          │ HTTP
                          ▼
         ┌────────────────────────────────────────┐
         │ Training Host Service (Port 5002)      │
         │  ┌──────────────────────────────────┐ │
         │  │ HostTrainingOrchestrator         │ │
         │  │  - Creates TrainingProgressBridge│ │
         │  │  - Calls TrainingPipeline        │ │
         │  └──────────────────────────────────┘ │
         │                │                       │
         │                ▼                       │
         │  ┌──────────────────────────────────┐ │
         │  │ TrainingPipeline (same code!)    │ │
         │  │  - Orchestrates data prep        │ │
         │  │  - Calls ModelTrainer.train()    │ │
         │  └──────────────────────────────────┘ │
         │                │                       │
         │                ▼                       │
         │  ┌──────────────────────────────────┐ │
         │  │ ModelTrainer (same code!)        │ │
         │  │  - Training loop                 │ │
         │  │  - Collects epoch metrics        │ │
         │  │  - Emits progress callbacks      │ │
         │  └──────────────────────────────────┘ │
         └────────────────────────────────────────┘
```

**Key Insight**: `ModelTrainer` and `TrainingPipeline` are **identical** in both modes. The only difference is where they run (Docker container vs. host machine) and how progress flows back to the API.

### Current Progress Flow

**Local Training:**
```
ModelTrainer.train()
  ↓ progress_callback(epoch, total, metrics)
LocalTrainingOrchestrator._create_progress_callback()
  ↓ routes to
TrainingProgressBridge.on_epoch()
  ↓ emits to
GenericProgressManager
  ↓ triggers callback
OperationsService.update_progress()
  ↓ stores
Operation.progress = {...}
```

**Host Service Training:**
```
ModelTrainer.train()  (on host machine)
  ↓ progress_callback(epoch, total, metrics)
HostTrainingOrchestrator._create_progress_callback()
  ↓ routes to
TrainingProgressBridge.on_epoch()
  ↓ sends HTTP POST
Training Host Service /sessions/{id}/snapshot
  ↓ receives
TrainingService (in Docker)
  ↓ updates
OperationsService.update_progress()
  ↓ stores
Operation.progress = {...}
```

**Current Limitation**: In both modes, only **current epoch summary** is stored in progress. Historical metrics are collected in `ModelTrainer.history` but **never exposed**.

---

## Proposed Architecture

### Metrics Storage in Operation Model

**Location**: `ktrdr/api/models/operations.py`

```python
class Operation(BaseModel):
    """Core operation model (domain-agnostic)."""

    operation_id: str
    type: OperationType
    status: OperationStatus

    # Real-time execution status
    progress: OperationProgress

    # Final outcome (when complete)
    result: Optional[OperationResult] = None

    # NEW: Domain-specific metrics (generic container)
    metrics: Optional[dict[str, Any]] = Field(
        None,
        description="Domain-specific metrics (structure varies by operation type)"
    )

    # ... other fields ...
```

**For Training Operations**, `metrics` contains:
```python
{
    "epochs": [
        {"epoch": 0, "train_loss": 0.8234, "val_loss": 0.8912, ...},
        {"epoch": 1, "train_loss": 0.7123, "val_loss": 0.7456, ...},
        # ... more epochs ...
    ],
    "best_epoch": 35,
    "best_val_loss": 0.4123,
    "epochs_since_improvement": 8,
    "is_overfitting": false,
    "is_plateaued": false,
    "total_epochs_planned": 100,
    "total_epochs_completed": 43
}
```

---

## Component Architecture

### 1. ModelTrainer (ENHANCED - Both Modes)

**Location**: `ktrdr/training/model_trainer.py`

**Current Behavior**:
- Collects metrics in `self.history: List[TrainingMetrics]`
- Emits progress via `self.progress_callback(epoch, total_epochs, metrics_dict)`

**Changes Required**:

```python
# In ModelTrainer.train() - existing epoch callback
if self.progress_callback:
    # EXISTING: Summary metrics for progress display
    epoch_metrics = {
        "epoch": epoch,
        "total_epochs": epochs,
        "progress_type": "epoch",
        "train_loss": avg_train_loss,
        "val_loss": val_loss,
        "train_accuracy": train_accuracy,
        "val_accuracy": val_accuracy,
        # ... existing fields ...
    }

    # NEW: Add full metrics for storage
    epoch_metrics["full_metrics"] = {
        "epoch": epoch,
        "train_loss": float(avg_train_loss),
        "train_accuracy": float(train_accuracy),
        "val_loss": float(val_loss) if val_loss is not None else None,
        "val_accuracy": float(val_accuracy) if val_accuracy is not None else None,
        "learning_rate": optimizer.param_groups[0]["lr"],
        "duration": duration,
        "timestamp": datetime.utcnow().isoformat(),
    }

    self.progress_callback(epoch, epochs, epoch_metrics)
```

**Why This Works for Both Modes**:
- ✅ `ModelTrainer` is same code in local and host service
- ✅ `progress_callback` signature unchanged
- ✅ Orchestrators receive same data structure
- ✅ Just adding `"full_metrics"` field to existing dict

---

### 2. TrainingProgressBridge (ENHANCED - Both Modes)

**Location**:
- `ktrdr/api/services/training/progress_bridge.py` (local)
- `training-host-service/progress_bridge.py` (host - if different, or may be shared)

**Current Behavior**:
- `on_epoch()` receives metrics, formats progress, emits to GenericProgressManager

**Changes Required**:

```python
class TrainingProgressBridge:
    def __init__(
        self,
        context: TrainingOperationContext,
        progress_manager: GenericProgressManager,
        update_callback: Optional[Callable] = None,  # NEW: For metrics updates
        # ... existing params ...
    ):
        self._context = context
        self._progress_manager = progress_manager
        self._update_callback = update_callback  # NEW
        # ... existing fields ...

    def on_epoch(
        self,
        epoch: int,
        total_epochs: int | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        """Emit progress for a completed epoch."""
        self._check_cancelled()

        metrics = metrics or {}

        # EXISTING: Update progress
        # ... existing progress emission code ...

        # NEW: Store full metrics if available
        if "full_metrics" in metrics:
            self._store_epoch_metrics(metrics["full_metrics"])

    def _store_epoch_metrics(self, epoch_metrics: dict[str, Any]) -> None:
        """Store epoch metrics via update callback."""
        if self._update_callback:
            # For local training: callback directly updates OperationsService
            # For host training: callback sends HTTP request to API
            self._update_callback(
                operation_id=self._context.operation_id,
                metrics_update=epoch_metrics
            )
```

**Why This Works for Both Modes**:
- ✅ Bridge exists in both local and host orchestrators
- ✅ `update_callback` is mode-specific (see orchestrators below)
- ✅ Bridge doesn't care HOW metrics are stored, just calls callback

---

### 3a. LocalTrainingOrchestrator (ENHANCED - Local Mode)

**Location**: `ktrdr/api/services/training/local_orchestrator.py`

**Changes Required**:

```python
class LocalTrainingOrchestrator:
    def __init__(
        self,
        # ... existing params ...
        operations_service: OperationsService,  # Has access to ops service
    ):
        self.operations_service = operations_service
        # ... existing fields ...

    async def train(self, context: TrainingOperationContext) -> dict:
        """Execute training locally."""

        # Create progress bridge with metrics update callback
        progress_bridge = TrainingProgressBridge(
            context=context,
            progress_manager=progress_manager,
            update_callback=self._create_metrics_update_callback(context),  # NEW
            # ... existing params ...
        )

        # ... rest of training orchestration ...

    def _create_metrics_update_callback(
        self,
        context: TrainingOperationContext
    ) -> Callable:
        """Create callback that stores metrics in OperationsService."""

        def metrics_callback(operation_id: str, metrics_update: dict) -> None:
            """Store epoch metrics directly in operations service."""
            try:
                # Direct access to operations service (local mode)
                asyncio.create_task(
                    self.operations_service.add_metrics(
                        operation_id=operation_id,
                        metrics_data=metrics_update
                    )
                )
            except Exception as e:
                logger.error(f"Failed to store epoch metrics: {e}")

        return metrics_callback
```

**Local Mode Flow**:
```
ModelTrainer → progress_callback → Bridge.on_epoch() → metrics_callback
  → OperationsService.add_metrics() → Operation.metrics updated
```

---

### 3b. HostTrainingOrchestrator (ENHANCED - Host Service Mode)

**Location**: `training-host-service/orchestrator.py`

**Changes Required**:

```python
class HostTrainingOrchestrator:
    def __init__(
        self,
        # ... existing params ...
        api_client: HostServiceAPIClient,  # Has HTTP client for API
    ):
        self.api_client = api_client
        # ... existing fields ...

    async def train(self, session_id: str, config: dict) -> dict:
        """Execute training on host machine."""

        # Create progress bridge with metrics update callback
        progress_bridge = TrainingProgressBridge(
            context=context,
            progress_manager=progress_manager,
            update_callback=self._create_metrics_update_callback(session_id),  # NEW
            # ... existing params ...
        )

        # ... rest of training orchestration ...

    def _create_metrics_update_callback(
        self,
        session_id: str
    ) -> Callable:
        """Create callback that sends metrics to API via HTTP."""

        def metrics_callback(operation_id: str, metrics_update: dict) -> None:
            """Send epoch metrics to API via HTTP."""
            try:
                # Send HTTP request to API (host service mode)
                asyncio.create_task(
                    self.api_client.post(
                        f"/sessions/{session_id}/metrics",
                        json={
                            "operation_id": operation_id,
                            "metrics": metrics_update
                        }
                    )
                )
            except Exception as e:
                logger.error(f"Failed to send epoch metrics to API: {e}")

        return metrics_callback
```

**Host Service Mode Flow**:
```
ModelTrainer → progress_callback → Bridge.on_epoch() → metrics_callback
  → HTTP POST /sessions/{id}/metrics → TrainingService (in Docker)
  → OperationsService.add_metrics() → Operation.metrics updated
```

---

### 4. Training Host Service API (NEW ENDPOINT)

**Location**: `training-host-service/main.py` (or wherever endpoints are defined)

**New Endpoint**:

```python
@app.post("/sessions/{session_id}/metrics")
async def update_session_metrics(
    session_id: str,
    request: SessionMetricsUpdate
):
    """
    Receive epoch metrics from training session and forward to main API.

    Called by HostTrainingOrchestrator when epoch completes.
    """
    # Get session info (includes operation_id)
    session = get_session(session_id)

    # Forward to main API's operations service
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{API_URL}/api/v1/operations/{session.operation_id}/metrics",
            json=request.metrics
        )

    return {"success": True}


class SessionMetricsUpdate(BaseModel):
    operation_id: str
    metrics: dict[str, Any]
```

---

### 5. OperationsService (ENHANCED)

**Location**: `ktrdr/api/services/operations_service.py`

**New Method**:

```python
class OperationsService:
    async def add_metrics(
        self,
        operation_id: str,
        metrics_data: dict[str, Any]
    ) -> None:
        """
        Add domain-specific metrics to an operation.

        For training operations: expects epoch metrics
        For other operation types: structure varies
        """
        operation = await self.get_operation(operation_id)

        # Initialize metrics dict if needed
        if operation.metrics is None:
            operation.metrics = {}

        # Handle training-specific metrics
        if operation.type == OperationType.TRAINING:
            await self._add_training_epoch_metrics(operation, metrics_data)
        else:
            # For other operation types, store as-is
            operation.metrics.update(metrics_data)

        # Persist to database
        await self._save_operation(operation)

    async def _add_training_epoch_metrics(
        self,
        operation: Operation,
        epoch_metrics: dict[str, Any]
    ) -> None:
        """Add epoch metrics and update trend analysis."""
        # Initialize training metrics structure if needed
        if "epochs" not in operation.metrics:
            operation.metrics["epochs"] = []
            operation.metrics["total_epochs_planned"] = 0
            operation.metrics["total_epochs_completed"] = 0

        # Add epoch metrics
        operation.metrics["epochs"].append(epoch_metrics)
        operation.metrics["total_epochs_completed"] = len(
            operation.metrics["epochs"]
        )

        # Update trend analysis
        self._update_training_metrics_analysis(operation.metrics)

    def _update_training_metrics_analysis(
        self,
        metrics: dict[str, Any]
    ) -> None:
        """Compute trend indicators from epoch history."""
        epochs = metrics.get("epochs", [])
        if not epochs:
            return

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

        # Detect overfitting (train ↓, val ↑)
        if len(epochs) >= 10:
            recent = epochs[-10:]
            train_trend = recent[-1]["train_loss"] < recent[0]["train_loss"]
            val_trend = (
                recent[-1].get("val_loss", 0) > recent[0].get("val_loss", 0)
            )
            metrics["is_overfitting"] = train_trend and val_trend

        # Detect plateau
        metrics["is_plateaued"] = metrics.get("epochs_since_improvement", 0) >= 10
```

---

### 6. API Endpoints (NEW)

**Location**: `ktrdr/api/endpoints/operations.py`

**New Endpoint - Get Metrics**:

```python
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

    - Training: epoch metrics + trend analysis
    - Data loading: segment stats + cache info
    - Backtesting: trade stats + performance
    """
    operation = await operations_service.get_operation(operation_id)

    if operation.metrics is None:
        # No metrics yet
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


@router.post(
    "/operations/{operation_id}/metrics",
    response_model=StandardResponse,
    tags=["Operations"],
    summary="Add metrics to operation"
)
async def add_operation_metrics(
    operation_id: str,
    metrics: dict[str, Any],
    operations_service: OperationsService = Depends(get_operations_service)
) -> StandardResponse:
    """
    Add metrics to an operation.

    Called by:
    - Local training orchestrator (direct call)
    - Training host service (via HTTP from host machine)
    """
    await operations_service.add_metrics(operation_id, metrics)

    return StandardResponse(
        success=True,
        message="Metrics added successfully"
    )
```

**Enhanced - Include Metrics in Status**:

```python
@router.get(
    "/operations/{operation_id}",
    response_model=OperationStatusResponse,
    tags=["Operations"],
    summary="Get operation status"
)
async def get_operation_status(
    operation_id: str,
    include_metrics: bool = Query(False, description="Include full metrics"),
    operations_service: OperationsService = Depends(get_operations_service)
) -> OperationStatusResponse:
    """Get operation status, optionally including metrics."""
    operation = await operations_service.get_operation(operation_id)

    response_data = {
        "operation_id": operation.operation_id,
        "type": operation.type,
        "status": operation.status,
        "progress": operation.progress,
        "result": operation.result,
        # ... other fields ...
    }

    # Optionally include metrics
    if include_metrics and operation.metrics is not None:
        response_data["metrics"] = operation.metrics

    return OperationStatusResponse(success=True, data=response_data)
```

---

### 7. MCP Client (NEW METHODS)

**Location**: `mcp/src/clients/operations_client.py`

```python
class OperationsAPIClient(BaseAPIClient):
    # ... existing methods ...

    async def get_operation_metrics(
        self,
        operation_id: str
    ) -> dict[str, Any]:
        """
        Get domain-specific metrics for an operation.

        For training operations: returns epoch history + trend analysis
        For other operations: returns operation-specific metrics

        Example:
            metrics = await client.get_operation_metrics("op-training-123")
            if metrics["metrics"].get("is_overfitting"):
                print("Overfitting detected!")
        """
        return await self._request("GET", f"/operations/{operation_id}/metrics")

    async def get_operation_status(
        self,
        operation_id: str,
        include_metrics: bool = False
    ) -> dict[str, Any]:
        """
        Get operation status, optionally including metrics.

        Args:
            operation_id: Operation ID
            include_metrics: If True, include full metrics in response
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

---

## Complete Data Flow Diagrams

### Local Training Mode

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Training Request                                         │
│    POST /api/v1/training/train                              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. LocalTrainingOrchestrator                                │
│    - Creates operation in OperationsService                 │
│    - Creates TrainingProgressBridge with:                   │
│      • progress_manager → for progress updates              │
│      • metrics_callback → for metrics storage               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. TrainingPipeline.train_strategy()                        │
│    - Data preparation                                       │
│    - Calls ModelTrainer.train(progress_callback)            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. ModelTrainer.train() - Epoch Loop                        │
│    FOR EACH EPOCH:                                          │
│      - Train model                                          │
│      - Validate model                                       │
│      - Collect metrics (TrainingMetrics)                    │
│      - Call progress_callback(epoch, total, {              │
│          "train_loss": 0.4567,                              │
│          "val_loss": 0.5123,                                │
│          "full_metrics": {...}  ← NEW                       │
│        })                                                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. LocalOrchestrator._create_progress_callback()            │
│    - Routes to TrainingProgressBridge.on_epoch()            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. TrainingProgressBridge.on_epoch()                        │
│    - Updates progress → GenericProgressManager              │
│    - Stores metrics → metrics_callback()                    │
└─────────────────────────────────────────────────────────────┘
                     ↓                    ↓
         ┌──────────────────┐   ┌──────────────────────────┐
         │ Progress Path    │   │ Metrics Path (NEW)       │
         └──────────────────┘   └──────────────────────────┘
                     ↓                    ↓
         ┌──────────────────┐   ┌──────────────────────────┐
         │ OperationsService│   │ OperationsService        │
         │ .update_progress │   │ .add_metrics()           │
         └──────────────────┘   └──────────────────────────┘
                     ↓                    ↓
         ┌──────────────────┐   ┌──────────────────────────┐
         │ Operation        │   │ Operation                │
         │ .progress = {...}│   │ .metrics = {             │
         └──────────────────┘   │   epochs: [...],         │
                                │   best_epoch: 35,        │
                                │   is_overfitting: false  │
                                │ }                        │
                                └──────────────────────────┘
```

### Host Service Training Mode

**Key Point**: Both progress and metrics flow from the Host Service → Docker Container, then both are stored in the same Operation object in OperationsService.

```
┌────────────────────────────────────────────────────────────────────────┐
│ DOCKER CONTAINER (API - Port 8000)                                    │
│ ┌────────────────────────────────────────────────────────────────┐   │
│ │ 1. Training Request                                            │   │
│ │    POST /api/v1/training/train (USE_TRAINING_HOST_SERVICE)    │   │
│ └────────────────────────────────────────────────────────────────┘   │
│                            ↓                                           │
│ ┌────────────────────────────────────────────────────────────────┐   │
│ │ 2. TrainingService                                             │   │
│ │    - Creates operation in OperationsService                    │   │
│ │    - Forwards request to Training Host Service (HTTP)          │   │
│ └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│ ┌────────────────────────────────────────────────────────────────┐   │
│ │ 8. OperationsService (RECEIVES both paths)                     │   │
│ │    ┌──────────────────────┐   ┌───────────────────────────┐   │   │
│ │    │ update_progress()    │   │ add_metrics()             │   │   │
│ │    │ (existing)           │   │ (NEW)                     │   │   │
│ │    └──────────────────────┘   └───────────────────────────┘   │   │
│ │                ↓                          ↓                    │   │
│ │    ┌──────────────────────────────────────────────────────┐   │   │
│ │    │ SAME Operation Object (in database)                  │   │   │
│ │    │  - operation_id: "op-training-123"                   │   │   │
│ │    │  - progress: {percentage: 65%, ...}    ← Progress    │   │   │
│ │    │  - metrics: {epochs: [...], ...}       ← Metrics     │   │   │
│ │    └──────────────────────────────────────────────────────┘   │   │
│ └────────────────────────────────────────────────────────────────┘   │
│                            ↑                        ↑                  │
│                            │                        │                  │
└────────────────────────────┼────────────────────────┼──────────────────┘
                             │ HTTP                   │ HTTP
                             │ (existing)             │ (NEW)
                             │                        │
┌────────────────────────────┼────────────────────────┼──────────────────┐
│ HOST MACHINE (Training Host Service - Port 5002)   │                  │
│                            │                        │                  │
│ ┌──────────────────────────┴────────────────────────┴────────────┐   │
│ │ 7. Training Host Service HTTP Endpoints                        │   │
│ │    POST /sessions/{id}/snapshot  (existing - progress)         │   │
│ │    POST /sessions/{id}/metrics   (NEW - epoch metrics)         │   │
│ │                                                                 │   │
│ │    Both forward to Docker API:                                 │   │
│ │    • Snapshot → POST /api/v1/operations/{op_id}/progress       │   │
│ │    • Metrics  → POST /api/v1/operations/{op_id}/metrics        │   │
│ └─────────────────────────────────────────────────────────────────┘   │
│                            ↑                        ↑                  │
│                            │                        │                  │
│ ┌──────────────────────────┴────────────────────────┴────────────┐   │
│ │ 6. TrainingProgressBridge.on_epoch() [ON HOST MACHINE]         │   │
│ │                                                                 │   │
│ │    When epoch completes, makes TWO calls:                      │   │
│ │    1. _emit_progress() → sends progress snapshot (existing)    │   │
│ │    2. _store_epoch_metrics() → sends full metrics (NEW)        │   │
│ └─────────────────────────────────────────────────────────────────┘   │
│                            ↑                                           │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ 5. ModelTrainer.train() - Epoch Loop                            │ │
│ │    FOR EACH EPOCH:                                              │ │
│ │      - Train model (GPU accelerated)                            │ │
│ │      - Validate model                                           │ │
│ │      - Call progress_callback(epoch, total, {                  │ │
│ │          "train_loss": 0.4567,                                  │ │
│ │          "val_loss": 0.5123,                                    │ │
│ │          "full_metrics": {...}  ← NEW field                     │ │
│ │        })                                                       │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                            ↑                                           │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ 4. TrainingPipeline.train_strategy()                            │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                            ↑                                           │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ 3. HostTrainingOrchestrator                                     │ │
│ │    - Receives session request from Docker                       │ │
│ │    - Creates TrainingProgressBridge                             │ │
│ └──────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘

KEY INSIGHT: Both paths (progress and metrics) end up in the SAME OperationsService,
updating the SAME Operation object. They're just updating different fields:
  - Progress path → Operation.progress
  - Metrics path  → Operation.metrics
```

**Simplified Flow**:

```
[Host Machine]                          [Docker Container]

ModelTrainer
    ↓ callback
TrainingProgressBridge
    ↓ (makes 2 HTTP calls)
    ├─ POST /sessions/123/snapshot  ────────→  OperationsService.update_progress()
    │                                              ↓
    │                                           Operation.progress = {...}
    │
    └─ POST /sessions/123/metrics   ────────→  OperationsService.add_metrics()
                                                   ↓
                                                Operation.metrics = {...}

                                             ↓
                                        SAME Operation object!
                                        {
                                          operation_id: "op-123",
                                          progress: {...},  ← from snapshot
                                          metrics: {...}    ← from metrics
                                        }
```

**Summary of Host Service Mode**:

1. **Training runs on host machine** (for GPU access)
2. **TrainingProgressBridge on host makes TWO HTTP calls per epoch**:
   - `POST /sessions/{id}/snapshot` → existing progress updates
   - `POST /sessions/{id}/metrics` → NEW metrics storage
3. **Training Host Service receives both** and forwards to Docker API
4. **Docker API receives both** at different endpoints:
   - Progress → `/api/v1/operations/{id}/progress` (or similar existing endpoint)
   - Metrics → `/api/v1/operations/{id}/metrics` (NEW endpoint)
5. **Both update the SAME Operation object** in OperationsService:
   - Progress updates `Operation.progress` field
   - Metrics updates `Operation.metrics` field
6. **Agents query via MCP** → `GET /api/v1/operations/{id}/metrics` → returns `Operation.metrics`

**Why two separate paths**:
- Progress updates are frequent (every batch, every epoch) and lightweight
- Metrics are less frequent (once per epoch) and richer (full epoch data)
- Separating them keeps the existing progress system unchanged
- Metrics can be queried independently without fetching full operation status

---

## API Response Models

### OperationMetricsResponse

```python
class OperationMetricsResponse(BaseModel):
    success: bool
    data: dict[str, Any] = Field(..., description="Metrics data structure")

    # Example for training operation:
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "data": {
                    "operation_id": "op-training-123",
                    "operation_type": "training",
                    "metrics": {
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
                            }
                        ],
                        "best_epoch": 35,
                        "best_val_loss": 0.4123,
                        "epochs_since_improvement": 8,
                        "is_overfitting": False,
                        "is_plateaued": False,
                        "total_epochs_planned": 100,
                        "total_epochs_completed": 43
                    }
                }
            }
        }
    )
```

---

## Performance Considerations

### Storage Overhead

**Per Epoch**: ~200 bytes
**100 Epochs**: ~20KB
**Typical Training**: < 50KB

**Database Impact**: Negligible - stored as JSON field in Operation document

### Network Overhead (Host Service Mode)

**Per Epoch**: 1 HTTP POST request (~200 bytes payload)
**100 Epochs**: 100 requests over training duration
**Impact**: Negligible - requests are async, non-blocking

### Computation Overhead

**Trend Analysis** (per epoch):
- Find best epoch: O(n) where n = number of epochs
- Overfitting check: O(10) - last 10 epochs
- Total: < 1ms

**When Computed**: On each `add_metrics()` call (once per epoch)

---

## Error Handling

### Local Mode

**Metrics Storage Failure**:
```python
def metrics_callback(operation_id: str, metrics_update: dict) -> None:
    try:
        await self.operations_service.add_metrics(...)
    except Exception as e:
        # Log error but don't fail training
        logger.error(f"Failed to store epoch metrics: {e}")
        # Training continues - metrics just won't be available to agents
```

**Impact**: Training continues, but agents won't have metrics for decision-making

### Host Service Mode

**HTTP Request Failure**:
```python
def metrics_callback(operation_id: str, metrics_update: dict) -> None:
    try:
        await self.api_client.post(...)
    except httpx.RequestError as e:
        # Network error - retry once
        await asyncio.sleep(1)
        try:
            await self.api_client.post(...)
        except Exception:
            logger.error(f"Failed to send metrics after retry: {e}")
```

**Timeout Handling**:
- Use short timeout (5s) for metrics POST
- If timeout, log and continue
- Don't block training on metrics storage

---

## Testing Strategy

### Unit Tests

**OperationsService.add_metrics()**:
- Test training metrics structure initialization
- Test epoch appending
- Test trend analysis computation
- Test overfitting detection
- Test plateau detection

**TrainingProgressBridge**:
- Test `_store_epoch_metrics()` calls callback
- Test metrics extraction from progress dict

**API Endpoints**:
- Test `GET /operations/{id}/metrics` returns correct structure
- Test handling of operations without metrics
- Test `include_metrics` query parameter

### Integration Tests

**Local Training**:
- Start training operation
- Verify metrics accumulate in Operation.metrics
- Verify trend indicators update correctly
- Verify API returns metrics

**Host Service Training**:
- Start training with USE_TRAINING_HOST_SERVICE=true
- Verify HTTP requests flow correctly
- Verify metrics arrive in Docker API
- Verify Operation.metrics populated

**MCP Client**:
- Test `get_operation_metrics()` returns data
- Test agent decision-making scenarios

---

## Migration Strategy

### Phase 1: Add Metrics Field to Operation Model
- Add `metrics: Optional[dict]` field
- Database migration (add column)
- No breaking changes

### Phase 2: Enhance ModelTrainer
- Add `full_metrics` to progress callback
- Backward compatible (existing code ignores extra fields)

### Phase 3: Enhance Orchestrators
- Add metrics callback to both local and host orchestrators
- Add HTTP endpoint to training host service
- No breaking changes (new functionality)

### Phase 4: Add OperationsService Methods
- Implement `add_metrics()`
- Implement trend analysis
- No breaking changes (new methods)

### Phase 5: Add API Endpoints
- Add `GET /operations/{id}/metrics`
- Add `POST /operations/{id}/metrics`
- Enhance existing status endpoint
- No breaking changes (new endpoints)

### Phase 6: Add MCP Client Methods
- Add `get_operation_metrics()`
- Enhance `get_operation_status()`
- No breaking changes (new methods)

---

## Summary

This architecture provides:

- ✅ **Unified Metrics Collection**: Works identically for local and host service training
- ✅ **Generic Storage**: `Operation.metrics` supports all operation types
- ✅ **Real-Time Access**: Metrics available during training, not just after
- ✅ **Agent Empowerment**: MCP clients can fetch metrics and make intelligent decisions
- ✅ **No Breaking Changes**: Extends existing infrastructure, doesn't replace it
- ✅ **Minimal Overhead**: < 50KB storage, < 1ms computation per epoch
- ✅ **Error Resilient**: Metrics storage failures don't break training

**Next**: Implementation plan with phased rollout and testing strategy.

---

**END OF ARCHITECTURE DOCUMENT**
