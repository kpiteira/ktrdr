# Test: cli/regime-analyze

**Purpose:** Validate the `ktrdr regime analyze` CLI command produces correct regime analysis output from cached OHLCV data
**Duration:** <30s
**Category:** CLI / Local Analysis

---

## Pre-Flight Checks

**Required modules:**
- None (local command, no Docker or API server needed)

**Test-specific checks:**
- [ ] Data file exists: `data/EURUSD_1h.csv`
- [ ] Command is registered: `uv run ktrdr regime --help` shows `analyze` subcommand

---

## Test Data

```yaml
symbol: EURUSD
timeframe: 1h
data_file: data/EURUSD_1h.csv
start_date: "2019-01-01"
end_date: "2024-01-01"
horizon: 48
trending_threshold: 0.2
```

---

## Execution Steps

### 1. Pre-flight: Verify data file exists

**Command:**
```bash
ls -la data/EURUSD_1h.csv
wc -l data/EURUSD_1h.csv
```

**Expected:**
- File exists
- File has a substantial number of rows (thousands of bars expected for multi-year 1h data)

### 2. Pre-flight: Verify command registration

**Command:**
```bash
uv run ktrdr regime --help 2>&1
```

**Expected:**
- Exit 0
- Output contains `analyze`

### 3. Run regime analyze with tuned parameters

**Command:**
```bash
uv run ktrdr regime analyze EURUSD 1h \
  --start-date 2019-01-01 \
  --end-date 2024-01-01 \
  --horizon 48 \
  --trending-threshold 0.2 \
  2>&1
echo "EXIT_CODE=$?"
```

**Expected:**
- Exit 0
- Output contains `Analyzing regime labels for EURUSD 1h`
- Output contains bar count in parentheses (e.g., `(NNNNN bars)`)

**Capture:** Full output for subsequent verification steps

### 4. Verify Parameters section

**Check the captured output from Step 3:**

**Expected:**
- Contains `Parameters` header
- Contains `Horizon` with value `48 bars`
- Contains `Trending threshold` with value `0.2`

### 5. Verify Distribution section

**Check the captured output from Step 3:**

**Expected:**
- Contains `Distribution` header
- Contains column headers: `Regime`, `Fraction`, `Bars`
- Contains regime names: `trending_up`, `trending_down`, `ranging`
- Each regime row has a percentage (e.g., `XX.X%`) and bar count

### 6. Verify Duration/Persistence section

**Check the captured output from Step 3:**

**Expected:**
- Contains `Mean Duration (Persistence)` header
- Contains column headers: `Regime`, `Mean Duration (bars)`
- Each regime has a numeric duration value

### 7. Verify Return section

**Check the captured output from Step 3:**

**Expected:**
- Contains `Mean Forward Return by Regime` header
- Contains column headers: `Regime`, `Mean Return`
- Each regime has a signed percentage return value (e.g., `+0.0123%` or `-0.0045%`)

### 8. Verify Transition Matrix section

**Check the captured output from Step 3:**

**Expected:**
- Contains `Transition Matrix` header
- Contains `From \ To` header cell
- Matrix values are decimal probabilities (0.00 to 1.00)

### 9. Verify Summary line

**Check the captured output from Step 3:**

**Expected:**
- Contains `Summary:` followed by `labeled bars` and `transitions`
- Bar count is a positive integer > 1000 (multi-year hourly data)
- Transition count is a positive integer

### 10. Verify different parameters produce different output

**Command:**
```bash
# Run with default parameters (different from step 3)
uv run ktrdr regime analyze EURUSD 1h \
  --start-date 2019-01-01 \
  --end-date 2024-01-01 \
  --horizon 24 \
  --trending-threshold 0.5 \
  2>&1
echo "EXIT_CODE=$?"
```

**Expected:**
- Exit 0
- Distribution percentages differ from Step 3 output (different trending_threshold changes classification)
- Parameters section shows `Horizon` as `24 bars` and `Trending threshold` as `0.5`

### 11. Verify error on missing data

**Command:**
```bash
uv run ktrdr regime analyze NOSYMBOL 1h 2>&1
echo "EXIT_CODE=$?"
```

**Expected:**
- Exit code 1
- Output contains `Error loading data`

---

## Success Criteria

- [ ] Data file `data/EURUSD_1h.csv` exists with substantial row count
- [ ] `ktrdr regime analyze` exits 0 with valid symbol/timeframe
- [ ] Output contains `Parameters` section with correct parameter values
- [ ] Output contains `Distribution` section with regime names and percentages
- [ ] Output contains `Mean Duration (Persistence)` section with bar durations
- [ ] Output contains `Mean Forward Return by Regime` section with signed returns
- [ ] Output contains `Transition Matrix` section
- [ ] Output contains `Summary` line with bar count > 1000 and transition count
- [ ] Different parameters (horizon, trending-threshold) produce different distribution values
- [ ] Invalid symbol produces exit code 1 with error message

---

## Sanity Checks

**CRITICAL:** These catch false positives

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Bar count > 1000 | <= 1000 fails | Date range too short or data not loaded |
| At least 3 regime types in Distribution | < 3 fails | Labeler degenerate (all same regime) |
| Distribution fractions sum to ~100% | < 95% or > 105% fails | Labeling math error |
| Mean durations > 1.0 bars | Any <= 1.0 fails | Spurious regime switching |
| Transition count > 0 | 0 fails | No regime transitions detected |
| trending_threshold=0.2 vs 0.5 produce different distributions | Identical fails | Parameter not wired through |

---

## Troubleshooting

**If data file not found:**
- **Cause:** EURUSD 1h data not cached locally
- **Cure:** Run `uv run ktrdr data load EURUSD 1h --start-date 2019-01-01 --end-date 2024-01-01` first

**If import error mentioning torch/pytorch:**
- **Cause:** regime_labeler import bypassing the direct-import workaround
- **Cure:** Check that `ktrdr/cli/commands/regime.py` uses `importlib.util` to load regime_labeler directly

**If all bars classified as one regime:**
- **Cause:** Threshold parameters too extreme for the data
- **Cure:** Use `--trending-threshold 0.2` for more balanced classification

**If exit 0 but empty output:**
- **Cause:** Rich console not printing to captured stdout
- **Cure:** Check stderr as well (`2>&1` should capture both)

---

## Evidence to Capture

- Full command output from Step 3 (tuned parameters run)
- Full command output from Step 10 (default parameters run)
- Error output from Step 11 (invalid symbol)
- Data file line count (row count sanity check)
