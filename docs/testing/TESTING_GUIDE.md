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

### Data - Cache Operations (Fast)
- **Get Cached Data**: `GET /api/v1/data/{symbol}/{timeframe}`
  ```bash
  # Get bar count
  curl "http://localhost:8000/api/v1/data/EURUSD/1h" | jq '.data.dates | length'

  # Get first OHLCV bar
  curl "http://localhost:8000/api/v1/data/EURUSD/1h" | jq '{date: .data.dates[0], ohlcv: .data.ohlcv[0]}'
  ```
  Response format: `{success, data: {dates: [...], ohlcv: [[o,h,l,c,v], ...], metadata, points}}`

- **Get Data Range**: `POST /api/v1/data/range`
  ```json
  {
    "symbol": "EURUSD",
    "timeframe": "1h"
  }
  ```
  Response: `{success, data: {symbol, timeframe, start_date, end_date, point_count}}`

- **Get Data Info**: `GET /api/v1/data/info`
  Response: Available symbols and timeframes

### Data - Acquisition (Slow, requires IB)
- **Download Data**: `POST /api/v1/data/acquire/download` *(NEW in Phase 2)*
  ```json
  {
    "symbol": "EURUSD",
    "timeframe": "1h",
    "mode": "tail",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }
  ```
  Response: `{operation_id, status: "started"}`

- **Validate Symbol**: `POST /api/v1/data/acquire/validate-symbol` *(NEW in Phase 2)*
  ```json
  {
    "symbol": "AAPL"
  }
  ```
  Response: `{valid: true, instrument_type: "STK", exchange: "SMART"}`

- **Provider Health**: `GET /api/v1/data/acquire/provider-health` *(NEW in Phase 2)*
  Response: IB Gateway connection status

- **Deprecated**: `POST /api/v1/data/load` *(Still works in Phase 0/1, will be deprecated in Phase 2)*
  ```json
  {
    "symbol": "AAPL",
    "timeframe": "1d",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "mode": "tail"
  }
  ```
  **CRITICAL**: Must include `"mode":"tail"` to trigger IB download. Without mode parameter, defaults to `"local"` (cache-only, no IB download).
  Response: `{operation_id, status: "started"}`

### Operations
- **Get Status**: `GET /api/v1/operations/{operation_id}`
- **List Operations**: `GET /api/v1/operations?status=running&limit=10`
- **Cancel**: `DELETE /api/v1/operations/{operation_id}`

### Host Service Operations
- **Get Status**: `GET http://localhost:5002/api/v1/operations/{operation_id}`
- **Health**: `GET http://localhost:5002/health`

### IB Host Service (Port 5001)
- **Health**: `GET http://localhost:5001/health`
  Response: `{status: "healthy", ib_connected: true, gateway_version: "10.19"}`

- **Download Data (Direct)**: `POST http://localhost:5001/data/historical`
  ```json
  {
    "symbol": "EURUSD",
    "timeframe": "1h",
    "start_date": "2024-01-01T00:00:00",
    "end_date": "2024-12-31T23:59:59"
  }
  ```
  Response: `{data: [...], bars_count: 8760}`

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
tail -f ib-host-service/logs/ib-host-service.log  # Follow in real-time
```

**Important**: Always use `-f docker/docker-compose.yml` with docker-compose commands

### Service Health Checks
```bash
# Backend health
curl -s http://localhost:8000/health | jq

# Training host health
curl -s http://localhost:5002/health | jq

# IB host health (check if running)
curl -s http://localhost:5001/health | jq '.ib_connected'
# Returns: true (connected to IB Gateway) or false

# Check IB Gateway connection from host service
curl -s http://localhost:5001/health | jq '{service:.status, ib_connected:.ib_connected, gateway:.gateway_version}'
```

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

### Data Download Started
**String**: `Starting data download for {symbol} {timeframe}`
**Source**: Backend data acquisition service
**When**: Download operation starts
```bash
docker-compose -f docker/docker-compose.yml logs backend --since 60s | \
  grep "Starting data download"
```

### Data Saved to Cache
**String**: `Saved {rows} rows to cache: {symbol}_{timeframe}`
**Source**: LocalDataLoader
**When**: Data successfully saved after download
```bash
docker-compose -f docker/docker-compose.yml logs backend --since 60s | \
  grep "Saved.*rows to cache"
```

### IB Host Service Connection Errors
**String**: `Connection refused.*5001` or `IB Gateway not connected`
**When**: IB host service not running or IB Gateway disconnected
```bash
docker-compose -f docker/docker-compose.yml logs backend --since 60s | \
  grep -E "Connection refused.*5001|IB Gateway"
```
**Expected**: Empty output when services healthy

---

## 5. Test Data Parameters

### Available Data (EURUSD)
- **Location**: `data/EURUSD_*.csv` (may also be `.pkl`)
- **Daily (1d)**: 2007-2025 (~18.5 years, ~4,762 bars) - 272K CSV
- **Hourly (1h)**: 2005-2025 (~20.5 years, ~115,147 bars) - 6.0M CSV
- **5-minute (5m)**: 2005-2025 (~20.5 years, large dataset) - 84M CSV
- **Other**: 15m, 30m timeframes also available

**Check Availability**:
```bash
# List available data files (both formats)
ls -lh data/EURUSD_*.csv data/EURUSD_*.pkl 2>/dev/null

# Quick check for specific timeframes (either format)
for tf in 1d 1h 5m; do
  test -f "data/EURUSD_${tf}.csv" -o -f "data/EURUSD_${tf}.pkl" && echo "$tf available" || echo "$tf missing"
done
```

### Calibrated Test Durations

**Training Tests**:
| Purpose | Timeframe | Date Range | Samples | Duration | Use For |
|---------|-----------|------------|---------|----------|---------|
| Smoke Test | 1d | 2024-01-01 to 2024-12-31 | 258 | ~2s | Quick validation |
| Progress Test | 5m | 2023-01-01 to 2025-01-01 | 147K | ~62s | Progress monitoring |

**Data Tests (Cache Operations - Fast)**:
| Purpose | Timeframe | Date Range | Bars | Duration | Use For |
|---------|-----------|------------|------|----------|---------|
| Cache Read | 1h | All available | ~115K | <1s | Cache performance |
| Cache Read | 1d | 2024-01-01 to 2024-12-31 | 258 | <100ms | Quick validation |
| Range Query | Any | N/A | 0 | <50ms | Metadata check |

**Data Tests (IB Download - Slow)**:
| Purpose | Timeframe | Date Range | Expected Bars | Duration | Use For |
|---------|-----------|------------|---------------|----------|---------|
| Small Download | 1d | 2024-01-01 to 2024-12-31 | ~250 | 10-30s | Quick IB test |
| Medium Download | 1h | 2024-12-01 to 2024-12-31 | ~720 | 30-90s | Progress monitoring |
| Large Download | 1h | 2024-01-01 to 2024-12-31 | ~8760 | 5-15min | Full workflow test |

**Note**: IB download times vary based on:
- IB Gateway responsiveness
- Network conditions
- Historical data availability
- Time of day (market hours vs off-hours)

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

### Data Download Response (Started)
```json
{
  "operation_id": "op_data_20250127_hhmmss_xxxxxxxx",
  "status": "started",
  "message": "Data download started for EURUSD 1h"
}
```

### Data Download Status (Running)
```json
{
  "success": true,
  "data": {
    "operation_id": "op_data_...",
    "status": "running",
    "operation_type": "data_load",
    "progress": {
      "percentage": 45.0,
      "current_step": "Downloading segment 3/5",
      "items_processed": 4320,  // Bars downloaded
      "total_items": 8760
    }
  }
}
```

### Data Download Status (Completed)
```json
{
  "success": true,
  "data": {
    "status": "completed",
    "progress": {"percentage": 100.0},
    "result_summary": {
      "bars_downloaded": 8760,
      "symbols_processed": 1,
      "download_time": 127.5,
      "cached": true
    }
  }
}
```

### Data Range Response
```json
{
  "success": true,
  "data": {
    "symbol": "EURUSD",
    "timeframe": "1h",
    "start_date": "2005-03-14T00:00:00Z",
    "end_date": "2025-09-12T09:00:00Z",
    "point_count": 179697
  }
}
```

**Note**: Response does not include `file_exists` or `file_size_mb` fields. Use `point_count` instead of `row_count`.

---

## 7. Common Mistakes to Avoid

**Training**:
1. **Wrong endpoint**: `/api/v1/training/start` ❌ → `/api/v1/trainings/start` ✅
2. **Wrong status**: `"started"` ❌ → `"training_started"` ✅
3. **Custom task_id**: Ignored (always auto-generated)
4. **Docker path**: `docker-compose logs` ❌ → `docker-compose -f docker/docker-compose.yml logs` ✅
5. **Strategy path**: `config/strategies/` ❌ → `strategies/` ✅

**Data**:
1. **Wrong endpoint (Phase 2+)**: `/api/v1/data/load` ❌ (deprecated) → `/api/v1/data/acquire/download` ✅
2. **Wrong timeframe format**: `"1hour"` ❌ → `"1h"` ✅ | `"1day"` ❌ → `"1d"` ✅
3. **IB not running**: Check with `curl http://localhost:5001/health` before download tests
4. **IB Gateway not connected**: `ib_connected: false` means can't download, check IB Gateway
5. **Cache vs Download**: Use `GET /data/{symbol}/{timeframe}` for cache, `POST /data/acquire/download` for IB
6. **Date format**: Use ISO format: `"2024-01-01"` or `"2024-01-01T00:00:00"`

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

### Training
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

### Data
```bash
# Check IB service health
curl -s http://localhost:5001/health | jq '{status:.status, ib_connected:.ib_connected}'

# Load from cache (fast) - get bar count
curl "http://localhost:8000/api/v1/data/EURUSD/1h" | jq '.data.dates | length'

# Get data range (metadata only, very fast)
curl -s -X POST http://localhost:8000/api/v1/data/range \
  -H "Content-Type: application/json" \
  -d '{"symbol":"EURUSD","timeframe":"1h"}' | jq '.data'

# Download from IB (slow, requires IB running) - Phase 2+
curl -s -X POST http://localhost:8000/api/v1/data/acquire/download \
  -H "Content-Type: application/json" \
  -d '{"symbol":"EURUSD","timeframe":"1h","mode":"tail","start_date":"2024-12-01","end_date":"2024-12-31"}' | jq

# Validate symbol with IB - Phase 2+
curl -s -X POST http://localhost:8000/api/v1/data/acquire/validate-symbol \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL"}' | jq

# Check data files (CSV or PKL format)
ls -lh data/EURUSD_*.csv data/EURUSD_*.pkl 2>/dev/null
```

---

## 11. Troubleshooting Common Issues

### Issue: Download uses cache instead of IB

**Symptom**: Operation completes instantly, `ib_requests_made: 0`

**Cause**: Missing `"mode":"tail"` parameter defaults to cache-only

**Solution**:
```bash
# ❌ Wrong - defaults to local mode
curl -X POST http://localhost:8000/api/v1/data/load \
  -d '{"symbol":"AAPL","timeframe":"1d","start_date":"2024-01-01","end_date":"2024-12-31"}'

# ✅ Correct - includes mode parameter
curl -X POST http://localhost:8000/api/v1/data/load \
  -d '{"symbol":"AAPL","timeframe":"1d","start_date":"2024-01-01","end_date":"2024-12-31","mode":"tail"}'
```

### Issue: Operation fails with "Data not found"

**Symptom**: Operation status `failed`, error: "Data not found for SYMBOL (timeframe)"

**Cause**: Cache file doesn't exist and mode is set to "local"

**Solution**: Either create cache file or use `"mode":"tail"` to download from IB

### Issue: Cannot observe progress updates

**Symptom**: Operation shows 100% immediately after starting

**Cause**: Dataset too small (downloads in <5 seconds)

**Solution**: Use larger date ranges for progress monitoring tests:
- ❌ Small: 1 month 1h data (~720 bars) - too fast
- ✅ Medium: 1 year 1h data (~8760 bars) - 30-90s download
- ✅ Large: 2-3 years 1h data - 2-5 min download

### Issue: IB host service connection refused

**Symptom**: `Connection refused` when calling port 5001

**Cause**: IB host service not running

**Solution**:
```bash
# Start IB host service
cd ib-host-service
./start.sh

# Verify it's running
curl http://localhost:5001/health
```

### Issue: IB Gateway not connected

**Symptom**: Downloads fail, logs show "IB Gateway not connected"

**Cause**: IB Gateway TWS not logged in

**Solution**:
1. Launch IB Gateway TWS application
2. Log in with paper trading or live account
3. Verify connection:
```bash
curl http://localhost:5001/health | jq '{ib_connected:.ib_connected}'
# Should return: "ib_connected": true
```

### Issue: jq parse errors when running test commands

**Symptom**: `jq: parse error` or `Invalid numeric literal`

**Cause**: Bash variable expansion issues or malformed JSON

**Solution**: Use helper scripts instead of inline commands:
```bash
# Use test scripts (recommended)
./docs/testing/scripts/monitor_progress.sh "$OPERATION_ID" 10 12

# Or use single quotes for JSON payloads
curl -d '{"symbol":"AAPL",...}' # ✅ Single quotes
curl -d "{\"symbol\":\"AAPL\",...}" # ❌ Escaping nightmare
```

### Issue: Cache management during tests

**Problem**: Need to clear cache to force IB download, then restore it

**Solution**: Use cache management script:
```bash
# Before test: backup and clear
./docs/testing/scripts/manage_cache.sh backup EURUSD 1h

# Run test with IB download
# ...

# After test: restore original
./docs/testing/scripts/manage_cache.sh restore EURUSD 1h
```

### Issue: Docker container not running

**Symptom**: Cannot connect to `http://localhost:8000`

**Cause**: Backend not started

**Solution**:
```bash
# Check if running
docker ps | grep ktrdr-backend

# Start if not running
docker-compose -f docker/docker-compose.yml up -d

# Check logs
docker-compose -f docker/docker-compose.yml logs backend --since 60s
```

---

## 12. Test Helper Scripts

All test scripts are located in `docs/testing/scripts/`. See [scripts/README.md](scripts/README.md) for detailed usage.

### Quick Start

```bash
# Make scripts executable (first time only)
chmod +x docs/testing/scripts/*.sh

# Monitor operation progress
./docs/testing/scripts/monitor_progress.sh <operation_id> [interval] [max_polls]

# Manage cache files
./docs/testing/scripts/manage_cache.sh <action> <symbol> <timeframe>
```

### Example Workflow

```bash
# 1. Backup cache
./docs/testing/scripts/manage_cache.sh backup EURUSD 1h

# 2. Start download
RESP=$(curl -s -X POST http://localhost:8000/api/v1/data/load \
  -H "Content-Type: application/json" \
  -d '{"symbol":"EURUSD","timeframe":"1h","start_date":"2024-01-01","end_date":"2024-12-31","mode":"tail"}')
OP_ID=$(echo "$RESP" | jq -r '.data.operation_id')

# 3. Monitor progress
./docs/testing/scripts/monitor_progress.sh "$OP_ID" 10 12

# 4. Restore cache
./docs/testing/scripts/manage_cache.sh restore EURUSD 1h
```
