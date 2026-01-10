# Test: training/smoke

**Purpose:** Quick validation that training starts, completes, and produces valid output
**Duration:** <30 seconds
**Category:** Training

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] Strategy file exists: `~/.ktrdr/shared/strategies/test_e2e_local_pull.yaml`
- [ ] Data available: EURUSD 1d has data in cache

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

**Why this data:**
- EURUSD 1d: 258 samples, trains in ~2s (fast feedback)
- 1 year range: Sufficient for smoke test, not too large
- test_e2e_local_pull: Known-good strategy for testing

---

## Execution Steps

### 1. Start Training

**Command:**
```bash
RESPONSE=$(curl -s -X POST http://localhost:${API_PORT:-8000}/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbols":["EURUSD"],"timeframes":["1d"],"strategy_name":"test_e2e_local_pull","start_date":"2024-01-01","end_date":"2024-12-31"}')

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
echo "Task ID: $TASK_ID"
```

**Expected:**
- HTTP 200
- `success: true`
- `status: "training_started"`
- `task_id` returned

### 2. Wait for Completion

**Command:**
```bash
sleep 10
curl -s "http://localhost:${API_PORT:-8000}/api/v1/operations/$TASK_ID" | \
  jq '{status:.data.status, samples:.data.result_summary.data_summary.total_samples}'
```

**Expected:**
- `status: "completed"`
- `samples: 258`

### 3. Verify No Errors

**Command:**
```bash
docker compose logs backend --since 2m | grep -i "error\|exception" | grep -v "No error"
```

**Expected:**
- No error lines (or only benign ones)

---

## Success Criteria

- [ ] Training starts successfully (HTTP 200, task_id returned)
- [ ] Training completes (status = "completed")
- [ ] Correct sample count (258 samples)
- [ ] No errors in logs

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Accuracy < 99%** — If accuracy is 100%, likely model collapse (see E2E_CHALLENGES_ANALYSIS.md)
- [ ] **Loss > 0.001** — If loss is ~0, training may have collapsed to trivial solution
- [ ] **Duration > 1s** — If instant, something is wrong (cached result? skipped training?)

**Check command:**
```bash
curl -s "http://localhost:${API_PORT:-8000}/api/v1/operations/$TASK_ID" | \
  jq '.data.result_summary.training_metrics | {accuracy, final_loss, training_time}'
```

---

## Troubleshooting

**If "strategy file not found":**
- **Cause:** Strategy not in shared directory
- **Cure:** Copy strategy to `~/.ktrdr/shared/strategies/`

**If training times out:**
- **Cause:** Backend may be overloaded or stuck
- **Cure:** Check `docker compose logs backend --tail 50`

**If 0 samples:**
- **Cause:** Data not in cache
- **Cure:** Load data first: `curl -X POST .../api/v1/data/EURUSD/1d`

---

## Evidence to Capture

- Operation ID: `$TASK_ID`
- Final status: `curl ... | jq '.data.status'`
- Training metrics: `curl ... | jq '.data.result_summary.training_metrics'`
- Logs: `docker compose logs backend --since 5m | grep $TASK_ID`
