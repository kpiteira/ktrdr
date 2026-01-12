# Test: backtest/error-model-not-found

**Purpose:** Verify error handling for invalid model path
**Duration:** ~2 seconds
**Category:** Backtest (Error Handling)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

---

## Test Data

```json
{
  "model_path": "models/nonexistent_model/invalid_v99/model.pt",
  "strategy_name": "neuro_mean_reversion",
  "symbol": "EURUSD",
  "timeframe": "1d",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31"
}
```

---

## Execution Steps

### 1. Request Backtest with Invalid Model

**Command:**
```bash
curl -i -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/backtests/start \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "models/nonexistent_model/invalid_v99/model.pt",
    "strategy_name": "neuro_mean_reversion",
    "symbol": "EURUSD",
    "timeframe": "1d",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }'
```

**Expected:**
- HTTP 404 or 400, OR
- Operation fails early

---

## Success Criteria

- [ ] Error returned
- [ ] Error message: "Model file not found"
- [ ] No PyTorch stack traces
- [ ] System stable

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Not success** — Should fail for invalid model
- [ ] **Clean error** — No raw stack traces exposed

---

## Evidence to Capture

- HTTP status
- Error message
