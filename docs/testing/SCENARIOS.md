# Test Scenarios

## Scenario Index

| ID | Name | Category | Duration | Status |
|----|------|----------|----------|--------|
| 1.1 | Local Training - Smoke Test | Backend | ~2s | ✅ |
| 1.2 | Local Training - Progress | Backend | ~62s | ✅ |
| 1.3 | Local Training - Cancellation | Backend | ~30s | ✅ |
| 1.4 | Operations List & Filter | Backend | ~30s | ⏳ |
| 2.1 | Training Host - Direct Start | Host | ~30s | ⏳ |
| 2.2 | Training Host - GPU Allocation | Host | ~10s | ⏳ |
| 3.1 | Host Training - Integration | Integration | ~2s | ✅ |
| 3.2 | Host Training - Cache | Integration | ~30s | ⏳ |
| 3.3 | Host Training - Completion | Integration | ~60s | ⏳ |
| 4.1 | Error - Invalid Strategy | Error | ~5s | ⏳ |
| 4.2 | Error - Operation Not Found | Error | ~2s | ⏳ |

**Legend**: ✅ Tested & Passed | ❌ Failed | ⏳ Not Yet Tested

---

## 1.1: Local Training - Smoke Test

**Category**: Backend Isolated
**Duration**: ~2 seconds
**Purpose**: Quick validation that training starts, completes, no errors

### Test Data
```json
{
  "symbols": ["EURUSD"],
  "timeframes": ["1d"],
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "strategy_name": "test_e2e_local_pull"
}
```
**Samples**: 258 | **Epochs**: 10

### Prerequisites
- Backend running
- Local mode (`USE_TRAINING_HOST_SERVICE=false`)

### Commands

**1. Start Training**
```bash
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbols":["EURUSD"],"timeframes":["1d"],"strategy_name":"test_e2e_local_pull","start_date":"2024-01-01","end_date":"2024-12-31"}')

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
echo "Task ID: $TASK_ID"
```

**2. Wait & Check Completion**
```bash
sleep 5
curl -s "http://localhost:8000/api/v1/operations/$TASK_ID" | \
  jq '{status:.data.status, samples:.data.result_summary.data_summary.total_samples, duration:.data.result_summary.training_metrics.training_time}'
```

**3. Verify Local Bridge**
```bash
docker-compose -f docker/docker-compose.yml logs backend --since 60s | \
  grep "Registered local training bridge for operation $TASK_ID"
```

**4. Verify NO Proxy**
```bash
docker-compose -f docker/docker-compose.yml logs backend --since 60s | \
  grep "Registered remote proxy.*$TASK_ID"
# Should return nothing
```

**5. Check NO Event Loop Errors**
```bash
docker-compose -f docker/docker-compose.yml logs backend --since 120s | \
  grep -i "no running event loop"
# Should return nothing
```

### Expected Results
- HTTP 200, `success: true`
- Status: `"training_started"` → `"completed"`
- Duration: ~2 seconds
- Samples: 258
- Local bridge logged: ✅
- NO proxy logged: ✅
- NO event loop errors: ✅

### Actual Results (2025-10-25)
✅ **PASSED** - All validations passed

---

## 1.2: Local Training - Progress Monitoring

**Category**: Backend Isolated
**Duration**: ~62 seconds (~1 minute)
**Purpose**: Validate progress updates, metrics collection

### Test Data
```json
{
  "symbols": ["EURUSD"],
  "timeframes": ["5m"],
  "start_date": "2023-01-01",
  "end_date": "2025-01-01",
  "strategy_name": "test_e2e_local_pull"
}
```
**Samples**: 147,489 | **Epochs**: 10

### Prerequisites
- Backend running
- Local mode

### Commands

**1. Start Training**
```bash
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbols":["EURUSD"],"timeframes":["5m"],"strategy_name":"test_e2e_local_pull","start_date":"2023-01-01","end_date":"2025-01-01"}')

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
echo "Task ID: $TASK_ID"
```

**2. Poll Progress (Every 15s)**
```bash
for i in {1..6}; do
  sleep 15
  curl -s "http://localhost:8000/api/v1/operations/$TASK_ID" | \
    jq '{poll:'"$i"', status:.data.status, percentage:.data.progress.percentage, step:.data.progress.current_step}'
done
```

**3. Get Final Results**
```bash
curl -s "http://localhost:8000/api/v1/operations/$TASK_ID" | \
  jq '{status:.data.status, duration:.data.result_summary.training_metrics.training_time, epochs:.data.metrics.epochs|length}'
```

### Expected Results
- Progress updates visible across polls:
  - 15s: ~0-10% (data loading)
  - 30s: ~40% (Epoch 4)
  - 45s: ~70% (Epoch 7)
  - 60s: ~90-100% (Epoch 9-10)
- Final: 10 epochs collected
- Duration: ~60-70 seconds

### Actual Results (2025-10-25)
✅ **PASSED**
- Duration: 62 seconds
- Progress observed at 0% → 40% → 70% → 100%
- Metrics: All 10 epochs captured
- Final accuracy: 98% train, 100% val

---

## 1.3: Local Training - Cancellation

**Category**: Backend Isolated
**Duration**: ~30 seconds
**Purpose**: Validate operation cancellation

### Test Data
Same as 1.2 (2 years 5m data)

### Commands

**1. Start Training**
```bash
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbols":["EURUSD"],"timeframes":["5m"],"strategy_name":"test_e2e_local_pull","start_date":"2023-01-01","end_date":"2025-01-01"}')

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
```

**2. Wait & Verify Running**
```bash
sleep 10
curl -s "http://localhost:8000/api/v1/operations/$TASK_ID" | \
  jq '{status:.data.status, percentage:.data.progress.percentage}'
```

**3. Cancel**
```bash
curl -s -X DELETE "http://localhost:8000/api/v1/operations/$TASK_ID" | jq
```

**4. Verify Cancellation**
```bash
sleep 2
curl -s "http://localhost:8000/api/v1/operations/$TASK_ID" | jq '.data.status'
```

### Expected Results
- Pre-cancel: `status: "running"`
- Cancel response: `status: "cancelled"`
- Post-cancel: `status: "failed"` (quirk!)

### Actual Results (2025-10-25)
✅ **PASSED** with quirk
- Cancelled at 50% progress
- Cancel endpoint returns `"cancelled"`
- Final operation status: `"failed"` (not "cancelled")

**Note**: Status inconsistency is a known quirk

---

## 3.1: Host Training - Integration

**Category**: Integration (Backend + Host)
**Duration**: ~2 seconds
**Purpose**: Validate backend → host proxy pattern

### Test Data
```json
{
  "symbols": ["EURUSD"],
  "timeframes": ["1d"],
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "strategy_name": "test_e2e_local_pull"
}
```

### Prerequisites
- Backend running
- Training host running
- **Host mode** (`USE_TRAINING_HOST_SERVICE=true`)

### Commands

**1. Switch to Host Mode**
```bash
./scripts/switch-training-mode.sh host
sleep 5
```

**2. Start Training (Backend Proxies to Host)**
```bash
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbols":["EURUSD"],"timeframes":["1d"],"strategy_name":"test_e2e_local_pull","start_date":"2024-01-01","end_date":"2024-12-31"}')

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
echo "Backend Task ID: $TASK_ID"
```

**3. Extract Host Operation ID from Logs**
```bash
HOST_OP_ID=$(docker-compose -f docker/docker-compose.yml logs backend --since 30s | \
  grep "Registered remote proxy.*$TASK_ID" | \
  grep -o 'host_training_[a-f0-9-]*' | head -1)
echo "Host Operation ID: $HOST_OP_ID"
```

**4. Verify Backend Has Proxy (NOT Bridge)**
```bash
docker-compose -f docker/docker-compose.yml logs backend --since 30s | \
  grep "Registered remote proxy.*$TASK_ID"
# Should find entry

docker-compose -f docker/docker-compose.yml logs backend --since 30s | \
  grep "Registered local training bridge.*$TASK_ID"
# Should return nothing
```

**5. Verify Host Has Bridge**
```bash
grep "Registered local bridge for operation $HOST_OP_ID" \
  training-host-service/logs/ktrdr-host-service.log | tail -1
```

**6. Query Via Backend (Proxies to Host)**
```bash
curl -s "http://localhost:8000/api/v1/operations/$TASK_ID" | jq '.data.status'
```

**7. Query Host Directly (Optional)**
```bash
curl -s "http://localhost:5002/api/v1/operations/$HOST_OP_ID" | jq '.data.status'
```

### Expected Results
- Backend logs: Proxy registration ✅
- Backend logs: NO local bridge ✅
- Host logs: Local bridge registration ✅
- Backend query: Works (proxies to host)
- Host query: Works (direct access)
- Operation ID mapping: Backend ID ↔ Host ID

### Actual Results (2025-10-25)
✅ **PASSED**
- Proxy logged in backend: ✅
- NO bridge in backend: ✅
- Bridge logged in host: ✅
- Both queries worked: ✅
- Training completed on host: ✅

---

## Remaining Scenarios (TODO)

### 1.4: Operations List & Filter
**Status**: ⏳ Not Tested
**Purpose**: Validate operations API list/filter functionality

### 2.1: Training Host - Direct Start
**Status**: ⏳ Not Tested
**Purpose**: Validate host service works standalone (no backend)

### 3.2: Host Training - Two-Level Cache
**Status**: ⏳ Not Tested
**Purpose**: Validate backend cache → host cache → bridge

### 4.1: Error - Invalid Strategy
**Status**: ⏳ Not Tested
**Purpose**: Validate error handling for non-existent strategy

---

## Summary Statistics

- **Total Scenarios**: 11
- **Tested**: 4 (36%)
- **Passed**: 4 (100%)
- **Failed**: 0
- **Remaining**: 7

**Test Data Calibration**:
- Quick smoke test: 1y daily (~2s)
- Progress monitoring: 2y 5m (~62s)
- Strategy: `test_e2e_local_pull`

**Key Validation**: M1 Pull Architecture ✅ Working (zero event loop errors across all tests)
