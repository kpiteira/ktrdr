# Pre-Flight: Training

**Used by:** Training E2E tests
**Purpose:** Verify training-specific prerequisites before test execution

---

## Checks

### 1. Strategy File Exists

**Command:**
```bash
STRATEGY_NAME="${STRATEGY_NAME:-test_e2e_local_pull}"
test -f ~/.ktrdr/shared/strategies/${STRATEGY_NAME}.yaml && echo "OK" || echo "MISSING"
```

**Pass if:** Output is `OK`

**Fail message:** "Strategy file not found: ${STRATEGY_NAME}.yaml"

---

### 2. Training Data Available

**Command:**
```bash
SYMBOL="${SYMBOL:-EURUSD}"
TIMEFRAME="${TIMEFRAME:-1d}"
ls data/${SYMBOL}_${TIMEFRAME}.csv data/${SYMBOL}_${TIMEFRAME}.pkl 2>/dev/null | head -1 && echo "OK" || echo "MISSING"
```

**Pass if:** File exists

**Fail message:** "Training data not found: ${SYMBOL} ${TIMEFRAME}"

---

### 3. Training Worker Available

**Command:**
```bash
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/workers" | \
  jq -e '.workers[] | select(.type=="training" and .status=="idle")' > /dev/null && echo "OK" || echo "BUSY"
```

**Pass if:** At least one idle training worker

**Fail message:** "No idle training workers available"

---

## Quick Check Script

```bash
#!/bin/bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

echo "=== Pre-Flight: Training ==="

# Check 1: Strategy
STRATEGY_NAME="${STRATEGY_NAME:-test_e2e_local_pull}"
if ! test -f ~/.ktrdr/shared/strategies/${STRATEGY_NAME}.yaml; then
  echo "FAIL: Strategy file not found: ${STRATEGY_NAME}.yaml"
  exit 1
fi
echo "OK: Strategy exists"

# Check 2: Data
SYMBOL="${SYMBOL:-EURUSD}"
TIMEFRAME="${TIMEFRAME:-1d}"
if ! ls data/${SYMBOL}_${TIMEFRAME}.* 2>/dev/null | head -1 > /dev/null; then
  echo "FAIL: Data not found for ${SYMBOL} ${TIMEFRAME}"
  exit 1
fi
echo "OK: Data available"

# Check 3: Worker
WORKERS=$(curl -s "http://localhost:$API_PORT/api/v1/workers" | jq '[.workers[] | select(.type=="training" and .status=="idle")] | length')
if [ "$WORKERS" -eq 0 ]; then
  echo "WARN: No idle training workers (may need to wait)"
fi
echo "OK: Workers checked"

echo "=== Training pre-flight passed ==="
```

---

## Symptom→Cure Mappings

### Strategy Not Found

**Symptom:** "Strategy file not found" error

**Cause:** Strategy not in shared directory

**Cure:**
```bash
# Copy strategy to shared location
cp strategies/${STRATEGY_NAME}.yaml ~/.ktrdr/shared/strategies/
```

**Max Retries:** 1
**Wait After Cure:** 0 seconds

---

### Data Not Found

**Symptom:** "Data not found" error

**Cause:** Data not cached for this symbol/timeframe

**Cure:**
```bash
# Check if data exists elsewhere and copy
if [ -f ~/.ktrdr/shared/data/${SYMBOL}_${TIMEFRAME}.csv ]; then
  cp ~/.ktrdr/shared/data/${SYMBOL}_${TIMEFRAME}.csv data/
else
  echo "Need to download data for ${SYMBOL} ${TIMEFRAME}"
fi
```

**Max Retries:** 1
**Wait After Cure:** 0 seconds

---

### No Idle Workers

**Symptom:** "No idle training workers" warning

**Cause:** Workers busy with other operations

**Cure:**
```bash
# Wait for workers to become available
sleep 10
```

**Max Retries:** 3
**Wait After Cure:** 10 seconds
