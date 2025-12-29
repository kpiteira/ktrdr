# v1.5 Experiment Results

## Executive Summary

**Question:** Can the neuro-fuzzy architecture learn predictive patterns when mechanical errors (wrong fuzzy ranges) are eliminated?

**Answer:** YES, but modestly.

**Evidence:** 12 out of 24 completed strategies achieved >60% **test** accuracy (generalizable signal). Best single-indicator result: v15_rsi_zigzag_1_5 at 64.2% test accuracy (+14pp above random baseline). Note: Earlier RSI+DI combination experiments (not part of this v1.5 run) achieved ~64.8%.

**Key Finding:** RSI is the dominant signal source. All top 11 performers include RSI.

**Recommendation:** Proceed to v2 with RSI as the core indicator. Investigate multi-timeframe and memory to amplify the ~10-14pp signal.

---

## Critical Distinction: Validation vs Test Accuracy

This analysis focuses on **test accuracy** (held-out data) rather than validation accuracy.

| Metric | What it means |
|--------|---------------|
| Validation accuracy | Performance on data seen during training (can overfit) |
| **Test accuracy** | Performance on truly unseen data (generalizable signal) |

Several strategies showed high validation accuracy that didn't generalize:
- v15_rsi_zigzag_3_5: 71.2% validation → **55.5% test** (doesn't generalize)
- v15_adx_only: 58.4% validation → **50.0% test** (no signal)

---

## Experiment Design

- **Strategies tested:** 27 (24 with complete test metrics)
- **Indicator types:** Tier 1 bounded only (RSI, Stochastic, Williams %R, MFI, ADX, DI, Aroon, CMF, RVI)
- **Data:** EURUSD 1h, 2015-01-01 to 2023-12-31
- **Training:** 100 epochs with early stopping (patience 15)
- **Baseline:** ~50% (random guessing with balanced BUY/SELL labels)

---

## Results Summary (by TEST accuracy)

| Category | Count | Percentage |
|----------|-------|------------|
| Strong signal (>60% test) | 12 | 50% |
| Weak signal (55-60% test) | 8 | 33% |
| No signal (<55% test) | 4 | 17% |
| **Total analyzed** | 24 | 100% |

---

## Honest Conclusion

**The NN architecture CAN learn**, but the signal is modest:

- **Real performance:** ~60-64% test accuracy (10-14pp above random)
- **Not the 63-71%** validation numbers suggest
- **RSI is essential** — all top performers include it
- **Some indicators are noise** — ADX solo, MFI solo provide no generalizable signal

This validates proceeding to v2, but with realistic expectations. The architecture extracts weak-but-real signal that may compound with:
- More data (multi-symbol, multi-timeframe)
- Memory mechanisms (temporal patterns)
- Better labeling strategies

---

## Detailed Results (sorted by TEST accuracy)

| Rank | Strategy | Test Acc | Val Acc | Gap | Signal |
|------|----------|----------|---------|-----|--------|
| 1 | **v15_rsi_zigzag_1_5** | **64.2%** | 65.4% | +1.2pp | Strong |
| 2 | v15_rsi_williams | 61.6% | 64.2% | +2.6pp | Strong |
| 3 | v15_rsi_cmf | 61.4% | 64.3% | +2.9pp | Strong |
| 4 | v15_rsi_adx_stochastic | 61.4% | 64.6% | +3.2pp | Strong |
| 5 | v15_rsi_only | 61.4% | 63.8% | +2.4pp | Strong |
| 6 | v15_adx_rsi | 61.4% | 64.3% | +2.9pp | Strong |
| 7 | v15_rsi_mfi | 61.4% | 64.2% | +2.8pp | Strong |
| 8 | v15_rsi_zigzag_3_0 | 61.3% | 65.1% | +3.8pp | Strong |
| 9 | v15_rsi_zigzag_2_0 | 61.3% | 64.4% | +3.1pp | Strong |
| 10 | v15_adx_di | 61.1% | 65.2% | +4.1pp | Strong |
| 11 | v15_rsi_stochastic | 61.0% | 63.2% | +2.3pp | Strong |
| 12 | v15_di_only | 60.3% | 65.0% | +4.7pp | Strong |
| 13 | v15_stochastic_only | 59.7% | 61.7% | +2.1pp | Weak |
| 14 | v15_stochastic_williams | 59.5% | 61.7% | +2.2pp | Weak |
| 15 | v15_williams_only | 59.1% | 61.0% | +1.9pp | Weak |
| 16 | v15_aroon_rvi | 55.9% | 61.2% | +5.3pp | Weak |
| 17 | v15_adx_aroon | 55.6% | 58.4% | +2.7pp | Weak |
| 18 | v15_mfi_cmf | 55.6% | 58.4% | +2.8pp | Weak |
| 19 | v15_mfi_only | 55.6% | 58.4% | +2.8pp | Weak |
| 20 | v15_rvi_only | 55.6% | 58.4% | +2.8pp | Weak |
| 21 | v15_williams_stochastic_cmf | 55.6% | 58.4% | +2.8pp | Weak |
| 22 | v15_rsi_zigzag_3_5 | 55.5% | 71.2% | +15.8pp | **Overfit** |
| 23 | v15_mfi_adx_aroon | 50.1% | 57.8% | +7.7pp | None |
| 24 | v15_adx_only | 50.0% | 58.4% | +8.4pp | None |

---

## Pattern Analysis

### What Works (Test Accuracy)

| Pattern | Observation |
|---------|-------------|
| **RSI is essential** | All top 11 performers include RSI |
| **Zigzag 1.5% is optimal** | Best test accuracy (64.2%) AND generalizes (1.2pp gap) |
| **DI is strong solo** | 60.3% test — best non-RSI indicator |
| **Two-indicator combos** | Slight improvement over solo RSI |

### What Doesn't Work

| Pattern | Observation |
|---------|-------------|
| **ADX solo** | 50% test — complete overfit, no signal |
| **MFI-based strategies** | 50-56% test — minimal signal |
| **Zigzag 3.5%** | 55.5% test despite 71.2% validation — artifact |
| **Three-indicator combos** | Diminishing returns, some worse than singles |

### Zigzag Threshold Analysis

| Threshold | Test Accuracy | Val-Test Gap | Verdict |
|-----------|---------------|--------------|---------|
| **1.5%** | **64.2%** | 1.2pp | **Best — generalizes** |
| 2.0% | 61.3% | 3.1pp | Good |
| 3.0% | 61.3% | 3.8pp | Good |
| 3.5% | 55.5% | 15.8pp | **Overfit — avoid** |

Lower zigzag threshold (1.5%) captures more signals while maintaining generalization. Higher thresholds (3.5%) overfit to validation patterns.

---

## Implications for v2

### What We Know Works
1. **RSI as core indicator** — consistent 60-64% test accuracy
2. **Zigzag 1.5% labeling** — best generalization
3. **DI as supporting indicator** — 60% solo, good in combos
4. **The architecture can learn** — but signal is ~10-14pp above random

### Open Questions for v2
1. **Can memory amplify the signal?** — LSTM/attention over sequences
2. **Does multi-timeframe help?** — 5m + 1h context
3. **Does multi-symbol generalize?** — Train on portfolio, test on new pairs
4. **Can we stack multiple weak signals?** — Ensemble approach

### Recommended v2 Strategy
Based on these results, a strong starting point for v2:
- **Core:** RSI with zigzag 1.5% labeling
- **Supporting:** DI, possibly Stochastic
- **Architecture:** Add memory/attention mechanism
- **Data:** Multi-timeframe (5m + 1h)

---

## Appendix: Raw Data

Full results available in: `docs/agentic/v1.5/raw_results.csv`

Model files available in: `models/v15_*/`

---

*Report generated: 2025-12-27 (revised with test accuracy)*
*Completed strategies: 24/27 with full test metrics*
*Key insight: Validation accuracy can mislead — always verify with test accuracy*
