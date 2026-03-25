# Test: training/host-start

**Purpose:** Validate training host service works standalone (without backend)
**Duration:** ~5 seconds
**Category:** Training (Host Service)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] Training host service running (port 5002)
- [ ] Strategy file accessible from host: `strategies/test_e2e_local_pull.yaml`

**Host service check:**
```bash
curl -s http://localhost:5002/health | jq
```

---

## Test Data

```json
{
  "strategy_yaml": "<content of test_e2e_local_pull.yaml>",
  "symbols": ["EURUSD"],
  "timeframes": ["1d"],
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}
```

**Why this data:**
- Same quick training as smoke test
- Tests host service directly, bypassing backend

---

## Execution Steps

### 1. Read Strategy YAML

**Command:**
```bash
STRATEGY_YAML=$(cat ~/.ktrdr/shared/strategies/test_e2e_local_pull.yaml)
echo "Strategy loaded: $(echo "$STRATEGY_YAML" | head -1)"
```

**Expected:**
- Strategy content loaded

### 2. Start Training Directly on Host

**Command:**
```bash
RESPONSE=$(curl -s -X POST http://localhost:5002/training/start \
  -H "Content-Type: application/json" \
  -d "{
    \"strategy_yaml\": $(echo "$STRATEGY_YAML" | jq -Rs .),
    \"symbols\": [\"EURUSD\"],
    \"timeframes\": [\"1d\"],
    \"start_date\": \"2024-01-01\",
    \"end_date\": \"2024-12-31\"
  }")

SESSION_ID=$(echo "$RESPONSE" | jq -r '.session_id')
echo "Session ID: $SESSION_ID"
echo "$RESPONSE" | jq '{session_id, gpu_allocated}'
```

**Expected:**
- `session_id` returned
- `gpu_allocated: true` (or false if no GPU)

### 3. Check Status

**Command:**
```bash
sleep 5
curl -s "http://localhost:5002/training/status/$SESSION_ID" | \
  jq '{status:.status, gpu:.gpu_usage.gpu_allocated}'
```

**Expected:**
- `status: "completed"` (or "running" if still in progress)
- GPU usage info present

---

## Success Criteria

- [ ] Host service accepts direct requests (no backend needed)
- [ ] Returns session_id
- [ ] GPU allocation info included
- [ ] Status queryable independently
- [ ] Training completes successfully

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Session ID format** — Should be a valid UUID
- [ ] **Response has required fields** — `session_id`, `gpu_allocated` present
- [ ] **Status endpoint works** — Can query status by session_id

---

## Troubleshooting

**If connection refused:**
- **Cause:** Training host service not running
- **Cure:** Start host service: `cd training-host-service && ./start.sh`

**If "strategy_yaml required":**
- **Cause:** JSON escaping issue with YAML content
- **Cure:** Ensure `jq -Rs` properly escapes the YAML string

**If GPU not allocated:**
- **Note:** This is OK if no GPU available — training falls back to CPU
- Host service still works correctly without GPU

---

## Notes

**Endpoint difference:** Host service uses `/training/start` (not `/api/v1/training/start`)

---

## Evidence to Capture

- Session ID: `$SESSION_ID`
- Start response: `{session_id, gpu_allocated}`
- Status response: `{status, gpu_usage}`
- Host logs: `tail -20 training-host-service/logs/ktrdr-host-service.log`
