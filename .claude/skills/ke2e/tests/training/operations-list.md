# Test: training/operations-list

**Purpose:** Validate operations API list and filter functionality
**Duration:** ~5 seconds
**Category:** Training

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] At least one previous operation exists (run smoke test first if needed)

---

## Test Data

No specific test data required — tests the operations API.

---

## Execution Steps

### 1. Start a Quick Training (create operation data)

**Command:**
```bash
curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbols":["EURUSD"],"timeframes":["1d"],"strategy_name":"test_e2e_local_pull","start_date":"2024-01-01","end_date":"2024-12-31"}' | jq
```

**Expected:**
- Training starts (creates operation data for testing)

### 2. List All Operations

**Command:**
```bash
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations" | \
  jq '{success:.success, count:(.data|length), total:.total_count}'
```

**Expected:**
- `success: true`
- `count: > 0`
- `total_count` present

### 3. Filter by Status

**Command:**
```bash
# Filter running
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations?status=running" | \
  jq '{status:"running", count:(.data|length)}'

# Filter completed
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations?status=completed" | \
  jq '{status:"completed", count:(.data|length)}'
```

**Expected:**
- Both queries return valid responses
- Count reflects actual operations with that status

### 4. Filter by Operation Type

**Command:**
```bash
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations?operation_type=training" | \
  jq '{type:"training", count:(.data|length)}'
```

**Expected:**
- Returns only training operations
- Count > 0 (we just started one)

### 5. Test Limit Parameter

**Command:**
```bash
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations?limit=5" | \
  jq '{limit:5, count:(.data|length), total:.total_count}'
```

**Expected:**
- `count <= 5`
- `total_count` may be higher than count

---

## Success Criteria

- [ ] List returns operations array with total_count
- [ ] Status filter returns only matching operations
- [ ] Type filter returns only training operations
- [ ] Limit restricts results correctly
- [ ] Response structure: `{success, data: [...], total_count, active_count}`

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Count matches filter** — Filtered results only contain matching status/type
- [ ] **total_count >= count** — Total should be >= returned count with limit

**Check command:**
```bash
# Verify a filtered result actually has the right status
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations?status=completed&limit=1" | \
  jq '.data[0].status'
```

**Expected:** Should return `"completed"`

---

## Troubleshooting

**If count is 0:**
- **Cause:** No operations exist yet
- **Cure:** Run smoke test first to create operation data

**If filter returns wrong results:**
- **Cause:** Bug in filter implementation
- **Cure:** Check backend logs for SQL query errors

---

## Evidence to Capture

- List response: `{success, count, total_count}`
- Filter responses: Status and type filter results
- Logs: `docker compose logs backend --since 1m | grep operations`
