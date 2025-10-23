# E2E Test Guide: Local Training with Pull-Based Operations

## Document Information

**Date**: 2025-01-23
**Purpose**: Manual validation of M1 pull-based operations architecture for local training
**Target Audience**: Human testers (QA, developers)
**Execution Time**: ~30-45 minutes
**Prerequisites**: Backend API running, test dataset available

---

## Overview

This guide provides step-by-step scenarios to validate that local training correctly implements pull-based operations architecture. The key changes being validated:

1. **Workers write to ProgressBridge** (<1μs synchronous writes)
2. **Clients pull via OperationsService** (client-driven refresh)
3. **TTL-based cache** (1-second freshness by default)
4. **NO "no running event loop" errors** (fixed async/sync boundary issue)
5. **Metrics stored correctly** (M2 bug fixed)

**What We're NOT Testing**: Host service integration (that's M2/M3)

---

## Prerequisites

### 1. System Setup

**Backend API must be running:**
```bash
# Option 1: Docker
./docker_dev.sh start

# Option 2: Direct
uv run python scripts/run_api_server.py
```

**Verify API is accessible:**
```bash
curl http://localhost:8000/api/v1/health
# Expected: {"status": "ok"}
```

### 2. Test Data

**Ensure test symbols are available:**
```bash
# Check available data
ktrdr data show AAPL 1d --limit 5

# If needed, load test data
ktrdr data load AAPL 1d --start-date 2023-01-01 --end-date 2023-12-31
```

### 3. Test Strategy Configuration

**Create a simple test strategy:**
```bash
# File: config/strategies/test_e2e.yaml
name: E2E Test Strategy
description: Fast training for E2E validation

training:
  epochs: 10  # Small number for quick testing
  batch_size: 32
  validation_split: 0.2

model:
  type: lstm
  layers: 2
  hidden_size: 64

indicators:
  - name: sma
    period: 20
  - name: rsi
    period: 14
```

---

## Test Scenarios

### Scenario 1: Start Training and Verify Operation Created

**Objective**: Verify training starts and operation is registered correctly.

#### Setup
- Backend API running
- Test strategy file exists (`config/strategies/test_e2e.yaml`)
- Terminal open for commands

#### Actions

1. **Start training:**
   ```bash
   ktrdr models train --strategy config/strategies/test_e2e.yaml \
                       --symbols AAPL \
                       --timeframes 1d \
                       --start-date 2023-01-01 \
                       --end-date 2023-06-30
   ```

2. **Note the operation_id from response:**
   ```
   Training started. Operation ID: op_training_20250123_abc123
   ```

3. **Immediately query the operation:**
   ```bash
   curl http://localhost:8000/api/v1/operations/op_training_20250123_abc123
   ```

#### Expected Outcome

**CLI Output:**
```json
{
  "operation_id": "op_training_20250123_abc123",
  "status": "running",
  "message": "Training started",
  "created_at": "2025-01-23T10:00:00Z"
}
```

**API Response:**
```json
{
  "operation_id": "op_training_20250123_abc123",
  "status": "RUNNING",
  "operation_type": "TRAINING",
  "created_at": "2025-01-23T10:00:00.123Z",
  "updated_at": "2025-01-23T10:00:01.456Z",
  "progress": {
    "percentage": 0.0,
    "message": "Initializing training...",
    "current_step": 0,
    "items_processed": 0
  },
  "metadata": {
    "symbols": ["AAPL"],
    "timeframes": ["1d"],
    "strategy": "test_e2e"
  }
}
```

#### How to Verify

**Check operation was created:**
- ✅ `operation_id` is returned
- ✅ `status` is "RUNNING"
- ✅ `operation_type` is "TRAINING"
- ✅ `progress.percentage` is 0.0 or small value
- ✅ `metadata` contains correct symbols/strategy

**Check logs (backend):**
```bash
# Search for operation creation
docker logs ktrdr-backend | grep "Created operation.*op_training"

# Expected:
# 2025-01-23 10:00:00 INFO Created operation op_training_20250123_abc123
```

#### If It Fails

**Problem: No operation_id returned**
- Check: Is backend API running? (`curl http://localhost:8000/api/v1/health`)
- Check: Are there errors in backend logs? (`docker logs ktrdr-backend`)
- Check: Is strategy file valid? (YAML syntax errors)

**Problem: Status is FAILED immediately**
- Check backend logs for exception stack trace
- Common causes: Missing dependencies, invalid strategy config

---

### Scenario 2: Progress Updates via Pull

**Objective**: Verify progress updates correctly as training progresses via client-driven pull.

#### Setup
- Training running from Scenario 1 (or start new training)
- Have operation_id ready

#### Actions

**Poll operation progress every 5 seconds for ~30 seconds:**
```bash
#!/bin/bash
# Save as: test_progress_polling.sh

OPERATION_ID="op_training_20250123_abc123"  # Replace with your operation_id

for i in {1..6}; do
  echo "=== Poll $i ==="
  curl -s http://localhost:8000/api/v1/operations/$OPERATION_ID | jq '.progress'
  sleep 5
done
```

Run the script:
```bash
chmod +x test_progress_polling.sh
./test_progress_polling.sh
```

#### Expected Outcome

**Progress should increase over time:**

Poll 1 (t=0s):
```json
{
  "percentage": 5.0,
  "message": "Epoch 1/10",
  "current_step": 1,
  "items_processed": 32,
  "epoch_index": 1,
  "total_epochs": 10
}
```

Poll 2 (t=5s):
```json
{
  "percentage": 15.0,
  "message": "Epoch 2/10",
  "current_step": 2,
  "items_processed": 64,
  "epoch_index": 2,
  "total_epochs": 10
}
```

Poll 3 (t=10s):
```json
{
  "percentage": 25.0,
  "message": "Epoch 3/10",
  "current_step": 3,
  "items_processed": 96,
  "epoch_index": 3,
  "total_epochs": 10
}
```

**Key observations:**
- Percentage increases: 5% → 15% → 25% → ...
- Epoch index increases: 1 → 2 → 3 → ...
- Items processed increases monotonically
- Message updates with current epoch

#### How to Verify

**Check progress is updating:**
- ✅ `percentage` increases over time (not stuck at 0%)
- ✅ `message` shows current epoch
- ✅ `epoch_index` increments (1, 2, 3, ...)
- ✅ `items_processed` increases
- ✅ No errors in backend logs

**Check backend logs for cache behavior:**
```bash
# Enable debug logging (set LOG_LEVEL=DEBUG in .env)
docker logs ktrdr-backend | grep "Refreshed operation"

# Expected (every ~1 second when polled):
# 2025-01-23 10:00:01 DEBUG Cache hit for operation op_training_... (age=0.2s)
# 2025-01-23 10:00:05 DEBUG Cache miss for operation op_training_... (age=1.3s) - refreshing
# 2025-01-23 10:00:05 DEBUG Refreshed operation op_training_... from bridge (cursor 0 → 1)
```

**Check for NO async errors:**
```bash
# Search for the old error
docker logs ktrdr-backend | grep "no running event loop"

# Expected: NO RESULTS (this error should NOT appear!)
```

#### If It Fails

**Problem: Progress stuck at 0%**
- Check: Is bridge registered? Search logs for "Registered local bridge"
- Check: Is `_refresh_from_bridge()` being called? Add debug logging
- Check: Is bridge `get_status()` returning data? Add logging to bridge

**Problem: Progress updates but not increasing**
- Check: Is worker calling `bridge.on_epoch()`? Add logging to worker
- Check: Are epoch numbers incrementing in worker logs?

**Problem: "No running event loop" error appears**
- This should NOT happen! If it does, pull architecture not fully implemented
- Check: No `asyncio.create_task()` in TrainingProgressBridge
- Check: No `metrics_callback` parameter in bridge constructor

---

### Scenario 3: Metrics Collection

**Objective**: Verify epoch metrics are being stored correctly and retrievable via API.

#### Setup
- Training running or recently completed
- Have operation_id ready

#### Actions

1. **Query operation metrics:**
   ```bash
   curl -s http://localhost:8000/api/v1/operations/op_training_20250123_abc123/metrics \
        | jq '.'
   ```

2. **Query with cursor (incremental read):**
   ```bash
   # First query (cursor=0, get all metrics)
   curl -s "http://localhost:8000/api/v1/operations/op_training_20250123_abc123/metrics?cursor=0" \
        | jq '.'

   # Second query (cursor=5, get only new metrics since cursor 5)
   curl -s "http://localhost:8000/api/v1/operations/op_training_20250123_abc123/metrics?cursor=5" \
        | jq '.'
   ```

#### Expected Outcome

**First query (cursor=0, get all):**
```json
{
  "metrics": [
    {
      "epoch": 1,
      "train_loss": 2.456,
      "train_accuracy": 0.45,
      "val_loss": 2.512,
      "val_accuracy": 0.43,
      "learning_rate": 0.001,
      "duration": 1.234,
      "timestamp": "2025-01-23T10:00:05Z"
    },
    {
      "epoch": 2,
      "train_loss": 2.123,
      "train_accuracy": 0.52,
      "val_loss": 2.234,
      "val_accuracy": 0.50,
      "learning_rate": 0.001,
      "duration": 1.187,
      "timestamp": "2025-01-23T10:00:07Z"
    },
    // ... more epochs
  ],
  "new_cursor": 10
}
```

**Second query (cursor=5, incremental):**
```json
{
  "metrics": [
    {
      "epoch": 6,
      "train_loss": 1.234,
      "train_accuracy": 0.68,
      // ... only epochs 6-10
    },
    // ...
  ],
  "new_cursor": 10
}
```

**If no new metrics since cursor:**
```json
{
  "metrics": [],
  "new_cursor": 10
}
```

#### How to Verify

**Check metrics are present:**
- ✅ `metrics` array contains epoch data
- ✅ Each metric has `epoch`, `train_loss`, `val_loss`, `train_accuracy`, `val_accuracy`
- ✅ `new_cursor` value equals number of metrics (cursor for next query)

**Check cursor increments:**
- ✅ First query with cursor=0 returns all metrics
- ✅ Second query with cursor=5 returns only metrics since cursor 5
- ✅ Cursor value increases: 0 → 5 → 10
- ✅ No duplicate metrics returned

**Check metrics match epochs:**
- ✅ Number of metrics equals number of completed epochs
- ✅ Epoch numbers are sequential (1, 2, 3, ...)
- ✅ Loss values generally decrease over epochs (training is learning)

#### If It Fails

**Problem: Metrics array is empty**
- Check: Is `on_epoch()` being called? Add logging to bridge
- Check: Is `_append_metric()` being called in `on_epoch()`? Add logging
- Check: Does `get_metrics()` return data? Test bridge directly in unit test

**Problem: Cursor not incrementing**
- Check: Is `_metrics_cursors` being updated in `_refresh_from_bridge()`?
- Check backend logs for cursor tracking

**Problem: Duplicate metrics**
- Check: Is cursor being stored correctly after each query?
- Check: Cursor should increment after metrics are appended

---

### Scenario 4: Training Completion

**Objective**: Verify training completes successfully and operation status updates.

#### Setup
- Start a training with small epoch count (5-10 epochs) for faster completion
- Have operation_id ready

#### Actions

1. **Wait for training to complete** (or monitor in real-time):
   ```bash
   # Poll until status is COMPLETED
   while true; do
     STATUS=$(curl -s http://localhost:8000/api/v1/operations/op_training_20250123_abc123 | jq -r '.status')
     echo "Status: $STATUS"
     if [ "$STATUS" = "COMPLETED" ]; then
       echo "Training completed!"
       break
     fi
     sleep 5
   done
   ```

2. **Query final operation state:**
   ```bash
   curl -s http://localhost:8000/api/v1/operations/op_training_20250123_abc123 | jq '.'
   ```

3. **Query operation results:**
   ```bash
   curl -s http://localhost:8000/api/v1/operations/op_training_20250123_abc123/results | jq '.'
   ```

#### Expected Outcome

**Operation status:**
```json
{
  "operation_id": "op_training_20250123_abc123",
  "status": "COMPLETED",
  "operation_type": "TRAINING",
  "created_at": "2025-01-23T10:00:00Z",
  "updated_at": "2025-01-23T10:05:30Z",
  "completed_at": "2025-01-23T10:05:30Z",
  "progress": {
    "percentage": 100.0,
    "message": "Training completed",
    "current_step": 10,
    "items_processed": 320,
    "epoch_index": 10,
    "total_epochs": 10
  },
  "metadata": {
    "symbols": ["AAPL"],
    "final_epoch": 10,
    "best_val_loss": 0.856
  }
}
```

**Results:**
```json
{
  "status": "success",
  "final_metrics": {
    "best_epoch": 8,
    "best_val_loss": 0.856,
    "best_val_accuracy": 0.72,
    "final_train_loss": 0.723,
    "final_val_loss": 0.921,
    "total_epochs": 10,
    "training_duration_seconds": 124.5
  },
  "model_path": "/path/to/model.pkl",
  "artifacts": {
    "metrics_plot": "/path/to/metrics.png",
    "model_summary": "/path/to/summary.txt"
  }
}
```

#### How to Verify

**Check completion status:**
- ✅ `status` is "COMPLETED"
- ✅ `completed_at` timestamp is present
- ✅ `progress.percentage` is 100.0
- ✅ `progress.message` indicates completion

**Check no further refreshes after completion:**
```bash
# Query the completed operation multiple times
for i in {1..5}; do
  curl -s http://localhost:8000/api/v1/operations/op_training_20250123_abc123 > /dev/null
  sleep 1
done

# Check logs - should see NO refresh calls for COMPLETED operations
docker logs ktrdr-backend | grep "Refreshed operation.*op_training_20250123_abc123"

# Expected: No new refresh logs after completion (completed ops are immutable)
```

**Check results are stored:**
- ✅ Results contain final metrics
- ✅ Model path is present
- ✅ Training duration is reasonable

#### If It Fails

**Problem: Training never completes (stuck in RUNNING)**
- Check: Did worker finish? Check worker logs for completion
- Check: Did orchestrator call `complete_operation()`? Check logs
- Check: Are there exceptions in worker? Check error logs

**Problem: Status is COMPLETED but percentage < 100%**
- This is OK if training was cancelled early
- If not cancelled: Check progress calculation logic in bridge

**Problem: Refresh still happening after completion**
- Check: Does `get_operation()` skip refresh for COMPLETED status?
- Check condition: `if operation.status == RUNNING and operation_id in self._local_bridges`

---

### Scenario 5: Bridge Registration Verification

**Objective**: Verify bridge is registered correctly when training starts.

#### Setup
- Backend API running
- Terminal ready to start training
- Log level set to DEBUG for detailed logs

#### Actions

1. **Enable debug logging:**
   ```bash
   # In .env or environment
   export LOG_LEVEL=DEBUG

   # Restart backend if needed
   docker-compose restart backend
   ```

2. **Start training:**
   ```bash
   ktrdr models train --strategy config/strategies/test_e2e.yaml \
                       --symbols AAPL \
                       --timeframes 1d
   ```

3. **Immediately check logs:**
   ```bash
   docker logs ktrdr-backend | grep -A 5 "Registered local bridge"
   ```

#### Expected Outcome

**Log output:**
```
2025-01-23 10:00:00.123 INFO Created operation op_training_20250123_abc123 (type=TRAINING)
2025-01-23 10:00:00.125 INFO Registered local bridge for operation op_training_20250123_abc123
2025-01-23 10:00:00.126 DEBUG Bridge registered, starting training worker
2025-01-23 10:00:00.127 INFO Starting training: symbols=['AAPL'], epochs=10
```

**Verify internal state (via debug endpoint if available, or check logs):**
```
2025-01-23 10:00:00.128 DEBUG _local_bridges contains op_training_20250123_abc123
2025-01-23 10:00:00.128 DEBUG _metrics_cursors[op_training_20250123_abc123] = 0
```

#### How to Verify

**Check registration happens:**
- ✅ "Registered local bridge" log appears
- ✅ Registration happens BEFORE "Starting training"
- ✅ Operation ID in registration matches created operation

**Check registration order:**
1. Create operation
2. Create bridge
3. **Register bridge** ← Must happen here
4. Start worker
5. Worker calls `bridge.on_epoch()`

**Check bridge is accessible:**
```bash
# After registration, first poll should work
curl -s http://localhost:8000/api/v1/operations/op_training_20250123_abc123 | jq '.progress'

# Expected: Progress data returned (not null)
```

#### If It Fails

**Problem: "Registered local bridge" log not found**
- Check: Is `register_local_bridge()` being called in TrainingService?
- Check: Is logging level DEBUG?
- Check: Is there an exception before registration?

**Problem: Bridge registered but queries return null progress**
- Check: Is correct operation_id being used?
- Check: Is `get_operation()` calling `_refresh_from_bridge()`?
- Check: Is bridge reference correct (not None)?

---

### Scenario 6: Metrics Cursor Behavior

**Objective**: Verify cursor-based incremental metrics retrieval works correctly.

#### Setup
- Training running with at least 5 epochs completed
- Have operation_id ready

#### Actions

**Script to test cursor behavior:**
```bash
#!/bin/bash
# Save as: test_cursor_behavior.sh

OPERATION_ID="op_training_20250123_abc123"  # Replace with your operation_id

echo "=== Initial Query (cursor=0, get all metrics) ==="
RESPONSE=$(curl -s "http://localhost:8000/api/v1/operations/$OPERATION_ID/metrics?cursor=0")
echo "$RESPONSE" | jq '.'
CURSOR=$(echo "$RESPONSE" | jq -r '.new_cursor')
COUNT=$(echo "$RESPONSE" | jq '.metrics | length')
echo "Received $COUNT metrics, new cursor: $CURSOR"

echo ""
echo "=== Wait for more epochs (10 seconds) ==="
sleep 10

echo ""
echo "=== Incremental Query (cursor=$CURSOR, get only new metrics) ==="
RESPONSE=$(curl -s "http://localhost:8000/api/v1/operations/$OPERATION_ID/metrics?cursor=$CURSOR")
echo "$RESPONSE" | jq '.'
NEW_CURSOR=$(echo "$RESPONSE" | jq -r '.new_cursor')
NEW_COUNT=$(echo "$RESPONSE" | jq '.metrics | length')
echo "Received $NEW_COUNT new metrics, new cursor: $NEW_CURSOR"

echo ""
echo "=== Verify no duplicates (query again with old cursor) ==="
RESPONSE=$(curl -s "http://localhost:8000/api/v1/operations/$OPERATION_ID/metrics?cursor=$CURSOR")
DUPLICATE_COUNT=$(echo "$RESPONSE" | jq '.metrics | length')
echo "Should get same $NEW_COUNT metrics (not duplicated)"
echo "Received $DUPLICATE_COUNT metrics"

if [ "$DUPLICATE_COUNT" -eq "$NEW_COUNT" ]; then
  echo "✅ PASS: No duplicates"
else
  echo "❌ FAIL: Duplicate count mismatch"
fi
```

Run the script:
```bash
chmod +x test_cursor_behavior.sh
./test_cursor_behavior.sh
```

#### Expected Outcome

**Output:**
```
=== Initial Query (cursor=0, get all metrics) ===
{
  "metrics": [ /* 5 metrics */ ],
  "new_cursor": 5
}
Received 5 metrics, new cursor: 5

=== Wait for more epochs (10 seconds) ===

=== Incremental Query (cursor=5, get only new metrics) ===
{
  "metrics": [ /* 3 new metrics (epochs 6,7,8) */ ],
  "new_cursor": 8
}
Received 3 new metrics, new cursor: 8

=== Verify no duplicates (query again with old cursor) ===
Should get same 3 metrics (not duplicated)
Received 3 metrics
✅ PASS: No duplicates
```

#### How to Verify

**Check cursor increments correctly:**
- ✅ First query: cursor=0 → returns all metrics, new_cursor=N
- ✅ Second query: cursor=N → returns only new metrics, new_cursor=N+M
- ✅ Cursor always increases (never decreases)

**Check no duplicate metrics:**
- ✅ Query with cursor=5 twice → same metrics returned both times
- ✅ Metrics from first query NOT included in second query (after cursor update)

**Check incremental efficiency:**
```bash
# After 10 epochs, query with cursor=9 (should get only epoch 10)
curl -s "http://localhost:8000/api/v1/operations/$OPERATION_ID/metrics?cursor=9" | jq '.metrics | length'

# Expected: 1 (only one new metric)
```

#### If It Fails

**Problem: New cursor doesn't increment**
- Check: Is `_metrics_cursors` being updated in `_refresh_from_bridge()`?
- Check: Is new cursor calculated as `len(self._metrics_history)`?

**Problem: Duplicate metrics returned**
- Check: Is cursor being passed correctly to `bridge.get_metrics(cursor)`?
- Check: Is bridge slicing correctly: `metrics[cursor:]`?

**Problem: Missing metrics (gaps in epoch numbers)**
- Check: Is `_append_metric()` being called for every epoch?
- Check: Are metrics being lost during refresh?

---

### Scenario 7: Error-Free Execution

**Objective**: Verify no async/sync errors or warnings appear during training.

#### Setup
- Backend API running
- Training completed (from any previous scenario)
- Terminal access to backend logs

#### Actions

**Search logs for common error patterns:**

1. **Check for async event loop errors:**
   ```bash
   docker logs ktrdr-backend 2>&1 | grep -i "no running event loop"

   # Expected: NO RESULTS (this is the bug we fixed!)
   ```

2. **Check for async callback failures:**
   ```bash
   docker logs ktrdr-backend 2>&1 | grep -i "callback.*failed\|asyncio.*error\|create_task.*error"

   # Expected: NO RESULTS
   ```

3. **Check for metrics storage warnings:**
   ```bash
   docker logs ktrdr-backend 2>&1 | grep -i "metrics.*failed\|failed to store metrics\|metrics.*warning"

   # Expected: NO RESULTS
   ```

4. **Check for bridge errors:**
   ```bash
   docker logs ktrdr-backend 2>&1 | grep -i "bridge.*error\|refresh.*failed"

   # Expected: NO RESULTS (or only benign warnings)
   ```

5. **Check for exceptions during training:**
   ```bash
   docker logs ktrdr-backend 2>&1 | grep -A 10 "Exception\|Traceback"

   # Expected: NO RESULTS (or only unrelated exceptions)
   ```

6. **Check for cache warnings:**
   ```bash
   docker logs ktrdr-backend 2>&1 | grep -i "cache.*error\|ttl.*error"

   # Expected: NO RESULTS
   ```

#### Expected Outcome

**ALL searches should return zero or minimal results:**

```
# Search 1: NO RESULTS
docker logs ktrdr-backend 2>&1 | grep -i "no running event loop" | wc -l
0

# Search 2: NO RESULTS
docker logs ktrdr-backend 2>&1 | grep -i "callback.*failed" | wc -l
0

# Search 3: NO RESULTS
docker logs ktrdr-backend 2>&1 | grep -i "metrics.*failed" | wc -l
0

# Search 4: NO RESULTS
docker logs ktrdr-backend 2>&1 | grep -i "bridge.*error" | wc -l
0

# Search 5: NO RESULTS (or only unrelated)
docker logs ktrdr-backend 2>&1 | grep "Exception" | wc -l
0

# Search 6: NO RESULTS
docker logs ktrdr-backend 2>&1 | grep -i "cache.*error" | wc -l
0
```

#### How to Verify

**Check log cleanliness:**
- ✅ NO "no running event loop" errors (this is THE bug we fixed)
- ✅ NO async callback failures
- ✅ NO metrics storage warnings
- ✅ NO bridge errors
- ✅ NO unhandled exceptions
- ✅ NO cache-related errors

**Check successful operation logs:**
```bash
# Look for success patterns
docker logs ktrdr-backend 2>&1 | grep -E "(Created operation|Registered local bridge|Refreshed operation|Completed operation)" | tail -20

# Expected: Clean sequence of operation lifecycle events
```

**Count warnings vs errors:**
```bash
# Warnings are OK, errors are not
docker logs ktrdr-backend 2>&1 | grep -c "WARNING"   # Should be low
docker logs ktrdr-backend 2>&1 | grep -c "ERROR"     # Should be 0
```

#### If It Fails

**Problem: "No running event loop" error found**
- **This is CRITICAL** - means pull architecture not fully implemented
- Check: Is `asyncio.create_task()` still present in TrainingProgressBridge?
- Check: Is `metrics_callback` still being used?
- Check: Review Task 1.2 implementation (push mechanism removal)

**Problem: Callback failures**
- Check: Are there any remaining async callbacks from worker threads?
- Check: Is bridge using only sync methods?

**Problem: Metrics storage warnings**
- Check: Are metrics being appended correctly in bridge?
- Check: Is cursor incrementing properly?

**Problem: Bridge errors**
- Check: Is bridge being registered before worker starts?
- Check: Is bridge reference valid (not None)?

---

## Post-Test Validation

After running all scenarios, perform these final checks:

### 1. Summary Check

**Run all operations and verify success:**
```bash
curl -s http://localhost:8000/api/v1/operations | jq '[.operations[] | {id: .operation_id, status: .status, type: .operation_type}]'

# Expected: All operations should be COMPLETED or RUNNING (none FAILED)
```

### 2. Performance Check

**Verify worker overhead is low:**
- Training should complete in reasonable time
- No significant slowdown compared to pre-pull architecture
- Expected: <1μs overhead per `on_epoch()` call (not measurable by user)

### 3. Architecture Validation

**Confirm pull architecture:**
- ✅ Workers write to bridge (sync, fast)
- ✅ Clients pull from OperationsService (async, cached)
- ✅ NO background polling tasks (except HealthService)
- ✅ NO async/sync boundary violations
- ✅ Metrics stored correctly

### 4. Cache Behavior Verification

**Check cache hit/miss ratio:**
```bash
# If debug logging enabled
docker logs ktrdr-backend | grep "Cache hit" | wc -l   # Should be high
docker logs ktrdr-backend | grep "Cache miss" | wc -l  # Should be low

# Expected: Hit rate > 80% with multiple concurrent clients
```

---

## Troubleshooting

### Problem: Progress not updating

**Symptoms**: Progress percentage stays at 0%, message doesn't change

**Check:**
1. Is bridge registered?
   ```bash
   docker logs ktrdr-backend | grep "Registered local bridge"
   ```
2. Is `get_operation()` calling `_refresh_from_bridge()`?
   ```bash
   docker logs ktrdr-backend | grep "Refreshed operation"
   ```
3. Is bridge `get_status()` returning data?
   - Add debug logging to `ProgressBridge.get_status()`
4. Is worker calling `bridge.on_epoch()`?
   - Add debug logging to worker training loop

**Solution**:
- Verify bridge registration happens before training starts
- Verify refresh logic in `get_operation()` is correct
- Verify bridge methods are being called

---

### Problem: Metrics not stored

**Symptoms**: `GET /operations/{id}/metrics` returns empty array

**Check:**
1. Is `on_epoch()` being called?
   ```bash
   docker logs ktrdr-backend | grep "on_epoch"
   ```
2. Is `_append_metric()` being called in `on_epoch()`?
   - Add debug logging to `TrainingProgressBridge.on_epoch()`
3. Is cursor incrementing?
   ```bash
   docker logs ktrdr-backend | grep "cursor.*→"
   ```

**Solution**:
- Verify `on_epoch()` calls `_append_metric()` when `progress_type == "epoch"`
- Verify metrics are being added to `_metrics_history`
- Verify cursor is incrementing in `_refresh_from_bridge()`

---

### Problem: "No running event loop" error

**Symptoms**: Error appears in logs, metrics not stored

**THIS SHOULD NOT HAPPEN** - If it does, pull architecture not fully implemented

**Check:**
1. Is push mechanism removed?
   ```bash
   grep -r "asyncio.create_task" ktrdr/api/services/training/progress_bridge.py
   # Expected: NO RESULTS
   ```
2. Is `metrics_callback` removed?
   ```bash
   grep -r "metrics_callback" ktrdr/api/services/training/progress_bridge.py
   # Expected: NO RESULTS (except in docstrings/comments)
   ```
3. Is bridge using only sync methods?
   ```bash
   grep -r "async def" ktrdr/api/services/training/progress_bridge.py
   # Expected: NO RESULTS (all methods should be sync)
   ```

**Solution**:
- Review Task 1.2 implementation
- Remove ALL async callback code from bridge
- Ensure bridge is pure sync

---

### Problem: Cache not working (always refreshing)

**Symptoms**: Every query triggers refresh, logs show cache miss every time

**Check:**
1. Is `_last_refresh` being updated?
   ```bash
   docker logs ktrdr-backend | grep "_last_refresh"
   ```
2. Is cache TTL too low?
   ```bash
   echo $OPERATIONS_CACHE_TTL  # Should be 1.0 (default)
   ```
3. Is cache freshness check correct?
   - Review `_refresh_from_bridge()` cache logic

**Solution**:
- Verify `_last_refresh[operation_id] = time.time()` after each refresh
- Verify cache age calculation: `time.time() - self._last_refresh.get(operation_id, 0)`
- Verify TTL comparison: `if age < self._cache_ttl: return`

---

### Problem: Training never completes

**Symptoms**: Status stays RUNNING forever, percentage reaches 100% but status doesn't change

**Check:**
1. Did worker finish?
   ```bash
   docker logs ktrdr-backend | grep "Training completed"
   ```
2. Did orchestrator call `complete_operation()`?
   ```bash
   docker logs ktrdr-backend | grep "Completed operation"
   ```
3. Are there exceptions in worker?
   ```bash
   docker logs ktrdr-backend | grep -A 10 "Exception"
   ```

**Solution**:
- Verify orchestrator calls `complete_operation()` after training finishes
- Verify no exceptions in worker that prevent completion
- Check if operation status is being updated correctly

---

## Success Criteria

Mark M1 Task 1.5 as complete when ALL scenarios pass:

- ✅ **Scenario 1**: Operation created successfully
- ✅ **Scenario 2**: Progress updates correctly via pull
- ✅ **Scenario 3**: Metrics stored and retrievable
- ✅ **Scenario 4**: Training completes, status updates
- ✅ **Scenario 5**: Bridge registered before training
- ✅ **Scenario 6**: Cursor-based incremental metrics work
- ✅ **Scenario 7**: NO async/sync errors in logs

**Additional criteria:**
- ✅ NO "no running event loop" errors (M2 bug fixed)
- ✅ Metrics visible during training (not just after completion)
- ✅ Cache prevents redundant bridge reads
- ✅ Progress updates within 1 second of actual worker progress

---

## Next Steps

After successful validation:

1. **Report Results**: Update M1 Exit Criteria checklist in implementation plan
2. **Document Issues**: If any failures, create detailed bug reports
3. **Proceed to M2**: Begin host service operations API implementation
4. **Performance Baseline**: Record training times for regression testing

---

## Appendix A: Useful Commands

### Quick Status Check
```bash
# Check if operation is still running
curl -s http://localhost:8000/api/v1/operations/op_training_20250123_abc123 | jq -r '.status'
```

### Watch Progress Live
```bash
# Watch progress update every 2 seconds
watch -n 2 'curl -s http://localhost:8000/api/v1/operations/op_training_20250123_abc123 | jq ".progress"'
```

### Count Metrics
```bash
# Count how many metrics are stored
curl -s http://localhost:8000/api/v1/operations/op_training_20250123_abc123/metrics | jq '.metrics | length'
```

### List All Operations
```bash
# List all operations (running and completed)
curl -s http://localhost:8000/api/v1/operations | jq '.operations[] | {id: .operation_id, status: .status, percentage: .progress.percentage}'
```

### Check Backend Health
```bash
# Health check
curl -s http://localhost:8000/api/v1/health | jq '.'
```

---

## Appendix B: Expected Log Patterns

### Successful Training Sequence

```
# Operation creation
2025-01-23 10:00:00.123 INFO Created operation op_training_20250123_abc123 (type=TRAINING)

# Bridge registration
2025-01-23 10:00:00.125 INFO Registered local bridge for operation op_training_20250123_abc123
2025-01-23 10:00:00.126 DEBUG _local_bridges[op_training_20250123_abc123] = <ProgressBridge>
2025-01-23 10:00:00.127 DEBUG _metrics_cursors[op_training_20250123_abc123] = 0

# Training start
2025-01-23 10:00:00.130 INFO Starting training: symbols=['AAPL'], epochs=10

# Progress updates (from client queries)
2025-01-23 10:00:01.234 DEBUG Cache miss for operation op_training_20250123_abc123 (age=1.1s) - refreshing
2025-01-23 10:00:01.235 DEBUG Refreshed operation op_training_20250123_abc123 from bridge (cursor 0 → 1)
2025-01-23 10:00:05.456 DEBUG Cache hit for operation op_training_20250123_abc123 (age=0.2s)
2025-01-23 10:00:07.789 DEBUG Cache miss for operation op_training_20250123_abc123 (age=1.3s) - refreshing
2025-01-23 10:00:07.790 DEBUG Refreshed operation op_training_20250123_abc123 from bridge (cursor 1 → 2)

# Training completion
2025-01-23 10:05:30.123 INFO Training completed successfully
2025-01-23 10:05:30.124 INFO Completed operation op_training_20250123_abc123 with results
```

---

## Document Version

**Version**: 1.0
**Last Updated**: 2025-01-23
**Next Review**: After M1 completion and before M2 start
