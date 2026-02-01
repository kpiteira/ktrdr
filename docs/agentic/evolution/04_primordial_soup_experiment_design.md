---
title: "Primordial Soup: v0 Evolution Experiment"
date: 2026-02
stage: experiment-design
status: ready-for-implementation
builds_on:
  - 03_synthesis_researcher_genome_evolution.md
contributors: Karl + Claude + ChatGPT (fitness function input)
summary: |
  Concrete design for the first evolution experiment. Simple amoeba-genome
  researchers with brutal selection, reproduction with mutation, run for
  several generations. Goal: observe if selection pressure produces emergent
  patterns in trait combinations.
---

# Primordial Soup: v0 Evolution Experiment

## 1. Purpose

Test the core hypothesis: **can selection pressure on researcher genomes produce meaningful evolution?**

This is not about finding a winning strategy. It's about observing whether:
- Certain trait combinations get selected for
- Later generations outperform earlier ones
- Patterns emerge that we didn't explicitly design

Think: Earth a billion years ago. Brutal, simple, fast.

---

## 2. The Amoeba Genome (v0)

Three traits, three values each. Deliberately minimal.

```yaml
amoeba_genome_v0:
  novelty_seeking:
    values: [off, low, high]
    meaning:
      off: Systematic exploration (try indicators in order)
      low: Mild randomness in choices
      high: Random/creative combinations

  skepticism:
    values: [off, low, high]
    meaning:
      off: Accepts results at face value
      low: Basic sanity checks
      high: Demands robustness, questions everything

  memory_depth:
    values: [off, low, high]
    meaning:
      off: Each experiment starts fresh
      low: References last 2-3 experiments
      high: Synthesizes patterns across full history
```

**Total genome space**: 3 × 3 × 3 = 27 possible combinations

This is small enough to observe patterns, large enough for selection to matter.

---

## 3. Population Dynamics

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Population size | 9-12 | Covers ~1/3 of genome space per generation |
| Experiments per researcher | 1-2 | Keep compute cheap |
| Selection rate | 50% die | Brutal but not extinction |
| Reproduction rate | 2 offspring per survivor | Maintains population |
| Mutation rate | 1 trait per offspring | Slow drift, not chaos |
| Generations | 5-10 | Enough to see trends |

### Generation Lifecycle

```
Generation N:
│
├── Each researcher designs 1-2 experiments
├── Experiments run (training + backtesting)
├── Fitness evaluated for each researcher
│
├── SELECTION: Bottom 50% die
│
├── REPRODUCTION: Each survivor spawns 2 offspring
│   └── Each offspring has 1 random trait mutated (±1 level)
│
└── Generation N+1 begins
```

---

## 4. Fitness Function

### Layer A: Gates (Instant Death)

Binary checks. Fail any → fitness = -∞, researcher dies immediately.

| Gate | Threshold | Why |
|------|-----------|-----|
| Minimum trades | ≥ 30 in eval window | Prevents "do nothing" coward strategies |
| Maximum drawdown | < 35% | Stops exploding candidates from breeding |
| Action diversity | Not trivially all-long or all-short | Basic sanity |
| Cost-aware | Evaluated with spread/slippage/fees | Blocks fake edges |

### Layer B: Performance Score

Evaluated across **3 micro-slices** (different time periods, same symbol/timeframe).

Per slice `i`:
- `R_i` = net return (after costs)
- `DD_i` = max drawdown
- `S_i` = Sharpe ratio (mean daily return / std daily return)

**Fitness formula:**

```
fitness = mean(S_i) - λ_dd * mean(DD_i) - λ_var * std(S_i) - λ_cmp * complexity
```

Where:
- `λ_dd` = 1.0 (drawdown penalty)
- `λ_var` = 1.0 (stability penalty — anti-lottery-ticket)
- `λ_cmp` = 0.1 (tiny complexity penalty)

**Complexity** (crude scalar):
- Number of indicators used
- NN parameter count bucket (small/medium/large)

### Layer C: Novelty Bonus (Deferred)

Skip for v0. If we observe monoculture (everyone converges to same genome), add novelty bonus in v1.

---

## 5. Reproduction Mechanics

```python
def reproduce(parent_genome, mutation_rate=1):
    """
    Create offspring with exactly 1 random trait mutated.
    Mutation moves trait up or down by 1 level (with clamping).
    """
    child = copy(parent_genome)

    # Pick random trait to mutate
    trait = random.choice(['novelty_seeking', 'skepticism', 'memory_depth'])

    # Mutate by ±1 level
    levels = ['off', 'low', 'high']
    current_idx = levels.index(child[trait])
    direction = random.choice([-1, 1])
    new_idx = clamp(0, 2, current_idx + direction)
    child[trait] = levels[new_idx]

    return child


def next_generation(population, fitness_scores):
    """
    Bottom 50% die. Survivors each produce 2 offspring.
    """
    # Sort by fitness
    ranked = sorted(zip(population, fitness_scores), key=lambda x: x[1], reverse=True)

    # Top 50% survive
    survivors = [genome for genome, score in ranked[:len(ranked)//2]]

    # Each survivor produces 2 offspring
    new_population = []
    for parent in survivors:
        new_population.append(reproduce(parent))
        new_population.append(reproduce(parent))

    return new_population
```

---

## 6. What We're Measuring

### Per Generation
- Genome distribution (how many of each trait value)
- Mean fitness, max fitness, min fitness
- Fitness variance
- Which genomes died, which survived

### Across Generations
- Fitness trend (are later generations better?)
- Trait convergence (do certain values dominate?)
- Diversity trend (is the gene pool narrowing?)
- Surprising patterns (trait combinations we didn't expect)

### End State Questions
1. Did any trait combination consistently survive?
2. Did fitness improve across generations?
3. Did the population converge or stay diverse?
4. Any emergent behaviors we didn't design for?

---

## 7. The Bacteria Transition Marker

This experiment tests amoeba-level evolution. But we should know what "leveling up" would look like.

**Amoeba characteristic**: Each researcher is isolated. Only sees its own experiments.

**Bacteria characteristic**: Researchers can reference and build on OTHER researchers' experiments in the population.

**Transition marker**: The first generation where a researcher demonstrably uses another researcher's learnings ("I saw researcher X tried RSI with these parameters, which failed, so I'm trying...") has crossed into bacteria territory.

This isn't a genome trait — it's a structural capability unlock that would require:
- Shared experiment memory across the population
- Prompt changes to encourage cross-referencing
- Possibly a "cooperation" gene in the genome

We don't implement this in v0. But we watch for signs that it would help.

---

## 8. Practical Considerations

### Compute Budget
- 9-12 researchers × 1-2 experiments × 5-10 generations = 45-240 experiments
- Each experiment: strategy generation + training + backtesting
- Rough estimate: 1-2 days of runtime? (depends on training time)

### Data Requirements
- Need 3 distinct time slices for fitness evaluation
- Same symbol, same timeframe, different periods
- Suggest: 3 non-overlapping months of data

### What Could Go Wrong
- All researchers die (gates too strict) → loosen gates
- No differentiation (all fitness ~same) → gates not strict enough
- Immediate convergence to one genome → add novelty bonus
- Random noise dominates (no trend) → need more generations or larger population

---

## 9. Success Criteria

The experiment "works" if:

1. **Selection has teeth**: Some researchers die each generation (not everyone passes gates)
2. **Fitness improves**: Mean fitness in generation 5 > generation 0
3. **Patterns emerge**: Some trait values are over-represented in survivors
4. **We learn something**: Even negative results ("traits don't matter") are informative

The experiment "exceeds expectations" if:

5. **Emergent behavior**: Researchers start doing something we didn't explicitly prompt for
6. **Clear winners**: Specific trait combinations consistently outperform
7. **The nagging thing clarifies**: We understand what was missing from the theory

---

## 10. Next Steps

1. **Translate to KTRDR** — Map genome traits to concrete prompt/config changes
2. **Build harness** — Generation loop, fitness evaluation, reproduction
3. **Prepare data** — Select symbol, timeframe, define 3 time slices
4. **Run generation 0** — Seed population, run experiments
5. **Iterate** — Run through generations, collect data
6. **Analyze** — What emerged?

---

*Document Version: 0.1*
*Date: February 2026*
*Status: Ready for implementation*
