# Test: cli/context-analyze

**Purpose:** Validate that `ktrdr context analyze` produces valid 3-class context labels, statistics, and quality gate results from real cached EURUSD market data.
**Duration:** <30 seconds
**Category:** CLI (Local, no Docker/API)

---

## Pre-Flight Checks

**Required modules:** None (pure local CLI command)

**Test-specific checks:**
- [ ] Cached daily data exists: `data/EURUSD_1d.csv` is present and non-empty
- [ ] Cached hourly data exists: `data/EURUSD_1h.csv` is present and non-empty
- [ ] Both files contain data covering the 2020-01-01 to 2025-01-01 range
- [ ] `uv` is available on the system

**Pre-flight commands:**
```bash
# Verify data files exist and have content
test -s data/EURUSD_1d.csv || { echo "FAIL: data/EURUSD_1d.csv missing or empty"; exit 1; }
test -s data/EURUSD_1h.csv || { echo "FAIL: data/EURUSD_1h.csv missing or empty"; exit 1; }

# Verify date range coverage (daily file should have 2020+ data)
grep -c "^202[0-4]" data/EURUSD_1d.csv | xargs -I{} test {} -gt 100 || {
  echo "FAIL: EURUSD_1d.csv has insufficient data in the 2020-2025 range"
  exit 1
}
```

---

## Test Data

```json
{
  "symbol": "EURUSD",
  "timeframe": "1d",
  "start_date": "2020-01-01",
  "end_date": "2025-01-01",
  "horizon": 10,
  "bullish_threshold": 0.007,
  "bearish_threshold": -0.007,
  "hourly_timeframe": "1h"
}
```

**Why this data:**
- 5-year daily range (2020-2025) provides ~1300 bars -- enough for statistically meaningful label distribution
- Horizon=10 and threshold=+/-0.007 are the optimal parameters found via prior analysis (produce balanced 3-class distribution)
- Hourly timeframe (1h) enables the return-by-context analysis section
- EURUSD is the most liquid FX pair with clear trending/ranging behavior across this period

---

## Execution Steps

### 1. Run the Full Context Analyze Command

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-predictive-features-M3

OUTPUT=$(uv run ktrdr context analyze EURUSD 1d \
  --start-date 2020-01-01 \
  --end-date 2025-01-01 \
  --horizon 10 \
  --bullish-threshold 0.007 \
  --bearish-threshold -0.007 \
  --hourly-timeframe 1h 2>&1)

EXIT_CODE=$?
echo "Exit code: $EXIT_CODE"
echo "---OUTPUT START---"
echo "$OUTPUT"
echo "---OUTPUT END---"
```

**Expected:**
- Exit code is 0
- Output contains multiple sections of text (not empty or error-only)

### 2. Verify Exit Code

**Command:**
```bash
echo "EXIT_CODE=$EXIT_CODE"
test "$EXIT_CODE" -eq 0 || { echo "FAIL: Non-zero exit code"; exit 1; }
```

**Expected:**
- `EXIT_CODE=0`

### 3. Verify Distribution Section

**Command:**
```bash
echo "$OUTPUT" | grep -i "distribution" || { echo "FAIL: No Distribution section"; exit 1; }
echo "$OUTPUT" | grep -i "bullish" || { echo "FAIL: No Bullish class"; exit 1; }
echo "$OUTPUT" | grep -i "bearish" || { echo "FAIL: No Bearish class"; exit 1; }
echo "$OUTPUT" | grep -i "neutral" || { echo "FAIL: No Neutral class"; exit 1; }
```

**Expected:**
- Output contains "Distribution" heading
- All three class names appear: Bullish, Bearish, Neutral

### 4. Verify Persistence Section

**Command:**
```bash
echo "$OUTPUT" | grep -i "persistence" || { echo "FAIL: No Persistence section"; exit 1; }

# Persistence values should be numeric and present for each class
# Look for duration-like numbers (e.g., "8.3", "7.9", "4.1")
echo "$OUTPUT" | grep -i "persistence" -A 10 | grep -E "[0-9]+\.[0-9]" || {
  echo "FAIL: No numeric duration values found in Persistence section"
  exit 1
}
```

**Expected:**
- Output contains "Persistence" heading
- Duration values are present as decimal numbers

### 5. Verify Return by Context Section

**Command:**
```bash
echo "$OUTPUT" | grep -i "return.*context\|return by" || {
  echo "FAIL: No Return by Context section"
  exit 1
}

# Hourly return values should include percentage-like numbers
echo "$OUTPUT" | grep -i "return.*context\|return by" -A 10 | grep -E "[+-]?[0-9]+\.[0-9]+%" || {
  echo "FAIL: No percentage return values found"
  exit 1
}
```

**Expected:**
- Output contains "Return by Context" heading (since --hourly-timeframe was provided)
- Return values are formatted as percentages

### 6. Verify Quality Gate Summary

**Command:**
```bash
echo "$OUTPUT" | grep -i "quality gate" || { echo "FAIL: No Quality Gate Summary"; exit 1; }

# Check that PASS/FAIL indicators appear
echo "$OUTPUT" | grep -iE "PASS|FAIL" | head -5
GATE_LINES=$(echo "$OUTPUT" | grep -icE "PASS|FAIL")
echo "Found $GATE_LINES PASS/FAIL lines"
test "$GATE_LINES" -ge 3 || {
  echo "FAIL: Expected at least 3 quality gate lines (distribution, persistence, return diff)"
  exit 1
}
```

**Expected:**
- Output contains "Quality Gate Summary" heading
- At least 3 PASS/FAIL indicators (distribution balance, persistence, return differentiation)

### 7. Verify Data Loading Messages

**Command:**
```bash
# Confirm data was actually loaded (not short-circuited)
echo "$OUTPUT" | grep -E "Loaded [0-9]+ bars" || {
  echo "FAIL: No 'Loaded N bars' message found"
  exit 1
}

# Confirm hourly data was also loaded
echo "$OUTPUT" | grep -E "Loaded [0-9]+ hourly bars" || {
  echo "FAIL: No hourly data loading message"
  exit 1
}

# Confirm labels were generated
echo "$OUTPUT" | grep -E "Generated [0-9]+ context labels" || {
  echo "FAIL: No 'Generated N context labels' message"
  exit 1
}
```

**Expected:**
- "Loaded N bars" message for daily data (N should be ~1300 for 5 years of daily data)
- "Loaded N hourly bars" message for hourly data
- "Generated N context labels" message

---

## Success Criteria

- [ ] Command exits with code 0
- [ ] Output contains "Distribution" section with Bullish, Bearish, and Neutral classes
- [ ] Output contains "Persistence" section with numeric duration values
- [ ] Output contains "Return by Context" section with percentage values (hourly data was provided)
- [ ] Output contains "Quality Gate Summary" with at least 3 PASS/FAIL indicators
- [ ] Daily data loaded (>1000 bars for 2020-2025 range)
- [ ] Hourly data loaded (confirmed by "Loaded N hourly bars" message)
- [ ] Context labels generated (confirmed by "Generated N context labels" message)

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Daily bar count is realistic** -- For 2020-01-01 to 2025-01-01 daily data, expect ~1250-1310 bars. If "Loaded 0 bars" or "Loaded 5 bars", the cache read silently returned truncated data. Extract the number: `echo "$OUTPUT" | grep -oE "Loaded ([0-9]+) bars" | grep -oE "[0-9]+"` and verify it is > 1000.
- [ ] **Labels generated count is close to bar count minus horizon** -- If 1300 bars and horizon=10, expect ~1290 labels. If label count is 0 or much smaller, the labeler is broken. Extract: `echo "$OUTPUT" | grep -oE "Generated ([0-9]+) context labels" | grep -oE "[0-9]+"` and verify > 1000.
- [ ] **All three classes appear in Distribution** -- If only 1-2 classes appear, the threshold parameters are too extreme and the labeling is degenerate. The word "Bullish" AND "Bearish" AND "Neutral" must all appear in the output.
- [ ] **Hourly bar count is realistic** -- For 2020-2025 1h data, expect >30000 bars. If much smaller, the hourly cache is truncated or corrupted. Extract: `echo "$OUTPUT" | grep -oE "Loaded ([0-9]+) hourly bars" | grep -oE "[0-9]+"` and verify > 20000.
- [ ] **No Python traceback in output** -- If a traceback appears, the command may have exited 0 due to Rich console catching the exception. Check: `echo "$OUTPUT" | grep -c "Traceback" | xargs test 0 -eq`.
- [ ] **Output is not just help text** -- If the command args were wrong, Typer prints help and exits 0. Verify "Distribution" appears (help text would not contain this word).

---

## Troubleshooting

**If command fails with "No cached data for EURUSD 1d":**
- **Cause:** CSV files not in the expected location or DataRepository cannot find them
- **Category:** ENVIRONMENT
- **Cure:** Verify `data/EURUSD_1d.csv` exists. If the repository looks elsewhere, check `DataRepository.load_from_cache()` for path resolution logic. May need to run `uv run ktrdr data load EURUSD --timeframe 1d` first.

**If command fails with ImportError (torch):**
- **Cause:** `ktrdr.training.__init__.py` imports torch transitively and the lazy import guard is not working
- **Category:** CODE_BUG
- **Cure:** The CLI command uses lazy imports inside the function body. If torch is not installed, the import chain `ktrdr.training.context_labeler` must not trigger `ktrdr.training.__init__`. Check that `context.py` imports `ContextLabeler` directly, not `from ktrdr.training import context_labeler`.

**If only 1-2 classes appear (degenerate labels):**
- **Cause:** Threshold parameters too extreme for the data range, or labeler bug
- **Category:** CODE_BUG or TEST_ISSUE
- **Cure:** With horizon=10 and threshold=0.007, the EURUSD 2020-2025 data should produce a balanced 3-class split. If not, try adjusting thresholds. Check `ContextLabeler.label()` logic.

**If "Return by Context" section is missing:**
- **Cause:** Hourly data failed to load (cache miss) or `--hourly-timeframe` not recognized
- **Category:** ENVIRONMENT or CODE_BUG
- **Cure:** Check that `data/EURUSD_1h.csv` exists and covers the date range. The command prints a warning if hourly data is missing -- look for "Warning: No cached hourly data".

**If quality gates all show FAIL:**
- **Cause:** Labeling parameters produce poor-quality labels for this data range
- **Category:** TEST_ISSUE (not necessarily a bug -- the gate is working correctly)
- **Cure:** This test does not require all gates to PASS. It verifies the gate mechanism exists and produces results. However, with the recommended parameters (horizon=10, threshold=0.007), at least distribution and persistence gates should PASS for EURUSD.

**If command hangs or takes >60 seconds:**
- **Cause:** Loading large hourly CSV is slow, or pandas processing is unexpectedly expensive
- **Category:** PERFORMANCE
- **Cure:** The 1h CSV for 2005-2025 may be very large. The date range filter (2020-2025) should reduce the dataset. If still slow, check `DataRepository.load_from_cache()` for whether it loads the full file then filters, or reads only the needed range.

---

## Evidence to Capture

- Exit code: `$EXIT_CODE`
- Full command output: `$OUTPUT`
- Daily bar count: extracted from "Loaded N bars" line
- Hourly bar count: extracted from "Loaded N hourly bars" line
- Label count: extracted from "Generated N context labels" line
- Quality gate results: all PASS/FAIL lines from Quality Gate Summary section

---

## Notes

- **No Docker required** -- This is a pure local CLI test that reads cached CSV files. No sandbox, no API server, no containers.
- **No network required** -- All data comes from local cache files in `data/`.
- **Rich output** -- The command uses Rich tables and colored text. When capturing output, ANSI codes may be present. The test assertions use case-insensitive grep which handles this. If running in a terminal that strips colors, the assertions still work.
- **Torch not needed at runtime** -- The `context_labeler.py` module only uses pandas. The lazy import pattern in `context.py` avoids triggering `ktrdr.training.__init__.py` which would pull in torch. If torch IS installed, the command works fine either way.
- **Parameters are pre-validated** -- The horizon=10, threshold=0.007 parameters were determined through prior analysis to produce a balanced 3-class distribution for EURUSD daily data. These are not arbitrary.
- **Dependency:** None. This test is self-contained and can run independently of any other E2E test.
