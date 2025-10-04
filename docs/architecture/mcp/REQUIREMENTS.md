# MCP Async Operations Integration - Requirements Document

**Version**: 1.1
**Status**: Draft - In Review
**Last Updated**: 2025-10-04
**Authors**: Claude + Karl

---

## 🎯 PRIMARY PURPOSE

**Enable AI agents to leverage KTRDR's existing async operations infrastructure through MCP tools.**

This is NOT a backend refactor - this is an **MCP integration layer** that exposes existing capabilities to AI agents.

**What Already Exists (Backend):**
- ✅ ServiceOrchestrator pattern for data loading and training
- ✅ OperationsService with in-memory operation tracking
- ✅ Progress tracking (percentage, steps, context)
- ✅ Cancellation with propagation to host services
- ✅ Operation listing with filters
- ✅ Live status updates for training operations

**What We're Building:**
- 🆕 MCP tools that call existing backend APIs
- 🆕 Consistent agent-friendly interface
- 🆕 Operation discovery without prior context

**What We're NOT Building (Out of Scope):**
- ❌ Backend refactors or new backend features
- ❌ New training host service capabilities
- ❌ Graceful cancellation (already exists, just expose it)
- ❌ GPU metrics collection (nice-to-have examples only)

---

## Executive Summary

This document defines requirements for integrating KTRDR's **existing** async operations infrastructure with the MCP (Model Context Protocol) server, enabling AI agents to initiate, monitor, and manage long-running operations through a stateless, token-efficient interface.

**Key Design Principles:**
1. **Leverage Existing Backend** - Use what's already built, minimal backend changes
2. **Stateless MCP Layer** - MCP server is a pure API pass-through, no persistent state
3. **Fire-and-Forget Pattern** - Agents initiate operations, check status when needed (not continuous polling)
4. **Token Efficiency** - Minimize token consumption for agent interactions
5. **Discoverability** - Agents can find operations without prior context

---

## 1. Current State & Gap Analysis

### 1.1 What Exists Today (Backend)

#### **OperationsService** ([ktrdr/api/services/operations_service.py](../ktrdr/api/services/operations_service.py))
- ✅ In-memory operation registry (`_operations` dict)
- ✅ Create, track, update, complete/fail operations
- ✅ Progress tracking with rich context (percentage, steps, domain-specific data)
- ✅ Cancellation support with token propagation
- ✅ List operations with filters (type, status, active_only)
- ✅ Live status updates for training (polls host service)
- ✅ Operation cleanup functionality

#### **Backend API Endpoints**
- ✅ `GET /api/v1/operations` - List operations
- ✅ `GET /api/v1/operations/{operation_id}` - Get operation status
- ✅ `POST /api/v1/operations/{operation_id}/cancel` - Cancel operation
- ✅ `POST /api/v1/data/load` - Trigger data loading (returns operation_id)
- ✅ `POST /api/v1/trainings/start` - Start training (returns operation_id)

#### **Async Infrastructure**
- ✅ ServiceOrchestrator for data and training managers
- ✅ GenericProgressManager for progress tracking
- ✅ CancellationCoordinator for unified cancellation
- ✅ Host service integration (IB data, GPU training)
- ✅ Graceful cancellation with checkpoint save

### 1.2 What's Missing (The Gap)

#### **MCP Server** ([mcp/src/server.py](../../mcp/src/server.py))
- ❌ No tools to list/query existing operations
- ❌ No tools to get operation status/progress
- ❌ No tools to cancel operations
- ❌ Training tools don't return operation_id for tracking
- ❌ Data loading tools don't expose async pattern

**The Gap**: MCP server can trigger operations but can't manage them.

---

## 2. Core Requirements

### 2.1 MCP Tool Suite

> **Implementation Note**: These are NEW MCP tools that call EXISTING backend endpoints. No backend changes needed unless explicitly noted.

#### **2.1.1 Data Operations**

##### ✅ `get_market_data()` (Already Exists - No Changes)
**Purpose**: Get cached market data (fast, synchronous)
**Backend**: `GET /api/v1/data/{symbol}/{timeframe}`
**Implementation**: Already exists in MCP, no changes needed

---

##### 🆕 `trigger_data_loading()` (New MCP Tool)
**Purpose**: Initiate async data loading from external sources (IB Gateway)
**Backend**: `POST /api/v1/data/load` (already exists ✅)
**Implementation**: Rename existing `load_data_from_source()` and ensure it returns operation_id

```python
@mcp.tool()
async def trigger_data_loading(
    symbol: str,
    timeframe: str = "1h",
    mode: str = "tail",  # local, tail, backfill, full
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> dict[str, Any]:
    """Trigger async data loading operation (returns operation_id for tracking)

    This does NOT return market data - it initiates a background loading operation.
    Use get_market_data() to retrieve the loaded data after operation completes.
    """
    async with get_api_client() as client:
        result = await client.load_data_operation(
            symbol, timeframe, mode, start_date, end_date
        )
        return result  # Contains operation_id
```

**Returns**:
```json
{
  "success": true,
  "operation_id": "op_data_load_20251004_143022_a4b3c2d1",
  "operation_type": "data_load",
  "status": "started",
  "message": "Data loading started for AAPL 1h (tail mode)"
}
```

---

#### **2.1.2 Training Operations**

##### 🆕 `start_training()` (Update Existing MCP Tool)
**Purpose**: Initiate neural network training
**Backend**: `POST /api/v1/trainings/start` (already exists ✅)
**Implementation**: Update existing `start_model_training()` to return operation_id

```python
@mcp.tool()
async def start_training(
    strategy_config_path: str,
    symbols: list[str],
    timeframes: list[str] = ["1h"],
    training_config: Optional[dict] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> dict[str, Any]:
    """Start neural network training (returns operation_id for tracking)"""
    async with get_api_client() as client:
        result = await client.start_neural_training(
            symbols=symbols,
            timeframe=timeframes[0],  # Backend limitation - single timeframe
            config=training_config or {},
            start_date=start_date,
            end_date=end_date
        )
        return result  # Contains operation_id
```

**Returns**:
```json
{
  "success": true,
  "operation_id": "op_training_20251004_143530_b5c6d7e8",
  "operation_type": "training",
  "status": "started",
  "message": "Training started for MLP strategy on AAPL, MSFT"
}
```

> **Backend Note**: Training endpoint should integrate with OperationsService to return operation_id (minor backend enhancement needed)

---

#### **2.1.3 Generic Operation Management**

##### 🆕 `list_operations()` (New MCP Tool)
**Purpose**: Discover operations without prior knowledge
**Backend**: `GET /api/v1/operations` (already exists ✅)
**Implementation**: New MCP tool calling existing endpoint

```python
@mcp.tool()
async def list_operations(
    operation_type: Optional[str] = None,  # "data_load", "training"
    status: Optional[str] = None,  # "pending", "running", "completed", "failed", "cancelled"
    active_only: bool = False,  # Only pending + running
    limit: int = 10,  # Default to 10 most recent
    offset: int = 0
) -> dict[str, Any]:
    """List operations with optional filters

    Examples:
    - list_operations(active_only=True) → All running operations
    - list_operations(operation_type="training", status="running") → Active training
    - list_operations(status="failed", limit=5) → Last 5 failed operations
    """
    async with get_api_client() as client:
        result = await client.list_operations(
            operation_type=operation_type,
            status=status,
            active_only=active_only,
            limit=limit,
            offset=offset
        )
        return result
```

**Returns**:
```json
{
  "success": true,
  "data": [
    {
      "operation_id": "op_training_20251004_143530_b5c6d7e8",
      "operation_type": "training",
      "status": "running",
      "created_at": "2025-10-04T14:35:30Z",
      "progress_percentage": 65.2,
      "current_step": "Epoch 32/50",
      "symbol": "AAPL",
      "duration_seconds": 1247.5
    }
  ],
  "total_count": 47,
  "active_count": 2,
  "returned_count": 10
}
```

**Pagination Note**: Default limit is 10. Agent can request more with `limit` parameter. Always returns most recent operations first (sorted by `created_at` DESC).

---

##### 🆕 `get_operation_status()` (New MCP Tool)
**Purpose**: Get detailed status and progress for specific operation
**Backend**: `GET /api/v1/operations/{operation_id}` (already exists ✅)
**Implementation**: New MCP tool calling existing endpoint

```python
@mcp.tool()
async def get_operation_status(
    operation_id: str
) -> dict[str, Any]:
    """Get detailed operation status with progress and context

    Returns rich progress information including domain-specific context
    (e.g., epochs/batches for training, segments for data loading)
    """
    async with get_api_client() as client:
        result = await client.get_operation_status(operation_id)
        return result
```

**Returns** (Training - Running):
```json
{
  "success": true,
  "data": {
    "operation_id": "op_training_20251004_143530_b5c6d7e8",
    "operation_type": "training",
    "status": "running",
    "created_at": "2025-10-04T14:35:30Z",
    "started_at": "2025-10-04T14:35:35Z",
    "progress": {
      "percentage": 65.2,
      "current_step": "Epoch 32/50, Batch 245/640",
      "steps_completed": 32,
      "steps_total": 50,
      "context": {
        "epoch_index": 32,
        "total_epochs": 50,
        "batch_number": 245,
        "batch_total": 640,
        "epoch_metrics": {
          "train_loss": 0.0234,
          "val_loss": 0.0312
        }
      }
    },
    "metadata": {
      "symbol": "AAPL",
      "parameters": {
        "strategy_name": "mlp_basic",
        "symbols": ["AAPL", "MSFT"],
        "session_id": "train_session_a4b3c2d1"
      }
    }
  }
}
```

**Returns** (Data Load - Completed):
```json
{
  "success": true,
  "data": {
    "operation_id": "op_data_load_20251004_140012_c8d9e0f1",
    "operation_type": "data_load",
    "status": "completed",
    "progress": {
      "percentage": 100.0,
      "current_step": "Data loading complete"
    },
    "result_summary": {
      "bars_loaded": 1247,
      "date_range": {
        "start": "2024-01-01",
        "end": "2025-10-03"
      },
      "gaps_filled": 3,
      "data_source": "ib_gateway"
    }
  }
}
```

**Returns** (Training - Failed):
```json
{
  "success": true,
  "data": {
    "operation_id": "op_training_20251004_150000_x9y8z7w6",
    "operation_type": "training",
    "status": "failed",
    "completed_at": "2025-10-04T15:12:45Z",
    "error_message": "Training failed: CUDA out of memory",
    "progress": {
      "percentage": 12.5,
      "current_step": "Epoch 6/50 (failed)"
    }
  }
}
```

> **Note**: The `context` field contains domain-specific details. GPU metrics (if present) are included but NOT required - they're already collected by the training host service if available.

---

##### 🆕 `cancel_operation()` (New MCP Tool)
**Purpose**: Cancel a running operation
**Backend**: `POST /api/v1/operations/{operation_id}/cancel` (already exists ✅)
**Implementation**: New MCP tool calling existing endpoint

```python
@mcp.tool()
async def cancel_operation(
    operation_id: str,
    reason: Optional[str] = None
) -> dict[str, Any]:
    """Cancel a running operation

    Cancellation propagates to backend → host services → processes.
    Graceful shutdown with checkpoint save is already supported by the backend.
    """
    async with get_api_client() as client:
        result = await client.cancel_operation(operation_id, reason)
        return result
```

**Returns**:
```json
{
  "success": true,
  "data": {
    "operation_id": "op_training_20251004_143530_b5c6d7e8",
    "status": "cancelled",
    "cancelled_at": "2025-10-04T15:12:45Z",
    "cancellation_reason": "User changed strategy parameters",
    "task_cancelled": true,
    "training_session_cancelled": true
  }
}
```

> **Implementation Note**: Graceful cancellation already exists in the backend. No new functionality needed - just expose it via MCP.

---

##### 🆕 `get_operation_results()` (New MCP Tool + Backend Enhancement)
**Purpose**: Retrieve summary results and analytics paths from completed operation
**Backend**: `GET /api/v1/operations/{operation_id}/results` (NEW endpoint needed)
**Implementation**: New MCP tool + new backend endpoint

```python
@mcp.tool()
async def get_operation_results(
    operation_id: str
) -> dict[str, Any]:
    """Get operation results (summary metrics + paths to detailed analytics)

    Returns lightweight summary metrics and paths/links to detailed data.
    Works for any operation type (data loading, training, backtesting).
    """
    async with get_api_client() as client:
        result = await client.get_operation_results(operation_id)
        return result
```

**Returns** (Training):
```json
{
  "success": true,
  "operation_id": "op_training_20251004_143530_b5c6d7e8",
  "operation_type": "training",
  "status": "completed",
  "results": {
    "training_metrics": {
      "final_train_loss": 0.0187,
      "final_val_loss": 0.0245,
      "epochs_completed": 50,
      "training_time_minutes": 32.5
    },
    "validation_metrics": {
      "accuracy": 0.892,
      "precision": 0.875
    },
    "artifacts": {
      "model_path": "/data/models/mlp_basic_AAPL_MSFT_20251004.pt",
      "analytics_directory": "/data/training/mlp_basic_20251004_143530/analytics"
    }
  }
}
```

**Returns** (Data Loading):
```json
{
  "success": true,
  "operation_id": "op_data_load_20251004_140012_c8d9e0f1",
  "operation_type": "data_load",
  "status": "completed",
  "results": {
    "bars_loaded": 1247,
    "date_range": {
      "start": "2024-01-01",
      "end": "2025-10-03"
    },
    "gaps_filled": 3,
    "segments_processed": 5,
    "data_source": "ib_gateway",
    "cache_updated": true,
    "storage_location": "/data/cache/TSLA_1d.parquet"
  }
}
```

> **Backend Enhancement Needed**: Create new endpoint `/api/v1/operations/{operation_id}/results` that returns `result_summary` from OperationInfo.

---

##### ⏭️ Phase 2: Operation-Type-Specific Details (Future)

For deep-dive analytics, Phase 2 will add **operation-type-specific** detail tools and endpoints:

**Training Details** - `get_training_details(operation_id)`:
- Full epoch-by-epoch training history
- Loss curves, accuracy plots
- Confusion matrices, feature importance
- Hyperparameter tuning results

**Backtest Details** - `get_backtest_details(operation_id)`:
- Trade-by-trade breakdown
- Equity curves, drawdown analysis
- Risk metrics over time
- Performance by market regime

**Data Loading Details** - `get_data_loading_details(operation_id)`:
- Segment-by-segment validation results
- Gap detection and filling analysis
- Data quality metrics
- Source-specific diagnostics

> **Note**: These are future enhancements (Phase 2). Phase 1 provides summary metrics + paths to analytics files via `get_operation_results()`.

---

### 2.2 Backend Requirements

#### **2.2.1 What Already Exists (No Changes)**
- ✅ OperationsService with full operation tracking
- ✅ Progress tracking with rich context
- ✅ Cancellation with propagation
- ✅ Live status updates for training
- ✅ Graceful shutdown with checkpoint save
- ✅ List operations with filters

#### **2.2.2 Minor Backend Enhancements Needed**

##### Enhancement 1: Training Endpoint Integration
**File**: [ktrdr/api/endpoints/training.py](../../ktrdr/api/endpoints/training.py)
**Change**: Ensure `POST /api/v1/trainings/start` returns operation_id from OperationsService

**Before**:
```python
# Returns training task_id (internal)
{"task_id": "train_session_a4b3c2d1", ...}
```

**After**:
```python
# Returns operation_id from OperationsService
{"operation_id": "op_training_20251004_143530_b5c6d7e8", "task_id": "...", ...}
```

##### Enhancement 2: Results Endpoint
**File**: [ktrdr/api/endpoints/operations.py](../../ktrdr/api/endpoints/operations.py)
**Change**: Add new endpoint `GET /api/v1/operations/{operation_id}/results`

```python
@router.get("/operations/{operation_id}/results")
async def get_operation_results(
    operation_id: str,
    operations_service: OperationsService = Depends(get_operations_service)
):
    """Get operation results (returns result_summary from OperationInfo)"""
    operation = await operations_service.get_operation(operation_id)

    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")

    if operation.status not in [OperationStatus.COMPLETED, OperationStatus.FAILED]:
        raise HTTPException(
            status_code=400,
            detail=f"Operation not finished (status: {operation.status})"
        )

    return {
        "success": True,
        "operation_id": operation_id,
        "operation_type": operation.operation_type,
        "status": operation.status,
        "results": operation.result_summary
    }
```

##### Enhancement 3: API Client Methods
**File**: [mcp/src/api_client.py](../../mcp/src/api_client.py)
**Change**: Add new methods to KTRDRAPIClient

```python
class KTRDRAPIClient:
    # ... existing methods ...

    async def list_operations(
        self,
        operation_type: Optional[str] = None,
        status: Optional[str] = None,
        active_only: bool = False,
        limit: int = 10,
        offset: int = 0
    ) -> dict[str, Any]:
        """List operations with filters"""
        params = {"limit": limit, "offset": offset}
        if operation_type:
            params["operation_type"] = operation_type
        if status:
            params["status"] = status
        if active_only:
            params["active_only"] = active_only

        return await self._request("GET", "/api/v1/operations", params=params)

    async def get_operation_status(self, operation_id: str) -> dict[str, Any]:
        """Get operation status"""
        return await self._request("GET", f"/api/v1/operations/{operation_id}")

    async def cancel_operation(
        self, operation_id: str, reason: Optional[str] = None
    ) -> dict[str, Any]:
        """Cancel operation"""
        payload = {"reason": reason} if reason else {}
        return await self._request(
            "POST", f"/api/v1/operations/{operation_id}/cancel", json=payload
        )

    async def get_operation_results(self, operation_id: str) -> dict[str, Any]:
        """Get operation results"""
        return await self._request("GET", f"/api/v1/operations/{operation_id}/results")
```

#### **2.2.3 Pagination & Operation Lifecycle**
**File**: [ktrdr/api/services/operations_service.py](../../ktrdr/api/services/operations_service.py)
**Status**: Already implemented ✅

The existing `list_operations()` method already supports pagination:
```python
async def list_operations(
    self,
    status: Optional[OperationStatus] = None,
    operation_type: Optional[OperationType] = None,
    limit: int = 100,  # Default 100, we'll change to 10 in API layer
    offset: int = 0,
    active_only: bool = False,
) -> tuple[list[OperationInfo], int, int]:
```

**Minor Changes**:
1. API endpoint should default `limit=10` instead of 100
2. Operations sorted by `created_at` DESC (most recent first) - already implemented ✅

**Operation Cleanup Policy**:
- **No automatic cleanup** - operations remain in registry indefinitely
- Agents use pagination to get most recent operations (default limit=10)
- Manual cleanup via `cleanup_old_operations()` method if needed (already exists ✅)
- Phase 2: PostgreSQL persistence will enable configurable retention policies

---

### 2.3 Agent Experience

#### **2.3.1 Fire-and-Forget Pattern**
✅ Agent initiates operation → receives operation_id
✅ Agent stores operation_id in conversation context
✅ Agent checks status **when needed** (not continuous polling)
✅ **Token Efficient**: Only query when user asks or checking completion

**Example Agent Workflow**:
```python
# Agent initiates training
result = start_training(strategy_config_path="mlp_basic", symbols=["AAPL"])
operation_id = result["operation_id"]

# Agent continues with other tasks...
# ... hours later, user asks "how's training?" ...

status = get_operation_status(operation_id)
# Agent: "Training is 65% complete (Epoch 32/50)"
```

#### **2.3.2 Discoverability**
✅ Agent can list operations without prior knowledge
✅ Agent can filter by type, status, active state
✅ Agent can find "orphaned" operations from previous sessions

**Example**:
```python
# New conversation, no prior context
operations = list_operations(operation_type="training", active_only=True)

# Agent: "I found 1 active training operation (AAPL, 85% complete)"
```

#### **2.3.3 Error Handling & Recovery**
✅ Failed operations store status and detailed error message
✅ Error message includes exception details when applicable
✅ Agents can query failed operations and understand what went wrong
✅ **No retry functionality** in Phase 1 - agents can start new operations if needed

**Example**:
```python
# Agent checks failed operation
status = get_operation_status("op_training_20251004_150000_x9y8z7w6")

# Response includes failure details:
# {
#   "status": "failed",
#   "error_message": "Training failed: CUDA out of memory at epoch 6/50",
#   "progress": {"percentage": 12.5, "current_step": "Epoch 6/50 (failed)"}
# }

# Agent can inform user and suggest actions (reduce batch size, use CPU, etc.)
```

#### **2.3.4 Example Scenarios (Illustrative Only)**

> **Important**: These scenarios illustrate what agents CAN DO with the existing system. They are NOT new features to implement.

**Scenario 1**: Agent sees training stuck
- Agent queries status, sees `progress_percentage: 12.0` hasn't changed in 30 minutes
- Agent investigates (checks logs) or cancels
- **Capability**: Already exists via `get_operation_status()` and `cancel_operation()`

**Scenario 2**: Agent monitors GPU usage (if available)
- Agent queries status, sees `context.gpu_usage.utilization_percent: 5`
- Agent recognizes potential configuration issue
- **Capability**: Already exists - training host service may include GPU metrics in progress context (optional, not required)

**Scenario 3**: Agent detects validation loss increasing
- Agent queries status, sees `context.epoch_metrics.val_loss` increasing
- Agent considers early stopping
- **Capability**: Already exists via progress context

> **Note to Future Implementation**: These scenarios require NO new backend features. They illustrate capabilities already present in the existing progress tracking system.

---

## 3. What We're NOT Building

### ❌ Out of Scope (No Implementation Required)

1. **Backend Refactors**
   - OperationsService is sufficient as-is
   - No new progress tracking mechanisms
   - No new cancellation systems

2. **Training Host Service Changes**
   - Graceful cancellation already exists ✅
   - GPU metrics already collected (if available) ✅
   - No new monitoring capabilities needed

3. **New Async Infrastructure**
   - ServiceOrchestrator is sufficient ✅
   - GenericProgressManager is sufficient ✅
   - CancellationCoordinator is sufficient ✅

4. **Phase 1 Exclusions**
   - PostgreSQL persistence (Phase 2)
   - Detailed results API (Phase 2)
   - Backtesting async operations (Phase 2 - not migrated to ServiceOrchestrator yet)
   - Operation retry/resume
   - Streaming progress (SSE/WebSockets)

---

## 4. Implementation Summary

### Phase 1: MCP Async Operations

**New MCP Tools** (Primary Deliverable):
1. ✅ `trigger_data_loading()` - Rename existing, ensure returns operation_id
2. ✅ `start_training()` - Update existing, ensure returns operation_id
3. 🆕 `list_operations()` - New tool
4. 🆕 `get_operation_status()` - New tool
5. 🆕 `cancel_operation()` - New tool
6. 🆕 `get_operation_results()` - New tool

**Minor Backend Changes**:
1. Training endpoint returns operation_id (5 lines of code)
2. New results endpoint (20 lines of code)
3. API client new methods (30 lines of code)
4. API endpoint default limit to 10 (1 line)

**Zero Backend Refactors**: We're using what exists.

### Phase 2: Future Enhancements

⏭️ **PostgreSQL Persistence**: Docker container initially, configurable for remote database
⏭️ **Operation-Type-Specific Detail APIs**: `get_training_details()`, `get_backtest_details()`, `get_data_loading_details()`
⏭️ **Backtesting Async Operations**: After backtesting migrates to ServiceOrchestrator pattern

---

## 5. Success Criteria

### Phase 1 Complete When:
- [ ] Agent can trigger data loading via `trigger_data_loading()` and receive operation_id
- [ ] Agent can start training via `start_training()` and receive operation_id
- [ ] Agent can list operations with `list_operations()` (type, status, active filters)
- [ ] Agent can query operation status with `get_operation_status()`
- [ ] Agent can cancel operations with `cancel_operation()`
- [ ] Agent can get summary results with `get_operation_results()`
- [ ] Pagination works with default limit=10, sorted by most recent
- [ ] All operations tracked in-memory by existing OperationsService
- [ ] Zero backend refactors (only 4 minor enhancements)
- [ ] Backward compatible (existing MCP tools still work)

---

## Appendix A: API Endpoint Mapping

| MCP Tool | Backend Endpoint | Method | Status |
|----------|------------------|--------|--------|
| `get_market_data()` | `/api/v1/data/{symbol}/{timeframe}` | GET | ✅ Exists |
| `trigger_data_loading()` | `/api/v1/data/load` | POST | ✅ Exists |
| `start_training()` | `/api/v1/trainings/start` | POST | ✅ Exists (minor update needed) |
| `list_operations()` | `/api/v1/operations` | GET | ✅ Exists |
| `get_operation_status()` | `/api/v1/operations/{operation_id}` | GET | ✅ Exists |
| `cancel_operation()` | `/api/v1/operations/{operation_id}/cancel` | POST | ✅ Exists |
| `get_operation_results()` | `/api/v1/operations/{operation_id}/results` | GET | 🆕 New endpoint |

**Phase 2 Endpoints (Type-Specific Details)**:
| Tool | Endpoint | Method |
|------|----------|--------|
| `get_training_details()` | `/api/v1/trainings/{operation_id}/details` | GET |
| `get_backtest_details()` | `/api/v1/backtests/{operation_id}/details` | GET |
| `get_data_loading_details()` | `/api/v1/data/{operation_id}/details` | GET |

---

## Appendix B: Example Agent Workflows

### Workflow 1: Training a Model (Fire-and-Forget)
```python
# === Conversation Turn 1: User asks to train ===
# Agent initiates training
result = start_training(
    strategy_config_path="mlp_basic",
    symbols=["AAPL", "MSFT"],
    timeframes=["1h"]
)
operation_id = result["operation_id"]
# Agent: "Training started! Operation ID: op_training_20251004_143530_b5c6d7e8"
# Agent stores operation_id in context

# === 30 minutes later, different conversation turn ===
# User: "How's the training going?"
status = get_operation_status(operation_id)
# Agent: "Training is 65% complete, currently on Epoch 32/50 with validation loss of 0.0312"

# === 1 hour later ===
# User: "Is it done yet?"
status = get_operation_status(operation_id)
if status["status"] == "completed":
    results = get_operation_results(operation_id)
    # Agent: "Yes! Training completed. Final accuracy: 89.2%, model saved to /data/models/..."
```

### Workflow 2: Discovering Orphaned Operations
```python
# New conversation, agent has no prior context
operations = list_operations(active_only=True)

# Discovers operations from previous session
# Agent: "I found 2 active operations:
#  1. Training AAPL (85% complete, started 2 hours ago)
#  2. Data loading TSLA (failed - connection error)"

# Agent can take action
cancel_operation("op_training_...", reason="User wants different strategy")
```

### Workflow 3: Data Loading then Analysis
```python
# === User asks for fresh data ===
result = trigger_data_loading(
    symbol="TSLA",
    timeframe="1d",
    mode="tail",
    start_date="2024-01-01"
)
operation_id = result["operation_id"]
# Agent: "Data loading started, operation ID: op_data_load_..."

# === Later, check if complete ===
status = get_operation_status(operation_id)
if status["status"] == "completed":
    # Now get the actual data
    data = get_market_data(symbol="TSLA", timeframe="1d", start_date="2024-01-01")
    # Agent analyzes the fresh data
```

---

**End of Requirements Document**
