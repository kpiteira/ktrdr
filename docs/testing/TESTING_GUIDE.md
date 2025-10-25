# LLM Testing Guide - Building Blocks

This guide provides all the building blocks needed to create and execute test scenarios for KTRDR.

---

## 1. Service URLs & Ports

- **Backend API**: `http://localhost:8000/api/v1`
- **Training Host**: `http://localhost:5002`
- **IB Host**: `http://localhost:5001` (often not running)

---

## 2. Key API Endpoints

### Training
- **Start Training**: `POST /api/v1/trainings/start` (note: **plural**)
  ```json
  {
    "symbols": ["EURUSD"],
    "timeframes": ["5m"],
    "strategy_name": "test_e2e_local_pull",
    "start_date": "2023-01-01",
    "end_date": "2025-01-01"
  }
  ```
  Response: `{success, task_id, status: "training_started"}`

  **Note**: `task_id` is always auto-generated (custom task_id in request is ignored)

### Operations
- **Get Status**: `GET /api/v1/operations/{operation_id}`
- **List Operations**: `GET /api/v1/operations?status=running&limit=10`
- **Cancel**: `DELETE /api/v1/operations/{operation_id}`

### Host Service Operations
- **Get Status**: `GET http://localhost:5002/api/v1/operations/{operation_id}`
- **Health**: `GET http://localhost:5002/health`

---

## 3. Scripts & Commands

### Mode Switching
```bash
# Switch to local mode (training in backend container)
./scripts/switch-training-mode.sh local

# Switch to host mode (training on host service with GPU)
./scripts/switch-training-mode.sh host

# Verify mode
docker-compose -f docker/docker-compose.yml exec -T backend env | grep USE_TRAINING_HOST_SERVICE
# Returns: USE_TRAINING_HOST_SERVICE=false (local) or true (host)
```

### Log Access
```bash
# Backend logs
docker-compose -f docker/docker-compose.yml logs backend --since 60s

# Training host logs (file)
grep "pattern" training-host-service/logs/ktrdr-host-service.log

# IB host logs (file)
grep "pattern" ib-host-service/logs/ib-host-service.log
```

**Important**: Always use `-f docker/docker-compose.yml` with docker-compose commands

---

## 4. Log Strings (Verified from Code)

### Local Bridge Registration
**String**: `Registered local training bridge for operation {operation_id}`
**Source**: `ktrdr/api/services/training_service.py:216`
**When**: Backend in LOCAL mode
```bash
docker-compose -f docker/docker-compose.yml logs backend --since 60s | \
  grep "Registered local training bridge"
```

### Remote Proxy Registration
**String**: `Registered remote proxy for operation {backend_operation_id} → host {host_operation_id}`
**Source**: `ktrdr/api/services/training_service.py:318`
**When**: Backend in HOST mode
```bash
docker-compose -f docker/docker-compose.yml logs backend --since 60s | \
  grep "Registered remote proxy"
```

### Event Loop Error (Should NEVER appear)
**String**: `no running event loop`
**When**: M1 bug present (async callback from sync thread)
```bash
docker-compose -f docker/docker-compose.yml logs backend --since 120s | \
  grep -i "no running event loop"
```
**Expected**: Empty output (M1 pull architecture working correctly)

---

## 5. Test Data Parameters

### Available Data (EURUSD)
- **Location**: `data/EURUSD_*.csv`
- **Daily**: 2007-2025 (~18.5 years, 4,763 rows)
- **Hourly**: 2005-2025 (~20.5 years, 115,148 rows)
- **5-minute**: 2005-2025 (~20.5 years, 1,508,613 rows)

### Calibrated Test Durations

| Purpose | Timeframe | Date Range | Samples | Duration | Use For |
|---------|-----------|------------|---------|----------|---------|
| Smoke Test | 1d | 2024-01-01 to 2024-12-31 | 258 | ~2s | Quick validation |
| Progress Test | 5m | 2023-01-01 to 2025-01-01 | 147K | ~62s | Progress monitoring |

**Strategy**: `test_e2e_local_pull` (location: `strategies/test_e2e_local_pull.yaml`)
- 10 epochs
- Minimal architecture for fast testing

---

## 6. Common Response Formats

### Training Start Response
```json
{
  "success": true,
  "task_id": "op_training_20251025_hhmmss_xxxxxxxx",
  "status": "training_started",
  "message": "Neural network training started for EURUSD...",
  "symbols": ["EURUSD"],
  "timeframes": ["5m"],
  "strategy_name": "test_e2e_local_pull",
  "estimated_duration_minutes": 30
}
```

### Operation Status (Running)
```json
{
  "success": true,
  "data": {
    "operation_id": "op_training_...",
    "status": "running",
    "progress": {
      "percentage": 40.0,
      "current_step": "Epoch 4/10",
      "steps_completed": 4,
      "steps_total": 10,
      "items_processed": 58996
    },
    "metadata": {
      "training_mode": "local",
      "use_host_service": false
    }
  }
}
```

### Operation Status (Completed)
```json
{
  "success": true,
  "data": {
    "status": "completed",
    "progress": {"percentage": 100.0},
    "result_summary": {
      "training_metrics": {
        "training_time": 62.3,
        "final_train_accuracy": 0.98
      },
      "data_summary": {
        "total_samples": 147489
      }
    },
    "metrics": {
      "epochs": [{epoch: 0, ...}, ...] // 10 epochs
    }
  }
}
```

---

## 7. Common Mistakes to Avoid

1. **Wrong endpoint**: `/api/v1/training/start` ❌ → `/api/v1/trainings/start` ✅
2. **Wrong status**: `"started"` ❌ → `"training_started"` ✅
3. **Custom task_id**: Ignored (always auto-generated)
4. **Docker path**: `docker-compose logs` ❌ → `docker-compose -f docker/docker-compose.yml logs` ✅
5. **Strategy path**: `config/strategies/` ❌ → `strategies/` ✅

---

## 8. Example Scenario Template

### Scenario: [Name]

**Purpose**: [What this validates]
**Duration**: [Expected time]
**Prerequisites**:
- Service X running
- Mode set to Y

**Test Data**:
```json
{
  "symbols": ["EURUSD"],
  "timeframes": ["5m"],
  "start_date": "2023-01-01",
  "end_date": "2025-01-01",
  "strategy_name": "test_e2e_local_pull"
}
```

**Steps**:

1. **Start Operation**
```bash
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbols":["EURUSD"],"timeframes":["5m"],"strategy_name":"test_e2e_local_pull","start_date":"2023-01-01","end_date":"2025-01-01"}')

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
```

**Expected**: `success: true`, `status: "training_started"`

2. **Verify Logs**
```bash
docker-compose -f docker/docker-compose.yml logs backend --since 60s | \
  grep "Registered local training bridge for operation $TASK_ID"
```

**Expected**: Log entry found

3. **Check Status**
```bash
curl -s "http://localhost:8000/api/v1/operations/$TASK_ID" | jq '.data.status'
```

**Expected**: `"running"` or `"completed"`

**Validation**:
- [ ] Operation started
- [ ] Logs confirm expected behavior
- [ ] Final status correct

---

## 9. Scenario Categories

### Backend Isolated (Local Mode)
- Backend with `USE_TRAINING_HOST_SERVICE=false`
- Tests: Local training, operations API, cancellation
- Validates: Bridge registration, pull architecture

### Host Service Isolated
- Host service standalone (no backend)
- Tests: Direct host operations, GPU allocation
- Validates: Host service independence

### Integration (Backend + Host)
- Backend with `USE_TRAINING_HOST_SERVICE=true`
- Tests: Proxy pattern, operation ID mapping, two-level cache
- Validates: Distributed architecture

### Error Handling
- Invalid inputs, service failures
- Tests: Error messages, graceful degradation
- Validates: Robustness

---

## 10. Quick Reference Commands

```bash
# Start local training (quick)
curl -X POST http://localhost:8000/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbols":["EURUSD"],"timeframes":["1d"],"strategy_name":"test_e2e_local_pull","start_date":"2024-01-01","end_date":"2024-12-31"}'

# Check operation status
curl "http://localhost:8000/api/v1/operations/{task_id}" | jq '.data.status'

# Cancel operation
curl -X DELETE "http://localhost:8000/api/v1/operations/{task_id}"

# Check logs for bridge
docker-compose -f docker/docker-compose.yml logs backend --since 60s | grep "Registered local training bridge"

# Switch mode
./scripts/switch-training-mode.sh local  # or host
```
