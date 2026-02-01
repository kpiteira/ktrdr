---
title: "Research System Evolution: Selection Pressure & Forcing Functions"
date: 2026-01
stage: brainstorm
superseded_by: 03_synthesis_researcher_genome_evolution.md
contributors: Karl + Claude
summary: |
  Explores what forces drive evolution in the research system. Identifies the
  "Baby forever" problem (accumulation without evolution) and proposes selection
  mechanisms: resource scarcity, environmental pressure (Research Director), and
  internal drive. Introduces behavioral signals for detecting stage transitions.
key_insights:
  - Evolution requires selection pressure, not just accumulation
  - Research Director as observer/guide, not promoter
  - Stages should be recognized, not promoted to
---

# Research System Evolution: Brainstorm

## Status: Superseded (see synthesis doc) — preserved for reasoning history

This document captures thinking about how the KTRDR research system evolves from simple to sophisticated — not just in performance metrics, but in capabilities, behavior, and research style.

This is NOT a design doc yet. It's a record of an ongoing conversation about what evolution means and what drives it.

---

## The Problem: Accumulation Without Evolution

The current system runs research cycles in Baby stage. Each cycle produces an experiment record, potentially validates a hypothesis, and adds to memory. But nothing forces the system to grow.

**What happens today:**
- Agent designs simple strategies (1-2 indicators, tiny NNs)
- Experiments accumulate in memory
- Agent reads recent experiments and designs the next one
- Gates are low (10% accuracy, 10% win rate) — nearly everything passes
- No mechanism demands increasing sophistication

**What's missing:**
- No selection pressure (every experiment is "fine")
- No escalating challenge (goals stay the same forever)
- No complexity incentive (simple strategies are easier, so why try harder?)
- No threshold-crossing detection (nothing notices "this agent is behaving differently now")

**Result:** Endless string of small learnings. No evolution. A Baby forever.

---

## The Vision: Organic Maturity Progression

Inspired by biological development, the system should evolve like a living organism — not through hard gates ("pass 35% accuracy 5 times = Toddler") but through behavioral change that an observer can recognize.

### Human Development Analogy

A child doesn't get "promoted" to the next stage. A pediatrician observes behavioral patterns and recognizes: "this child is now speaking in sentences" or "this child can reason about abstract concepts." The transition is gradual, continuous, and multi-dimensional.

Similarly, a Research Director agent should observe the system's behavior and recognize stage transitions naturally:

> "Over the last 30 experiments, this agent has started building on successes 80% of the time, references history in design rationale, and has validated 3 hypotheses. This looks like Toddler behavior."

### Key Principle

There should be no explicit "gate" from one stage to another. Instead, a combination of:
1. Mechanisms that incentivize evolution (selection pressure)
2. Observation that recognizes evolution has occurred (behavioral assessment)

---

## Two Dimensions That Need Unifying

Currently the project has two separate progression models:

### 1. Performance Maturity (Baby → Teenager)
Defined in v2.5/DESIGN.md. About gate strictness — how reliable must strategies be?

| Stage | Accuracy | Loss | Win Rate | Focus |
|-------|----------|------|----------|-------|
| Baby | 10% | -50% | 10% | Explore, gather data |
| Toddler | 35% | 0% | 30% | Validate early patterns |
| Child | 45% | 10% | 40% | Consolidate learnings |
| Pre-teen | 55% | 15% | 45% | Optimize within patterns |
| Teenager | 60% | 20% | 50% | Production ready |

### 2. Capability Complexity (v2 → v5)
Defined in roadmap.md. About what the system can do.

| Version | Capability |
|---------|-----------|
| v2 | Memory, hypotheses, capability requests |
| v3 | Automated synthesis, pattern extraction |
| v4 | Multi-agent research, parallel streams |
| v5+ | Meta-learning, architecture evolution |

### The Insight

These need to be unified into a single organic progression. A Baby researcher doesn't just have low performance — it also has simple capabilities and naive behavior. A Toddler doesn't just have higher accuracy — it also behaves differently, designs differently, learns differently.

---

## Proposed Developmental Dimensions

Evolution should be measured across multiple dimensions simultaneously, like human development spans motor skills, cognition, language, and social skills.

### Dimension 1: Strategy Complexity
What the system designs.

| Stage | Characteristic |
|-------|---------------|
| Baby | 1-2 indicators, fixed params, tiny NN (8-16 neurons) |
| Toddler | 2-3 indicators, starts exploring param ranges, small NN (32-64) |
| Child | Compositions that work together, medium NN, starts noticing "what works where" |
| Pre-teen | Multi-timeframe, regime awareness, larger NNs |
| Teenager | Context-dependent architectures, specialized pathways |
| Adult | Brain-like regions, attention mechanisms, meta-strategies |

### Dimension 2: Learning Behavior
How the system learns from experience.

| Stage | Characteristic |
|-------|---------------|
| Baby | Pure exploration, accepts any result, no pattern recognition |
| Toddler | Starts building on successes, avoids obvious failures |
| Child | Forms hypotheses, pursues them systematically |
| Pre-teen | Recognizes ceilings, requests new capabilities |
| Teenager | Synthesizes patterns across experiments, meta-learning |
| Adult | Proposes architectural innovations, cross-domain transfer |

### Dimension 3: Memory Usage
How the system uses accumulated history.

| Stage | Characteristic |
|-------|---------------|
| Baby | Reads last N experiments, doesn't really synthesize |
| Toddler | References specific past results, builds on them |
| Child | Tracks hypotheses, validates/refutes them |
| Pre-teen | Sees patterns across many experiments |
| Teenager | Has accumulated "wisdom" — knows what works in what context |
| Adult | Has meta-knowledge — knows how to learn efficiently |

### Dimension 4: Research Style
The "character" of the research.

| Stage | Characteristic |
|-------|---------------|
| Baby | Curious, tries everything, no judgment |
| Toddler | Starting to have preferences based on experience |
| Child | Can explain why it's trying something |
| Pre-teen | Strategic, allocates effort to promising directions |
| Teenager | Focused, deep exploration of working patterns |
| Adult | Wise, knows when to explore vs exploit |

### More Dimensions to Explore
- Error analysis sophistication
- Hypothesis quality and specificity
- Self-awareness (knowing what it doesn't know)
- Communication quality (how it reports findings)
- Resource efficiency (budget per insight)

---

## Selection Pressure: What Drives Evolution?

In biology, evolution requires selection pressure. Without it, you get random genetic drift — no direction, no progress.

### Why the Current System Doesn't Evolve

There's no consequence for staying simple. The agent gets the same budget, same gates, same treatment whether it designs a trivial strategy or a sophisticated one. Nothing selects for complexity.

### Candidate Selection Mechanisms

#### A. Resource Scarcity
Limited budget forces competition between ideas.

- **Hypothesis budgeting**: 10 hypotheses compete for 3 testing slots. Director picks based on expected value. Unfunded hypotheses are archived (not tested).
- **Strategy survival**: Only strategies that pass gates get to "reproduce" (inform next designs). Failed strategies contribute less to memory.
- **Memory decay**: Low-impact experiments fade over time. Only meaningful work persists. If you don't build on learnings, they disappear.

*Evolutionary analog: Food is scarce → only fit organisms survive → fitness increases over generations.*

#### B. Environmental Pressure (Escalating Challenges)
Something external demands growth.

- **Research Director sets goals** that get progressively harder:
  - Early: "Find any indicator that works"
  - Later: "Break the 65% ceiling"
  - Later: "Find a strategy that works across multiple symbols"
- If the agent can't meet goals, resources shift to directions that show promise.

*Evolutionary analog: Climate changes → organisms must adapt → complexity increases.*

#### C. Internal Drive (Curiosity / Dissatisfaction)
The agent itself wants to evolve.

- **Ceiling detection**: "I've hit 64.8% three times. This is boring. I need something new."
- **Novelty seeking**: Preference for experiments that explore new territory over repeating what's known.
- **Ambition**: "I want to design something more sophisticated than I have before."

This is less like natural selection and more like human drive for mastery.

*Analog: Humans don't just survive — we're intrinsically curious and want to grow.*

### A Possible Synthesis

All three mechanisms working together:

```
Research Director (Environmental Pressure)
  │
  ├── Observes behavior patterns across experiments
  ├── Sets increasingly ambitious challenges
  ├── Allocates resources to promising directions
  └── Lets unpromising directions "die off"
          │
          ▼
Selection Mechanisms (Resource Scarcity)
  │
  ├── Hypothesis budgeting (N compete for M < N slots)
  ├── Memory compaction (low-impact fades, high-impact persists)
  ├── Goal escalation (bar keeps rising)
  └── Complexity nudging ("you've done 20 simple strategies...")
          │
          ▼
Researcher Agent (Internal Drive)
  │
  ├── Designs experiments within Director's constraints
  ├── Receives feedback that shapes future designs
  ├── Detects ceilings and gets "bored"
  └── Naturally evolves because environment demands it
```

---

## The Invisible Threshold

How stages are "crossed" without explicit promotion:

### Baby Behavior Pattern
- Tries random indicators
- Doesn't reference past experiments much
- No strong preferences
- Small NNs, simple strategies
- Hypotheses are vague ("maybe RSI works?")

### Toddler Behavior Pattern
- Builds on what worked before
- References past experiments explicitly
- Has preferences ("RSI works better than MACD")
- Starts requesting "I want to try this with a bigger NN"
- Hypotheses are specific ("RSI+DI at 1h with zigzag 1.5% should exceed 65%")

### How a Research Director Detects This

Possible behavioral signals:
- **Build-on-past rate**: % of experiments that explicitly extend prior work
- **Hypothesis specificity**: Vague vs. precise, testable predictions
- **Reference density**: How often past experiments are cited in design rationale
- **Success trajectory**: Are recent experiments outperforming earlier ones?
- **Complexity trend**: Are strategies getting more sophisticated over time?
- **Ceiling awareness**: Does the agent recognize and articulate when it's stuck?
- **Exploration vs. exploitation balance**: Is the agent starting to focus?

The Director doesn't promote — it observes and labels:
> "Current developmental assessment: early Toddler. Evidence: build-on-past rate 70% (vs 20% at start), hypotheses now reference specific metrics, 3 validated hypotheses in last 20 experiments."

---

## Open Questions

### Fundamental
- What exactly is the forcing function? We know it needs to exist, but the precise mechanism isn't clear.
- Is the Director an LLM-based agent observing periodically? A rules-based scorer? Both?
- Does capability unlock (new tools available at higher stages) help or hurt the organic feel?
- How do we avoid the agent gaming the signals? (e.g., always citing past work without actually building on it)

### Practical
- When does the Director run? After every N experiments? On a schedule? On demand?
- What is the Director's output? A developmental assessment? Updated goals? Resource allocation?
- How does memory compaction work without losing valuable early learnings?
- What does "complexity nudging" look like in practice? Is it in the prompt? In the goals?

### Philosophical
- Is it better to have the evolutionary pressure be external (Director pushes) or emergent (system naturally evolves because accumulated memory creates richer context)?
- In nature, evolution is undirected — selection pressure + random variation = emergent complexity. Should we aim for that, or is directed evolution (goals + incentives) more practical?
- At what point does the Research Director become the real intelligence, with the Researcher just executing? How do we keep the Researcher as the creative force?

---

## Connection to Existing Architecture

### What Already Exists
- **Memory system** (`ktrdr/agents/memory.py`): Experiment records, hypothesis tracking
- **Gate system** (`ktrdr/agents/gates.py`): Performance thresholds per stage
- **Assessment worker** (`ktrdr/agents/workers/assessment_worker.py`): Per-experiment analysis
- **Design worker** (`ktrdr/agents/workers/design_worker.py`): Strategy generation with history context
- **Multi-research** (v2.6): Parallel research execution

### What Would Need to Be Built
- **Research Director agent**: Observes, assesses, guides
- **Synthesis mechanism**: Distills patterns from accumulated experiments
- **Goal/challenge system**: Escalating objectives for the Researcher
- **Behavioral scoring**: Metrics that capture developmental dimensions
- **Memory evolution**: Compaction, decay, and promotion of learnings

### Related Docs
- `docs/agentic/vision_north_star.md` — The ultimate dream
- `docs/agentic/roadmap.md` — The learning ladder (v2→v5)
- `docs/agentic/v2.0/PHILOSOPHY.md` — Memory as stories, not rules
- `docs/agentic/v2.5/DESIGN.md` — Current Baby stage + maturity table
- `docs/agentic/architecture_north_star.md` — Multi-agent organization

---

*Document Version: 0.1 (brainstorm)*
*Date: January 2026*
*Status: Active exploration — not yet actionable*
*Contributors: Karl + Claude*
