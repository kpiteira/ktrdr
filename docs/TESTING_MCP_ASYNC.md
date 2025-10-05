# Testing MCP Async Operations from Claude Desktop

This guide provides detailed instructions for testing the new MCP async operations tools from Claude Desktop.

## Prerequisites

1. **KTRDR backend running** on `http://localhost:8000`
2. **MCP server rebuilt** with new tools
3. **Claude Desktop connected** to MCP server

---

## Step 1: Rebuild MCP Server

First, rebuild the MCP container to include the new tools:

```bash
cd ~/Documents/dev/ktrdr2/mcp
./build_mcp.sh
```

Wait for rebuild to complete (~30 seconds).

---

## Step 2: Restart Claude Desktop

**Close and reopen Claude Desktop** to reconnect to the MCP server.

**Verify connection**: In a new Claude Desktop conversation, the MCP tools should be available.

---

## Step 3: Basic Health Check

Start by verifying the backend is accessible:

### Test 1: Check Backend Health

In Claude Desktop, ask:

```
Can you check if the KTRDR backend is healthy?
```

**Expected behavior**: Claude should use the `check_backend_health()` tool and report the backend status.

**Expected output**:
```json
{
  "status": "healthy",
  "health": {...},
  "message": "KTRDR backend is accessible and healthy"
}
```

✅ **Success**: Backend is reachable
❌ **Failure**: Start KTRDR backend with `./start_ktrdr.sh`

---

## Step 4: Test Operations Management Tools

### Test 2: List Current Operations

Ask Claude:

```
Show me all active operations
```

**Expected behavior**: Claude uses `list_operations(active_only=True)`

**Expected output**:
```json
{
  "success": true,
  "data": [...],
  "total_count": X,
  "active_count": X
}
```

If no operations are running, you'll see empty lists. That's normal!

---

### Test 3: Trigger Data Loading (Async Operation)

Ask Claude:

```
Load AAPL daily data for 2024
```

**Expected behavior**:
1. Claude uses `trigger_data_loading("AAPL", "1d", start_date="2024-01-01", end_date="2024-12-31")`
2. Returns immediately with an `operation_id`

**Expected output**:
```json
{
  "success": true,
  "operation_id": "op_data_load_AAPL_1d_20241004_125500",
  "status": "Operation started",
  ...
}
```

✅ **Success**: Got operation_id back immediately
❌ **Failure**: Check if IB Gateway is running or use `mode="local"`

---

### Test 4: Monitor Operation Progress

While the data loading is running, ask Claude:

```
What's the status of operation op_data_load_AAPL_1d_20241004_125500?
```

(Use the actual operation_id from Test 3)

**Expected behavior**: Claude uses `get_operation_status(operation_id)`

**Expected output**:
```json
{
  "success": true,
  "data": {
    "operation_id": "op_data_load_...",
    "status": "running",  // or "completed"
    "progress": 45.5,
    "message": "Loading bars: 1825/4000",
    "eta_seconds": 15,
    ...
  }
}
```

**Status progression**: `pending` → `running` → `completed` or `failed`

✅ **Success**: See progress updates
❌ **Failure**: Operation might have completed too quickly (that's OK!)

---

### Test 5: Get Operation Results

Once the operation completes, ask Claude:

```
Show me the results of operation op_data_load_AAPL_1d_20241004_125500
```

**Expected behavior**: Claude uses `get_operation_results(operation_id)`

**Expected output**:
```json
{
  "success": true,
  "operation_id": "op_data_load_...",
  "operation_type": "data_load",
  "status": "completed",
  "results": {
    "bars_loaded": 252,
    "date_range": "2024-01-01 to 2024-12-31",
    "symbol": "AAPL",
    "timeframe": "1d"
  }
}
```

✅ **Success**: Results show bars loaded
❌ **Failure**: Check operation completed successfully first

---

### Test 6: Cancel an Operation

Start a long data load and cancel it:

```
Load EURUSD 5-minute data for all of 2024
```

Then immediately:

```
Cancel that operation
```

**Expected behavior**:
1. First request starts operation with `trigger_data_loading()`
2. Second request uses `cancel_operation(operation_id, reason="User requested cancellation")`

**Expected output**:
```json
{
  "success": true,
  "data": {
    "status": "cancelled",
    "message": "Operation cancelled"
  }
}
```

✅ **Success**: Operation cancelled
⚠️ **Note**: If operation completes too fast, cancellation will fail (operation must be in `running` status)

---

## Step 5: Test Training Operations

### Test 7: Start Neural Training (Async)

Ask Claude:

```
Start training a neural network on AAPL hourly data
```

**Expected behavior**: Claude uses `start_training(symbols=["AAPL"], timeframe="1h")`

**Expected output**:
```json
{
  "success": true,
  "operation_id": "op_training_20241004_130000",
  "task_id": "op_training_20241004_130000",  // backward compat
  "status": "training_started",
  "symbols": ["AAPL"],
  "timeframes": ["1h"],
  ...
}
```

**Note**: Training takes several minutes. Operation returns immediately.

---

### Test 8: Monitor Training Progress

While training is running:

```
What's the status of the training operation?
```

**Expected behavior**: Claude uses `get_operation_status()` with the training operation_id

**Expected output** (example):
```json
{
  "success": true,
  "data": {
    "operation_id": "op_training_...",
    "status": "running",
    "progress": 25.0,
    "message": "Epoch 25/100",
    "context": {
      "epoch": 25,
      "total_epochs": 100,
      "loss": 0.0234,
      "accuracy": 0.8452
    },
    "eta_seconds": 180
  }
}
```

✅ **Success**: See epoch progress and loss/accuracy metrics

---

### Test 9: Get Training Results

After training completes:

```
Show me the training results
```

**Expected behavior**: Claude uses `get_operation_results()` for the training operation

**Expected output**:
```json
{
  "success": true,
  "operation_id": "op_training_...",
  "operation_type": "training",
  "status": "completed",
  "results": {
    "final_loss": 0.0123,
    "final_accuracy": 0.8934,
    "epochs_completed": 100,
    "training_time_seconds": 456.7,
    "model_path": "/path/to/model.pth"
  }
}
```

---

## Step 6: Advanced Workflows

### Test 10: Multi-Step Workflow

Test the complete data loading → training workflow:

```
I want to train a model on MSFT. First load hourly data for 2024, then start training when the data is ready.
```

**Expected behavior**: Claude orchestrates:
1. `trigger_data_loading("MSFT", "1h", start_date="2024-01-01", end_date="2024-12-31")`
2. Polls `get_operation_status()` until data loading completes
3. `start_training(symbols=["MSFT"], timeframe="1h")`
4. Polls `get_operation_status()` for training progress

**This tests**: Sequential async operations with proper waiting

---

### Test 11: List and Filter Operations

```
Show me all completed training operations
```

**Expected behavior**: `list_operations(operation_type="training", status="completed")`

```
Show me the last 5 operations
```

**Expected behavior**: `list_operations(limit=5)`

---

### Test 12: Error Handling

Test error scenarios:

**A) Invalid symbol:**
```
Load data for symbol INVALID_SYMBOL_XYZ
```

**Expected**: Error message from backend about invalid symbol

**B) Get results for running operation:**
```
Get results for operation op_training_... (while it's still running)
```

**Expected**: 400 error - "Operation not finished"

**C) Cancel completed operation:**
```
Cancel operation op_data_load_... (after it completed)
```

**Expected**: Error - can't cancel completed operation

---

## Troubleshooting

### Issue: Claude can't find the tools

**Solution**:
1. Rebuild MCP: `cd mcp && ./build_mcp.sh`
2. Restart Claude Desktop completely
3. Check MCP logs: `docker logs ktrdr-mcp`

### Issue: Backend not reachable

**Solution**:
```bash
# Check backend is running
curl http://localhost:8000/health

# If not running, start it
./start_ktrdr.sh
```

### Issue: Operations complete too fast to monitor

**Solution**: Use larger datasets or slower operations:
```
Load EURUSD 1-minute data for all of 2024 (this takes longer)
```

### Issue: Training fails with "No data available"

**Solution**: Load data first before training:
```
1. Load AAPL hourly data for 2024
2. Wait for it to complete
3. Then start training
```

---

## Expected Test Results Summary

| Test | Expected Result | Time |
|------|----------------|------|
| 1. Health check | Backend healthy | <1s |
| 2. List operations | Empty or populated list | <1s |
| 3. Trigger data loading | operation_id returned | <1s |
| 4. Monitor progress | Progress updates | 1-30s |
| 5. Get results | bars_loaded data | <1s |
| 6. Cancel operation | Operation cancelled | <1s |
| 7. Start training | operation_id returned | <1s |
| 8. Monitor training | Epoch progress | 1-5min |
| 9. Training results | Model metrics | <1s |
| 10. Multi-step workflow | Complete pipeline | 2-10min |

---

## Success Criteria

✅ **All 6 new tools work correctly**:
- `list_operations`
- `get_operation_status`
- `cancel_operation`
- `get_operation_results`
- `trigger_data_loading`
- `start_training`

✅ **Async operations lifecycle**:
- Start operation (get operation_id)
- Monitor progress (poll status)
- Get results (when completed)
- Cancel if needed

✅ **Error handling**:
- Invalid parameters rejected
- Appropriate errors for wrong operation states
- Backend errors propagated correctly

---

## Quick Test Script

For rapid testing, you can copy-paste this conversation to Claude Desktop:

```
1. Check if KTRDR backend is healthy
2. List all active operations
3. Load AAPL daily data for 2024
4. Monitor that operation's progress
5. When it completes, show me the results
6. Now start training on AAPL hourly data
7. Show me the training progress every 30 seconds
```

Claude should execute all these steps using the new MCP tools!

---

## Need Help?

- **MCP Server Logs**: `docker logs ktrdr-mcp`
- **Backend Logs**: `docker logs ktrdr-backend`
- **MCP Tools Documentation**: [mcp/MCP_TOOLS.md](../mcp/MCP_TOOLS.md)
- **Issue Tracker**: Create GitHub issue with logs

---

**Last Updated**: 2024-12-04
**PR**: #73
**Branch**: `feature/mcp-async-operations`
