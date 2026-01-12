# Test: training/host-cache

**Purpose:** Validate backend → host proxy with operation ID mapping
**Duration:** ~5 seconds
**Category:** Training (Integration)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] Backend running
- [ ] Training host service running
- [ ] Host mode enabled

---

## Test Data

Same as host-integration test.

---

## Execution Steps

### 1. Ensure Host Mode

**Command:**
```bash
./scripts/switch-training-mode.sh host 2>/dev/null || echo "Already in host mode or script not found"
```

### 2. Start Training via Backend

**Command:**
```bash
RESPONSE=$(curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbols":["EURUSD"],"timeframes":["1d"],"strategy_name":"test_e2e_local_pull","start_date":"2024-01-01","end_date":"2024-12-31"}')

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
```

### 3. Extract Host Operation ID

**Command:**
```bash
sleep 3
HOST_OP_ID=$(docker compose logs backend --since 30s | \
  grep "Registered remote proxy.*$TASK_ID" | \
  grep -o 'host_training_[a-f0-9-]*' | head -1)
echo "Backend ID: $TASK_ID"
echo "Host ID: $HOST_OP_ID"
```

### 4. Query Both Backend and Host

**Command:**
```bash
sleep 5

echo "Backend query (proxies to host):"
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$TASK_ID" | \
  jq '{status:.data.status}'

echo "Host query (direct):"
curl -s "http://localhost:5002/api/v1/operations/$HOST_OP_ID" | \
  jq '{status:.data.status}'
```

**Expected:**
- Both return same status
- Backend query proxies transparently

---

## Success Criteria

- [ ] Backend registers proxy (not local bridge)
- [ ] Backend ID maps to host ID
- [ ] Both queries return consistent data
- [ ] Backend query proxies to host transparently

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Both IDs exist** — Neither is null or empty
- [ ] **Status matches** — Both queries return same status
- [ ] **ID mapping logged** — Proxy log shows both IDs

---

## Troubleshooting

**If host query fails:**
- **Cause:** Wrong host operation ID or host service down
- **Cure:** Verify HOST_OP_ID extraction, check host service

**If status mismatch:**
- **Cause:** Caching issue or timing
- **Cure:** Wait longer, try again

---

## Evidence to Capture

- Backend ID: `$TASK_ID`
- Host ID: `$HOST_OP_ID`
- Backend query result
- Host query result
- Proxy registration log
