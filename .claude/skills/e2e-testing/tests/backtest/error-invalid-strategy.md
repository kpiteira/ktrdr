# Test: backtest/error-invalid-strategy

**Purpose:** Verify error handling for non-existent strategy
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
  "model_path": "models/neuro_mean_reversion/1d_v21/model.pt",
  "strategy_name": "nonexistent_strategy_xyz",
  "symbol": "EURUSD",
  "timeframe": "1d",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31"
}
```

---

## Execution Steps

### 1. Request Backtest with Invalid Strategy

**Command:**
```bash
curl -i -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/backtests/start \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "models/neuro_mean_reversion/1d_v21/model.pt",
    "strategy_name": "nonexistent_strategy_xyz",
    "symbol": "EURUSD",
    "timeframe": "1d",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }'
```

**Expected:**
- HTTP 400 or 404, OR
- Operation fails quickly with clear error

---

## Success Criteria

- [ ] Error returned (HTTP 4xx or operation fails)
- [ ] Error message: "Strategy file not found"
- [ ] Shows searched paths
- [ ] No stack traces
- [ ] System stable

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Not HTTP 200 with success** — Should fail
- [ ] **Message is helpful** — User knows what went wrong

---

## Evidence to Capture

- HTTP status
- Error message
