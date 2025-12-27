# v1.5 Implementation Plan: Prove the NN Can Learn

**Goal:** Determine if the neuro-fuzzy architecture can learn anything at all when mechanical errors (wrong fuzzy ranges) are eliminated.

**Approach:** Run controlled experiments with bounded indicators + correct fuzzy ranges, analyze results, conclude.

**Success Criteria:** >30% of strategies achieve >55% validation accuracy → NN works

---

## Milestone 1: Validate Analytics Works

**Goal:** Confirm TrainingAnalyzer produces correct, readable output before we depend on it.

**Why:** The analytics code exists but has never been tested or run. We need to verify it works before using it to draw conclusions.

### Tasks

#### 1.1 Create Test Strategy with Analytics Enabled

- Copy `neuro_mean_reversion.yaml` as base
- Replace indicators with RSI only (Tier 1, known good)
- Add correct fuzzy sets from reference
- Add `model.training.analytics.enabled: true`
- Save as `strategies/v15_test_analytics.yaml`

#### 1.2 Run Short Training

- Use API: `POST /training/start`
- Short run: 10 epochs, single symbol (EURUSD), 1h timeframe
- Small date range for speed

#### 1.3 Check Output Files Exist

- Look for `training_analytics/runs/{run_id}/`
- Expected files:
  - `metrics.csv`
  - `detailed_metrics.json`
  - `alerts.txt`
  - `config.yaml`

#### 1.4 Diagnose Issues (if any)

If files missing or malformed:

- Check training logs for errors
- Check if analytics code path was executed
- Identify specific failure point in TrainingAnalyzer
- Document what's broken

#### 1.5 Fix Issues (if any)

- Fix TrainingAnalyzer bugs
- Add missing error handling
- Add unit tests for the fixed code
- Re-run training to verify fix

#### 1.6 Verify Metrics Are Readable and Sensible

- Claude reads `metrics.csv`
- Verify columns match expected schema
- Verify values make sense (accuracy 0-1, loss > 0, etc.)
- Verify `learning_signal_strength` is populated

### Acceptance Criteria

- [ ] Training completes without error
- [ ] All 4 output files exist and are non-empty
- [ ] Claude can read and interpret metrics.csv
- [ ] Claude can report: "Training reached X% accuracy, learning signal was Y"
- [ ] Any bugs found are fixed with tests

---

## Milestone 2: Create Bounded-Indicator Strategies

**Goal:** Prepare 20+ strategies using only Tier 1 indicators with correct fuzzy ranges.

### Tier 1 Indicators (from DESIGN.md)

| Indicator | Range | Fuzzy Sets |
|-----------|-------|------------|
| RSI | [0, 100] | oversold [0,30,40], neutral [35,50,65], overbought [60,70,100] |
| Stochastic | [0, 100] | oversold [0,20,30], neutral [25,50,75], overbought [70,80,100] |
| Williams %R | [-100, 0] | oversold [-100,-80,-60], neutral [-65,-50,-35], overbought [-40,-20,0] |
| MFI | [0, 100] | Same as RSI |
| ADX | [0, 100] | weak [0,15,25], moderate [20,35,50], strong [45,60,100] |
| +DI | [0, 100] | weak [0,15,25], moderate [20,35,50], strong [45,60,100] |
| -DI | [0, 100] | weak [0,15,25], moderate [20,35,50], strong [45,60,100] |
| Aroon Up | [0, 100] | weak [0,25,40], moderate [35,50,65], strong [60,75,100] |
| Aroon Down | [0, 100] | weak [0,25,40], moderate [35,50,65], strong [60,75,100] |
| CMF | [-1, 1] | selling [-1,-0.3,-0.05], neutral [-0.1,0,0.1], buying [0.05,0.3,1] |
| RVI | [0, 100] | low [0,20,40], neutral [30,50,70], high [60,80,100] |

### Strategy Matrix

#### Single Indicator (9 strategies)
| ID | Name | Indicators |
|----|------|------------|
| S01 | v15_rsi_only | RSI |
| S02 | v15_stochastic_only | Stochastic |
| S03 | v15_williams_only | Williams %R |
| S04 | v15_mfi_only | MFI |
| S05 | v15_adx_only | ADX |
| S06 | v15_aroon_only | Aroon Up + Aroon Down |
| S07 | v15_cmf_only | CMF |
| S08 | v15_rvi_only | RVI |
| S09 | v15_di_only | +DI + -DI |

#### Two Indicator Combos (11+ strategies)
| ID | Name | Indicators | Rationale |
|----|------|------------|-----------|
| C01 | v15_rsi_adx | RSI + ADX | Momentum + Trend Strength |
| C02 | v15_rsi_stochastic | RSI + Stochastic | Dual momentum oscillators |
| C03 | v15_rsi_williams | RSI + Williams %R | Momentum confirmation |
| C04 | v15_rsi_mfi | RSI + MFI | Price momentum + Volume |
| C05 | v15_adx_aroon | ADX + Aroon | Trend strength + Trend timing |
| C06 | v15_adx_di | ADX + DI | Trend strength + Direction |
| C07 | v15_stochastic_williams | Stochastic + Williams %R | Oversold/overbought confirmation |
| C08 | v15_mfi_cmf | MFI + CMF | Dual volume indicators |
| C09 | v15_rsi_cmf | RSI + CMF | Momentum + Money flow |
| C10 | v15_adx_rsi | ADX + RSI | Filter momentum by trend |
| C11 | v15_aroon_rvi | Aroon + RVI | Trend + Vigor |

#### Three Indicator Combos (3 strategies)
| ID | Name | Indicators |
|----|------|------------|
| C12 | v15_rsi_adx_stochastic | RSI + ADX + Stochastic |
| C13 | v15_mfi_adx_aroon | MFI + ADX + Aroon |
| C14 | v15_williams_stochastic_cmf | Williams + Stochastic + CMF |

#### Zigzag Threshold Variations (4 strategies)
Test whether labeling threshold affects learning signal.

| ID | Name | Indicators | Zigzag Threshold |
|----|------|------------|------------------|
| Z01 | v15_rsi_zigzag_1.5 | RSI | 1.5% (more signals) |
| Z02 | v15_rsi_zigzag_2.0 | RSI | 2.0% |
| Z03 | v15_rsi_zigzag_3.0 | RSI | 3.0% |
| Z04 | v15_rsi_zigzag_3.5 | RSI | 3.5% (fewer signals) |

Note: Baseline strategies use 2.5% threshold.

**Total: 27 strategies**

### Tasks

#### 2.1 Create Strategy Template
- Base YAML with:
  - Analytics enabled
  - Consistent training params (epochs, lr, batch_size)
  - Single symbol: EURUSD
  - Single timeframe: 1h
  - Zigzag labeling at 2.5%

#### 2.2 Generate All 27 Strategies
- Use template + indicator variations
- Ensure fuzzy sets match reference table exactly
- Name convention: `v15_{indicator_combo}.yaml`

#### 2.3 Validate Strategies
- Each strategy passes basic config validation
- No non-Tier-1 indicators used

### Acceptance Criteria
- [ ] 27 strategy YAML files created in `strategies/`
- [ ] All use only Tier 1 indicators
- [ ] All have correct fuzzy ranges from reference
- [ ] All have analytics enabled

---

## Milestone 3: Run Experiments

**Goal:** Execute training on all 27 strategies, collect results.

### Training Configuration
- **Symbol:** EURUSD
- **Timeframe:** 1h
- **Date range:** 2015-01-01 to 2023-12-31 (8 years)
- **Split:** 70% train / 15% val / 15% test
- **Epochs:** 100 (with early stopping)
- **Analytics:** Enabled

### Tasks

#### 3.1 Run All Strategies via API
- For each strategy:
  - `POST /training/start` with strategy name
  - Wait for completion
  - Record operation_id

#### 3.2 Track Progress
- Maintain list of:
  - Strategy name
  - Operation ID
  - Status (pending/running/completed/failed)

#### 3.3 Handle Failures
- If training fails, note error
- Retry once if transient error
- Exclude from analysis if persistent failure

### Acceptance Criteria
- [ ] All 27 strategies have been run
- [ ] Training analytics files exist for each
- [ ] Failures documented

---

## Milestone 4: Analyze and Conclude

**Goal:** Claude reads all results, produces summary, answers "did the NN learn?"

### Analysis Approach

Claude reads each `training_analytics/runs/{run_id}/metrics.csv` and extracts:
- **Final validation accuracy** (last epoch, or best epoch)
- **Learning signal strength** (strong/medium/weak)
- **Loss curve shape** (decreasing/flat/oscillating)
- **Any alerts** generated

### Classification

| Category | Criteria |
|----------|----------|
| **Learned** | val_accuracy > 55% |
| **Marginal** | val_accuracy 50-55% |
| **No learning** | val_accuracy < 50% |

### Output Report

```markdown
## v1.5 Experiment Results

### Summary
- Total strategies: 27
- Learned (>55%): X (Y%)
- Marginal (50-55%): X (Y%)
- No learning (<50%): X (Y%)

### Conclusion
[If >30% learned: "NN architecture CAN learn. Proceed to v2."]
[If <30% learned: "NN architecture shows fundamental limitations. Investigate before v2."]

### Detailed Results
| Strategy | Best Accuracy | Signal Strength | Alerts |
|----------|---------------|-----------------|--------|
| v15_rsi_only | 57.2% | strong | none |
| v15_adx_only | 51.3% | weak | class_imbalance |
| ... | ... | ... | ... |

### Top Performers
1. v15_rsi_williams: 59.3%
2. v15_rsi_adx: 57.8%
3. ...

### Common Failure Patterns
- [If applicable: "X strategies collapsed to single class prediction"]
- [If applicable: "Y strategies showed zero-variance features"]
```

### Tasks

#### 4.1 Collect All Results
- List all run directories in `training_analytics/runs/`
- Map to strategy names via config.yaml

#### 4.2 Extract Metrics from Each Run
- Read metrics.csv for each
- Extract final/best val_accuracy
- Extract learning_signal_strength

#### 4.3 Produce Summary Report
- Aggregate results
- Classify each strategy
- Calculate percentages
- Draw conclusion

#### 4.4 Save Report
- Save to `docs/agentic/v1.5/RESULTS.md`

### Acceptance Criteria
- [ ] All results collected
- [ ] Summary report produced
- [ ] Clear conclusion: "NN works" or "NN has problems"

---

## Timeline

| Milestone | Est. Effort | Dependencies |
|-----------|-------------|--------------|
| M1: Validate Analytics | 1-2 hours | None |
| M2: Create Strategies | 2-3 hours | M1 |
| M3: Run Experiments | ~4-8 hours (training time) | M2 |
| M4: Analyze & Conclude | 1 hour | M3 |

**Total:** ~1-2 days (mostly waiting for training)

---

## What This Replaces

This plan replaces the original v1.5 architecture which proposed:
- New TrainingDiagnostics module → Not needed (TrainingAnalyzer exists)
- Indicator Reference for agent → Not needed (we pick indicators manually)
- Strategy Validator enhancements → Not needed (we validate manually)
- MCP tools → Not needed (we access files directly)

The original approach added infrastructure. This approach answers the question directly.

---

*Document Version: 2.0*
*Created: December 2025*
*Approach: Lean experimentation over infrastructure*
