# v1.5: Prove the Concept

> **Note:** The implementation approach has been superseded by a lean experiment-focused
> approach. Instead of building new infrastructure, we run controlled experiments manually.
> See [PLAN.md](PLAN.md) for the actual implementation.
>
> This document remains valid for: problem statement, goals, indicator classification
> (Tier 1/2/3), success criteria, and fuzzy set reference values.

---

## Problem Statement

The MVP agentic system successfully executes the design→train→backtest→assess cycle, but strategies consistently fail to pass training gates. Investigation revealed:

1. **55% of strategies have completely wrong fuzzy set ranges** (e.g., ATR fuzzy sets at [0, 0.2, 0.4] when actual ATR is ~0.001)
2. **Agent uses scale-dependent indicators without normalization** (ATR, MACD) where correct ranges vary by instrument
3. **No feedback loop** - agent doesn't understand WHY training fails, just that it failed
4. **Haiku performs same as Opus** - indicating agent isn't doing meaningful reasoning

Before building learning & memory (v2), we must determine: **Can this architecture learn anything at all when mechanical errors are eliminated?**

---

## Goals

1. **Validate the core hypothesis**: Can neuro-fuzzy architecture learn predictive patterns from bounded indicators?
2. **Eliminate mechanical failures**: Restrict to indicators with known, fixed ranges
3. **Understand failure modes**: When training fails, know WHY (not just that it failed)
4. **Establish baseline**: What accuracy is achievable with "correct" strategies?

---

## Non-Goals (Out of Scope)

1. **Cross-experiment learning** - That's v2 (learning & memory)
2. **New indicator development** - Use existing bounded indicators
3. **Alternative labeling methods** - Stick with segment-based zigzag
4. **Multi-agent coordination** - Single agent focus
5. **Finding profitable strategies** - Goal is learning signal, not profit

---

## Success Criteria

| Metric | Target | Rationale |
|--------|--------|-----------|
| Strategies with correct fuzzy ranges | 100% | Mechanical correctness |
| Training completion rate | >90% | No crashes/errors |
| Strategies showing learning (>55% accuracy) | >30% | Above random (~50% for binary-ish labels) |
| Failure diagnostics available | 100% | Every failure explained |

---

## User Experience

### Scenario 1: Agent Designs Strategy

**Before v1.5:**
```
Agent: "I'll use ATR with fuzzy sets [0, 0.2, 0.4]..."
Training: Loss stuck at 1.09 (random)
Result: "Training failed" (no explanation)
```

**After v1.5:**
```
Agent: "Available bounded indicators: RSI, ADX, Stochastic, Williams %R, MFI, Aroon, CMF"
Agent: "I'll use RSI with fuzzy sets [0,30,40], [35,50,65], [60,70,100]..."
Training: Loss decreases to 0.85, accuracy 57%
Result: "Training completed. Model learned signal (57% vs 50% random baseline)"
```

### Scenario 2: Training Fails

**Before v1.5:**
```
Result: "Training gate failed"
Agent: Tries random different strategy
```

**After v1.5:**
```
Result: "Training failed - Diagnosis:
  - Loss curve: Flat from epoch 1 (never learned)
  - Prediction distribution: 98% class 1 (HOLD collapse)
  - Feature analysis: ADX_14 has zero variance (all values identical after fuzzy transform)
  - Likely cause: Fuzzy sets don't capture indicator variation"
Agent: "ADX fuzzy sets might be too narrow. Let me widen the ranges..."
```

### Scenario 3: Reviewing Experiment Results

**After v1.5:**
```
User: "ktrdr agent results"

Last 10 experiments:
  #1  RSI+ADX          57.1% acc  ✓ Learned (above 50% baseline)
  #2  RSI+Stoch        52.2% acc  ~ Marginal
  #3  ADX+MFI          49.1% acc  ✗ No learning (at random)
  #4  RSI+Williams     59.3% acc  ✓ Learned
  #5  Stoch+CMF        54.8% acc  ~ Marginal
  ...

Summary: 3/10 showed learning (>55%), 4/10 marginal (50-55%), 3/10 no learning
Best performer: RSI+Williams (59.3%)
```

---

## Key Decisions

### Decision 1: Restrict to Bounded Indicators Only

**Choice:** Agent can ONLY use Tier 1 indicators (RSI, ADX, Stochastic, Williams %R, MFI, Aroon, CMF)

**Alternatives considered:**
- Allow all indicators with normalization → Adds complexity, normalization itself can fail
- Allow all with warnings → Agent ignores warnings, still makes errors

**Rationale:** Eliminate one variable completely. If bounded indicators don't work, problem is deeper. If they work, we can add normalization for others in v2.

### Decision 2: Provide Fuzzy Set Reference

**Choice:** Agent receives a reference table of correct fuzzy set ranges for each indicator

**Alternatives considered:**
- Let agent learn ranges from data → Takes many experiments, slow
- Hard-code ranges in strategy validator → Removes agent flexibility

**Rationale:** Agent should reason about strategy design, not guess indicator ranges. Reference table is like giving a developer documentation.

### Decision 3: Structured Failure Diagnostics

**Choice:** Every training result includes structured diagnostic information

**Diagnostics include:**
- Loss curve classification (decreasing/flat/oscillating/diverging)
- Prediction distribution (balanced/collapsed to single class)
- Feature statistics (variance, range, correlation with labels)
- Suggested cause and remediation

**Rationale:** Agent can't learn from failures it doesn't understand. This is immediate feedback, not cross-experiment memory.

### Decision 4: "Learning Signal" Definition

**Choice:** A strategy "shows learning" if validation accuracy > 55%

**Important:** With segment-based zigzag labeling at 2.5% threshold, label distribution is approximately **50% BUY / 1% HOLD / 49% SELL**. This is effectively binary classification, so:
- Random baseline = ~50% (not 33%)
- Learning detected = >55% (5 percentage points above random)
- Strong learning = >60%

**Alternatives considered:**
- Use loss threshold → Loss scale varies, hard to interpret
- Use statistical significance → Requires many runs, complex

**Rationale:** Simple, interpretable threshold. 55% is 5 percentage points above the actual random baseline for our label distribution.

---

## Indicator Classification (Empirically Verified)

Based on analysis of EURUSD 1h data (115,243 bars, 2005-2025):

### TIER 1: Perfectly Bounded (Allowed in v1.5)

| Indicator | Actual Range | Theoretical | Suggested Fuzzy Sets |
|-----------|--------------|-------------|----------------------|
| **RSI** | [0, 94] | [0, 100] | oversold [0,30,40], neutral [35,50,65], overbought [60,70,100] |
| **Stochastic %K** | [0.5, 99.6] | [0, 100] | oversold [0,20,30], neutral [25,50,75], overbought [70,80,100] |
| **Williams %R** | [-100, 0] | [-100, 0] | oversold [-100,-80,-60], neutral [-65,-50,-35], overbought [-40,-20,0] |
| **MFI** | [0, 100] | [0, 100] | Same as RSI |
| **ADX** | [6, 88] | [0, 100] | weak [0,15,25], moderate [20,35,50], strong [45,60,100] |
| **+DI / -DI** | [2, 87] | [0, 100] | weak [0,15,25], moderate [20,35,50], strong [45,60,100] |
| **Aroon Up/Down** | [0, 100] | [0, 100] | weak [0,25,40], moderate [35,50,65], strong [60,75,100] |
| **CMF** | [-0.89, 0.45] | [-1, 1] | selling [-1,-0.3,-0.05], neutral [-0.1,0,0.1], buying [0.05,0.3,1] |
| **RVI** | [3, 100] | [0, 100] | low [0,20,40], neutral [30,50,70], high [60,80,100] |

### TIER 2: Semi-Bounded (May add in v2)

| Indicator | Actual Range | Notes |
|-----------|--------------|-------|
| **Fisher Transform** | [-7.6, 7.6] | Usually ±5, can exceed in extreme markets |
| **BB %B** | [-0.5, 1.6] | Usually 0-1, exceeds during breakouts |
| **ROC %** | [-4.8%, 5.3%] | Percentage-based, fairly stable for forex |
| **Distance from MA %** | [-3.4%, 4.6%] | Percentage-based, instrument-agnostic |

### TIER 3: Not Fuzzy-Friendly (Excluded)

| Indicator | Reason for Exclusion |
|-----------|----------------------|
| ATR | Price-scale dependent (0.001 forex, 5.0 stocks) |
| MACD | Price-scale dependent |
| Momentum | Price-scale dependent |
| SMA / EMA | Price level, not a signal |
| OBV | Cumulative, unbounded |
| CCI | Unbounded, extreme values common |
| Volume Ratio | Can spike to 20x+, unstable |
| Bollinger Bands (upper/lower) | Price-dependent (use BB %B instead) |
| Donchian/Keltner Channels | Price-dependent |
| Parabolic SAR | Price-dependent |
| Ichimoku | Price-dependent (5 components, all price-based) |
| SuperTrend | Price-dependent |
| VWAP | Price-dependent |
| ADLine | Cumulative |
| ZigZag | Used for labels, not features |

---

## Open Questions

1. **Should we also restrict symbols?** Focus on forex only (consistent characteristics) or include stocks?
   - *Recommendation*: Start with forex (EURUSD, GBPUSD, USDJPY) - consistent scale

2. **What zigzag threshold to use?** Current strategies use 2.5% which gives balanced segment labels
   - *Recommendation*: Keep 2.5% with segment labeling - already produces 50/50 split

3. **How many experiments before concluding?**
   - *Recommendation*: 30 experiments minimum - enough to see patterns

4. **Should diagnostics be automated or agent-interpreted?**
   - *Recommendation*: Automated classification with raw data available for agent reasoning

---

## Relationship to Roadmap

```
MVP (done)     →  v1.5 (this)      →  v2              →  v3+

Mechanics      →  Prove concept    →  Learning &      →  Knowledge
work              + diagnostics       Memory             Base
```

v1.5 is a **checkpoint** - we need confidence the architecture can work before investing in learning systems.

---

*Document Version: 1.0*
*Created: December 2024*
