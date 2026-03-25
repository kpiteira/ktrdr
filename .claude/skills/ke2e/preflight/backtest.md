# Pre-Flight: Backtest

**Used by:** Backtest E2E tests
**Purpose:** Verify backtest-specific prerequisites before test execution

---

## Checks

### 1. Model File Exists

**Command:**
```bash
MODEL_PATH="${MODEL_PATH:-models/neuro_mean_reversion/1d_v21/model.pt}"
test -f "$MODEL_PATH" && echo "OK" || echo "MISSING"
```

**Pass if:** Output is `OK`

**Fail message:** "Model file not found: ${MODEL_PATH}"

---

### 2. Strategy File Exists

**Command:**
```bash
STRATEGY_NAME="${STRATEGY_NAME:-neuro_mean_reversion}"
test -f ~/.ktrdr/shared/strategies/${STRATEGY_NAME}.yaml && echo "OK" || echo "MISSING"
```

**Pass if:** Output is `OK`

**Fail message:** "Strategy file not found: ${STRATEGY_NAME}.yaml"

---

### 3. Backtest Data Available

**Command:**
```bash
SYMBOL="${SYMBOL:-EURUSD}"
TIMEFRAME="${TIMEFRAME:-1d}"
ls data/${SYMBOL}_${TIMEFRAME}.csv data/${SYMBOL}_${TIMEFRAME}.pkl 2>/dev/null | head -1 && echo "OK" || echo "MISSING"
```

**Pass if:** File exists

**Fail message:** "Backtest data not found: ${SYMBOL} ${TIMEFRAME}"

---

### 4. Backtest Worker Available

**Command:**
```bash
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/workers" | \
  jq -e '.workers[] | select(.type=="backtest")' > /dev/null && echo "OK" || echo "MISSING"
```

**Pass if:** At least one backtest worker registered

**Fail message:** "No backtest workers registered"

---

## Quick Check Script

```bash
#!/bin/bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

echo "=== Pre-Flight: Backtest ==="

# Check 1: Model
MODEL_PATH="${MODEL_PATH:-models/neuro_mean_reversion/1d_v21/model.pt}"
if ! test -f "$MODEL_PATH"; then
  echo "FAIL: Model not found: $MODEL_PATH"
  exit 1
fi
echo "OK: Model exists"

# Check 2: Strategy
STRATEGY_NAME="${STRATEGY_NAME:-neuro_mean_reversion}"
if ! test -f ~/.ktrdr/shared/strategies/${STRATEGY_NAME}.yaml; then
  echo "FAIL: Strategy not found: ${STRATEGY_NAME}.yaml"
  exit 1
fi
echo "OK: Strategy exists"

# Check 3: Data
SYMBOL="${SYMBOL:-EURUSD}"
TIMEFRAME="${TIMEFRAME:-1d}"
if ! ls data/${SYMBOL}_${TIMEFRAME}.* 2>/dev/null | head -1 > /dev/null; then
  echo "FAIL: Data not found for ${SYMBOL} ${TIMEFRAME}"
  exit 1
fi
echo "OK: Data available"

# Check 4: Worker
WORKERS=$(curl -s "http://localhost:$API_PORT/api/v1/workers" | jq '[.workers[] | select(.type=="backtest")] | length')
if [ "$WORKERS" -eq 0 ]; then
  echo "FAIL: No backtest workers registered"
  exit 1
fi
echo "OK: Backtest workers available"

echo "=== Backtest pre-flight passed ==="
```

---

## Symptom→Cure Mappings

### Model Not Found

**Symptom:** "Model not found" error

**Cause:** Model path incorrect or model not trained

**Cure:**
```bash
# List available models
find models -name "model.pt" -type f 2>/dev/null | head -5
echo "Update MODEL_PATH to use an existing model"
```

**Max Retries:** 0 (manual fix required)
**Wait After Cure:** 0 seconds

---

### Strategy Not Found

**Symptom:** "Strategy not found" error

**Cause:** Strategy not in shared directory

**Cure:**
```bash
cp strategies/${STRATEGY_NAME}.yaml ~/.ktrdr/shared/strategies/
```

**Max Retries:** 1
**Wait After Cure:** 0 seconds

---

### No Backtest Workers

**Symptom:** "No backtest workers registered"

**Cause:** Workers not started or crashed

**Cure:**
```bash
# Restart backtest workers
docker compose restart backtest-worker-1 backtest-worker-2
```

**Max Retries:** 1
**Wait After Cure:** 15 seconds
