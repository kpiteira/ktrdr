# Test: training/progress

**Purpose:** Validate progress updates and metrics collection during extended training
**Duration:** ~60-90 seconds
**Category:** Training

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] Strategy file exists: `~/.ktrdr/shared/strategies/test_e2e_local_pull.yaml`
- [ ] Data available: EURUSD 5m has sufficient data (2+ years)

---

## Test Data

```json
{
  "symbols": ["EURUSD"],
  "timeframes": ["5m"],
  "strategy_name": "test_e2e_local_pull",
  "start_date": "2023-01-01",
  "end_date": "2025-01-01"
}
```

**Why this data:**
- EURUSD 5m: ~147,000 samples over 2 years, trains in ~60s
- Long enough to observe progress updates across multiple epochs
- 10 epochs give regular progress increments

---

## Execution Steps

### 1. Start Training

**Command:**
```bash
RESPONSE=$(curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbols":["EURUSD"],"timeframes":["5m"],"strategy_name":"test_e2e_local_pull","start_date":"2023-01-01","end_date":"2025-01-01"}')

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
echo "Task ID: $TASK_ID"
```

**Expected:**
- HTTP 200
- `success: true`
- `task_id` returned

### 2. Poll Progress Every 15s

**Command:**
```bash
for i in {1..6}; do
  sleep 15
  curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$TASK_ID" | \
    jq '{poll:'"$i"', status:.data.status, percentage:.data.progress.percentage, step:.data.progress.current_step}'
done
```

**Expected:**
- Progress increases: 0% → ~40% → ~70% → ~90% → 100%
- Status transitions: `running` → `completed`
- `current_step` shows epoch progress

### 3. Get Final Results

**Command:**
```bash
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$TASK_ID" | \
  jq '{status:.data.status, duration:.data.result_summary.training_metrics.training_time, epochs:.data.metrics.epochs|length}'
```

**Expected:**
- `status: "completed"`
- `duration: ~60-70` (seconds)
- `epochs: 10`

---

## Success Criteria

- [ ] Training starts successfully (task_id returned)
- [ ] Progress percentage increases over time
- [ ] Progress visible at intermediate polls (not just 0% then 100%)
- [ ] Final status is "completed"
- [ ] All 10 epochs captured in metrics
- [ ] Duration approximately 60-90 seconds

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Progress was observable** — At least one poll showed progress between 10% and 90%
- [ ] **Duration > 30s** — If training_time < 30s for this dataset, something skipped
- [ ] **Epochs count = 10** — Missing epochs means metrics collection failed
- [ ] **Final accuracy < 100%** — 100% val_accuracy on this dataset indicates model collapse

**Check command:**
```bash
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$TASK_ID" | \
  jq '{val:.data.result_summary.training_metrics.final_val_accuracy,time:.data.result_summary.training_metrics.training_time,epochs:(.data.metrics.epochs|length)}'
```

**Expected output (example):**
```json
{"val": 0.98, "time": 62, "epochs": 10}
```
*Thresholds: val < 1.0, time > 30, epochs = 10*

---

## Troubleshooting

**If progress jumps from 0% to 100%:**
- **Cause:** Polling interval too long OR training faster than expected
- **Cure:** Increase dataset size or decrease poll interval to 5s

**If training takes > 5 minutes:**
- **Cause:** Backend may be overloaded or CPU-throttled in Docker
- **Cure:** Check `docker stats` for resource usage

**If epochs count < 10:**
- **Cause:** Metrics not being collected properly
- **Cure:** Check backend logs for metrics collection errors

**If 0 samples:**
- **Cause:** Data not in cache or timeframe mismatch
- **Cure:** Verify EURUSD 5m data exists: `ls data/EURUSD_5m*`

---

## Evidence to Capture

- Operation ID: `$TASK_ID`
- Progress snapshots: Save output from step 2
- Final metrics: `curl ... | jq '.data.result_summary.training_metrics'`
- Logs: `docker compose logs backend --since 5m | grep $TASK_ID`
