# Test: training/host-integration

**Purpose:** Validate backend → host proxy pattern
**Duration:** ~5 seconds
**Category:** Training (Integration)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] Backend running
- [ ] Training host service running (port 5002)
- [ ] Host mode enabled: `USE_TRAINING_HOST_SERVICE=true`

**Mode check:**
```bash
docker compose exec backend env | grep USE_TRAINING_HOST_SERVICE
```

---

## Test Data

```json
{
  "symbols": ["EURUSD"],
  "timeframes": ["1d"],
  "strategy_name": "test_e2e_local_pull",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}
```

---

## Execution Steps

### 1. Switch to Host Mode (if needed)

**Command:**
```bash
./scripts/switch-training-mode.sh host
sleep 5
```

**Expected:**
- Mode switched to host
- Backend restarted

### 2. Start Training via Backend

**Command:**
```bash
RESPONSE=$(curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbols":["EURUSD"],"timeframes":["1d"],"strategy_name":"test_e2e_local_pull","start_date":"2024-01-01","end_date":"2024-12-31"}')

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
echo "Backend Task ID: $TASK_ID"
```

**Expected:**
- `task_id` returned
- Backend accepts request

### 3. Extract Host Operation ID from Logs

**Command:**
```bash
sleep 3
HOST_OP_ID=$(docker compose logs backend --since 30s | \
  grep "Registered remote proxy.*$TASK_ID" | \
  grep -o 'host_training_[a-f0-9-]*' | head -1)
echo "Host Operation ID: $HOST_OP_ID"
```

**Expected:**
- Host operation ID extracted
- Format: `host_training_<uuid>`

### 4. Verify Backend Has Proxy (NOT Bridge)

**Command:**
```bash
# Should find proxy registration
docker compose logs backend --since 30s | \
  grep "Registered remote proxy.*$TASK_ID"

# Should NOT find local bridge
docker compose logs backend --since 30s | \
  grep "Registered local training bridge.*$TASK_ID" && echo "UNEXPECTED: Local bridge found" || echo "OK: No local bridge"
```

**Expected:**
- Proxy registration found
- NO local bridge logged

### 5. Verify Host Has Bridge

**Command:**
```bash
grep "Registered local bridge for operation $HOST_OP_ID" \
  training-host-service/logs/ktrdr-host-service.log | tail -1
```

**Expected:**
- Bridge registration in host logs

### 6. Query Via Backend

**Command:**
```bash
sleep 5
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$TASK_ID" | \
  jq '{status:.data.status}'
```

**Expected:**
- Status returned (proxied from host)

---

## Success Criteria

- [ ] Backend logs: Proxy registration
- [ ] Backend logs: NO local bridge
- [ ] Host logs: Local bridge registration
- [ ] Backend query works (proxies to host)
- [ ] Operation ID mapping: Backend ID ↔ Host ID

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Proxy logged, not bridge** — Backend should NOT have local bridge
- [ ] **Host has bridge** — Training actually ran on host
- [ ] **IDs are different** — Backend ID starts with `op_training_`, host ID with `host_training_`

---

## Troubleshooting

**If local bridge found in backend:**
- **Cause:** Still in local mode
- **Cure:** Run `./scripts/switch-training-mode.sh host` and restart

**If host operation ID not found:**
- **Cause:** Logs rotated or wrong time window
- **Cure:** Increase `--since` duration or check full logs

**If query fails:**
- **Cause:** Proxy not working
- **Cure:** Check host service is running and accessible

---

## Evidence to Capture

- Backend Task ID: `$TASK_ID`
- Host Operation ID: `$HOST_OP_ID`
- Proxy registration log line
- Host bridge registration log line
- Final status query result
