---
design: docs/agentic/v1.5/DESIGN.md
architecture: docs/agentic/v1.5/ARCHITECTURE.md
plan: docs/agentic/v1.5/PLAN.md
---

# Milestone 4: Analyze and Conclude

**Goal:** Answer the core question with evidence: "Can the neuro-fuzzy architecture learn?"

**Why M4:** This is the entire point of the experiment. We synthesize results into a clear conclusion that determines next steps.

---

## Questions This Milestone Must Answer

| # | Question | How We'll Answer It | Success Criteria |
|---|----------|---------------------|------------------|
| Q4.1 | What % of strategies showed learning (>55%)? | Count and calculate | Have exact percentage |
| Q4.2 | What % were marginal (50-55%)? | Count and calculate | Have exact percentage |
| Q4.3 | What % showed no learning (<50%)? | Count and calculate | Have exact percentage |
| Q4.4 | **Can the NN learn?** | Apply success criteria | >30% at >55% → YES, else NO |
| Q4.5 | Were there common failure patterns? | Analyze failed strategies | Documented patterns (if any) |
| Q4.6 | What's the recommendation? | Based on Q4.4 | Clear next step |

---

## Success Criteria (from DESIGN.md)

| Metric | Target | Interpretation |
|--------|--------|----------------|
| Strategies showing learning (>55% val_accuracy) | >30% | NN architecture works, proceed to v2 |
| Strategies showing learning (>55% val_accuracy) | <30% | Fundamental issue, investigate before v2 |

**Important Context:**
- With ~50% BUY / ~1% HOLD / ~49% SELL labels, random baseline is ~50%
- >55% means 5 percentage points above random
- >60% would indicate strong learning

---

## Task 4.1: Collect All Results

**Type:** RESEARCH
**Estimated time:** 30 minutes

**Description:**
Extract final metrics from all completed training runs.

**Collection Script:**

```bash
#!/bin/bash
# collect_v15_results.sh

OUTPUT_FILE="docs/agentic/v1.5/raw_results.csv"

echo "strategy_name,run_id,total_epochs,best_val_accuracy,final_val_accuracy,learning_signal,alerts_count" > $OUTPUT_FILE

for run_dir in training_analytics/runs/*/; do
  RUN_ID=$(basename $run_dir)

  # Get strategy name from config
  STRATEGY_NAME=$(grep "name:" "$run_dir/config.yaml" | head -1 | sed 's/name: //' | tr -d '"' | tr -d ' ')

  # Skip non-v15 runs
  if [[ ! "$STRATEGY_NAME" =~ ^v15_ ]]; then
    continue
  fi

  # Get metrics from CSV
  TOTAL_EPOCHS=$(tail -n +2 "$run_dir/metrics.csv" | wc -l)
  BEST_VAL_ACC=$(tail -n +2 "$run_dir/metrics.csv" | cut -d',' -f5 | sort -rn | head -1)
  FINAL_VAL_ACC=$(tail -1 "$run_dir/metrics.csv" | cut -d',' -f5)

  # Get learning signal from last epoch
  LEARNING_SIGNAL=$(tail -1 "$run_dir/metrics.csv" | cut -d',' -f7)

  # Count alerts
  ALERTS_COUNT=$(grep -c "Epoch" "$run_dir/alerts.txt" 2>/dev/null || echo "0")

  echo "$STRATEGY_NAME,$RUN_ID,$TOTAL_EPOCHS,$BEST_VAL_ACC,$FINAL_VAL_ACC,$LEARNING_SIGNAL,$ALERTS_COUNT" >> $OUTPUT_FILE
done

echo "Results collected to: $OUTPUT_FILE"
cat $OUTPUT_FILE
```

**Alternative: Python Collection Script:**

```python
#!/usr/bin/env python3
# collect_v15_results.py

import csv
import json
from pathlib import Path
import yaml

results = []
runs_dir = Path("training_analytics/runs")

for run_dir in runs_dir.iterdir():
    if not run_dir.is_dir():
        continue

    config_file = run_dir / "config.yaml"
    metrics_file = run_dir / "metrics.csv"
    json_file = run_dir / "detailed_metrics.json"

    if not all(f.exists() for f in [config_file, metrics_file]):
        continue

    # Get strategy name
    with open(config_file) as f:
        config = yaml.safe_load(f)
    strategy_name = config.get("name", "")

    # Skip non-v15 strategies
    if not strategy_name.startswith("v15_"):
        continue

    # Read metrics
    with open(metrics_file) as f:
        reader = csv.DictReader(f)
        metrics = list(reader)

    if not metrics:
        continue

    # Extract key values
    val_accuracies = [float(m.get("val_accuracy", 0)) for m in metrics if m.get("val_accuracy")]
    best_val_acc = max(val_accuracies) if val_accuracies else 0
    final_val_acc = float(metrics[-1].get("val_accuracy", 0))
    final_signal = metrics[-1].get("learning_signal_strength", "unknown")

    # Read detailed JSON for additional info
    alerts_count = 0
    if json_file.exists():
        with open(json_file) as f:
            detailed = json.load(f)
        alerts_count = len(detailed.get("alerts", []))

    results.append({
        "strategy_name": strategy_name,
        "run_id": run_dir.name,
        "total_epochs": len(metrics),
        "best_val_accuracy": best_val_acc,
        "final_val_accuracy": final_val_acc,
        "learning_signal": final_signal,
        "alerts_count": alerts_count,
    })

# Write results
output_file = Path("docs/agentic/v1.5/raw_results.csv")
with open(output_file, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

print(f"Collected {len(results)} results to {output_file}")
for r in sorted(results, key=lambda x: -x["best_val_accuracy"]):
    print(f"{r['strategy_name']}: {r['best_val_accuracy']:.1%}")
```

**Output: raw_results.csv**

| strategy_name | run_id | total_epochs | best_val_accuracy | final_val_accuracy | learning_signal | alerts_count |
|---------------|--------|--------------|-------------------|--------------------|-----------------|--------------|
| v15_rsi_only | ... | ... | ... | ... | ... | ... |
| ... | ... | ... | ... | ... | ... | ... |

**Acceptance Criteria:**
- [ ] Results collected for all completed runs
- [ ] Strategy names correctly mapped to runs
- [ ] raw_results.csv created and readable

---

## Task 4.2: Classify and Analyze Results

**Type:** RESEARCH
**Estimated time:** 30 minutes

**Description:**
Classify each strategy and calculate aggregate statistics.

**Classification Criteria:**

| Category | Criteria | Interpretation |
|----------|----------|----------------|
| **Learned** | best_val_accuracy > 55% | NN extracted signal from features |
| **Marginal** | 50% ≤ best_val_accuracy ≤ 55% | Unclear, near random |
| **No Learning** | best_val_accuracy < 50% | Worse than random, possible issue |

**Analysis Script:**

```python
#!/usr/bin/env python3
# analyze_v15_results.py

import csv
from collections import defaultdict

# Read results
results = []
with open("docs/agentic/v1.5/raw_results.csv") as f:
    reader = csv.DictReader(f)
    results = list(reader)

# Classify
learned = []     # >55%
marginal = []    # 50-55%
no_learning = [] # <50%

for r in results:
    acc = float(r["best_val_accuracy"])
    if acc > 0.55:
        learned.append(r)
    elif acc >= 0.50:
        marginal.append(r)
    else:
        no_learning.append(r)

total = len(results)

print("=== v1.5 Experiment Results ===")
print()
print(f"Total strategies: {total}")
print()
print(f"LEARNED (>55%): {len(learned)} ({len(learned)/total*100:.1f}%)")
for r in sorted(learned, key=lambda x: -float(x["best_val_accuracy"])):
    print(f"  {r['strategy_name']}: {float(r['best_val_accuracy']):.1%}")
print()
print(f"MARGINAL (50-55%): {len(marginal)} ({len(marginal)/total*100:.1f}%)")
for r in sorted(marginal, key=lambda x: -float(x["best_val_accuracy"])):
    print(f"  {r['strategy_name']}: {float(r['best_val_accuracy']):.1%}")
print()
print(f"NO LEARNING (<50%): {len(no_learning)} ({len(no_learning)/total*100:.1f}%)")
for r in sorted(no_learning, key=lambda x: -float(x["best_val_accuracy"])):
    print(f"  {r['strategy_name']}: {float(r['best_val_accuracy']):.1%}")
print()

# Success criteria check
learned_pct = len(learned) / total * 100
if learned_pct > 30:
    print("✅ SUCCESS: >30% of strategies showed learning")
    print("   Conclusion: NN architecture CAN learn")
    print("   Recommendation: Proceed to v2 (learning & memory)")
else:
    print("❌ BELOW THRESHOLD: <30% of strategies showed learning")
    print("   Conclusion: NN architecture shows limitations")
    print("   Recommendation: Investigate before v2")

# Pattern analysis
print()
print("=== Pattern Analysis ===")

# By indicator count
single = [r for r in results if r["strategy_name"].count("_") <= 2]
combo = [r for r in results if r["strategy_name"].count("_") > 2]
print(f"Single indicator strategies: {len(single)}, avg acc: {sum(float(r['best_val_accuracy']) for r in single)/len(single):.1%}")
print(f"Combo indicator strategies: {len(combo)}, avg acc: {sum(float(r['best_val_accuracy']) for r in combo)/len(combo):.1%}")

# Zigzag variations
zigzag = [r for r in results if "zigzag" in r["strategy_name"]]
if zigzag:
    print()
    print("Zigzag threshold impact:")
    for r in sorted(zigzag, key=lambda x: x["strategy_name"]):
        print(f"  {r['strategy_name']}: {float(r['best_val_accuracy']):.1%}")
```

**Acceptance Criteria:**
- [ ] All strategies classified
- [ ] Percentages calculated
- [ ] Success criteria applied
- [ ] Patterns identified

---

## Task 4.3: Produce Summary Report

**File:** `docs/agentic/v1.5/RESULTS.md`
**Type:** CODING
**Estimated time:** 30 minutes

**Description:**
Create the final summary report documenting conclusions and recommendations.

**Report Template:**

```markdown
# v1.5 Experiment Results

## Executive Summary

**Question:** Can the neuro-fuzzy architecture learn predictive patterns when mechanical errors (wrong fuzzy ranges) are eliminated?

**Answer:** [YES / NO / INCONCLUSIVE]

**Evidence:** X out of Y strategies (Z%) achieved >55% validation accuracy.

**Recommendation:** [Proceed to v2 / Investigate further / Pivot approach]

---

## Experiment Design

- **Strategies tested:** 27
- **Indicator types:** Tier 1 bounded only (RSI, Stochastic, Williams %R, MFI, ADX, DI, Aroon, CMF, RVI)
- **Data:** EURUSD 1h, 2015-01-01 to 2023-12-31
- **Training:** 100 epochs with early stopping (patience 15)
- **Success threshold:** >30% of strategies showing >55% accuracy

---

## Results Summary

| Category | Count | Percentage |
|----------|-------|------------|
| Learned (>55%) | X | Y% |
| Marginal (50-55%) | X | Y% |
| No Learning (<50%) | X | Y% |
| **Total** | 27 | 100% |

---

## Conclusion

[If >30% learned:]
**The NN architecture CAN learn.** When given properly configured bounded indicators with correct fuzzy ranges, the neural network extracts predictive signal above random chance.

This validates the core hypothesis and supports proceeding to v2 (learning & memory).

[If <30% learned:]
**The NN architecture shows limitations.** Even with correct fuzzy configurations, fewer than 30% of strategies showed meaningful learning.

Before proceeding to v2, investigate:
- [Possible causes based on patterns]
- [Recommended next steps]

---

## Detailed Results

### Top Performers

| Rank | Strategy | Best Accuracy | Signal Strength |
|------|----------|---------------|-----------------|
| 1 | [name] | X.X% | [strong/medium/weak] |
| 2 | [name] | X.X% | [strong/medium/weak] |
| 3 | [name] | X.X% | [strong/medium/weak] |

### All Results (sorted by accuracy)

| Strategy | Best Val Acc | Final Val Acc | Epochs | Signal | Category |
|----------|--------------|---------------|--------|--------|----------|
| [name] | X.X% | X.X% | N | [s/m/w] | Learned |
| ... | ... | ... | ... | ... | ... |

---

## Pattern Analysis

### Single vs Combination Indicators

| Type | Count | Avg Accuracy | Learned (>55%) |
|------|-------|--------------|----------------|
| Single | 9 | X.X% | N (Y%) |
| Two combo | 11 | X.X% | N (Y%) |
| Three combo | 3 | X.X% | N (Y%) |

[Observation about whether combinations help or hurt]

### Zigzag Threshold Impact

| Threshold | Strategy | Accuracy |
|-----------|----------|----------|
| 1.5% | v15_rsi_zigzag_1.5 | X.X% |
| 2.0% | v15_rsi_zigzag_2.0 | X.X% |
| 2.5% | v15_rsi_only (baseline) | X.X% |
| 3.0% | v15_rsi_zigzag_3.0 | X.X% |
| 3.5% | v15_rsi_zigzag_3.5 | X.X% |

[Observation about optimal threshold]

### Indicator Performance

| Indicator | Solo Accuracy | Best Combo Accuracy |
|-----------|---------------|---------------------|
| RSI | X.X% | X.X% (with Y) |
| ADX | X.X% | X.X% (with Y) |
| ... | ... | ... |

---

## Common Failure Patterns (if any)

[If patterns found:]
- **Pattern 1:** [description]
  - Affected strategies: [list]
  - Possible cause: [hypothesis]

- **Pattern 2:** [description]
  - Affected strategies: [list]
  - Possible cause: [hypothesis]

[If no patterns:]
Failures appear random with no systematic pattern, suggesting individual indicator/combination characteristics rather than infrastructure issues.

---

## Recommendations

### If NN Works (>30% success):

1. **Proceed to v2** — Learning & Memory system
2. **Note successful patterns** — [list indicators/combinations that worked]
3. **Consider for v2:** [any insights about what helps learning]

### If NN Limitations (<30% success):

1. **Before v2, investigate:**
   - [ ] Is 3-state labeling appropriate?
   - [ ] Are fuzzy transforms actually differentiating?
   - [ ] Is the NN architecture sufficient?

2. **Potential experiments:**
   - [ ] Try binary labels (BUY/SELL only)
   - [ ] Try different fuzzy membership shapes
   - [ ] Try deeper/wider networks

---

## Appendix: Raw Data

Full results available in: `docs/agentic/v1.5/raw_results.csv`

Analytics files available in: `training_analytics/runs/`

---

*Report generated: [date]*
*Experiment duration: [X hours]*
*Completed strategies: [N/27]*
```

**Acceptance Criteria:**
- [ ] Report file created
- [ ] Executive summary has clear answer
- [ ] All data tables populated
- [ ] Patterns analyzed
- [ ] Recommendations provided

---

## Milestone 4 Verification

### E2E Test Scenario

**Purpose:** Verify we have answered the core question with evidence
**Duration:** ~30 minutes (analysis time)
**Prerequisites:** M3 complete with ≥25 completed runs

**Test Steps:**

```bash
# 1. Verify raw results collected
cat docs/agentic/v1.5/raw_results.csv | wc -l
# Expected: ≥26 (header + 25+ results)

# 2. Verify classification done
grep -c "Learned\|Marginal\|No Learning" docs/agentic/v1.5/RESULTS.md
# Expected: >0 (categories present)

# 3. Verify conclusion present
grep "CAN learn\|shows limitations" docs/agentic/v1.5/RESULTS.md
# Expected: One of these phrases

# 4. Verify recommendation present
grep "Proceed to v2\|investigate" docs/agentic/v1.5/RESULTS.md
# Expected: Match found
```

**Success Criteria:**
- [ ] Raw results collected for all runs
- [ ] Classification complete
- [ ] Clear conclusion (YES/NO)
- [ ] Recommendations provided
- [ ] Report is readable and complete

### Completion Checklist

- [ ] Task 4.1: All results collected
- [ ] Task 4.2: Results classified and analyzed
- [ ] Task 4.3: Summary report produced
- [ ] All M4 questions answered:
  - [ ] Q4.1: % strategies learned (>55%)
  - [ ] Q4.2: % strategies marginal (50-55%)
  - [ ] Q4.3: % strategies no learning (<50%)
  - [ ] Q4.4: **Can the NN learn?** (YES/NO)
  - [ ] Q4.5: Common failure patterns documented
  - [ ] Q4.6: Clear recommendation provided

### Validation Checkpoint

After M4, we must be able to answer **YES** to:
- [ ] "Do we have a definitive answer to 'can the NN learn'?"
- [ ] "Is the conclusion supported by evidence?"
- [ ] "Do we know what to do next?"

---

## Final Experiment Outcome

After completing M4, update OVERVIEW.md with final status:

```markdown
## Final Outcome

**Conclusion:** [NN CAN learn / NN shows limitations]
**Evidence:** [X/27 strategies (Y%) achieved >55% accuracy]
**Recommendation:** [Proceed to v2 / Investigate before v2]
**Report:** [Link to RESULTS.md]
```

---

*Estimated time: 1-2 hours*
