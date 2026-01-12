# Test: training/error-not-found

**Purpose:** Validate error handling for non-existent operation
**Duration:** ~1 second
**Category:** Training (Error Handling)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

---

## Test Data

Operation ID that doesn't exist: `nonexistent_operation_id_12345`

---

## Execution Steps

### 1. Query Non-Existent Operation

**Command:**
```bash
curl -i -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/nonexistent_operation_id_12345"
```

**Expected:**
- HTTP 404 Not Found
- Error message: "Operation not found: nonexistent_operation_id_12345"

---

## Success Criteria

- [ ] HTTP 404 returned
- [ ] Error message is clear
- [ ] No stack traces
- [ ] System stable

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Not HTTP 200** — Should not return empty success
- [ ] **Not HTTP 500** — Should be 404, not server error
- [ ] **Message includes ID** — User can verify which ID was not found

---

## Troubleshooting

**If HTTP 500:**
- **Cause:** Unhandled exception in lookup
- **Cure:** Check backend logs, report bug

**If HTTP 200 with empty data:**
- **Cause:** API returning success for missing data
- **Cure:** Fix API to return 404

---

## Evidence to Capture

- HTTP status code: Should be 404
- Response body: `{"detail": "Operation not found: ..."}`
