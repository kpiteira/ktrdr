---
design: docs/agentic/v1.5/DESIGN.md
architecture: docs/agentic/v1.5/ARCHITECTURE.md
plan: docs/agentic/v1.5/PLAN.md
---

# Milestone 2: Create Experimental Strategies

**Goal:** Prepare 27 strategies with known-correct configurations, ensuring experimental validity.

**Why M2:** The experiment's validity depends entirely on having correctly configured strategies. If fuzzy sets are wrong, we're testing the wrong thing.

---

## Questions This Milestone Must Answer

| # | Question | How We'll Answer It | Success Criteria |
|---|----------|---------------------|------------------|
| Q2.1 | Do all strategies use only Tier 1 indicators? | Review each YAML | No ATR, MACD, or other Tier 2/3 indicators |
| Q2.2 | Are fuzzy sets exactly as specified? | Compare to reference table | Byte-for-byte match with DESIGN.md values |
| Q2.3 | Is the experimental design sound? | Review strategy matrix | Each indicator tested in isolation AND in combos |
| Q2.4 | Are training parameters consistent? | Check all YAMLs | Same epochs, lr, batch_size, date range across all |
| Q2.5 | Do all strategies pass basic validation? | Run validator API | No config errors |
| Q2.6 | Is zigzag labeling consistent? | Check all YAMLs | All use 2.5% except Z01-Z04 variations |

---

## Tier 1 Indicator Reference (from DESIGN.md)

**CRITICAL:** Use these EXACT values. Do not modify.

| Indicator | Range | Fuzzy Sets |
|-----------|-------|------------|
| **RSI** | [0, 100] | oversold [0,30,40], neutral [35,50,65], overbought [60,70,100] |
| **Stochastic** | [0, 100] | oversold [0,20,30], neutral [25,50,75], overbought [70,80,100] |
| **Williams %R** | [-100, 0] | oversold [-100,-80,-60], neutral [-65,-50,-35], overbought [-40,-20,0] |
| **MFI** | [0, 100] | oversold [0,30,40], neutral [35,50,65], overbought [60,70,100] |
| **ADX** | [0, 100] | weak [0,15,25], moderate [20,35,50], strong [45,60,100] |
| **+DI** | [0, 100] | weak [0,15,25], moderate [20,35,50], strong [45,60,100] |
| **-DI** | [0, 100] | weak [0,15,25], moderate [20,35,50], strong [45,60,100] |
| **Aroon Up** | [0, 100] | weak [0,25,40], moderate [35,50,65], strong [60,75,100] |
| **Aroon Down** | [0, 100] | weak [0,25,40], moderate [35,50,65], strong [60,75,100] |
| **CMF** | [-1, 1] | selling [-1,-0.3,-0.05], neutral [-0.1,0,0.1], buying [0.05,0.3,1] |
| **RVI** | [0, 100] | low [0,20,40], neutral [30,50,70], high [60,80,100] |

---

## Strategy Matrix (27 total)

### Single Indicator Strategies (9)

| ID | Name | Indicators | Purpose |
|----|------|------------|---------|
| S01 | v15_rsi_only | RSI | Baseline - most common bounded indicator |
| S02 | v15_stochastic_only | Stochastic | Momentum oscillator alternative |
| S03 | v15_williams_only | Williams %R | Negative range indicator test |
| S04 | v15_mfi_only | MFI | Volume-weighted momentum |
| S05 | v15_adx_only | ADX | Trend strength (no direction) |
| S06 | v15_aroon_only | Aroon Up + Aroon Down | Trend timing pair |
| S07 | v15_cmf_only | CMF | Money flow (bipolar range) |
| S08 | v15_rvi_only | RVI | Vigor/momentum alternative |
| S09 | v15_di_only | +DI + -DI | Directional movement pair |

### Two Indicator Combinations (11)

| ID | Name | Indicators | Rationale |
|----|------|------------|-----------|
| C01 | v15_rsi_adx | RSI + ADX | Momentum + Trend Strength |
| C02 | v15_rsi_stochastic | RSI + Stochastic | Dual momentum oscillators |
| C03 | v15_rsi_williams | RSI + Williams %R | Momentum confirmation |
| C04 | v15_rsi_mfi | RSI + MFI | Price momentum + Volume |
| C05 | v15_adx_aroon | ADX + Aroon | Trend strength + Trend timing |
| C06 | v15_adx_di | ADX + +DI + -DI | Full ADX system |
| C07 | v15_stochastic_williams | Stochastic + Williams %R | Oversold/overbought confirmation |
| C08 | v15_mfi_cmf | MFI + CMF | Dual volume indicators |
| C09 | v15_rsi_cmf | RSI + CMF | Momentum + Money flow |
| C10 | v15_adx_rsi | ADX + RSI | Filter momentum by trend |
| C11 | v15_aroon_rvi | Aroon + RVI | Trend + Vigor |

### Three Indicator Combinations (3)

| ID | Name | Indicators |
|----|------|------------|
| C12 | v15_rsi_adx_stochastic | RSI + ADX + Stochastic |
| C13 | v15_mfi_adx_aroon | MFI + ADX + Aroon |
| C14 | v15_williams_stochastic_cmf | Williams + Stochastic + CMF |

### Zigzag Threshold Variations (4)

| ID | Name | Base Indicator | Zigzag Threshold |
|----|------|----------------|------------------|
| Z01 | v15_rsi_zigzag_1.5 | RSI | 1.5% (more signals) |
| Z02 | v15_rsi_zigzag_2.0 | RSI | 2.0% |
| Z03 | v15_rsi_zigzag_3.0 | RSI | 3.0% |
| Z04 | v15_rsi_zigzag_3.5 | RSI | 3.5% (fewer signals) |

Note: Baseline strategies use 2.5% threshold. S01 (v15_rsi_only) serves as the 2.5% baseline for comparison.

---

## Task 2.1: Create Strategy Template

**File:** `strategies/v15_template.yaml` (reference only, not for training)
**Type:** CODING
**Estimated time:** 20 minutes

**Description:**
Create a base template with consistent training parameters. All v1.5 strategies will share these settings.

**Template Configuration:**

```yaml
# === v1.5 EXPERIMENTAL STRATEGY TEMPLATE ===
# DO NOT MODIFY training parameters - must be consistent across experiments

name: "v15_{indicator_name}"
description: "v1.5 experiment: {indicator description}"
version: "1.0"

# === FIXED TRAINING DATA CONFIG ===
training_data:
  symbols:
    mode: "single_symbol"
    list: ["EURUSD"]  # FIXED: Single forex pair
  timeframes:
    mode: "single_timeframe"
    list: ["1h"]      # FIXED: 1-hour timeframe
    base_timeframe: "1h"
  history_required: 200

# === INDICATORS (VARIES BY STRATEGY) ===
indicators:
  # [Strategy-specific indicators here]

# === FUZZY SETS (VARIES BY STRATEGY) ===
fuzzy_sets:
  # [Strategy-specific fuzzy sets here]

# === FIXED MODEL CONFIG ===
model:
  type: "mlp"
  architecture:
    hidden_layers: [64, 32]  # Standard complexity
    activation: "relu"
    output_activation: "softmax"
    dropout: 0.2
  features:
    include_price_context: false  # Pure fuzzy features only
    lookback_periods: 2
    scale_features: true
  training:
    learning_rate: 0.001
    batch_size: 32
    epochs: 100           # FIXED: Allow full convergence
    optimizer: "adam"
    early_stopping:
      enabled: true
      patience: 15        # Stop if no improvement for 15 epochs
      min_delta: 0.001
    analytics:
      enabled: true       # CRITICAL: Must be enabled
      export_csv: true
      export_json: true
      export_alerts: true

# === FIXED TRAINING CONFIG ===
training:
  method: "supervised"
  labels:
    source: "zigzag"
    zigzag_threshold: 0.025  # FIXED: 2.5% (except Z01-Z04)
    label_lookahead: 20
  data_split:
    train: 0.7
    validation: 0.15
    test: 0.15
  date_range:
    start: "2015-01-01"   # FIXED: 8 years of data
    end: "2023-12-31"
```

**Fixed Parameters (DO NOT VARY):**
- Symbol: EURUSD
- Timeframe: 1h
- Epochs: 100 (with early stopping)
- Learning rate: 0.001
- Batch size: 32
- Train/val/test: 70/15/15
- Date range: 2015-01-01 to 2023-12-31
- Zigzag threshold: 2.5% (except Z01-Z04)

**Variable Parameters:**
- Strategy name
- Indicators (per strategy matrix)
- Fuzzy sets (per indicator reference)
- Zigzag threshold (Z01-Z04 only)

**Acceptance Criteria:**
- [ ] Template file created
- [ ] All fixed parameters documented
- [ ] Clear placeholders for variable sections

---

## Task 2.2: Generate All 27 Strategy Files

**Files:** `strategies/v15_*.yaml` (27 files)
**Type:** CODING
**Estimated time:** 1-2 hours

**Description:**
Generate all strategy files from the template, following the strategy matrix exactly.

**Generation Process:**

1. For each strategy in the matrix:
   - Copy template
   - Set strategy name and description
   - Add indicators with correct feature_id naming
   - Add fuzzy sets from reference table (EXACT values)
   - Set zigzag threshold (2.5% for all except Z01-Z04)

**Indicator Configuration Patterns:**

```yaml
# RSI
- name: "rsi"
  feature_id: rsi_14
  period: 14
  source: "close"

# Stochastic
- name: "stochastic"
  feature_id: stochastic_14
  k_period: 14
  d_period: 3
  source: "close"

# Williams %R
- name: "williams_r"
  feature_id: williams_14
  period: 14
  source: "close"

# MFI
- name: "mfi"
  feature_id: mfi_14
  period: 14

# ADX
- name: "adx"
  feature_id: adx_14
  period: 14

# +DI / -DI (comes with ADX indicator)
# Note: ADX indicator produces adx_14, plus_di_14, minus_di_14

# Aroon (produces both up and down)
- name: "aroon"
  feature_id: aroon_25
  period: 25

# CMF
- name: "cmf"
  feature_id: cmf_20
  period: 20

# RVI
- name: "rvi"
  feature_id: rvi_10
  period: 10
```

**Fuzzy Set Configuration Patterns:**

```yaml
# RSI (0-100)
rsi_14:
  oversold:
    type: "triangular"
    parameters: [0, 30, 40]
  neutral:
    type: "triangular"
    parameters: [35, 50, 65]
  overbought:
    type: "triangular"
    parameters: [60, 70, 100]

# Stochastic (0-100)
stochastic_14:
  oversold:
    type: "triangular"
    parameters: [0, 20, 30]
  neutral:
    type: "triangular"
    parameters: [25, 50, 75]
  overbought:
    type: "triangular"
    parameters: [70, 80, 100]

# Williams %R (-100 to 0)
williams_14:
  oversold:
    type: "triangular"
    parameters: [-100, -80, -60]
  neutral:
    type: "triangular"
    parameters: [-65, -50, -35]
  overbought:
    type: "triangular"
    parameters: [-40, -20, 0]

# MFI (same as RSI)
mfi_14:
  oversold:
    type: "triangular"
    parameters: [0, 30, 40]
  neutral:
    type: "triangular"
    parameters: [35, 50, 65]
  overbought:
    type: "triangular"
    parameters: [60, 70, 100]

# ADX (0-100, trend strength)
adx_14:
  weak:
    type: "triangular"
    parameters: [0, 15, 25]
  moderate:
    type: "triangular"
    parameters: [20, 35, 50]
  strong:
    type: "triangular"
    parameters: [45, 60, 100]

# +DI / -DI (same as ADX)
plus_di_14:
  weak:
    type: "triangular"
    parameters: [0, 15, 25]
  moderate:
    type: "triangular"
    parameters: [20, 35, 50]
  strong:
    type: "triangular"
    parameters: [45, 60, 100]

minus_di_14:
  weak:
    type: "triangular"
    parameters: [0, 15, 25]
  moderate:
    type: "triangular"
    parameters: [20, 35, 50]
  strong:
    type: "triangular"
    parameters: [45, 60, 100]

# Aroon Up/Down (0-100)
aroon_up_25:
  weak:
    type: "triangular"
    parameters: [0, 25, 40]
  moderate:
    type: "triangular"
    parameters: [35, 50, 65]
  strong:
    type: "triangular"
    parameters: [60, 75, 100]

aroon_down_25:
  weak:
    type: "triangular"
    parameters: [0, 25, 40]
  moderate:
    type: "triangular"
    parameters: [35, 50, 65]
  strong:
    type: "triangular"
    parameters: [60, 75, 100]

# CMF (-1 to 1)
cmf_20:
  selling:
    type: "triangular"
    parameters: [-1, -0.3, -0.05]
  neutral:
    type: "triangular"
    parameters: [-0.1, 0, 0.1]
  buying:
    type: "triangular"
    parameters: [0.05, 0.3, 1]

# RVI (0-100)
rvi_10:
  low:
    type: "triangular"
    parameters: [0, 20, 40]
  neutral:
    type: "triangular"
    parameters: [30, 50, 70]
  high:
    type: "triangular"
    parameters: [60, 80, 100]
```

**File Checklist:**

Single Indicator (9):
- [ ] `v15_rsi_only.yaml`
- [ ] `v15_stochastic_only.yaml`
- [ ] `v15_williams_only.yaml`
- [ ] `v15_mfi_only.yaml`
- [ ] `v15_adx_only.yaml`
- [ ] `v15_aroon_only.yaml`
- [ ] `v15_cmf_only.yaml`
- [ ] `v15_rvi_only.yaml`
- [ ] `v15_di_only.yaml`

Two Indicator (11):
- [ ] `v15_rsi_adx.yaml`
- [ ] `v15_rsi_stochastic.yaml`
- [ ] `v15_rsi_williams.yaml`
- [ ] `v15_rsi_mfi.yaml`
- [ ] `v15_adx_aroon.yaml`
- [ ] `v15_adx_di.yaml`
- [ ] `v15_stochastic_williams.yaml`
- [ ] `v15_mfi_cmf.yaml`
- [ ] `v15_rsi_cmf.yaml`
- [ ] `v15_adx_rsi.yaml`
- [ ] `v15_aroon_rvi.yaml`

Three Indicator (3):
- [ ] `v15_rsi_adx_stochastic.yaml`
- [ ] `v15_mfi_adx_aroon.yaml`
- [ ] `v15_williams_stochastic_cmf.yaml`

Zigzag Variations (4):
- [ ] `v15_rsi_zigzag_1.5.yaml` (threshold: 0.015)
- [ ] `v15_rsi_zigzag_2.0.yaml` (threshold: 0.020)
- [ ] `v15_rsi_zigzag_3.0.yaml` (threshold: 0.030)
- [ ] `v15_rsi_zigzag_3.5.yaml` (threshold: 0.035)

**Acceptance Criteria:**
- [ ] All 27 files created
- [ ] All use only Tier 1 indicators
- [ ] All fuzzy sets match reference EXACTLY
- [ ] All fixed parameters are identical
- [ ] Zigzag thresholds correct for Z01-Z04

---

## Task 2.3: Validate All Strategies

**Type:** VERIFICATION
**Estimated time:** 30 minutes

**Description:**
Run the validation API on all 27 strategies to catch configuration errors before training.

**Validation Script:**

```bash
#!/bin/bash
# validate_v15_strategies.sh

STRATEGIES=$(ls strategies/v15_*.yaml | xargs -n1 basename | sed 's/.yaml//')

echo "Validating $(echo $STRATEGIES | wc -w) strategies..."
echo ""

FAILED=0
PASSED=0

for strategy in $STRATEGIES; do
  RESULT=$(curl -s -X POST "http://localhost:8000/api/v1/strategies/validate/$strategy")
  VALID=$(echo $RESULT | jq -r '.valid')

  if [ "$VALID" = "true" ]; then
    echo "✓ $strategy"
    PASSED=$((PASSED + 1))
  else
    echo "✗ $strategy"
    echo "  Issues: $(echo $RESULT | jq -r '.issues[] | .message')"
    FAILED=$((FAILED + 1))
  fi
done

echo ""
echo "Summary: $PASSED passed, $FAILED failed"

if [ $FAILED -gt 0 ]; then
  echo "FIX FAILURES BEFORE PROCEEDING"
  exit 1
fi
```

**Common Validation Errors:**

| Error | Cause | Fix |
|-------|-------|-----|
| Unknown indicator | Typo in indicator name | Check exact name in indicator factory |
| Invalid fuzzy set reference | feature_id mismatch | Ensure fuzzy_sets keys match indicator feature_id |
| Missing required field | Incomplete config | Check all required sections exist |

**Acceptance Criteria:**
- [ ] All 27 strategies pass validation
- [ ] No errors reported
- [ ] Warnings reviewed (warnings are acceptable if understood)

---

## Task 2.4: Experimental Design Review

**Type:** VERIFICATION
**Estimated time:** 20 minutes

**Description:**
Review the strategy set to confirm it provides valid experimental data.

**Review Checklist:**

### 1. Indicator Coverage
- [ ] Each Tier 1 indicator tested in isolation (S01-S09)
- [ ] Each indicator appears in at least one combination
- [ ] No Tier 2 or Tier 3 indicators used

### 2. Fuzzy Set Correctness
Spot-check 3 strategies against reference table:

```bash
# Check RSI fuzzy sets in v15_rsi_only.yaml
grep -A4 "oversold:" strategies/v15_rsi_only.yaml
# Expected: parameters: [0, 30, 40]

# Check Williams %R (negative range) in v15_williams_only.yaml
grep -A4 "oversold:" strategies/v15_williams_only.yaml
# Expected: parameters: [-100, -80, -60]

# Check CMF (bipolar range) in v15_cmf_only.yaml
grep -A4 "selling:" strategies/v15_cmf_only.yaml
# Expected: parameters: [-1, -0.3, -0.05]
```

### 3. Training Parameter Consistency

```bash
# All should have same epochs
grep "epochs:" strategies/v15_*.yaml | sort | uniq -c
# Expected: 27 "epochs: 100"

# All should have same learning_rate
grep "learning_rate:" strategies/v15_*.yaml | sort | uniq -c
# Expected: 27 "learning_rate: 0.001"

# All should have same date range
grep "start:" strategies/v15_*.yaml | sort | uniq -c
# Expected: 27 "start: \"2015-01-01\""
```

### 4. Zigzag Threshold Verification

```bash
# Check threshold values
grep "zigzag_threshold:" strategies/v15_rsi_zigzag_*.yaml
# Expected: 0.015, 0.020, 0.030, 0.035

grep "zigzag_threshold:" strategies/v15_rsi_only.yaml
# Expected: 0.025 (baseline)
```

### 5. Comparison Design

Can we make valid comparisons?

| Comparison | Strategies | Valid? |
|------------|------------|--------|
| RSI alone vs RSI+ADX | S01 vs C01 | ✓ Only difference is ADX added |
| Effect of zigzag threshold | S01 vs Z01-Z04 | ✓ Only difference is threshold |
| Single vs multi indicator | S01 vs C02 | ✓ Same RSI, different additional |

**Acceptance Criteria:**
- [ ] All indicators tested in isolation
- [ ] Fuzzy sets verified against reference
- [ ] Training parameters consistent across all
- [ ] Zigzag variations correct
- [ ] Comparison groups are valid

---

## Milestone 2 Verification

### E2E Test Scenario

**Purpose:** Verify all 27 strategies are correctly configured and valid
**Duration:** ~10 minutes
**Prerequisites:** Backend running

**Test Steps:**

```bash
# 1. Count strategy files
ls strategies/v15_*.yaml | wc -l
# Expected: 27 (plus v15_template.yaml = 28)

# 2. Validate all strategies
for f in strategies/v15_*.yaml; do
  name=$(basename $f .yaml)
  if [ "$name" = "v15_template" ]; then continue; fi
  valid=$(curl -s -X POST "http://localhost:8000/api/v1/strategies/validate/$name" | jq -r '.valid')
  echo "$name: $valid"
done

# 3. Check no Tier 2/3 indicators
grep -l "macd\|atr\|cci\|obv\|vwap" strategies/v15_*.yaml
# Expected: no output (no matches)

# 4. Check fuzzy sets are from reference
# (Manual spot check of 3 files)

# 5. Check training params are consistent
grep "epochs: 100" strategies/v15_*.yaml | wc -l
# Expected: 27
```

**Success Criteria:**
- [ ] Exactly 27 strategy files (excluding template)
- [ ] All 27 pass validation
- [ ] No Tier 2/3 indicators found
- [ ] Fuzzy sets match reference
- [ ] Training parameters consistent

### Completion Checklist

- [ ] Task 2.1: Template created
- [ ] Task 2.2: All 27 strategy files generated
- [ ] Task 2.3: All strategies pass validation
- [ ] Task 2.4: Experimental design reviewed
- [ ] All M2 questions answered:
  - [ ] Q2.1: Only Tier 1 indicators used
  - [ ] Q2.2: Fuzzy sets match reference exactly
  - [ ] Q2.3: Experimental design is sound
  - [ ] Q2.4: Training parameters consistent
  - [ ] Q2.5: All strategies pass validation
  - [ ] Q2.6: Zigzag labeling consistent

### Validation Checkpoint

After M2, we must be able to answer **YES** to:
- [ ] "If a strategy fails, is it the NN's fault and not a config error?"
- [ ] "Are we testing what we think we're testing?"
- [ ] "Can we compare results across strategies fairly?"

If any answer is NO, fix before proceeding to M3.

---

*Estimated time: 2-3 hours*
