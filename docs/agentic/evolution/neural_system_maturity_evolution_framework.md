---
title: "Neural System Maturity & Evolution Framework"
date: 2026-01
stage: brainstorm
superseded_by: 03_synthesis_researcher_genome_evolution.md
contributors: Karl + ChatGPT
summary: |
  Defines what evolution looks like (vs what forces it). Introduces capability
  accumulation over strategy refinement, the competency lattice, and stages as
  emergent plateaus. Provides detailed competency spectrum from foundational
  (infant) through adult.
key_insights:
  - Evolution via capabilities, not strategies
  - Stages are labels applied after the fact, not gates
  - Competencies cluster into stages when enough are present
  - Complexity is earned, not injected
---

# Neural System Maturity & Evolution Framework

> **Purpose**
> This document captures the discoveries, reasoning, and conceptual framework developed during the conversation on how to evolve an automated research-and-training system toward increasing intelligence, novelty, and structural complexity.
> It is intended as a *handoff artifact* for a coding agent and as a stable reference for future design decisions.
>
> **Status**: Superseded (see synthesis doc) — preserved for reasoning history

---

## 1. Core Problem Statement

The current system operates as a closed automated loop:

1. A research agent proposes a strategy or model
2. The strategy is trained
3. The model is backtested
4. Training dynamics and backtest metrics are assessed
5. Learnings are extracted
6. The loop repeats

### Observed limitations

- Each iteration tends to remain *locally incremental*
- The system fixates on a single promising idea (e.g. RSI-like behavior)
- Novelty is accidental rather than intentional
- Complexity does not naturally accumulate
- There is no clear mechanism for:
  - combining learnings
  - evolving structure
  - forming specialized components

The central question:

> **How do we design a system that evolves toward increasing intelligence and structural complexity, without hard-coding domain knowledge or rehashing existing patterns?**

---

## 2. Key Insight: Evolution via Capabilities, Not Strategies

A crucial reframing emerged:

- **Strategies are transient**
- **Capabilities are cumulative**

Human learning does not progress by discovering one optimal behavior and refining it forever. Instead:

- It accumulates *skills*
- Skills interact
- Structure emerges once enough skills coexist

Therefore:

> The system should not evolve by chasing better strategies, but by accumulating *capabilities*.

---

## 3. Stages of Maturity as Emergent Plateaus

### Rejecting arbitrary thresholds

- Fixed counts (e.g. "1,000 experiments") are arbitrary
- Nature does not evolve by counters
- Babies do not know they are practicing

Instead:

> Stages of maturity are **labels applied after the fact** when enough capabilities are present simultaneously.

Stages are:

- Descriptive, not prescriptive
- Overlapping
- Gradual
- Potentially reversible

---

## 4. Organic Analogy: Human Development

The biological analogy used throughout:

- A baby performs many random, low-quality experiments
- Micro-adjustments accumulate unconsciously
- One day, balance emerges
- Walking is not learned directly, it *appears*

Mapping to the system:

- Early iterations may look random
- Learning happens below the level of explicit objectives
- Structural coherence emerges once prerequisites align

---

## 5. Global Competency Map (Capability Lattice)

Instead of a linear ladder, we define a **capability lattice**:

- A long list of competencies
- Ordered roughly from primitive to advanced
- Not strictly sequential
- Partially fulfillable

Stages correspond to **dense clusters** of competencies.

---

## 6. Competency Spectrum (Draft)

### A. Foundational Competencies (Infant / Baby)

These reflect *basic perceptual and stability abilities*.

- Distinguish signal from pure noise better than chance
- Produce temporally coherent outputs (no random flip-flopping)
- React differently to different input regimes
- Maintain numerical stability during training
- Fail in bounded ways (loss does not catastrophically explode)
- Show repeatable behavior under similar conditions
- Demonstrate that learnings influence future iterations

If most of these are absent, the system is considered *pre-baby*.

---

### B. Sensorimotor Competencies (Baby → Toddler)

This stage corresponds to "learning to stand".

- Detect persistent directional bias without explicit instruction
- Delay or suppress action when confidence is low
- Reduce drawdown relative to random baselines
- Exhibit regime sensitivity (behavior changes with conditions)
- Combine multiple inputs without collapsing into noise
- Retain useful internal structure across retraining
- Demonstrate output invariance to small input perturbations

When most of these are present:

> The system is no longer flailing.

This marks **toddler-stage maturity**.

---

### C. Coordinated Competencies (Child)

Walking, running, coordination.

- Combine multiple learned behaviors coherently
- Implicitly balance risk vs opportunity
- Maintain performance across datasets or regimes
- Reuse learned substructures across strategies
- Exhibit early specialization (components outperform in niches)
- Recover from errors instead of compounding them
- Display sensitivity to delayed rewards

---

### D. Abstract & Strategic Competencies (Adolescent)

Meta-cognition begins to appear.

- Modify internal objective trade-offs
- Explore novelty intentionally when progress stalls
- Detect diminishing returns
- Allocate capacity to promising subspaces
- Dynamically balance exploration vs exploitation
- Detect and revise faulty internal assumptions
- Preserve existing skills while acquiring new ones

---

### E. Modular Cognitive Competencies (Adult)

Brain-like organization.

- Persistent specialized regions (emergent, not hard-coded)
- Multi-timescale reasoning
- Context-aware decision policies
- Rich action space beyond buy/sell
- Cross-domain signal fusion (price, structure, external data)
- Internal abstractions reused across tasks
- Self-stabilizing learning dynamics

---

## 7. Stage Transitions via Capability Density

### Critical rule

> **No stage is unlocked by a single skill.**

Instead:

- Each stage corresponds to a *bundle of competencies*
- A stage is considered "passed" when *most* competencies in its cluster are demonstrated
- Partial presence is expected
- Regression is allowed

Example (Baby → Toddler):

The system becomes toddler-stage when it consistently:

- Beats random baselines
- Produces stable outputs
- Avoids catastrophic failure
- Responds to regime changes
- Exhibits at least one stable behavioral motif
- Learns faster in later iterations than earlier ones
- Retains useful structure

---

## 8. Novelty vs Performance: Dual-Objective Evolution

Another key discovery:

- Performance alone leads to local optima
- Novelty alone leads to chaos

### Proposed solution

Introduce a **meta-assessment layer** that evaluates:

- Performance
- Stability
- Novelty (distance from prior approaches)
- Structural contribution (new capabilities added)

Then:

- Dynamically choose what the *next iteration optimizes for*
- Allow:
  - performance-seeking iterations
  - novelty-seeking iterations
  - falsification / failure-seeking iterations

Failures are treated as *validated hypotheses*, not waste.

---

## 9. Complexity Growth Without Arbitrary Design

### Avoiding a central architect

Nature did not design the brain.

Instead, evolution:

- Selected for capabilities
- Allowed structure to emerge

### Codified equivalent

The system does not design its own architecture freely.

It is governed by:

- A **competency vocabulary**
- A **stage-aware growth policy**
- **Permissions** that unlock structural complexity

Examples of unlocks:

- Allow deeper models once stability plateaus
- Allow multiple sub-networks once coordination appears
- Allow richer action spaces once prediction stabilizes

Complexity is *earned*, not injected.

---

## 10. Agent-Oriented Codification

All of the above is explicitly designed to be LLM-agent compatible.

Agents can:

- Assess competencies qualitatively and quantitatively
- Argue whether a competency is present
- Track capability emergence over time
- Decide which objective to prioritize next
- Recommend structural evolution steps

The human role shifts from architect to **evolutionary rule designer**.

---

## 11. Key Takeaways

- Evolution happens through **capability accumulation**, not strategy refinement
- Stages are **emergent plateaus**, not hard gates
- Competencies are more fundamental than indicators or architectures
- Novelty must be explicitly valued
- Complexity should be unlocked via demonstrated balance and coordination

> **You don’t evolve by chasing better strategies.  
> You evolve by quietly accumulating capabilities—until structure emerges.**

---

## 12. Open Next Steps (Intentionally Left Open)

- Refine and formalize the competency list
- Define assessment signals per competency
- Decide how stage labels influence search policies
- Translate this framework into concrete agent prompts
- Define governance and safety constraints

This document is intentionally conceptual but precise, serving as a stable foundation for implementation and iteration.
