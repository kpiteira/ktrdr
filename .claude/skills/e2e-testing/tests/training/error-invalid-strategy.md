# Test: training/error-invalid-strategy

**Purpose:** Validate error handling for non-existent strategy
**Duration:** ~1 second
**Category:** Training (Error Handling)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

---

## Test Data

```json
{
  "symbols": ["EURUSD"],
  "timeframes": ["1d"],
  "strategy_name": "nonexistent_strategy_xyz",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}
```

**Why this data:**
- Uses strategy name that definitely doesn't exist
- Tests error path, not success path

---

## Execution Steps

### 1. Request Training with Invalid Strategy

**Command:**
```bash
curl -i -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbols":["EURUSD"],"timeframes":["1d"],"strategy_name":"nonexistent_strategy_xyz","start_date":"2024-01-01","end_date":"2024-12-31"}'
```

**Expected:**
- HTTP 400 Bad Request
- Error message indicates strategy not found
- Lists searched locations

---

## Success Criteria

- [ ] HTTP 400 returned (not 500)
- [ ] Error message is clear: "Strategy file not found"
- [ ] Searched paths listed in response
- [ ] No stack traces exposed
- [ ] System remains stable

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Not HTTP 200** — Request should fail, not succeed silently
- [ ] **Not HTTP 500** — Should be client error (4xx), not server error
- [ ] **Message is helpful** — User can understand what went wrong

---

## Troubleshooting

**If HTTP 500:**
- **Cause:** Unhandled exception
- **Cure:** Check backend logs for stack trace, report bug

**If HTTP 200:**
- **Cause:** Validation not happening at API level
- **Cure:** Check if error surfaces later in operation status

---

## Evidence to Capture

- HTTP status code
- Response body: `{"detail": "..."}`
- Backend logs: Any error messages
