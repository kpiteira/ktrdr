# Troubleshooting: Data

Common data-related issues during E2E testing.

---

## Data Location Issues

**Symptom:**
- "Data not found" errors
- Empty data responses
- Tests can't find cached data

**Cause:** Data directory not mounted or path mismatch.

**Diagnosis Steps:**
```bash
# Check data directory exists
ls -la data/

# Check data files
ls data/*.csv data/*.pkl 2>/dev/null | head -5

# Check Docker mount
docker compose exec backend ls /app/data/ | head -5
```

**Solution:**
1. Verify data directory has files: `ls data/`
2. Check Docker volume mount in compose file
3. Use shared data directory: `~/.ktrdr/shared/data/`

**Prevention:**
- Keep data in standard location: `data/` or `~/.ktrdr/shared/data/`
- Verify mounts before running tests

---

## Missing Symbol Data

**Symptom:**
- 404 when requesting specific symbol
- "No data for SYMBOL" error
- Test needs data that doesn't exist

**Cause:** Symbol not downloaded or cached.

**Diagnosis Steps:**
```bash
# Check if symbol data exists
ls data/EURUSD_* 2>/dev/null

# Check via API
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/data/info" | jq '.data.total_symbols'
```

**Solution:**
1. Download data: Use data acquisition API
2. Copy from shared cache: `cp ~/.ktrdr/shared/data/SYMBOL_*.csv data/`
3. Use different symbol that exists

---

## Timeframe Mismatch

**Symptom:**
- Strategy expects 1d but test provides 5m
- "No features computed" in logs
- 0 samples in training

**Cause:** Test data timeframe doesn't match strategy requirements.

**Diagnosis Steps:**
```bash
# Check strategy timeframe requirements
grep -A5 "timeframes:" strategies/my_strategy.yaml

# Check available timeframes
ls data/EURUSD_*.csv | sed 's/.*_//' | sed 's/.csv//'
```

**Solution:**
1. Match test parameters to strategy requirements
2. Download data for required timeframe
3. Update strategy to accept available timeframe

---

## Stale Cache

**Symptom:**
- Data seems outdated
- Recent dates missing
- Unexpectedly old data returned

**Cause:** Cache not refreshed, using old data.

**Diagnosis Steps:**
```bash
# Check file modification times
ls -lt data/EURUSD_1h.csv

# Check date range in cache
head -2 data/EURUSD_1h.csv
tail -2 data/EURUSD_1h.csv
```

**Solution:**
1. Re-download with fresh data
2. Use `mode: "tail"` to get latest
3. Delete and re-download: `rm data/SYMBOL_*.csv`

---

## Data Validation Errors

**Symptom:**
- "Validation failed" in logs
- Data loads but has issues
- Gaps detected in data

**Cause:** Data has quality issues (gaps, missing values).

**Diagnosis Steps:**
```bash
# Check validation logs
docker compose logs backend --since 5m | grep -i "validation"
```

**Solution:**
1. Minor gaps are usually OK (non-blocking)
2. For major issues: re-download data
3. Use different date range to avoid gaps

**Note:** Some gaps are expected (weekends, holidays). Only concern if affecting test results.
