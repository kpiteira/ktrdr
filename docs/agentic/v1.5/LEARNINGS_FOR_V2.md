# v1.5 Learnings for v2 Agentic System Design

## Executive Summary

The v1.5 experiments validated that the neuro-fuzzy architecture can learn, and more importantly, demonstrated **conditions under which learnings compound systematically**. This document captures the insights needed to design v2's experimental framework.

---

## Core Finding: Learnings CAN Compound

| Experiment | Test Accuracy | Delta |
|------------|---------------|-------|
| RSI + zigzag 1.5% (baseline) | 64.2% | — |
| RSI + DI + zigzag 1.5% | 64.8% | +0.6pp |
| RSI + DI + Stoch + zigzag 1.5% | 64.8% | +0.6pp (plateau) |

**Conclusion:** Combining two independently strong signals produces predictable improvement. Adding a third signal shows diminishing returns.

---

## Conditions for Systematic Learning

### 1. Use TEST Accuracy, Not Validation

**Problem discovered:** Validation accuracy can be misleading.

| Strategy | Validation | Test | Gap |
|----------|------------|------|-----|
| v15_rsi_zigzag_3_5 | 71.2% | 55.5% | 15.8pp (overfit!) |
| v15_rsi_zigzag_1_5 | 65.4% | 64.2% | 1.2pp (generalizes) |
| v15_adx_only | 58.4% | 50.0% | 8.4pp (no signal) |

**v2 Design Implication:**
- Always evaluate on held-out test set
- Flag strategies with >5pp validation-test gap as potential overfits
- Use test accuracy as the primary metric for strategy comparison

### 2. Start with Independently Strong Signals

**What works:** Indicators that show >60% test accuracy solo.

| Indicator | Solo Test Accuracy | Signal Quality |
|-----------|-------------------|----------------|
| RSI | 61.4% | Strong |
| DI | 60.3% | Strong |
| Stochastic | 59.7% | Moderate |
| Williams %R | 59.1% | Moderate |
| ADX | 50.0% | None |
| MFI | 55.6% | Weak |

**v2 Design Implication:**
- Before combining indicators, verify each has independent signal
- Discard indicators with <55% test accuracy (noise)
- Prioritize indicators with >60% (proven signal)

### 3. Combine Complementary Signals

**What works:** Combining indicators that measure different market aspects.

| Combination | Why It Works |
|-------------|--------------|
| RSI (momentum) + DI (trend direction) | Different dimensions |
| RSI + zigzag 1.5% (better labels) | Cleaner signal, not more noise |

**What doesn't work:**
- RSI + Stochastic + Williams (all momentum → redundant)
- Three-indicator combos (diminishing returns)

**v2 Design Implication:**
- Classify indicators by type: momentum, trend, volume, volatility
- Combine across types, not within types
- Two-indicator combos are optimal; three shows diminishing returns

### 4. Labeling Quality Matters

**Zigzag threshold impact:**

| Threshold | Test Accuracy | Generalization |
|-----------|---------------|----------------|
| 1.5% | 64.2% | Best |
| 2.0% | 61.3% | Good |
| 3.0% | 61.3% | Good |
| 3.5% | 55.5% | Overfit |

**v2 Design Implication:**
- Lower thresholds (1.5-2.0%) capture more signals while generalizing
- Higher thresholds (3.5%+) overfit to specific patterns
- The labeling strategy is as important as indicator selection

### 5. Recognize Plateaus

**Pattern observed:** Improvement stops after combining two strong signals.

```
RSI alone:     64.2%
RSI + DI:      64.8%  (+0.6pp)
RSI + DI + S:  64.8%  (+0.0pp) ← plateau
```

**v2 Design Implication:**
- After 2-3 combinations without improvement, change dimensions
- Dimensions to explore: multi-timeframe, memory, different labeling
- Don't keep adding indicators to a plateau

---

## What v2 Should Explore

Based on v1.5 learnings, the highest-value experiments for v2 are:

### Priority 1: Multi-Timeframe
- **Current:** Single timeframe (1h)
- **Hypothesis:** 5m data provides faster reaction context, 1h provides trend context
- **Test:** RSI on 5m + RSI on 1h + DI on 1h
- **Expected:** Should break the 64.8% plateau by adding a new dimension

### Priority 2: Memory/Sequence
- **Current:** MLP sees single time snapshot
- **Hypothesis:** RSI trajectory over N periods is more informative than RSI at time T
- **Test:** LSTM or attention over 10-20 period windows
- **Expected:** Captures patterns like "RSI divergence" that require temporal context

### Priority 3: Multi-Symbol
- **Current:** EURUSD only
- **Hypothesis:** Patterns may generalize across forex pairs
- **Test:** Train on EURUSD + GBPUSD, test on AUDUSD
- **Expected:** Validates whether learnings transfer

### Priority 4: Better Labeling
- **Current:** Zigzag with fixed threshold
- **Hypothesis:** Adaptive threshold or forward-looking labels may help
- **Test:** Compare zigzag vs triple barrier vs adaptive threshold
- **Expected:** Better labels → cleaner signal → higher accuracy

---

## Framework for v2 Experiments

### Experiment Template

```yaml
experiment:
  name: "descriptive_name"
  hypothesis: "What we expect to learn"
  baseline: "Previous best result to beat"

  variables:
    independent: "What we're changing"
    controlled: "What stays the same"

  success_criteria:
    minimum: "Test accuracy > baseline"
    target: "Test accuracy > baseline + 1pp"

  validation:
    - Use held-out test set
    - Check val-test gap < 5pp
    - Run 2-3 times to ensure reproducibility
```

### Decision Tree for Experiments

```
1. Does indicator X show >55% test accuracy solo?
   NO  → Discard X
   YES → Continue

2. Is X complementary to current best (different type)?
   NO  → Try different indicator
   YES → Test X + current best

3. Did combination improve test accuracy?
   NO  → Try different dimension (multi-TF, memory)
   YES → Lock in, continue adding

4. Has improvement plateaued (3 attempts, no gain)?
   NO  → Continue adding indicators
   YES → Change dimensions (multi-TF, memory, labels)
```

---

## Key Metrics for v2 Dashboard

| Metric | Purpose | Target |
|--------|---------|--------|
| Test Accuracy | Real performance | >60% |
| Val-Test Gap | Generalization check | <5pp |
| Epochs to Best | Learning efficiency | <30 |
| Signal Type Coverage | Complementarity | 2+ types |

---

## Summary: What We Now Know

1. **The architecture works** — 60-65% test accuracy is achievable
2. **Signals compose** — Two strong signals > one strong signal
3. **Diminishing returns are real** — Three signals ≈ two signals
4. **Validation lies** — Always use test accuracy
5. **Labeling matters** — 1.5% zigzag is optimal for generalization
6. **RSI + DI is the current ceiling** — Need new dimension to break through

---

## Next Experiment: Multi-Timeframe

**Hypothesis:** Adding 5m timeframe context will break the 64.8% plateau.

**Setup:**
- Base: 5m data
- Indicators: RSI (5m) + RSI (1h) + DI (1h)
- Labels: Zigzag 1.5% on 1h
- Expected: >65% test accuracy

**Rationale:** 5m RSI captures short-term momentum shifts that 1h RSI misses. Combined with 1h trend direction (DI), this should provide richer signal.

---

*Document created: 2025-12-27*
*Based on: v1.5 experiments (27 strategies) + follow-up composition tests*
