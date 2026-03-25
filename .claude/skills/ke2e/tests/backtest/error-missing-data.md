# Test: backtest/error-missing-data

**Purpose:** Verify error handling for invalid symbol
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
  "strategy_name": "neuro_mean_reversion",
  "symbol": "INVALID_SYMBOL_XYZ",
  "timeframe": "1d",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31"
}
```

---

## Execution Steps

### 1. Request Backtest with Invalid Symbol

**Command:**
```bash
curl -i -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/backtests/start \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "models/neuro_mean_reversion/1d_v21/model.pt",
    "strategy_name": "neuro_mean_reversion",
    "symbol": "INVALID_SYMBOL_XYZ",
    "timeframe": "1d",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }'
```

**Expected:**
- HTTP 404 or 400, OR
- Operation fails with clear error

---

## Success Criteria

- [ ] Error returned
- [ ] Error message: "Historical data not found" or similar
- [ ] Shows expected file path
- [ ] System stable

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Not success** — Should fail for invalid symbol
- [ ] **Message is clear** — User knows symbol not found

---

## Evidence to Capture

- HTTP status
- Error message
