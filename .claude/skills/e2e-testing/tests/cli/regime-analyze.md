# Test: cli/regime-analyze

**Purpose:** Validate the `ktrdr regime analyze` CLI command produces correct regime analysis output from cached OHLCV data using the multi-scale zigzag labeler
**Duration:** <30s
**Category:** CLI / Local Analysis

---

## Pre-Flight Checks

**Required modules:**
- None (local command, no Docker or API server needed)

**Test-specific checks:**
- [ ] Data file exists: `data/EURUSD_1h.csv` (or via `KTRDR_DATA_DIR` shared mount)
- [ ] Command is registered: `uv run ktrdr regime --help` shows `analyze` subcommand

---

## Test Data

```yaml
symbol: EURUSD
timeframe: 1h
data_file: data/EURUSD_1h.csv
start_date: "2019-01-01"
end_date: "2024-01-01"
macro_atr_mult: 3.0
micro_atr_mult: 1.0
atr_period: 14
progression_tolerance: 0.5
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

### 3. Run regime analyze with default parameters

**Command:**
```bash
uv run ktrdr regime analyze EURUSD 1h \
  --start-date 2019-01-01 \
  --end-date 2024-01-01 \
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
- Contains `Macro ATR mult` with value `3.0`
- Contains `Micro ATR mult` with value `1.0`
- Contains `ATR period` with value `14`
- Contains `Progression tolerance` with value `0.5`

### 5. Verify Distribution section

**Check the captured output from Step 3:**

**Expected:**
- Contains `Distribution` header
- Contains column headers: `Regime`, `Fraction`, `Bars`
- Contains regime names: `trending_up`, `trending_down`, `ranging`, `volatile`
- Each regime row has a percentage (e.g., `XX.X%`) and bar count
- No single class exceeds 60%

### 6. Verify Duration/Persistence section

**Check the captured output from Step 3:**

**Expected:**
- Contains `Mean Duration (Persistence)` header
- Contains column headers: `Regime`, `Mean Duration (bars)`
- Each regime has a numeric duration value > 1.0

### 7. Verify Return section

**Check the captured output from Step 3:**

**Expected:**
- Contains `Mean Forward Return by Regime` header
- Contains column headers: `Regime`, `Mean Return`
- Each regime has a signed percentage return value (e.g., `+0.0123%` or `-0.0045%`)
- trending_up return should be positive, trending_down return should be negative

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
uv run ktrdr regime analyze EURUSD 1h \
  --start-date 2019-01-01 \
  --end-date 2024-01-01 \
  --macro-atr-mult 5.0 \
  --micro-atr-mult 2.0 \
  --progression-tolerance 0.8 \
  2>&1
echo "EXIT_CODE=$?"
```

**Expected:**
- Exit 0
- Distribution percentages differ from Step 3 output (higher ATR mults → more RANGING)
- Parameters section shows `Macro ATR mult` as `5.0` and `Micro ATR mult` as `2.0`

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
- [ ] Output contains `Parameters` section with multi-scale zigzag parameter values
- [ ] Output contains `Distribution` section with 4 regime classes, no class >60%
- [ ] Output contains `Mean Duration (Persistence)` section with bar durations > 1.0
- [ ] Output contains `Mean Forward Return by Regime` section with signed returns
- [ ] Output contains `Transition Matrix` section
- [ ] Output contains `Summary` line with bar count > 1000 and transition count
- [ ] Different parameters (macro-atr-mult, progression-tolerance) produce different distribution values
- [ ] Invalid symbol produces exit code 1 with error message

---

## Sanity Checks

**CRITICAL:** These catch false positives

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Bar count > 1000 | <= 1000 fails | Date range too short or data not loaded |
| 4 regime types in Distribution | < 4 fails | Labeler degenerate (missing class) |
| No class > 60% | Any > 60% fails | Label collapse (same issue as v1 SER) |
| Distribution fractions sum to ~100% | < 95% or > 105% fails | Labeling math error |
| Mean durations > 1.0 bars | Any <= 1.0 fails | Spurious regime switching |
| Transition count > 0 | 0 fails | No regime transitions detected |
| trending_up return positive | Negative fails | Labels don't align with price direction |
| macro_atr_mult=3.0 vs 5.0 produce different distributions | Identical fails | Parameter not wired through |

---

## Troubleshooting

**If data file not found:**
- **Cause:** EURUSD 1h data not cached locally
- **Cure:** Run `uv run ktrdr data load EURUSD 1h --start-date 2019-01-01 --end-date 2024-01-01` first
- **Note:** In sandbox environments, data may be at `KTRDR_DATA_DIR` (shared mount path)

**If import error mentioning torch/pytorch:**
- **Cause:** multi_scale_regime_labeler or regime_labeler pulling torch transitively
- **Cure:** Verify CLI uses direct `from ktrdr.training.multi_scale_regime_labeler import ...` (not via `__init__.py`)

**If all bars classified as one regime:**
- **Cause:** ATR multiplier parameters too extreme for the data
- **Cure:** Use default params (macro_atr_mult=3.0, micro_atr_mult=1.0) for balanced classification

**If exit 0 but empty output:**
- **Cause:** Rich console not printing to captured stdout
- **Cure:** Check stderr as well (`2>&1` should capture both)

---

## Evidence to Capture

- Full command output from Step 3 (default parameters run)
- Full command output from Step 10 (different parameters run)
- Error output from Step 11 (invalid symbol)
- Data file line count (row count sanity check)
