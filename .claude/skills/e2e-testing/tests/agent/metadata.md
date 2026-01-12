# Test: agent/metadata

**Purpose:** Verify parent operation stores results from each phase
**Duration:** ~2 minutes
**Category:** Agent

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] Agent is idle before starting

---

## Execution Steps

### 1. Run Full Cycle

**Command:**
```bash
RESULT=$(curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/agent/trigger)
OP_ID=$(echo $RESULT | jq -r '.operation_id')
echo "Started operation: $OP_ID"

# Wait for completion
while true; do
    STATUS=$(curl -s http://localhost:${KTRDR_API_PORT:-8000}/api/v1/agent/status | jq -r '.status')
    echo -n "."
    if [ "$STATUS" == "idle" ]; then
        break
    fi
    sleep 5
done
echo ""
echo "Cycle complete"
```

### 2. Check Metadata

**Command:**
```bash
METADATA=$(curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$OP_ID" | jq '.data.metadata.parameters')
echo "Parent metadata:"
echo $METADATA | jq
```

### 3. Verify Required Fields

**Command:**
```bash
HAS_STRATEGY=$(echo $METADATA | jq 'has("strategy_name")')
HAS_TRAINING=$(echo $METADATA | jq 'has("training_result")')
HAS_BACKTEST=$(echo $METADATA | jq 'has("backtest_result")')
HAS_VERDICT=$(echo $METADATA | jq 'has("assessment_verdict")')

echo "strategy_name: $HAS_STRATEGY"
echo "training_result: $HAS_TRAINING"
echo "backtest_result: $HAS_BACKTEST"
echo "assessment_verdict: $HAS_VERDICT"
```

**Expected:**
- All fields present: true

---

## Success Criteria

- [ ] Cycle completes
- [ ] `strategy_name` present
- [ ] `training_result` present
- [ ] `backtest_result` present
- [ ] `assessment_verdict` present

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **All fields present** — Not just one or two
- [ ] **Values not null** — Fields have actual data
- [ ] **Verdict valid** — One of: promising, mediocre, poor, etc.

---

## Troubleshooting

**If metadata missing:**
- **Cause:** Phase didn't complete or didn't store results
- **Cure:** Check logs for phase completion messages

**If cycle didn't complete:**
- **Cause:** Timeout or error in one of the phases
- **Cure:** Check backend logs for errors

---

## Evidence to Capture

- Operation ID
- Full metadata JSON
