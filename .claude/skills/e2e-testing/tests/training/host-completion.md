# Test: training/host-completion

**Purpose:** Validate full training cycle through backend → host proxy
**Duration:** ~5 seconds
**Category:** Training (Integration)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] Backend and host service running
- [ ] Host mode enabled

---

## Test Data

Same quick training config.

---

## Execution Steps

### 1. Start Training

**Command:**
```bash
RESPONSE=$(curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbols":["EURUSD"],"timeframes":["1d"],"strategy_name":"test_e2e_local_pull","start_date":"2024-01-01","end_date":"2024-12-31"}')

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
```

### 2. Wait for Completion

**Command:**
```bash
sleep 10
```

### 3. Check Final Status and Metrics

**Command:**
```bash
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$TASK_ID" | \
  jq '{status:.data.status, epochs_count:(.data.metrics.epochs[0]|length), final_acc:.data.metrics.epochs[0][-1].val_accuracy}'
```

**Expected:**
- `status: "completed"`
- `epochs_count: 10`
- `final_acc: < 1.0` (reasonable accuracy)

---

## Success Criteria

- [ ] Training completes successfully
- [ ] Backend retrieves full metrics from host
- [ ] All 10 epochs collected
- [ ] Final accuracy metrics available

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Epochs = 10** — Full training completed
- [ ] **Metrics present** — Not null or empty
- [ ] **Accuracy reasonable** — < 100% (not model collapse)

---

## Troubleshooting

**If epochs missing:**
- **Cause:** Metrics not proxied correctly
- **Cure:** Check host service response format

**If status stuck at "running":**
- **Cause:** Proxy not updating
- **Cure:** Query host directly to verify completion

---

## Evidence to Capture

- Operation ID: `$TASK_ID`
- Final status and metrics
- Backend logs: completion message
