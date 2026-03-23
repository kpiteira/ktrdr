# Test: backtest/remote-progress

**Purpose:** Verify two-level progress tracking (backend proxies to remote)
**Duration:** ~25 seconds
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

### 1. Start via Backend (2-year range)

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

### 2. Extract Remote ID

**Command:**
```bash
sleep 3
REMOTE_OP_ID=$(docker compose logs backend --since 30s | \
  grep "Registered remote proxy" | grep -o 'op_backtest_[0-9_a-f]*' | tail -1)
```

### 3. Poll via Backend

**Command:**
```bash
for i in {1..5}; do
  sleep 5
  curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$BACKEND_OP_ID" | \
    jq '{poll:'"$i"', pct:.data.progress.percentage}'
done
```

### 4. Poll Remote Directly (verification)

**Command:**
```bash
curl -s "http://localhost:5003/api/v1/operations/$REMOTE_OP_ID" | \
  jq '{pct:.data.progress.percentage}'
```

---

## Success Criteria

- [ ] Backend progress matches remote progress (±1%)
- [ ] Progress synchronized
- [ ] Proxy latency low (<500ms)
- [ ] Both show 100% at completion

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Progress in sync** — Backend and remote show same percentage
- [ ] **Not stuck** — Progress increases over polls

---

## Evidence to Capture

- Backend progress snapshots
- Remote progress snapshot
- Sync comparison
