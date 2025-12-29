# v2.0: Learning & Memory

## What We Validated in v1.5

1. **The NN architecture can learn** — 60-65% test accuracy is achievable
2. **Learnings can compound** — RSI + DI > RSI alone
3. **Failures are information** — they generate hypotheses, not dead ends

## The Core Insight

The orchestrator already runs experiments. What it lacks is **memory**.

But not memory as a rulebook. Not "if X then Y" prescriptions.

Memory as **stories**. Experiences that surface when relevant, inform thinking, and shape intuition—without dictating action.

---

## What Memory Enables

### Creative Thinking Informed by Experience

The agent is considering using RSI on 5-minute data. Memory surfaces:

> *"Last time we tried RSI on 5m, it underperformed. We thought it might be
> because the NN was too small to capture the faster dynamics, or because
> the zigzag threshold was too aggressive. We tested bigger NN and it
> helped somewhat. We never tested combining 5m RSI with 1h RSI as a
> smoothing context..."*

This doesn't tell the agent what to do. It gives context for creative thinking. Maybe the agent decides:

- "Let me try 5m RSI with 1h RSI as context"
- Or "The bigger NN helped—let me push that further"
- Or "Actually, let me try something completely different"

The memory informs. The agent decides.

### Systematic Validation When Needed

Sometimes the agent wants to be methodical:

> *"I want to test whether indicator type matters for composition. What
> combinations have we tried?"*

Memory provides:

> *"RSI (momentum) + DI (trend) → improved. RSI + Stochastic (both momentum)
> → no improvement. We haven't tried combining volume indicators with
> momentum indicators yet."*

The agent can then systematically fill gaps. But it's the agent choosing to be systematic, not memory forcing it.

### Pattern Recognition Without Prescription

Memory accumulates observations:

> *"Zigzag 3.5% on 1h showed 71% validation but only 55% test. Same pattern
> with zigzag 4% on 1d. Both times we got fooled by validation accuracy."*

The agent notices the pattern. Next time it sees high validation with large zigzag thresholds, it's naturally skeptical. Not because a rule says "don't use zigzag > 3%" but because it remembers what happened.

---

## What Gets Remembered

### Stories, Not Rules

Instead of:
```yaml
anti_pattern:
  pattern: "zigzag > 3%"
  action: "avoid"
```

We remember:
```
When we tried zigzag 3.5% on 1h for RSI, validation looked great at 71%
but test crashed to 55%. The larger threshold created fewer but more
dramatic labels, and the model memorized specific patterns instead of
learning generalizable signals. This happened again with zigzag 4% on
daily data.
```

The story contains the learning, the context, and the reasoning. It's useful for both "avoid large zigzag" AND for "hmm, maybe on weekly timeframes larger thresholds make sense."

### Open Questions, Not Closed Answers

Instead of:
```yaml
validated:
  - "RSI works on 1h"
  - "RSI doesn't work on 5m"
```

We remember:
```
RSI on 1h consistently produces 61-64% test accuracy. On 5m with the
same setup, it dropped to 56%. We're not sure why—could be:
- NN capacity (we tested bigger, slight improvement)
- Zigzag threshold (tested smaller, pending results)
- RSI fundamentally designed for daily, may need adaptation for faster TF
- Maybe 5m needs 1h as context, not as standalone

The question "what makes an indicator work on faster timeframes?" is
still open.
```

### Connections, Not Categories

Instead of categorizing indicators by type and prescribing compositions:
```yaml
indicator_types:
  momentum: [RSI, Stochastic, Williams]
  trend: [DI, ADX]
composition_rule: "combine across types, not within"
```

We remember connections:
```
RSI + DI improved accuracy. Both measure different things—RSI is about
momentum extremes, DI is about directional strength. When we added
Stochastic (another momentum measure) to RSI+DI, no improvement.

There might be something about combining complementary dimensions. But
we also haven't tested whether two trend indicators would stack, or
whether the pattern holds on different timeframes.
```

---

## How Memory Surfaces

Memory isn't queried explicitly. It surfaces through context.

### During Planning

When the agent is deciding what to try next, relevant memories surface:

> "What do I know about multi-timeframe approaches?"
>
> *[Memory surfaces stories about 5m experiments, the hypothesis about
> using 1h as context, the observation that our successful experiments
> all used single timeframe...]*

### During Interpretation

When the agent sees results, memories help interpret:

> Validation: 68%, Test: 52%
>
> *[Memory surfaces the zigzag overfitting story, prompting deeper
> analysis instead of celebration]*

### During Creative Moments

When the agent is stuck or exploring:

> "Nothing's working on 5m..."
>
> *[Memory surfaces: "RSI was designed for daily", prompting the thought:
> "What if I used an indicator actually designed for intraday?"]*

---

## What Memory Is Not

### Not a Rulebook

Memory doesn't prescribe behavior. It informs thinking.

Wrong: "Memory says avoid zigzag > 3%, so I won't try it."

Right: "I remember zigzag 3.5% overfitting on 1h. But this is weekly data with way more bars—the context is different. Let me try it and see."

### Not a To-Do List

Memory isn't a queue of hypotheses to systematically test.

Wrong: "H1 is next in the queue, so I'll test bigger NN."

Right: "I'm curious whether 5m needs more capacity. I remember we thought about testing bigger NN. Let me try that."

### Not a Scorecard

Memory isn't just accuracy numbers to optimize.

Wrong: "64.8% is our best. Only accept strategies that beat 64.8%."

Right: "64.8% is our best on 1h EURUSD. What we learned getting there might help with other symbols and timeframes."

---

## The Design Principle

**Memory enables, doesn't prescribe.**

It provides context for reasoning—creative or systematic. It surfaces relevant experiences without forcing particular actions. It accumulates understanding without closing off exploration.

The agent thinks. Memory helps it think better.

---

## Implementation: Stories as the Primitive

The fundamental unit of memory is a **story**—a narrative of what happened, what we observed, and what it might mean.

```
Story: "5m RSI Underperformance"
When: December 2025
Setup: RSI on 5m EURUSD, zigzag 1.5%, same NN as successful 1h experiments
Result: 56% test accuracy (vs 64% on 1h)
Observations:
  - 5m has ~12x more bars than 1h
  - RSI oscillates much faster, more noise
  - The model might be underpowered for this complexity
  - Or RSI isn't suited for 5m timeframes
Hypotheses generated:
  - Bigger NN might help (partially tested, some improvement)
  - Smaller zigzag might help (pending)
  - Using 1h as context might help (not tested)
Connections: Related to "indicator-timeframe compatibility" question
Open questions: What makes an indicator work on faster TFs?
```

Stories link to each other. They build a web of experience, not a hierarchy of rules.

---

## Summary

v2 gives the agent memory—not as a playbook but as accumulated experience.

| Without Memory | With Memory |
|----------------|-------------|
| Each session starts fresh | Experiences carry forward |
| Failures are discarded | Failures become stories with hypotheses |
| No intuition builds | Pattern recognition develops |
| Creative ideas come from nowhere | Creative ideas are informed by context |
| Systematic exploration is manual | Past work is visible, gaps are apparent |

The agent already thinks. Memory helps it think with the benefit of everything it has learned.

---

## Appendix: Stories from v1.5

These are the actual learnings from our v1.5 experiments—the first entries in memory.

### Story: The Validation Lie

**When:** December 2025
**Setup:** 27 strategies tested with various indicators and zigzag thresholds
**What happened:**

We initially celebrated 100% success—all strategies exceeded 55% validation accuracy. Some hit 71%. Then we looked at test accuracy.

| Strategy | Validation | Test | Gap |
|----------|------------|------|-----|
| v15_rsi_zigzag_3_5 | 71.2% | 55.5% | 15.8pp |
| v15_rsi_zigzag_1_5 | 65.4% | 64.2% | 1.2pp |
| v15_adx_only | 58.4% | 50.0% | 8.4pp |

The 71% "winner" was actually random noise. The 64% "underperformer" was real signal.

**Learning:** Validation accuracy can lie. Test accuracy is truth. A val-test gap > 5pp is a red flag.

**Open question:** Why does larger zigzag cause overfitting? Is it fewer labels → model memorizes patterns?

---

### Story: RSI is King (On 1h)

**When:** December 2025
**Setup:** Testing 9 different indicators solo on 1h EURUSD
**Results:**

| Indicator | Test Accuracy |
|-----------|---------------|
| RSI | 61.4% |
| DI | 60.3% |
| Stochastic | 59.7% |
| Williams %R | 59.1% |
| CCI | 58.2% |
| MFI | 55.6% |
| ADX | 50.0% (no signal) |

**Learning:** RSI and DI have real signal. ADX alone has none. MFI is weak.

**Open question:** Why does RSI work better than Stochastic? Both measure momentum. Is it the calculation? The default period?

---

### Story: Signals Compose (But Plateau)

**When:** December 2025
**Setup:** Combining validated signals
**Results:**

```
RSI alone:           64.2% test
RSI + DI:            64.8% test  (+0.6pp)
RSI + DI + Stoch:    64.8% test  (+0.0pp)
```

**Learning:** Two complementary signals (momentum + trend) improve results. Adding a third (more momentum) doesn't help.

**Hypothesis:** Maybe complementary means "measuring different things." RSI + DI measure different dimensions. RSI + Stochastic both measure momentum—redundant.

**Open question:** Would two trend indicators (DI + something else) also plateau? Is it about indicator count or dimension count?

---

### Story: 5m Disappoints

**When:** December 2025
**Setup:** Same winning approach (RSI + DI + zigzag 1.5%) but on 5m instead of 1h
**Result:** 60.8% test accuracy (vs 64.8% on 1h)

**Observations:**
- 5m has ~12x more data points than 1h
- RSI oscillates much faster, potentially more noise
- Same NN architecture, same zigzag threshold, same everything else
- The degradation was significant but not catastrophic

**Hypotheses generated:**
1. **H1: NN too small** — 5m complexity needs more capacity. We tested [128, 64] → slight improvement to 61.5%
2. **H2: RSI not suited for 5m** — RSI was designed for daily data. Maybe fundamentally wrong for fast timeframes.
3. **H3: Zigzag threshold wrong** — 1.5% might be too coarse for 5m. Testing 0.5% (pending results).
4. **H4: Missing context** — Maybe 5m needs 1h as smoothing context, not as standalone.

**Status:** H1 partially confirmed (helped a little). H3 pending. H2 and H4 untested.

**Open question:** What makes an indicator work on faster timeframes? Is it about the indicator design, the NN capacity, the labeling, or the need for multi-timeframe context?

---

### Story: Zigzag Threshold Matters

**When:** December 2025
**Setup:** Same indicator (RSI), same timeframe (1h), different zigzag thresholds
**Results:**

| Threshold | Test Accuracy | Generalization |
|-----------|---------------|----------------|
| 1.5% | 64.2% | Best |
| 2.0% | 61.3% | Good |
| 3.0% | 61.3% | Good |
| 3.5% | 55.5% | Overfit |

**Learning:** 1.5% is the sweet spot for 1h EURUSD. Larger thresholds create fewer but more dramatic labels—the model memorizes them instead of learning patterns.

**Hypothesis:** The optimal threshold might scale with timeframe. 1h → 1.5%. Daily → maybe 3%? 5m → maybe 0.5%?

**Open question:** Is there a principled way to choose zigzag threshold based on timeframe volatility?

---

### Story: The Best We Found

**When:** December 2025
**Current best:** RSI + DI on 1h EURUSD with zigzag 1.5%
**Test accuracy:** 64.8%

This represents:
- ~15pp above random (50%)
- A validated composition of two complementary signals
- A plateau—adding more indicators doesn't help

**What it took to get here:**
1. Test 9 indicators solo → find RSI and DI have signal
2. Test zigzag thresholds → find 1.5% generalizes best
3. Combine RSI + best threshold → 64.2%
4. Add DI → 64.8%
5. Try adding Stochastic → no improvement (plateau)

**What's next:**
- Multi-timeframe (using 1h as context for 5m)
- Memory models (LSTM to capture RSI trajectories)
- Multi-symbol (does EURUSD learning transfer to GBPUSD?)

---

*Draft v2: 2025-12-28*
