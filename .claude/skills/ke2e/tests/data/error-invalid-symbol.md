# Test: data/error-invalid-symbol

**Purpose:** Validate error handling for invalid symbol
**Duration:** <1 second
**Category:** Data (Error Handling)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

---

## Test Data

Invalid symbol: `INVALID_SYMBOL_XYZ123`

---

## Execution Steps

### 1. Request Data for Invalid Symbol

**Command:**
```bash
curl -i -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/data/INVALID_SYMBOL_XYZ123/1h"
```

**Expected:**
- HTTP 404 Not Found
- Error message indicates data not found

---

## Success Criteria

- [ ] HTTP 404 returned (not 500)
- [ ] Error message is clear
- [ ] No stack traces exposed
- [ ] System remains stable

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Not HTTP 200** — Should fail, not return empty success
- [ ] **Not HTTP 500** — Should be client error, not server error
- [ ] **Message helpful** — User understands what's wrong

---

## Troubleshooting

**If HTTP 500:**
- **Cause:** Unhandled exception
- **Cure:** Check backend logs, report bug

**If HTTP 200 with empty data:**
- **Cause:** API returning success for missing data
- **Cure:** This may be expected behavior — check if empty array returned

---

## Evidence to Capture

- HTTP status code
- Response body
