# Autonomous Research Laboratory - Roadmap

## Document Purpose

This document provides the **high-level roadmap** for building the Autonomous Trading Research Laboratory. It defines the major milestones from validated learning through full autonomous operation.

**Related Documents**:

- `vision_north_star.md` - The dream we're building toward
- `architecture_north_star.md` - How the system works (to be updated)
- `v2.0/DESIGN.md` - Detailed v2 design

---

## The Learning Ladder

Each version **enables** the next. We can't skip steps because later capabilities emerge from earlier ones.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        THE LEARNING LADDER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  v1.5 ──────► v2.0 ──────► v2.x ──────► v3 ──────► v4+                      │
│  Validated    Memory       Capability   Automated   Multi-Agent             │
│  Learning     Foundation   Requests     Synthesis   Research                │
│                                                                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │ NN can  │  │ Agent   │  │ Agent   │  │ System  │  │ Parallel│            │
│  │ learn   │  │ remembers│  │ requests│  │ extracts│  │ research│            │
│  │ (proof) │  │ & builds │  │ what it │  │ patterns│  │ streams │            │
│  │         │  │ on past  │  │ needs   │  │ automat.│  │         │            │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘            │
│       │            │            │            │            │                  │
│       │            │            │            │            │                  │
│  PROVES:      ENABLES:      ENABLES:     ENABLES:    ENABLES:               │
│  Architecture  Informed     System       Learning    10x                    │
│  can work      decisions    evolution    compounds   throughput             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## v1.5: Validated Learning (COMPLETE)

**Goal**: Prove the neuro-fuzzy architecture can actually learn.

**What We Proved**:

- NN achieves 60-65% test accuracy (10-14pp above random)
- RSI + DI combination works best (64.8% test accuracy)
- Learnings compound: RSI + DI > RSI alone
- Validation can lie: test accuracy is truth
- Zigzag 1.5% generalizes best on 1h data

**What We Learned**:

- Some indicators have signal (RSI, DI), some don't (ADX solo)
- Composition helps but plateaus (two indicators, not three)
- Overfitting is detectable via val-test gap

**Hypotheses Generated**:

- H1: Multi-timeframe might break the 64.8% plateau
- H2: LSTM might capture temporal patterns
- H3: Cross-symbol training might improve generalization

**Status**: COMPLETE. See `v1.5/RESULTS.md` and `v1.5/LEARNINGS_FOR_V2.md`

---

## v2.0: Memory Foundation (CURRENT)

**Goal**: Agent remembers experiments and uses memory to design better strategies.

**The Problem**:

The agent currently has zero memory. It:

- Repeats the same strategies
- Doesn't know what worked or why
- Can't form or pursue hypotheses
- Explores randomly instead of systematically

**The Solution**:

Memory injected as context. The agent sees:

- Experiment records: what was tried, what happened
- Hypotheses: ideas to test, with status
- Learnings: synthesized patterns (initially curated)
- Requests: capabilities the agent wishes it had

**Key Components**:

1. **Experiment records** — Stored after each cycle
2. **Hypothesis tracking** — Agent generates, system tracks status
3. **Research summary** — Curated learnings injected into prompt
4. **Capability requests** — Agent can express what it needs

**Success Criteria**:

- Agent doesn't repeat identical experiments
- Agent references past results when designing
- Agent generates testable hypotheses
- Strategy quality improves over time (not random variation)

**What This Enables**:

- Agent can notice ceilings ("I've hit 64.8% three times")
- Agent can form hypotheses ("maybe I need multi-TF")
- Agent can request capabilities ("I need 5m data")
- System can evolve based on agent insights

**Details**: See `v2.0/DESIGN.md`

---

## v2.x: Incremental Improvements

These enhancements build on v2.0 as we learn what works:

### v2.1: Richer Experiment Records

- Store more context with each experiment
- Better matching for "similar past experiments"
- Agent sees relevant history, not just recent

### v2.2: Capability Request System

- Agent can formally request new indicators, data, architectures
- Human reviews and prioritizes requests
- Agent learns what capabilities exist

### v2.3: Automated Hypothesis Updates

- System automatically marks hypotheses tested/validated
- Agent sees which hypotheses are worth pursuing
- Reduces manual curation burden

---

## v3: Automated Synthesis

**Goal**: Learning compounds without manual curation.

**The Problem**:

In v2, humans curate the research summary. This doesn't scale.

**The Solution**:

Periodic synthesis job that:

- Analyzes experiment history for patterns
- Generates/updates learnings automatically
- Detects contradictions for investigation
- Prioritizes hypotheses by expected value

**Key Components**:

- Pattern detection across experiments
- Automatic learning extraction
- Contradiction detection
- Hypothesis prioritization

**Success Criteria**:

- Research summary updates automatically
- Novel insights emerge without human synthesis
- Agent discovers patterns humans might miss

**Prerequisites**: v2 complete and proven valuable

---

## v4: Multi-Agent Research

**Goal**: Specialized agents collaborate on research.

**The Problem**:

A single agent can only pursue one line of inquiry at a time.

**The Solution**:

Specialized roles:

| Agent | Responsibility |
|-------|---------------|
| **Researcher** | Creative strategy generation, hypothesis formulation |
| **Analyst** | Deep result analysis, pattern recognition |
| **Director** | Resource allocation, research stream prioritization |
| **Board** | Human interface, strategic direction |

**Key Capabilities**:

- Parallel research streams
- Different agents for different hypothesis areas
- Strategic resource allocation
- Natural language interaction

**Prerequisites**: v3 complete (shared knowledge foundation)

---

## v5+: Future Possibilities

**Meta-Learning**: Agent learns what kinds of experiments are fruitful
- "Adding dimensions helps more than tuning parameters"
- "Cross-validation catches overfitting earlier"

**Architecture Evolution**: Agent proposes new architectures
- "What if different NN regions for different regimes?"
- "Attention mechanism might capture indicator interactions"

**Cross-System Learning**: Transfer learning across symbols/timeframes
- "EURUSD patterns apply to GBPUSD with modifications"
- "1h learnings inform 5m strategy design"

These emerge from the foundation—we don't pre-build them.

---

## Constraints

**Budget**: $5/day for LLM costs (adjustable based on ROI)

**Compute**: Leverage existing KTRDR workers for training/backtesting

**Data**: Focus on forex pairs with comprehensive historical data

**Architecture**: Stay within neuro-fuzzy paradigm (interpretable strategies)

**Development Philosophy**: Memory-first. Don't add agent complexity until memory proves value.

---

## Success Metrics by Version

| Metric | v1.5 | v2 | v3 | v4 |
|--------|------|----|----|-----|
| Strategies tested/week | 27 (manual) | 50+ | 100+ | 200+ |
| Duplicate experiments | N/A | 0 | 0 | 0 |
| Agent cites past results | N/A | >80% | >90% | >90% |
| Hypotheses generated | Manual | 5+/week | 10+/week | 20+/week |
| Human curation required | Full | Weekly | Monthly | Minimal |
| Ceiling-breaking events | N/A | 1+ | 3+ | 5+ |

---

## The North Star

> "A research partner that works while you don't, accumulates knowledge, discovers capabilities it needs, and engages in meaningful discussion about what it's learned."

The path there:

1. **v1.5** ✓ Proved: The architecture can learn
2. **v2** ← Current: Memory enables directed research
3. **v3** Next: Learning compounds automatically
4. **v4** Future: Parallel research at scale

Not automation. **Augmentation.**

---

*Document Version: 2.0*
*Last Updated: December 2024*
*Key Change: Consolidated v2/v3, added learning ladder, refined version progression*
