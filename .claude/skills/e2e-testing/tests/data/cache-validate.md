# Test: data/cache-validate

**Purpose:** Verify data validation logic works
**Duration:** <1 second
**Category:** Data

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] EURUSD 1d data in cache

---

## Execution Steps

### 1. Load with Implicit Validation

**Command:**
```bash
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/data/EURUSD/1d" | \
  jq '{bars: (.data.ohlcv | length), first: .data.ohlcv[0], last: .data.ohlcv[-1]}'
```

**Expected:**
- Data loads successfully
- OHLCV arrays present

### 2. Check for Quality Issues in Logs

**Command:**
```bash
docker compose logs backend --since 30s | \
  grep -E "validation|data quality|gap detected" | tail -5
```

**Expected:**
- Validation runs automatically (logs may show validation messages)
- Minor issues (gaps) may be reported as warnings, not errors

---

## Success Criteria

- [ ] Data loads successfully
- [ ] All OHLCV columns present
- [ ] No NaN or null values in returned data
- [ ] Validation runs (visible in logs)

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **OHLCV structure correct** — Each bar has 5 values
- [ ] **Values not null** — First and last bars have numeric values
- [ ] **Reasonable values** — OHLCV prices are positive

**Check command:**
```bash
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/data/EURUSD/1d" | \
  jq '{bar_length: (.data.ohlcv[0] | length), first_open: .data.ohlcv[0][0], valid: (.data.ohlcv[0][0] > 0)}'
```

**Expected:** `bar_length: 5`, `first_open: > 0`, `valid: true`

---

## Troubleshooting

**If validation issues reported:**
- **Note:** Minor issues (gaps) are expected and non-blocking
- **Concern:** Only if "validation failed" appears

**If null values:**
- **Cause:** Data corruption
- **Cure:** Re-download data

---

## Evidence to Capture

- Bar count
- First/last bar values
- Validation log messages
