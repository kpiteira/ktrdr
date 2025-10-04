# KTRDR MCP Tools Documentation

This document describes all available MCP tools exposed by the KTRDR MCP server for AI agent integration.

## Table of Contents

1. [Async Operations Management](#async-operations-management)
2. [Data Operations](#data-operations)
3. [Training Operations](#training-operations)
4. [Market Data & Research](#market-data--research)
5. [Backtesting](#backtesting)

---

## Async Operations Management

The KTRDR backend executes long-running operations (data loading, training, backtesting) asynchronously. These tools allow AI agents to manage and monitor these operations.

### `list_operations`

List all async operations with optional filtering.

**Parameters:**
- `operation_type` (optional): Filter by type (`data_load`, `training`, `backtest`)
- `status` (optional): Filter by status (`running`, `completed`, `failed`, `cancelled`, `pending`)
- `active_only` (bool, default: False): Show only active (running/pending) operations
- `limit` (int, default: 10): Maximum operations to return (max 100)

**Returns:** List of operations with metadata (status, progress, created_at, etc.)

**Example Usage:**
```python
# List all active operations
operations = await list_operations(active_only=True)

# List recent training operations
training_ops = await list_operations(operation_type="training", limit=5)
```

### `get_operation_status`

Get detailed status of a specific operation for progress monitoring.

**Parameters:**
- `operation_id` (required): Unique operation identifier

**Returns:** Detailed operation state including:
- Current status (`running`, `completed`, etc.)
- Progress percentage
- ETA (estimated time to completion)
- Result summary (if completed)
- Error details (if failed)

**Example Usage:**
```python
# Poll for progress
status = await get_operation_status("op_training_20241201_123456")
print(f"Progress: {status['progress']}%")
```

### `cancel_operation`

Cancel a running async operation.

**Parameters:**
- `operation_id` (required): Operation to cancel
- `reason` (optional): Cancellation reason for audit trail

**Returns:** Cancellation confirmation

**Example Usage:**
```python
# Cancel a long-running data load
result = await cancel_operation(
    "op_data_load_20241201_123456",
    reason="User requested cancellation"
)
```

### `get_operation_results`

Retrieve results from a completed or failed operation.

**Parameters:**
- `operation_id` (required): Operation identifier

**Returns:** Result summary with:
- Metrics and statistics
- Paths to detailed artifacts
- Performance data

**Example Usage:**
```python
# Get training results
results = await get_operation_results("op_training_20241201_123456")
print(f"Model accuracy: {results['results']['accuracy']}")
```

---

## Data Operations

### `trigger_data_loading`

Start an async data loading operation.

**Parameters:**
- `symbol` (required): Trading symbol (e.g., "AAPL", "EURUSD")
- `timeframe` (default: "1h"): Data timeframe (`1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`)
- `start_date` (optional): Start date in YYYY-MM-DD format
- `end_date` (optional): End date in YYYY-MM-DD format
- `mode` (default: "local"): Loading mode (`local`, `ib`, `hybrid`)

**Returns:** Operation ID for tracking

**Example Usage:**
```python
# Load AAPL data for last year
result = await trigger_data_loading(
    symbol="AAPL",
    timeframe="1d",
    start_date="2024-01-01",
    end_date="2024-12-31",
    mode="ib"
)

# Monitor progress
operation_id = result["operation_id"]
status = await get_operation_status(operation_id)
```

### `get_market_data`

Get cached market data for analysis (fast, synchronous, local only).

**Parameters:**
- `symbol` (required): Trading symbol
- `timeframe` (default: "1h"): Data timeframe
- `start_date` (optional): Start date filter
- `end_date` (optional): End date filter
- `trading_hours_only` (default: False): Filter to trading hours only
- `limit_bars` (default: 50): Maximum bars to return

**Returns:** OHLCV data with dates

**Note:** This is a synchronous tool for quick data retrieval. For loading new data, use `trigger_data_loading`.

---

## Training Operations

### `start_training`

Start an async neural network training operation.

**Parameters:**
- `symbols` (required): List of symbols to train on (e.g., `["AAPL", "MSFT"]`)
- `timeframe` (default: "1h"): Data timeframe
- `config` (optional): Training configuration dict with:
  - `epochs` (default: 100)
  - `batch_size` (default: 32)
  - `learning_rate` (default: 0.001)
- `start_date` (optional): Training data start date
- `end_date` (optional): Training data end date

**Returns:** Operation ID for tracking

**Example Usage:**
```python
# Start multi-symbol training
result = await start_training(
    symbols=["AAPL", "MSFT", "GOOGL"],
    timeframe="1h",
    config={
        "epochs": 200,
        "batch_size": 64,
        "learning_rate": 0.0001
    },
    start_date="2023-01-01",
    end_date="2024-12-31"
)

# Monitor training progress
operation_id = result["operation_id"]
while True:
    status = await get_operation_status(operation_id)
    if status["status"] in ["completed", "failed"]:
        break
    print(f"Epoch {status['context']['epoch']}, Loss: {status['context']['loss']}")
    await asyncio.sleep(5)

# Get final results
results = await get_operation_results(operation_id)
```

---

## Market Data & Research

### `check_backend_health`

Check if KTRDR backend is healthy and accessible.

**Returns:** Health status and backend info

### `get_available_symbols`

Get list of all available trading symbols with metadata.

**Returns:** List of symbols with details

---

## Backtesting

(See existing tools in MCP server for backtesting functionality)

---

## Workflow Examples

### Complete Training Workflow

```python
# 1. Check backend health
health = await check_backend_health()
assert health["status"] == "healthy"

# 2. Load data if needed
data_op = await trigger_data_loading(
    symbol="AAPL",
    timeframe="1h",
    start_date="2023-01-01",
    end_date="2024-12-31"
)

# 3. Wait for data loading
while True:
    status = await get_operation_status(data_op["operation_id"])
    if status["status"] == "completed":
        break
    await asyncio.sleep(2)

# 4. Start training
training_op = await start_training(
    symbols=["AAPL"],
    timeframe="1h",
    config={"epochs": 100}
)

# 5. Monitor training
while True:
    status = await get_operation_status(training_op["operation_id"])
    if status["status"] in ["completed", "failed"]:
        break
    print(f"Progress: {status['progress']}%")
    await asyncio.sleep(10)

# 6. Get results
if status["status"] == "completed":
    results = await get_operation_results(training_op["operation_id"])
    print(f"Model performance: {results['results']}")
```

### Monitoring Multiple Operations

```python
# Start multiple operations
ops = []
for symbol in ["AAPL", "MSFT", "GOOGL"]:
    op = await trigger_data_loading(symbol=symbol, timeframe="1d")
    ops.append(op["operation_id"])

# Monitor all
while ops:
    for op_id in ops[:]:
        status = await get_operation_status(op_id)
        if status["status"] in ["completed", "failed"]:
            print(f"{op_id}: {status['status']}")
            ops.remove(op_id)
    await asyncio.sleep(5)
```

---

## Architecture

The MCP tools use a **domain-specific client architecture**:

```
MCP Tools
   ↓
KTRDRAPIClient (Unified Facade)
   ├── operations: OperationsAPIClient
   ├── data: DataAPIClient
   └── training: TrainingAPIClient
         ↓
    BaseAPIClient (Shared HTTP)
         ↓
   KTRDR Backend API (FastAPI)
```

**Benefits:**
- Clean separation of concerns
- Type-safe operations
- Consistent error handling
- Easy to extend with new domains

---

## Error Handling

All tools raise exceptions on errors. Common error patterns:

```python
try:
    result = await start_training(symbols=["INVALID"])
except Exception as e:
    print(f"Training failed: {e}")
    # Handle error appropriately
```

**Common Errors:**
- **404**: Operation/resource not found
- **400**: Invalid parameters or operation not in expected state
- **500**: Backend error (check backend health)
- **Connection Error**: Backend not accessible

---

## Best Practices

1. **Always check backend health** before starting operations
2. **Use operation IDs** to track long-running tasks
3. **Poll periodically** for status updates (every 5-10 seconds)
4. **Handle failures gracefully** - check operation status before getting results
5. **Cancel operations** if no longer needed to free resources
6. **Use filters** in `list_operations` to reduce response size
7. **Set reasonable limits** when fetching data to avoid timeouts

---

## Version

- **MCP Server Version**: 0.2.0
- **API Version**: v1
- **Last Updated**: 2024-12-01
