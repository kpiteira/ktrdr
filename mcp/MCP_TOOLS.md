# KTRDR MCP Tools Documentation

This document describes all available MCP tools exposed by the KTRDR MCP server for AI agent integration.

**Architecture**: The MCP server is a **pure interface layer** that delegates all business logic and data management to the backend API. It does not maintain any local state or storage.

## Table of Contents

1. [System Health](#system-health)
2. [Async Operations Management](#async-operations-management)
3. [Data Operations](#data-operations)
4. [Market Data & Research](#market-data--research)
5. [Training Operations](#training-operations)

---

## System Health

### `check_backend_health`

Check if the KTRDR backend API is accessible and healthy.

**Parameters:** None

**Returns:** Health status with service information

**Example:**
```python
health = await check_backend_health()
print(f"Backend status: {health['status']}")
```

---

## Async Operations Management

The KTRDR backend executes long-running operations (data loading, training) asynchronously. These tools allow monitoring and control.

### `list_operations`

List all async operations with optional filtering.

**Parameters:**
- `operation_type` (optional): Filter by type (`data_load`, `training`)
- `status` (optional): Filter by status (`running`, `completed`, `failed`, `cancelled`, `pending`)
- `active_only` (bool, default: False): Show only active operations
- `limit` (int, default: 10): Maximum operations to return

**Returns:** List of operations with status, progress, timestamps

**Example:**
```python
# List all active operations
operations = await list_operations(active_only=True)

# List recent training operations
training_ops = await list_operations(operation_type="training", limit=5)
```

### `get_operation_status`

Get detailed status of a specific operation.

**Parameters:**
- `operation_id` (required): Unique operation identifier

**Returns:** Status, progress percentage, ETA, results/errors

**Example:**
```python
status = await get_operation_status("op_training_20241201_123456")
print(f"Progress: {status['progress']}%")
```

### `cancel_operation`

Cancel a running async operation.

**Parameters:**
- `operation_id` (required): Operation to cancel
- `reason` (optional): Cancellation reason

**Returns:** Cancellation confirmation

**Example:**
```python
await cancel_operation("op_data_load_123", reason="User requested")
```

### `get_operation_results`

Retrieve results from a completed operation.

**Parameters:**
- `operation_id` (required): Operation identifier

**Returns:** Result summary with metrics, artifacts, performance data

**Example:**
```python
results = await get_operation_results("op_training_123")
print(f"Model accuracy: {results['results']['accuracy']}")
```

---

## Data Operations

### `get_available_symbols`

Get list of available trading symbols from the backend.

**Parameters:** None

**Returns:** List of supported symbols with metadata

**Example:**
```python
symbols = await get_available_symbols()
```

### `get_market_data`

Retrieve historical market data for a symbol.

**Parameters:**
- `symbol` (required): Trading symbol (e.g., "AAPL", "EURUSD")
- `timeframe` (default: "1h"): Data timeframe (1m, 5m, 1h, 4h, 1d)
- `start_date` (optional): Start date (YYYY-MM-DD)
- `end_date` (optional): End date (YYYY-MM-DD)
- `limit` (default: 100): Maximum bars to return

**Returns:** OHLCV data with timestamps

**Example:**
```python
data = await get_market_data("AAPL", timeframe="1d", limit=30)
```

### `trigger_data_loading`

Trigger async data loading operation.

**Parameters:**
- `symbol` (required): Trading symbol
- `timeframe` (default: "1h"): Data timeframe
- `mode` (default: "local"): Loading mode (local, tail, backfill, full)
- `start_date` (optional): Start date for data range
- `end_date` (optional): End date for data range

**Returns:** `operation_id` for tracking the async operation

**Example:**
```python
result = await trigger_data_loading(
    symbol="AAPL",
    timeframe="1h",
    mode="tail"
)
operation_id = result["data"]["operation_id"]

# Monitor progress
status = await get_operation_status(operation_id)
```

### `get_data_summary`

Get summary statistics about available data for a symbol.

**Parameters:**
- `symbol` (required): Trading symbol
- `timeframe` (default: "1h"): Data timeframe

**Returns:** Data range, bar count, gaps, quality metrics

**Example:**
```python
summary = await get_data_summary("AAPL", timeframe="1d")
print(f"Total bars: {summary['bar_count']}")
```

---

## Market Data & Research

### `get_available_indicators`

Get list of available technical indicators.

**Parameters:** None

**Returns:** List of indicators with parameters and descriptions

**Example:**
```python
indicators = await get_available_indicators()
```

### `get_available_strategies`

Get list of available trading strategies.

**Parameters:** None

**Returns:** List of strategy configurations

**Example:**
```python
strategies = await get_available_strategies()
```

---

## Training Operations

### `start_training`

Start async neural network training operation.

**Parameters:**
- `symbols` (required): List of trading symbols (e.g., ["AAPL", "MSFT"])
- `timeframe` (default: "1h"): Data timeframe
- `config` (optional): Training configuration dict (epochs, batch_size, learning_rate, etc.)
- `start_date` (optional): Training data start date
- `end_date` (optional): Training data end date

**Returns:** `operation_id` for tracking the async training

**Example:**
```python
result = await start_training(
    symbols=["AAPL"],
    timeframe="1h",
    config={"epochs": 100, "batch_size": 32}
)
operation_id = result["operation_id"]

# Monitor training progress
status = await get_operation_status(operation_id)
```

### `get_training_status`

Get status of a training operation (alias for get_operation_status for training ops).

**Parameters:**
- `task_id` (required): Training task/operation ID

**Returns:** Training status, progress, metrics

**Example:**
```python
status = await get_training_status("op_training_123")
```

### `get_model_performance`

Get detailed performance metrics for a trained model.

**Parameters:**
- `task_id` (required): Training task ID

**Returns:** Training metrics, test metrics, model information

**Example:**
```python
perf = await get_model_performance("op_training_123")
print(f"Test accuracy: {perf['test_metrics']['accuracy']}")
```

### `test_model_prediction`

Test a trained model with sample data.

**Parameters:**
- `model_name` (required): Name of the trained model
- `symbol` (required): Trading symbol for test data
- `timeframe` (default: "1h"): Data timeframe
- `sample_size` (default: 100): Number of samples to test

**Returns:** Prediction results and evaluation metrics

**Example:**
```python
results = await test_model_prediction(
    model_name="aapl_model_v1",
    symbol="AAPL",
    sample_size=50
)
```

---

## Workflow Examples

### Complete Training Workflow

```python
# 1. Ensure data is loaded
data_result = await trigger_data_loading(
    symbol="AAPL",
    timeframe="1h",
    mode="tail"
)
await get_operation_status(data_result["data"]["operation_id"])

# 2. Start training
training_result = await start_training(
    symbols=["AAPL"],
    timeframe="1h",
    config={"epochs": 100}
)
training_op_id = training_result["operation_id"]

# 3. Monitor training
while True:
    status = await get_operation_status(training_op_id)
    if status["status"] in ["completed", "failed"]:
        break
    print(f"Progress: {status['progress']}%")

# 4. Get results
if status["status"] == "completed":
    results = await get_operation_results(training_op_id)
    perf = await get_model_performance(training_op_id)
```

---

## Architecture Notes

**Design Principle**: The MCP server is a stateless interface layer. All data, operations, and results are managed by the backend API.

**Benefits**:
- ✅ No local state management
- ✅ CLI and MCP have identical capabilities
- ✅ Single source of truth (backend)
- ✅ Simplified MCP server maintenance

**What MCP Does NOT Do**:
- ❌ Store strategies, experiments, or knowledge locally
- ❌ Maintain SQLite databases
- ❌ Duplicate backend functionality
- ❌ Keep operation results after backend restart

**What Backend Provides**:
- ✅ All business logic
- ✅ Data persistence
- ✅ Operation tracking
- ✅ Model storage
- ✅ Strategy execution
