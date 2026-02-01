---
title: "Reflection: From Synthesis to Experiment"
date: 2026-02
stage: reflection
builds_on:
  - 03_synthesis_researcher_genome_evolution.md
leads_to:
  - 04_primordial_soup_experiment_design.md
contributors: Karl + Claude
summary: |
  Captures the thinking that bridged abstract synthesis to concrete experiment
  design. The key move: stop theorizing, start with a primordial soup and see
  what emerges.
---

# Reflection: From Synthesis to Experiment

## 1. Where We Were

After the synthesis doc, we had:
- A coherent model (phylogeny, researcher genomes, guided evolution)
- A genome structure sketch (traits → phenotypes → competencies)
- Director-as-environment-shaper framing
- Open questions and an unnamed "nagging thing"

The risk: continuing to theorize without grounding in reality.

## 2. The Turn Toward Practical

Karl's instinct: "Something is still nagging me, but I don't want perfect to be the enemy of good. We need to capture our thinking, start with something, then continue as we discover things."

This led to the question: **how do we get super practical from here?**

We identified four paths:
- A: Characterize the current researcher (map it to the genome model)
- B: Run and observe (let reality inform theory)
- C: Design one trait → prompt translation
- D: Define the amoeba → bacteria transition

Karl wanted a combination: **run an experiment with brutal selection AND figure out what the transition marker means.**

## 3. The Primordial Soup Idea

Karl's framing: "Think the Earth a billion years ago. It must have been fairly brutal."

This crystallized the experiment design:
- Simple amoeba-genome researchers (minimal traits)
- Brutal selection (50% die each generation)
- Reproduction with mutation
- Run for several generations
- See what emerges

The key insight: **we don't need to know what will happen. We need to create conditions where something CAN happen, then observe.**

## 4. Key Design Decisions

### Continuous vs Boolean Genome

We debated continuous traits (0.0-1.0) vs boolean/discrete.

Decision: **Coarse buckets (off/low/high)** for v0.

Reasoning:
- Simpler to debug and observe
- Easier crossover
- If patterns don't emerge with simple genomes, continuous won't save us
- 27 possible combinations is enough for selection, small enough to reason about

### Fitness Function

ChatGPT contributed a solid 3-layer approach:
- Layer A: Gates (instant death for garbage)
- Layer B: Performance score (the actual fitness)
- Layer C: Novelty bonus (prevent monoculture)

Key insights we kept:
- **Stability beats hero returns** — penalize variance across slices
- **Costs from day one** — no fake edges
- **Minimum trades** — no coward strategies
- **Gates are cheap** — fail fast, don't waste compute

For v0, we simplified:
- 3 micro-slices (different time periods)
- fitness = mean(Sharpe) - mean(DD) - std(Sharpe)
- Skip novelty bonus initially (add if we see monoculture)

### The Bacteria Transition

We needed to define what "leveling up" from amoeba would look like.

The answer: **cooperation / cross-referencing**.

| Amoeba | Bacteria |
|--------|----------|
| Isolated, only sees own experiments | Reads the shared soup |
| Each experiment starts fresh | Builds on others' learnings |
| No awareness of population | Knows what others have tried |

This maps to biological endosymbiosis — the jump wasn't "better at the same thing" but "can do a new kind of thing."

## 5. What We're Really Testing

The experiment isn't about finding a winning trading strategy.

It's about testing: **does selection pressure on researcher genomes produce meaningful evolution?**

Specifically:
- Do certain trait combinations get selected for?
- Do later generations outperform earlier ones?
- Do patterns emerge that we didn't explicitly design?

Even "null results" (traits don't matter, random noise dominates) would be informative.

## 6. The Nagging Thing (Still Unnamed)

We still don't know what's nagging. Candidates:
- Over-engineering the genome when simpler might work
- Is phylogeny actually the right frame?
- Memory's role (barely discussed)
- How researchers share (assumed, not designed)

The experiment might surface it. That's partly the point.

## 7. Next: Translate to KTRDR

The synthesis and experiment design are abstract. The next step is getting concrete:

- How do genome traits translate to actual prompts?
- What's the generation harness look like in code?
- How do we wire this into the existing research agent?
- What data do we use?

This is where theory meets the codebase.

---

*Date: February 2026*
*Status: Reflection complete, moving to implementation*
