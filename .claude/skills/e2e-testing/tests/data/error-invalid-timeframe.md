# Test: data/error-invalid-timeframe

**Purpose:** Validate error handling for invalid timeframe
**Duration:** <1 second
**Category:** Data (Error Handling)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

---

## Test Data

Invalid timeframe: `99x` (not a valid timeframe)

---

## Execution Steps

### 1. Request Data with Invalid Timeframe

**Command:**
```bash
curl -i -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/data/EURUSD/99x"
```

**Expected:**
- HTTP 400 or 404
- Error message indicates invalid timeframe

---

## Success Criteria

- [ ] HTTP 4xx returned (not 500)
- [ ] Error message is clear
- [ ] No stack traces exposed
- [ ] System remains stable

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Not HTTP 200** — Should fail for invalid timeframe
- [ ] **Not HTTP 500** — Should be client error
- [ ] **Valid timeframes work** — EURUSD/1d returns 200

**Verify valid timeframe works:**
```bash
curl -s -o /dev/null -w "%{http_code}" "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/data/EURUSD/1d"
```

**Expected:** `200`

---

## Troubleshooting

**If HTTP 500:**
- **Cause:** Timeframe validation not happening
- **Cure:** Check backend logs, report bug

**If HTTP 200:**
- **Cause:** API may be lenient with timeframes
- **Cure:** Check if empty data returned (may be expected)

---

## Evidence to Capture

- HTTP status code
- Response body
- Comparison with valid timeframe response
