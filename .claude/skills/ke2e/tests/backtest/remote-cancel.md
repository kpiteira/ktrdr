# Test: backtest/remote-cancel

**Purpose:** Verify cancellation propagates backend → remote
**Duration:** ~15 seconds
**Category:** Backtest (Remote)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] Backend in remote mode
- [ ] Remote service running

---

## Execution Steps

### 1. Start via Backend

**Command:**
```bash
RESPONSE=$(curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/backtests/start \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "/app/models/neuro_mean_reversion/1d_v21/model.pt",
    "strategy_name": "neuro_mean_reversion",
    "symbol": "EURUSD",
    "timeframe": "1d",
    "start_date": "2023-01-01",
    "end_date": "2024-12-31"
  }')

BACKEND_OP_ID=$(echo "$RESPONSE" | jq -r '.operation_id')
```

### 2. Wait and Extract Remote ID

**Command:**
```bash
sleep 5
REMOTE_OP_ID=$(docker compose logs backend --since 30s | \
  grep "Registered remote proxy" | grep -o 'op_backtest_[0-9_a-f]*' | tail -1)
```

### 3. Cancel via Backend

**Command:**
```bash
curl -s -X DELETE "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$BACKEND_OP_ID" | jq
```

### 4. Verify Both Cancelled

**Command:**
```bash
sleep 2

echo "Backend:"
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$BACKEND_OP_ID" | \
  jq '.data.status'

echo "Remote:"
curl -s "http://localhost:5003/api/v1/operations/$REMOTE_OP_ID" | \
  jq '.data.status'
```

**Expected:**
- Both show "cancelled"

---

## Success Criteria

- [ ] Backend DELETE triggers remote DELETE
- [ ] Both show "cancelled" status
- [ ] Progress frozen at both levels
- [ ] System stable

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Both cancelled** — Not just backend
- [ ] **System stable** — New operations work

---

## Evidence to Capture

- Cancel response
- Backend status post-cancel
- Remote status post-cancel
