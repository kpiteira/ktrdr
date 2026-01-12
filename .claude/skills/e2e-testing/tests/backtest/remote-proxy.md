# Test: backtest/remote-proxy

**Purpose:** Verify backend proxies to remote via OperationServiceProxy
**Duration:** ~10 seconds
**Category:** Backtest (Remote)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] Backend in remote mode: `USE_REMOTE_BACKTEST_SERVICE=true`
- [ ] Remote service running (port 5003)

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
    "start_date": "2024-01-01",
    "end_date": "2024-06-30"
  }')

BACKEND_OP_ID=$(echo "$RESPONSE" | jq -r '.operation_id')
```

### 2. Extract Remote Operation ID

**Command:**
```bash
sleep 3
REMOTE_OP_ID=$(docker compose logs backend --since 30s | \
  grep "Registered remote proxy.*$BACKEND_OP_ID" | \
  grep -o 'op_backtest_[0-9_a-f]*' | tail -1)
echo "Remote ID: $REMOTE_OP_ID"
```

### 3. Verify Proxy (NOT Bridge)

**Command:**
```bash
# Should find proxy
docker compose logs backend --since 30s | \
  grep "Registered remote proxy.*$BACKEND_OP_ID"

# Should NOT find bridge
docker compose logs backend --since 30s | \
  grep "Registered local.*bridge.*$BACKEND_OP_ID" && echo "UNEXPECTED" || echo "OK: No local bridge"
```

### 4. Verify Remote Has Bridge

**Command:**
```bash
docker logs backtest-worker --since 30s 2>&1 | \
  grep "Registered local.*bridge.*$REMOTE_OP_ID"
```

---

## Success Criteria

- [ ] Backend logs: Proxy registration
- [ ] Backend logs: NO local bridge
- [ ] Remote logs: Local bridge
- [ ] Operation ID mapping works

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Proxy not bridge** — Backend should NOT have local bridge
- [ ] **IDs different** — Backend ID and Remote ID are different

---

## Evidence to Capture

- Backend Operation ID
- Remote Operation ID
- Proxy registration log
- Remote bridge log
