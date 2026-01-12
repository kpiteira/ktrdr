# Test: backtest/remote-start

**Purpose:** Verify remote container runs independently
**Duration:** ~10 seconds
**Category:** Backtest (Remote)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] Remote backtest service running (port 5003)
- [ ] Volume mounts: data, models, strategies

**Service check:**
```bash
curl -s http://localhost:5003/health
```

---

## Test Data

```json
{
  "model_path": "/app/models/neuro_mean_reversion/1d_v21/model.pt",
  "strategy_name": "neuro_mean_reversion",
  "symbol": "EURUSD",
  "timeframe": "1d",
  "start_date": "2024-01-01",
  "end_date": "2024-06-30"
}
```

---

## Execution Steps

### 1. Start Directly on Remote

**Command:**
```bash
RESPONSE=$(curl -s -X POST http://localhost:5003/backtests/start \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "/app/models/neuro_mean_reversion/1d_v21/model.pt",
    "strategy_name": "neuro_mean_reversion",
    "symbol": "EURUSD",
    "timeframe": "1d",
    "start_date": "2024-01-01",
    "end_date": "2024-06-30"
  }')

REMOTE_OP_ID=$(echo "$RESPONSE" | jq -r '.operation_id')
echo "Remote Operation ID: $REMOTE_OP_ID"
```

### 2. Query Remote Status

**Command:**
```bash
sleep 10
curl -s "http://localhost:5003/api/v1/operations/$REMOTE_OP_ID" | jq
```

**Expected:**
- `status: "completed"`

### 3. Verify Local Mode in Remote

**Command:**
```bash
docker logs backtest-worker --since 60s 2>&1 | \
  grep "Registered local.*bridge.*$REMOTE_OP_ID"
```

**Expected:**
- Bridge registration in logs

---

## Success Criteria

- [ ] Remote accepts direct requests
- [ ] Status: "completed"
- [ ] Remote runs in LOCAL mode internally
- [ ] Model/data accessible via volumes

---

## Troubleshooting

**If connection refused:**
- **Cause:** Remote service not running
- **Cure:** Start remote: `docker compose up -d backtest-worker`

**If model not found:**
- **Cause:** Volume not mounted
- **Cure:** Check compose volumes for models directory

---

## Evidence to Capture

- Remote operation ID
- Final status
- Worker logs showing bridge registration
