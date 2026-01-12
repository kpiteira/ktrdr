# Test: data/cache-get

**Purpose:** Validate cache loading performance and correctness
**Duration:** <3 seconds
**Category:** Data

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] EURUSD 1h data exists: `ls data/EURUSD_1h.csv` or `data/EURUSD_1h.pkl`

---

## Test Data

No request payload — tests GET endpoint for cached data.

---

## Execution Steps

### 1. Check Data Available

**Command:**
```bash
test -f data/EURUSD_1h.csv && echo "Data available" || test -f data/EURUSD_1h.pkl && echo "Data available" || echo "Data missing - run download first"
```

**Expected:**
- Data file exists

### 2. Load from Cache

**Command:**
```bash
RESPONSE=$(curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/data/EURUSD/1h")
ROWS=$(echo "$RESPONSE" | jq '.data.ohlcv | length')
echo "Loaded $ROWS bars"
```

**Expected:**
- HTTP 200 OK
- Substantial bar count (>10,000 for 1h data)

### 3. Verify Data Structure

**Command:**
```bash
echo "$RESPONSE" | jq '{dates_count: (.data.dates | length), ohlcv_count: (.data.ohlcv | length), first_bar: .data.ohlcv[0]}'
```

**Expected:**
- `dates` and `ohlcv` arrays present
- OHLCV format: `[open, high, low, close, volume]`

### 4. Check Performance

**Command:**
```bash
time curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/data/EURUSD/1h" > /dev/null
```

**Expected:**
- Load time <3 seconds (acceptable for large datasets)

---

## Success Criteria

- [ ] HTTP 200 OK
- [ ] Response has `dates` and `ohlcv` arrays
- [ ] OHLCV format: [open, high, low, close, volume]
- [ ] Substantial data returned (>10,000 bars for 1h)
- [ ] Load time <3 seconds

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Data not empty** — ohlcv length > 0
- [ ] **Values reasonable** — OHLCV values are positive numbers
- [ ] **Dates present** — dates array has same length as ohlcv

**Check command:**
```bash
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/data/EURUSD/1h" | \
  jq '{bars: (.data.ohlcv | length), first_open: .data.ohlcv[0][0], dates_match: ((.data.dates | length) == (.data.ohlcv | length))}'
```

---

## Troubleshooting

**If 404:**
- **Cause:** Data not in cache
- **Cure:** Download data first or use different symbol

**If slow (>5s):**
- **Cause:** Large dataset or cold cache
- **Note:** First load may be slower

---

## Evidence to Capture

- Bar count
- Load time
- First and last dates
