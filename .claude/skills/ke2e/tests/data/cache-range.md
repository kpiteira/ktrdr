# Test: data/cache-range

**Purpose:** Validate metadata queries (no data loading)
**Duration:** <100ms
**Category:** Data

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] EURUSD 1h data in cache

---

## Execution Steps

### 1. Query Range

**Command:**
```bash
curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/data/range \
  -H "Content-Type: application/json" \
  -d '{"symbol":"EURUSD","timeframe":"1h"}' | jq
```

**Expected:**
- HTTP 200 OK
- Returns metadata without loading full data

### 2. Verify Response Fields

**Command:**
```bash
curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/data/range \
  -H "Content-Type: application/json" \
  -d '{"symbol":"EURUSD","timeframe":"1h"}' | \
  jq '{symbol:.data.symbol, timeframe:.data.timeframe, start:.data.start_date, end:.data.end_date, count:.data.point_count}'
```

**Expected:**
- `symbol`, `timeframe`, `start_date`, `end_date`, `point_count` present

### 3. Check Performance

**Command:**
```bash
time curl -s -X POST http://localhost:${KTRDR_API_PORT:-8000}/api/v1/data/range \
  -H "Content-Type: application/json" \
  -d '{"symbol":"EURUSD","timeframe":"1h"}' > /dev/null
```

**Expected:**
- Response time <100ms (metadata query, no data load)

---

## Success Criteria

- [ ] HTTP 200 OK
- [ ] Returns metadata without loading full data
- [ ] Response time <100ms
- [ ] Response has symbol, timeframe, dates, point_count

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **point_count > 0** — Data exists
- [ ] **Dates valid** — start_date < end_date
- [ ] **Fast response** — <100ms (not loading full data)

---

## Troubleshooting

**If slow (>500ms):**
- **Cause:** May be loading full data instead of metadata
- **Cure:** Check endpoint implementation

**If 404:**
- **Cause:** Symbol/timeframe not in cache
- **Cure:** Use different symbol or download data

---

## Evidence to Capture

- Response time
- Point count
- Date range
