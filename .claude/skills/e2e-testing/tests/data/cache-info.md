# Test: data/cache-info

**Purpose:** Validate data inventory API
**Duration:** <500ms
**Category:** Data

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

---

## Execution Steps

### 1. Get Data Info

**Command:**
```bash
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/data/info" | jq
```

**Expected:**
- HTTP 200 OK
- Lists available symbols and timeframes

### 2. Check Symbol Count

**Command:**
```bash
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/data/info" | \
  jq '{total_symbols:.data.total_symbols, timeframes:.data.timeframes_available}'
```

**Expected:**
- Multiple symbols listed
- Multiple timeframes available

### 3. Check EURUSD Entry

**Command:**
```bash
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/data/info" | \
  jq '.data.available_symbols[] | select(contains("EURUSD"))'
```

**Expected:**
- EURUSD found with multiple timeframes

---

## Success Criteria

- [ ] HTTP 200 OK
- [ ] Lists cached symbols (typically 30+)
- [ ] Shows available timeframes per symbol
- [ ] Response time <500ms

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **total_symbols > 0** — Some data cached
- [ ] **EURUSD present** — Common symbol in cache
- [ ] **Multiple timeframes** — At least 1d, 1h expected

---

## Troubleshooting

**If empty response:**
- **Cause:** No data in cache
- **Cure:** Download some data first

**If slow:**
- **Cause:** Scanning large data directory
- **Note:** May be slower with many files

---

## Evidence to Capture

- Total symbol count
- Available timeframes
- EURUSD entry details
