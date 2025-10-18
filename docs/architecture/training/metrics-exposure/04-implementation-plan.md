# Training Metrics Exposure: Implementation Plan

**Date**: 2025-01-17
**Status**: Implementation Planning
**Related**: [Problem Statement](./01-problem-statement.md), [Design](./02-design.md), [Architecture](./03-architecture.md)

---

## Branch Strategy

**Proposed Branch Name**: `feature/training-metrics-exposure`

**Branching Strategy**:

```bash
# Create feature branch from main
git checkout main
git pull origin main
git checkout -b feature/training-metrics-exposure
```

**Commit Strategy**:

- ✅ Commit after each milestone (not individual tasks)
- ✅ Each milestone must be testable end-to-end
- ✅ Run full test suite + quality checks before committing
- ✅ Commits should be runnable/deployable

---

## Overview

This implementation follows an **API-first approach** - build the complete interface first (returning "not implemented"), then light up functionality incrementally. Each milestone makes the API return more real data.

**4 Milestones**:

| Milestone | What It Delivers | What API Returns | Can Test With |
|-----------|------------------|------------------|---------------|
| **M1: API Contract** | Full API + MCP client + agent stubs | "Not implemented" or empty | Agent scripts, see structure |
| **M2: Local Training** | Metrics collection in local mode | Real metrics from local training | Same agent scripts, now with data |
| **M3: Host Service** | Metrics collection in host service mode | Real metrics from GPU training | Same agent scripts work remotely |
| **M4: Polish** | Documentation, examples, performance validation | Complete, production-ready | Full end-to-end validation |

**Key Benefit**: You can call the API and run agent scripts from day 1. Each milestone "lights up" more functionality without changing the interface.

**Progression Example - Same Agent Script, More Data Each Milestone**:

```bash
# YOU RUN THIS SAME COMMAND IN EVERY MILESTONE:
python examples/agents/training_monitor.py {operation_id}

# M1: ⏳ No metrics yet (API returns empty)
# M2: ✅ Epoch 0: train_loss=0.8234, val_loss=0.8912 (local training)
# M3: ✅ Epoch 0: train_loss=0.8234, val_loss=0.8912 (GPU training)
# M4: Same + polished documentation
```

---

## Milestone 1: API Contract (Interface First)

**Goal**: Build the complete API interface, MCP client, and agent examples FIRST - before any real implementation. Everything returns empty/stub data, but the interface is complete and testable.

**What Gets Built**:

- Generic `metrics` field in Operation model
- Database migration for metrics storage
- GET `/operations/{id}/metrics` endpoint (returns empty `metrics: {}`)
- POST `/operations/{id}/metrics` endpoint (accepts but ignores data for now)
- MCP client methods (`get_operation_metrics()`)
- Example agent scripts (monitor + analyzer) - work with empty data
- Comprehensive tests for the complete interface

**Why This First**: You can start calling the API and running agent scripts from day 1. As we implement M2 and M3, the same API calls will return real data without changing the interface.

**What API Returns at This Stage**: Empty structure, but valid:

```json
{
  "success": true,
  "data": {
    "operation_id": "op-training-123",
    "operation_type": "training",
    "metrics": {}  // Empty until M2
  }
}
```

### Single Task: Complete API Contract + Client + Examples

**Scope**: Build the ENTIRE interface stack - from database to agent examples. Everything compiles and runs, returns valid (but empty) responses. This is a complete vertical slice of the system.

**Files Modified**:

- `ktrdr/api/models/operations.py` - Add metrics field
- Database migration script
- `ktrdr/api/endpoints/operations.py` - GET + POST endpoints
- `mcp/src/clients/operations_client.py` - MCP client methods
- `examples/agents/training_monitor.py` (NEW) - Monitoring agent
- `examples/agents/loss_analyzer.py` (NEW) - Analysis agent
- `tests/api/models/test_operations.py` - Model tests
- `tests/api/endpoints/test_operations.py` - API endpoint tests
- `tests/unit/mcp/test_operations_client.py` - MCP client tests
- `tests/integration/test_metrics_api_contract.py` - End-to-end contract test

**Implementation Details**:

**1. Add `metrics` field to Operation model**:

```python
class Operation(BaseModel):
    """Core operation model."""
    # ... existing fields ...

    # NEW: Domain-specific metrics (generic container)
    metrics: Optional[dict[str, Any]] = Field(
        None,
        description="Domain-specific metrics (structure varies by operation type)"
    )
```

**2. Create database migration** to add `metrics` column (JSON/JSONB type)

**3. Implement GET metrics endpoint** (returns empty for now):

```python
@router.get(
    "/operations/{operation_id}/metrics",
    response_model=OperationMetricsResponse,
    tags=["Operations"],
    summary="Get operation metrics",
    description="Get domain-specific metrics for an operation. Returns empty until M2.",
)
async def get_operation_metrics(
    operation_id: str,
    operations_service: OperationsService = Depends(get_operations_service)
) -> OperationMetricsResponse:
    """Get domain-specific metrics for an operation."""
    operation = await operations_service.get_operation(operation_id)

    # M1: Always return empty metrics
    # M2+: Will return real metrics from Operation.metrics field
    return OperationMetricsResponse(
        success=True,
        data={
            "operation_id": operation_id,
            "operation_type": operation.type,
            "metrics": operation.metrics or {}  # Empty until M2
        }
    )
```

**4. Implement POST metrics endpoint** (accepts but doesn't store yet):

```python
@router.post(
    "/operations/{operation_id}/metrics",
    response_model=StandardResponse,
    tags=["Operations"],
    summary="Add operation metrics",
    description="Add metrics to an operation. Accepts but doesn't store until M2.",
)
async def add_operation_metrics(
    operation_id: str,
    metrics: dict[str, Any] = Body(...),
    operations_service: OperationsService = Depends(get_operations_service)
) -> StandardResponse:
    """
    Add metrics to an operation.

    M1: Accepts data but doesn't store (validates structure)
    M2+: Will actually store metrics
    """
    # Verify operation exists
    await operations_service.get_operation(operation_id)

    # M1: Just validate structure, don't store
    # M2+: Will call operations_service.add_metrics()
    logger.info(f"Received metrics for {operation_id} (not stored in M1)")

    return StandardResponse(
        success=True,
        message="Metrics accepted (not stored until M2)"
    )
```

**5. Implement MCP client methods**:

```python
class OperationsAPIClient(BaseAPIClient):
    async def get_operation_metrics(self, operation_id: str) -> dict[str, Any]:
        """
        Get domain-specific metrics for an operation.

        M1: Returns empty metrics
        M2+: Returns real training metrics

        Example:
            metrics = await client.get_operation_metrics("op-training-123")
            if metrics.get("metrics", {}).get("is_overfitting"):
                print("Overfitting detected!")
        """
        return await self._request("GET", f"/operations/{operation_id}/metrics")
```

**6. Create agent example scripts** (work with empty data):

`examples/agents/training_monitor.py`:

```python
#!/usr/bin/env python3
"""
Agent that monitors training and detects issues.

M1: Works with empty metrics, shows structure
M2+: Shows real metrics and provides recommendations
"""
import asyncio
from mcp.src.clients.operations_client import OperationsAPIClient

async def monitor_training(operation_id: str):
    """Monitor training for overfitting and plateaus."""
    async with OperationsAPIClient() as client:
        while True:
            response = await client.get_operation_metrics(operation_id)
            metrics = response.get("data", {}).get("metrics", {})

            if not metrics or not metrics.get("epochs"):
                print("⏳ No metrics yet (M1: API returns empty)")
                print(f"   Response structure: {response}")
                await asyncio.sleep(30)
                continue

            # M2+: Will have real metrics
            print(f"✅ Metrics available: {len(metrics.get('epochs', []))} epochs")
            # ... rest of monitoring logic

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python training_monitor.py <operation_id>")
        sys.exit(1)

    asyncio.run(monitor_training(sys.argv[1]))
```

`examples/agents/loss_analyzer.py`:

```python
#!/usr/bin/env python3
"""
Agent that analyzes loss trends.

M1: Shows API contract, handles empty data
M2+: Provides real analysis and recommendations
"""
import asyncio
from mcp.src.clients.operations_client import OperationsAPIClient

async def analyze_loss_trend(operation_id: str):
    """Analyze training loss trajectory."""
    async with OperationsAPIClient() as client:
        response = await client.get_operation_metrics(operation_id)
        metrics = response.get("data", {}).get("metrics", {})

        if not metrics or len(metrics.get("epochs", [])) < 10:
            print("❌ Not enough data yet")
            print(f"   M1: API returns empty metrics")
            print(f"   Response: {response}")
            return

        # M2+: Will provide real analysis
        epochs = metrics["epochs"]
        print(f"📈 Analyzing {len(epochs)} epochs...")
        # ... rest of analysis logic

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python loss_analyzer.py <operation_id>")
        sys.exit(1)

    asyncio.run(analyze_loss_trend(sys.argv[1]))
```

**TDD Workflow**:

1. Write tests for model changes
2. Write tests for API endpoints (GET + POST)
3. Write tests for MCP client methods
4. Implement model changes
5. Create and run database migration
6. Implement API endpoints
7. Implement MCP client methods
8. Create agent example scripts
9. Run test suite: `make test-unit`
10. Run quality checks: `make quality`
11. Manual validation with cURL + agent scripts

**Tests to Write**:

- **Model tests**: Verify metrics field serialization/deserialization
- **API tests**: GET returns 200, POST accepts data, both handle errors correctly
- **MCP client tests**: Verify HTTP calls, response parsing, error handling
- **Contract integration test**: End-to-end from agent → MCP → API → database

### Milestone 1 Acceptance Criteria

**Manual Validation - API**:

```bash
# 1. Start API
./docker_dev.sh start

# 2. Create a training operation
uv run ktrdr models train --strategy config/strategies/example.yaml --epochs 5 &
OPERATION_ID=<get from output>

# 3. Query metrics endpoint with cURL
curl http://localhost:8000/api/v1/operations/$OPERATION_ID/metrics | jq

# Expected output:
{
  "success": true,
  "data": {
    "operation_id": "op-training-...",
    "operation_type": "training",
    "metrics": {}  # Empty in M1, will have data in M2
  }
}

# 4. POST metrics (accepts but doesn't store in M1)
curl -X POST http://localhost:8000/api/v1/operations/$OPERATION_ID/metrics \
  -H "Content-Type: application/json" \
  -d '{"epoch": 0, "train_loss": 0.5}' | jq

# Expected output:
{
  "success": true,
  "message": "Metrics accepted (not stored until M2)"
}
```

**Manual Validation - MCP Client**:

```bash
# 5. Test MCP client directly
python -c "
import asyncio
from mcp.src.clients.operations_client import OperationsAPIClient

async def test():
    async with OperationsAPIClient() as client:
        result = await client.get_operation_metrics('$OPERATION_ID')
        print(result)

asyncio.run(test())
"

# Expected: Same structure as cURL
```

**Manual Validation - Agent Scripts** (KEY VALIDATION):

```bash
# 6. Run monitoring agent (this is what you'll use every milestone!)
python examples/agents/training_monitor.py $OPERATION_ID

# Expected output:
# ⏳ No metrics yet (M1: API returns empty)
#    Response structure: {'success': True, 'data': {...}}
# (Ctrl+C after seeing this)

# 7. Run analyzer agent
python examples/agents/loss_analyzer.py $OPERATION_ID

# Expected output:
# ❌ Not enough data yet
#    M1: API returns empty metrics
#    Response: {'success': True, 'data': {...}}
```

**Automated Validation**:

```bash
# All tests pass
make test-unit

# All quality checks pass
make quality

# API documentation updated
# Visit http://localhost:8000/api/v1/docs
# Verify new endpoint appears in Swagger UI
```

**Success Criteria**:

- ✅ All tests pass (`make test-unit && make quality`)
- ✅ API endpoints functional (GET + POST)
- ✅ MCP client can query API
- ✅ Agent scripts run without errors
- ✅ Agent scripts show empty metrics with proper messaging
- ✅ Database migration runs cleanly
- ✅ Swagger UI shows new endpoints with descriptions
- **✅ YOU CAN RUN THE SAME AGENT SCRIPTS IN M2 AND SEE DATA APPEAR**

**Commit Message**:

```text
feat(training): add complete metrics API contract + MCP client + agents

API-first approach: Build complete interface before implementation.

Added:
- Operation.metrics field (database migration)
- GET /operations/{id}/metrics (returns empty until M2)
- POST /operations/{id}/metrics (accepts but doesn't store until M2)
- MCP client methods (get_operation_metrics)
- Example agent scripts (training_monitor.py, loss_analyzer.py)
- Comprehensive tests for entire stack

Milestone 1 complete: Complete API contract in place.
Can run agent scripts from day 1 - they handle empty data gracefully.
M2 will "light up" the same endpoints with real data.

Tests: make test-unit && make quality
Manual:
  - curl http://localhost:8000/api/v1/operations/{id}/metrics
  - python examples/agents/training_monitor.py {operation_id}
  - python examples/agents/loss_analyzer.py {operation_id}
```

---

## Milestone 2: Light Up Local Training

**Goal**: Make the API return REAL metrics when training locally. The agent scripts you ran in M1 will now show actual data!

**What Gets Built**:

- ModelTrainer emits full epoch metrics via progress callback
- OperationsService stores metrics and computes trend analysis
- TrainingProgressBridge forwards metrics to OperationsService
- LocalTrainingOrchestrator wires everything together
- POST endpoint actually stores data (was stubbed in M1)
- Comprehensive tests for the entire flow

**What Changes from M1**:

- GET `/operations/{id}/metrics` returns `metrics: {epochs: [...], best_epoch: ...}` instead of `{}`
- POST `/operations/{id}/metrics` actually stores data (was no-op in M1)
- **Agent scripts from M1 now show real data - no code changes needed!**

**Why Local First**: Local training is simpler (no HTTP layer), easier to debug, validates the core logic before adding host service complexity.

### Single Task: Complete Local Training Metrics Pipeline

**Scope**: Build the entire metrics collection flow for local training - from ModelTrainer emitting data, through the bridge, to OperationsService storing and analyzing it. This is a substantial end-to-end implementation.

**Files Modified**:

- `ktrdr/training/model_trainer.py`
- `ktrdr/api/services/operations_service.py`
- `ktrdr/api/services/training/progress_bridge.py`
- `ktrdr/api/services/training/local_orchestrator.py`
- `tests/training/test_model_trainer.py`
- `tests/api/services/test_operations_service.py`
- `tests/api/services/training/test_progress_bridge.py`
- `tests/integration/test_training_metrics_local.py`

**Implementation Details**:

**1. Enhance ModelTrainer** to emit full metrics in progress callback:

```python
# In ModelTrainer.train() - existing epoch callback enhancement
if self.progress_callback:
    epoch_metrics = {
        # ... existing fields (for progress display) ...
        "epoch": epoch,
        "total_epochs": epochs,
        "train_loss": avg_train_loss,
        "val_loss": val_loss,

        # NEW: Add full metrics for storage
        "full_metrics": {
            "epoch": epoch,
            "train_loss": float(avg_train_loss),
            "train_accuracy": float(train_accuracy),
            "val_loss": float(val_loss) if val_loss is not None else None,
            "val_accuracy": float(val_accuracy) if val_accuracy is not None else None,
            "learning_rate": optimizer.param_groups[0]["lr"],
            "duration": duration,
            "timestamp": datetime.utcnow().isoformat(),
        }
    }
    self.progress_callback(epoch, epochs, epoch_metrics)
```

**2. Add OperationsService methods** for metrics storage and analysis (M1 stubbed, now implement):

```python
async def add_metrics(self, operation_id: str, metrics_data: dict) -> None:
    """
    Add domain-specific metrics to an operation.

    M1: Method didn't exist
    M2: Now actually implemented
    """
    operation = await self.get_operation(operation_id)

    if operation.metrics is None:
        operation.metrics = {}

    if operation.type == OperationType.TRAINING:
        await self._add_training_epoch_metrics(operation, metrics_data)
    else:
        operation.metrics.update(metrics_data)

    await self._save_operation(operation)

async def _add_training_epoch_metrics(self, operation: Operation, epoch_metrics: dict) -> None:
    """Add epoch metrics and update trend analysis."""
    if "epochs" not in operation.metrics:
        operation.metrics["epochs"] = []
        operation.metrics["total_epochs_planned"] = 0
        operation.metrics["total_epochs_completed"] = 0

    operation.metrics["epochs"].append(epoch_metrics)
    operation.metrics["total_epochs_completed"] = len(operation.metrics["epochs"])

    self._update_training_metrics_analysis(operation.metrics)

def _update_training_metrics_analysis(self, metrics: dict) -> None:
    """Compute trend indicators: best epoch, overfitting, plateau."""
    epochs = metrics.get("epochs", [])
    if not epochs:
        return

    # Find best epoch (lowest val_loss)
    val_losses = [(i, e["val_loss"]) for i, e in enumerate(epochs) if e.get("val_loss")]
    if val_losses:
        best_idx, best_loss = min(val_losses, key=lambda x: x[1])
        metrics["best_epoch"] = best_idx
        metrics["best_val_loss"] = best_loss
        metrics["epochs_since_improvement"] = len(epochs) - 1 - best_idx

    # Detect overfitting (train ↓, val ↑)
    if len(epochs) >= 10:
        recent = epochs[-10:]
        train_trend = recent[-1]["train_loss"] < recent[0]["train_loss"]
        val_trend = recent[-1].get("val_loss", 0) > recent[0].get("val_loss", 0)
        metrics["is_overfitting"] = train_trend and val_trend

    # Detect plateau
    metrics["is_plateaued"] = metrics.get("epochs_since_improvement", 0) >= 10
```

**3. Enhance TrainingProgressBridge** to forward metrics:

```python
class TrainingProgressBridge:
    def __init__(
        self,
        # ... existing params ...
        update_callback: Optional[Callable] = None,  # NEW
    ):
        self._update_callback = update_callback
        # ... existing init ...

    def on_epoch(self, epoch: int, total_epochs: int, metrics: dict) -> None:
        """Handle epoch completion."""
        # ... existing progress update logic ...

        # NEW: Store full metrics if available
        if "full_metrics" in metrics and self._update_callback:
            self._store_epoch_metrics(metrics["full_metrics"])

    def _store_epoch_metrics(self, epoch_metrics: dict) -> None:
        """Store epoch metrics via callback."""
        if self._update_callback:
            self._update_callback(
                operation_id=self._context.operation_id,
                metrics_update=epoch_metrics
            )
```

**4. Wire up LocalTrainingOrchestrator** to provide metrics callback:

```python
class LocalTrainingOrchestrator:
    async def train(self, context: TrainingOperationContext) -> dict:
        """Execute local training."""
        # ... existing setup ...

        # Create progress bridge with metrics callback
        progress_bridge = TrainingProgressBridge(
            context=context,
            progress_manager=progress_manager,
            update_callback=self._create_metrics_callback(context),  # NEW
            # ... existing params ...
        )

        # ... rest of training ...

    def _create_metrics_callback(self, context: TrainingOperationContext) -> Callable:
        """
        Create callback that stores metrics in OperationsService.

        M1: Callback didn't exist
        M2: Calls OperationsService.add_metrics() which now works
        """
        def callback(operation_id: str, metrics_update: dict) -> None:
            try:
                asyncio.create_task(
                    self.operations_service.add_metrics(operation_id, metrics_update)
                )
            except Exception as e:
                logger.error(f"Failed to store metrics: {e}")

        return callback
```

**5. Update POST endpoint** to actually store (was stubbed in M1):

```python
@router.post("/operations/{operation_id}/metrics")
async def add_operation_metrics(
    operation_id: str,
    metrics: dict[str, Any] = Body(...),
    operations_service: OperationsService = Depends(get_operations_service)
) -> StandardResponse:
    """
    Add metrics to an operation.

    M1: Accepted but didn't store
    M2: NOW ACTUALLY STORES via OperationsService.add_metrics()
    """
    await operations_service.add_metrics(operation_id, metrics)  # NOW IMPLEMENTED

    return StandardResponse(
        success=True,
        message="Metrics added successfully"
    )
```

**TDD Workflow**:

1. Write tests for ModelTrainer metrics emission
2. Write tests for OperationsService methods (storage + trend analysis)
3. Write tests for TrainingProgressBridge metrics forwarding
4. Write integration test for full flow
5. Implement ModelTrainer changes
6. Implement OperationsService methods
7. Implement TrainingProgressBridge changes
8. Implement LocalTrainingOrchestrator changes
9. Run test suite: `make test-unit`
10. Run integration tests: `make test-integration`
11. Run quality checks: `make quality`
12. Manual end-to-end validation

**Tests to Write**:

- **ModelTrainer**: Verify `full_metrics` in callback payload, verify structure
- **OperationsService**: Test epoch appending, test trend analysis (best_epoch, overfitting, plateau)
- **TrainingProgressBridge**: Test callback invocation, test backward compatibility
- **LocalOrchestrator**: Test callback creation
- **Integration**: Full 10-epoch training, verify all metrics stored and analyzed

### Milestone 2 Acceptance Criteria

**End-to-End Test - API Returns Real Data Now**:

```bash
# 1. Ensure local training mode
export USE_TRAINING_HOST_SERVICE=false
./docker_dev.sh start

# 2. Start a small training job
uv run ktrdr models train --strategy config/strategies/example.yaml --epochs 10

# 3. Get operation ID from output
OPERATION_ID=<from training output>

# 4. Query metrics with cURL (M1: returned {}, M2: returns data!)
curl http://localhost:8000/api/v1/operations/$OPERATION_ID/metrics | jq

# Expected output (COMPARE TO M1 - NOW HAS DATA!):
{
  "success": true,
  "data": {
    "operation_id": "op-training-...",
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
        },
        // ... 9 more epochs
      ],
      "best_epoch": 7,
      "best_val_loss": 0.4123,
      "epochs_since_improvement": 2,
      "is_overfitting": false,
      "is_plateaued": false,
      "total_epochs_planned": 10,
      "total_epochs_completed": 10
    }
  }
}
```

**KEY VALIDATION - Same Agent Scripts from M1 Now Show Data**:

```bash
# 5. Run THE SAME monitoring agent from M1
python examples/agents/training_monitor.py $OPERATION_ID

# M1 output was: "⏳ No metrics yet"
# M2 output NOW IS:
# ✅ Epoch 0: train_loss=0.8234, val_loss=0.8912
# ✅ Epoch 1: train_loss=0.7123, val_loss=0.7456
# ... continues for all epochs

# 6. Run THE SAME analyzer agent from M1
python examples/agents/loss_analyzer.py $OPERATION_ID

# M1 output was: "❌ Not enough data yet"
# M2 output NOW IS:
# 📈 Loss Trend Analysis
#    Recent trend (last 10 epochs): improving
#    Change: -15.3%
#    Val loss: 0.8912 → 0.4123
#
# 🏆 Best Performance
#    Epoch 7 with val_loss=0.4123
#    2 epochs since improvement
#
# 💡 Recommendation: CONTINUE TRAINING
#    Model is still improving
```

**Automated Tests**:

```bash
# All tests pass
make test-unit
make test-integration

# Quality checks pass
make quality
```

**Success Criteria**:

- ✅ All 10 epochs appear in metrics
- ✅ Each epoch has all required fields (train_loss, val_loss, accuracy, learning_rate, duration, timestamp)
- ✅ Trend indicators computed correctly (best_epoch, epochs_since_improvement, is_overfitting, is_plateaued)
- ✅ No errors in logs during training
- ✅ Training completes successfully
- ✅ Metrics available immediately after each epoch
- ✅ All tests pass
- ✅ Quality checks pass

**Commit Message**:

```
feat(training): add metrics collection for local training

Complete end-to-end metrics pipeline for local training mode:
- ModelTrainer emits full epoch metrics in progress callback
- TrainingProgressBridge forwards metrics to storage
- OperationsService stores metrics and computes trend analysis
- LocalTrainingOrchestrator wires the complete flow
- Comprehensive unit and integration tests

Trend analysis includes:
- Best epoch detection (lowest val_loss)
- Overfitting detection (train ↓, val ↑)
- Plateau detection (no improvement in 10 epochs)

Milestone 2 complete: Local training metrics fully functional.
Can train locally and query complete epoch history with trend analysis.

Tests: make test-unit && make test-integration && make quality
Manual: Train 10 epochs, query metrics via API
```

---

## Milestone 3: Light Up Host Service (GPU Training)

**Goal**: Make the same API work when training runs on host service for GPU acceleration. Agent scripts still work with no changes!

**What Gets Built**:

- Training host service endpoint to receive metrics from bridge
- Training host service forwards metrics to Docker API via HTTP
- POST endpoint in Docker API to receive metrics
- HostTrainingOrchestrator sends metrics through HTTP layer
- Tests for HTTP forwarding and end-to-end host service flow

**Why After M2**: Host service adds HTTP complexity. We validate the core logic works locally first, then extend to remote execution.

### Single Task: Complete Host Service Metrics Pipeline

**Scope**: Extend the metrics collection to work through the HTTP layer when training runs on the host machine. This includes both host service and Docker API changes, plus testing the complete flow.

**Files Modified**:

- `training-host-service/main.py` (or endpoint file)
- `ktrdr/api/endpoints/operations.py`
- `training-host-service/orchestrator.py`
- `tests/training_host_service/test_metrics_endpoint.py`
- `tests/integration/test_training_metrics_host.py`

**Implementation Details**:

**1. Add metrics endpoint to Training Host Service**:

```python
@app.post("/sessions/{session_id}/metrics")
async def receive_session_metrics(
    session_id: str,
    request: SessionMetricsUpdate
):
    """
    Receive epoch metrics from training session.
    Forward to main API in Docker for storage.
    """
    session = get_session(session_id)

    # Forward to Docker API
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{API_URL}/api/v1/operations/{session.operation_id}/metrics",
            json=request.metrics,
            timeout=5.0
        )

    return {"success": True}

class SessionMetricsUpdate(BaseModel):
    metrics: dict[str, Any]
```

**2. Add POST metrics endpoint to Docker API**:

```python
@router.post(
    "/operations/{operation_id}/metrics",
    response_model=StandardResponse,
    tags=["Operations"],
)
async def add_operation_metrics(
    operation_id: str,
    metrics: dict[str, Any] = Body(...),
    operations_service: OperationsService = Depends(get_operations_service)
) -> StandardResponse:
    """
    Add metrics to an operation.

    Called by:
    - LocalTrainingOrchestrator (direct call)
    - Training host service (HTTP from host machine)
    """
    await operations_service.add_metrics(operation_id, metrics)
    return StandardResponse(success=True, message="Metrics added")
```

**3. Enhance HostTrainingOrchestrator** to send metrics via HTTP:

```python
class HostTrainingOrchestrator:
    def _create_metrics_callback(self, session_id: str) -> Callable:
        """Create callback that sends metrics to API via HTTP."""
        def callback(operation_id: str, metrics_update: dict) -> None:
            try:
                asyncio.create_task(
                    self.api_client.post(
                        f"/sessions/{session_id}/metrics",
                        json={"metrics": metrics_update},
                        timeout=5.0
                    )
                )
            except Exception as e:
                logger.error(f"Failed to send metrics: {e}")

        return callback
```

**TDD Workflow**:

1. Write tests for host service metrics endpoint (forwarding logic)
2. Write tests for Docker API POST endpoint
3. Write integration test for full host service flow
4. Implement host service endpoint
5. Implement Docker API endpoint
6. Implement HostTrainingOrchestrator changes
7. Run test suite: `make test-unit`
8. Run integration tests: `make test-integration`
9. Run quality checks: `make quality`
10. Manual end-to-end validation with GPU training

**Tests to Write**:

- **Host service endpoint**: Test HTTP forwarding, test error handling, test timeout handling
- **Docker API endpoint**: Test metrics storage, test with valid/invalid operation IDs
- **Integration**: Full GPU training with host service, verify metrics flow correctly

### Milestone 3 Acceptance Criteria

**End-to-End Test**:

```bash
# 1. Start training host service
cd training-host-service
./start.sh

# 2. Start API with host service mode enabled
export USE_TRAINING_HOST_SERVICE=true
./docker_dev.sh start

# 3. Start a small training job (will run on GPU)
uv run ktrdr models train --strategy config/strategies/example.yaml --epochs 10

# 4. Watch logs in both services to verify HTTP flow
tail -f training-host-service/logs/training-host-service.log
# Should see: "Received metrics for session {id}, forwarding to API"

docker logs ktrdr-backend -f
# Should see: "Added metrics for operation {id}"

# 5. Query metrics after training
OPERATION_ID=<from training output>
curl http://localhost:8000/api/v1/operations/$OPERATION_ID/metrics | jq

# Expected: Same structure as local mode, all 10 epochs present
```

**Success Criteria**:

- ✅ Training completes successfully on host service
- ✅ All 10 epochs appear in metrics
- ✅ No HTTP errors in logs (host or Docker)
- ✅ Metrics structure identical to local mode
- ✅ Trend analysis works correctly
- ✅ No performance degradation (HTTP calls are async)
- ✅ All tests pass
- ✅ Quality checks pass

**Commit Message**:

```
feat(training): add metrics collection for host service training

Extend metrics collection to work through HTTP layer for GPU training:
- Training host service receives and forwards epoch metrics
- Docker API accepts metrics from host service via HTTP POST
- HostTrainingOrchestrator sends metrics through HTTP
- Same metrics structure and analysis as local mode
- Comprehensive tests for HTTP forwarding and error handling

Milestone 3 complete: Host service training metrics fully functional.
Can train on GPU and query complete epoch history with trend analysis.

Tests: make test-unit && make test-integration && make quality
Manual: Train 10 epochs on host service, query metrics via API
```

---

## Milestone 4: MCP Integration

**Goal**: Enable AI agents to query and analyze training metrics via MCP client.

**What Gets Built**:

- MCP client methods for fetching metrics
- Agent example scripts demonstrating real-world usage
- Documentation for agent developers
- Tests for MCP client integration

**Why Last**: Validates the entire system works end-to-end from training → storage → API → MCP → agent decision making.

### Single Task: Complete MCP Client Integration

**Scope**: Build the complete agent access layer - MCP client methods, example scripts that demonstrate intelligent monitoring, and comprehensive documentation.

**Files Modified**:

- `mcp/src/clients/operations_client.py`
- `examples/agents/training_monitor.py` (new)
- `examples/agents/loss_analyzer.py` (new)
- `docs/guides/agent-training-metrics.md` (new)
- `tests/unit/mcp/test_operations_client.py`
- `tests/integration/test_mcp_training_metrics.py`

**Implementation Details**:

**1. Add MCP client methods**:

```python
class OperationsAPIClient(BaseAPIClient):
    async def get_operation_metrics(self, operation_id: str) -> dict[str, Any]:
        """
        Get domain-specific metrics for an operation.

        For training operations: returns epoch history + trend analysis

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
        """Get operation status, optionally including metrics."""
        params = {}
        if include_metrics:
            params["include_metrics"] = "true"

        return await self._request("GET", f"/operations/{operation_id}", params=params)
```

**2. Create example agent scripts** (see full examples in detailed plan above):

- `training_monitor.py`: Monitors training in real-time, detects overfitting/plateaus
- `loss_analyzer.py`: Analyzes loss trends and provides recommendations

**3. Write documentation** explaining:

- How to query metrics via MCP
- Metrics structure and field meanings
- Trend indicator interpretations
- Example agent workflows
- Best practices for monitoring

**TDD Workflow**:

1. Write tests for MCP client methods
2. Write integration tests with real API
3. Implement MCP client methods
4. Create example agent scripts
5. Test agent scripts with real training
6. Write documentation
7. Run test suite: `make test-unit`
8. Run integration tests: `make test-integration`
9. Run quality checks: `make quality`
10. Manual validation with agent scripts

**Tests to Write**:

- **MCP client**: Test metrics fetching, test status with metrics, test error handling
- **Integration**: Test agent querying real training metrics, verify data correctness
- **Agent scripts**: Verify scripts run without errors, handle edge cases

### Milestone 4 Acceptance Criteria

**End-to-End Agent Test**:

```bash
# 1. Start a training job (50 epochs for realistic testing)
uv run ktrdr models train --strategy config/strategies/example.yaml --epochs 50 &
OPERATION_ID=<from output>

# 2. In another terminal, run monitoring agent
python examples/agents/training_monitor.py $OPERATION_ID

# Expected output every 30 seconds:
# ⏳ Training starting, no metrics yet...
# ✅ Epoch 0: train_loss=0.8234, val_loss=0.8912
# ✅ Epoch 1: train_loss=0.7123, val_loss=0.7456
# ✅ Epoch 10: train_loss=0.5234, val_loss=0.5891
# ... continues until complete or issue detected

# 3. After training, run analyzer
python examples/agents/loss_analyzer.py $OPERATION_ID

# Expected output:
# 📈 Loss Trend Analysis
#    Recent trend (last 10 epochs): improving
#    Change: -15.3%
#    Val loss: 0.5891 → 0.4981
#
# 🏆 Best Performance
#    Epoch 42 with val_loss=0.3987
#    3 epochs since improvement
#
# 💡 Recommendation: CONTINUE TRAINING
#    Model is still improving
```

**Success Criteria**:

- ✅ MCP client methods work correctly
- ✅ Agent scripts run without errors
- ✅ Agents provide useful, accurate recommendations
- ✅ Error handling works (API down, no metrics, incomplete training)
- ✅ Documentation is clear and complete
- ✅ All tests pass
- ✅ Quality checks pass

**Commit Message**:

```text
feat(mcp): add training metrics support for AI agents

Complete MCP integration for agent access to training metrics:
- MCP client methods for querying training metrics
- Example agent scripts (monitor + analyzer) demonstrating real usage
- Comprehensive documentation for agent developers
- Integration tests for MCP → API → metrics flow

Agents can now:
- Monitor training in real-time
- Detect overfitting and plateaus
- Analyze loss trends
- Provide intelligent recommendations (continue, stop, use best checkpoint)

Milestone 4 complete: Agents can monitor and analyze training intelligently.

Tests: make test-unit && make test-integration && make quality
Manual: Run example agents with 50-epoch training
```

---

## Final Integration & Polish

**After all milestones**, do a final polish pass:

### Final Checklist

**Documentation**:

- [ ] Update main README with metrics capabilities
- [ ] Update API documentation (Swagger/OpenAPI descriptions)
- [ ] Update developer guide with metrics section

**Performance Validation**:

- [ ] Run 100-epoch training, verify storage < 50KB
- [ ] Verify no performance degradation vs. baseline
- [ ] Check database query performance

**Optional Enhancements**:

- [ ] Create Jupyter notebook for metrics visualization
- [ ] Add metrics comparison between training runs

### Final Commit

```
docs(training): complete metrics exposure documentation

- Update README with metrics capabilities and examples
- Enhanced API documentation with detailed descriptions
- Performance validation (100 epochs, <50KB, no degradation)
- Optional: Jupyter notebook for metrics visualization

All 4 milestones complete:
✅ M1: Foundation (storage + API)
✅ M2: Local training metrics
✅ M3: Host service training metrics
✅ M4: MCP integration for agents

Agents can now intelligently monitor training and make decisions
about early stopping, overfitting, and training health.
```

---

## Testing Strategy Summary

### Per Milestone

**M1 (Foundation)**:

- Unit tests: Model, API endpoint
- Manual: cURL validation
- Quality: `make test-unit && make quality`

**M2 (Local Training)**:

- Unit tests: ModelTrainer, OperationsService, Bridge, Orchestrator
- Integration test: Full 10-epoch training flow
- Manual: Train locally, inspect metrics
- Quality: `make test-unit && make test-integration && make quality`

**M3 (Host Service)**:

- Unit tests: Host service endpoint, Docker API endpoint
- Integration test: Full GPU training flow
- Manual: Train on host service, inspect metrics and logs
- Quality: `make test-unit && make test-integration && make quality`

**M4 (MCP Integration)**:

- Unit tests: MCP client methods
- Integration test: Agent querying real metrics
- Manual: Run example agent scripts with real training
- Quality: `make test-unit && make test-integration && make quality`

### Before Each Commit

```bash
# Run full test suite
make test-unit
make test-integration

# Run quality checks
make quality

# Manual validation
# (specific to each milestone)
```

---

## Rollback Plan

If issues are discovered at any milestone:

**M1**: Simply revert commit - no impact (read-only infrastructure)

**M2**: Training still works (metrics callback is optional, failure just logs error)

**M3**: Falls back gracefully if HTTP endpoints fail, training continues

**M4**: MCP methods fail gracefully if no metrics available, agents handle missing data

**Nuclear Option**:

```bash
# Revert entire feature branch
git checkout main
git branch -D feature/training-metrics-exposure
```

---

## Summary

**4 Milestones, 4 Substantial Tasks, 4 Commits**:

1. **M1 - Foundation** (1 task): Storage + API infrastructure
2. **M2 - Local Training** (1 task): Complete metrics pipeline for local mode
3. **M3 - Host Service** (1 task): Extend to GPU training via HTTP
4. **M4 - MCP Integration** (1 task): Agent access and example scripts

**Each milestone is independently deployable and testable.**

**Branch**: `feature/training-metrics-exposure`

**Each task is substantial** - justifies TDD overhead with full test suite and quality checks.

**Total Estimated Time**: 2-3 days of focused development

**Confidence Level**: High - building on proven infrastructure, clear validation at each step

---

**END OF IMPLEMENTATION PLAN**
