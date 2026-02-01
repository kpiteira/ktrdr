---
title: "Synthesis: Researcher Genome Evolution"
date: 2026-02
stage: synthesis
status: active
builds_on:
  - BRAINSTORM.md (selection pressure, forcing functions)
  - neural_system_maturity_evolution_framework.md (capability lattice, competencies)
contributors: Karl + Claude
summary: |
  Unifies the two prior brainstorms into a coherent model. The key reframe:
  evolution is phylogeny (populations evolve) not ontogeny (individuals mature).
  The unit of evolution is the researcher genome, not strategies. Guided evolution
  via Director-as-environment-shaper.
---

# Synthesis: Researcher Genome Evolution

## 1. What This Document Is

This synthesizes two prior brainstorms into a unified model for how the research system evolves. It is:

- A **synthesis**, not a design doc — we're capturing thinking, not specifying implementation
- **Active** — meant to evolve as experimentation reveals what works
- **Incomplete** — there's a nagging something we haven't named yet

The prior docs are preserved for reasoning history.

---

## 2. How We Got Here: The Reasoning Path

This section preserves the thinking trail so future readers understand not just *what* we concluded but *why*.

### 2.1 Starting Point: Two Complementary Brainstorms

The two prior docs attacked the same problem from different angles:

- **BRAINSTORM.md** asked: *What forces drive evolution?* (Selection pressure, Research Director, environmental challenges)
- **Neural Framework** asked: *What does evolution look like?* (Capability lattice, competency spectrum, emergent plateaus)

They're complementary layers:
- Neural Framework = ontology (what are we measuring, what does evolution look like)
- BRAINSTORM = dynamics (what creates pressure, what drives change)

You need both. Knowing what to look for doesn't tell you how to induce it. Knowing how to create pressure doesn't tell you what you're pressuring toward.

### 2.2 The First Key Question: Forced or Emergent?

We asked: Does capability accumulation require explicit forcing, or can it emerge naturally?

Two worldviews:

**A. Evolution must be forced.** Left alone, the system finds a local optimum and stays there. You need external pressure.

**B. Evolution can emerge.** Given enough memory and rich context, capabilities accumulate naturally. Sophistication becomes easier than naivety.

**Resolution**: It's a hybrid. Emergence is the baseline hope, but disruption helps break through plateaus. Like biological development — a child grows naturally, but growth spurts often follow challenge or struggle.

### 2.3 The Selection Problem

But emergence requires selection. In biology, natural selection operates continuously — variation happens, environment filters, evolution proceeds.

In the research system: what plays the role of selection during "emergence" periods?

We realized: **maybe nothing, currently**. There's no meaningful selection. Experiments accumulate, but nothing filters signal from noise. This explains the "Baby forever" problem — you can't have emergence without selection. Accumulation without filtering is just noise growing.

**Insight**: Selection is the missing piece, not disruption. Disruption helps break plateaus, but you can't plateau if you never climb. And you can't climb without selection.

### 2.4 The Introspection Exercise

We asked: What would make an LLM researcher (like me) shift from "try RSI, try MACD, try Fisher" to genuinely different thinking?

**What would NOT trigger the shift:**
- More experiments of the same kind (100 data points ≠ insight)
- Being told "try harder" (would just try more indicator combos)
- Having a bigger NN available (would make same strategy with more neurons)

**What MIGHT trigger it:**
- Noticing the ceiling myself (30 experiments all cluster at 45-50%)
- Seeing a contrastive outlier (ONE hit 65%, structurally different)
- Being asked a different question ("explain why strategies plateau")
- Scarcity forcing prioritization ("3 experiments left before archival")

This led to three candidate mechanisms.

### 2.5 Three Mechanisms That All Matter

We identified three mechanisms and initially wondered which was "right." Then realized they're all needed — they're layers, not alternatives:

**Prompt evolution (meta-updating)**: Something observes researcher patterns and injects new context. "You keep doing single-indicator strategies. What assumptions are you making?"

**Resources / survival of the fittest**: Selection at the approach level, not just results. Limited resources force prioritization.

**Swarm**: Multiple researchers with different orientations cross-pollinate. A meta researcher might notice "we're all stuck" in ways individuals can't.

These map to evolutionary mechanisms:
- Variation (swarm provides diversity)
- Selection (resources provide pressure)
- Inheritance (prompt evolution carries forward learnings)

### 2.6 The Genome Insight

If we have a population of researchers with different traits, and selection operates on which researchers succeed, then we're not evolving strategies — we're evolving *researcher genomes*.

This is a level shift:
- Strategies = phenotypes (observable output)
- Researchers = organisms (things that produce phenotypes)
- Researcher prompts/orientations = genotypes (the code that determines behavior)

Evolution operates on genomes, not phenotypes. The strategies are just expressions.

### 2.7 The Phylogeny Reframe

Then we noticed a conceptual confusion: the maturity stages (Baby → Toddler → Adult) sound like individual development (ontogeny), but evolution is population-level (phylogeny).

A single individual doesn't evolve — it develops. Evolution requires populations.

**The reframe**: The research system doesn't mature like a child. It evolves like a species.
- A Baby researcher is an amoeba — it doesn't grow up
- Evolution produces new generations (Toddler-type = bacteria-type)
- Stages are species types in an evolutionary tree, not developmental milestones

### 2.8 What Enabled Biological Transitions

We briefly explored what enabled jumps in biological complexity:

| Transition | Enabler |
|------------|---------|
| Prokaryote → Eukaryote | Endosymbiosis — cooperation, one organism inside another |
| Single-cell → Multicellular | Specialization — cells doing one thing well |
| Simple → Complex body plans | New sensory capabilities — more information |

The jump from amoeba to bacteria isn't "better at the same thing" — it's "can do a new *kind* of thing."

This needs more biology research (separate thread), but the principle is: capability jumps, not just parameter refinement.

### 2.9 Director as God

We asked what role the Director plays. Three options:

- **Creationism**: Director designs each generation (ceiling = Director's imagination)
- **Natural selection**: No director, just environment (too slow, undirected)
- **Guided evolution**: Director shapes the fitness landscape (direction + emergence)

We chose guided evolution. The Director is "god" — not designing creatures, but designing the world they must survive in. This matches the "emergence + disruption" hybrid.

### 2.10 The Nagging Thing

Throughout, there was a feeling that something wasn't complete. We couldn't name it. Rather than force it, we decided to capture current thinking and let experimentation surface what's missing.

Candidates for what might be nagging:
- Over-engineering the genome when simpler might work?
- Is phylogeny actually right, or is there a third option?
- Memory's role (barely discussed)
- How researchers actually share (assumed, not designed)

---

## 3. The Core Reframe: Phylogeny, Not Ontogeny

The original brainstorms mixed two biological concepts:

| Concept | Meaning | Original Framing |
|---------|---------|------------------|
| **Ontogeny** | Individual development (baby → adult) | "The system matures through stages" |
| **Phylogeny** | Species evolution (amoeba → human) | Not explicitly used |

**The problem**: Ontogeny implies one organism that grows up. But a single organism doesn't evolve — it develops. Evolution requires a *population* of organisms with varying traits, where selection pressure favors some over others.

**The reframe**: The research system doesn't mature like a child. It evolves like a species.

| Old Model (Ontogeny) | New Model (Phylogeny) |
|---------------------|----------------------|
| One system matures | Population evolves |
| Baby → Toddler → Adult | Amoeba → Bacteria → Multicellular |
| Same individual, different stages | Different organisms, different generations |
| The system "grows up" | The species "evolves" |

Implications:
- A Baby researcher *is* an amoeba. It doesn't grow up. It has a fixed genome.
- Evolution produces new generations — more complex researcher types
- "Stages" aren't developmental milestones, they're *species types* in an evolutionary tree
- Individual researchers don't evolve; the population of researcher types does

---

## 4. The Unit of Evolution: Researcher Genome

In biology: genes encode proteins → proteins enable capabilities → organisms survive or don't.

In the research system:

| Layer | What It Is | Example |
|-------|-----------|---------|
| **Genome** | Inherent traits/tendencies | `skepticism: 0.7`, `novelty_seeking: 0.4` |
| **Phenotype** | Expressed behavior (the prompt, the actions) | Designs experiments that challenge assumptions |
| **Competency** | Demonstrated capability | "Detects diminishing returns" |

**Key distinction**: The genome isn't the prompt. The genome is the *specification* that generates the prompt. Evolution operates on genomes; prompts are phenotypes.

### 4.1 Genome Structure (Draft)

```yaml
researcher_genome:
  # === Epistemic traits (how it knows) ===
  skepticism: 0.7           # how easily convinced by results
  memory_depth: 0.4         # how far back it looks
  pattern_sensitivity: 0.6  # notices cross-experiment patterns

  # === Action traits (how it acts) ===
  novelty_seeking: 0.3      # bored by repetition
  patience: 0.5             # willing to wait vs act
  risk_tolerance: 0.4       # wild swings vs incremental

  # === Meta traits (how it thinks about thinking) ===
  self_reflection: 0.2      # frequency of questioning own approach
  assumption_awareness: 0.1 # notices its own assumptions

  # === Structural traits (what it can build) ===
  integration_capacity: 0.5 # can hold multiple ideas together
  abstraction_tendency: 0.3 # sees patterns across domains
  specialization_affinity: 0.4  # focuses vs generalizes
```

An amoeba-genome has most traits near zero. A bacteria-genome has foundational traits active. More evolved organisms have richer trait profiles.

### 4.2 Why Traits, Not Competencies, Are the Genes

The Neural Framework defined a rich competency spectrum. Why not just use those as the genome?

Because competencies are *outcomes*, not *causes*. In biology, genes encode proteins, not capabilities. Capabilities emerge from proteins interacting with the environment.

Similarly:
- Genes → Proteins → Capabilities (biology)
- Traits → Behaviors → Competencies (research system)

A researcher with high `skepticism` and high `pattern_sensitivity` will, over many experiments, develop the competency "detects diminishing returns" — but only if the environment provides experiments to be skeptical about and patterns to notice.

The trait is heritable and fixed for an organism. The competency is emergent and context-dependent.

### 4.3 Competencies Emerge from Traits + Environment

Competencies (from the Neural Framework) aren't directly encoded. They emerge when traits interact with the research environment:

| Trait Combination | Emergent Competency |
|-------------------|---------------------|
| High `skepticism` + high `pattern_sensitivity` | "Detects diminishing returns" |
| High `memory_depth` + high `integration_capacity` | "Combines behaviors coherently" |
| High `self_reflection` + high `novelty_seeking` | "Explores when stalled" |
| High `patience` + high `memory_depth` | "Sensitivity to delayed rewards" |
| High `assumption_awareness` + high `abstraction_tendency` | "Revises faulty internal assumptions" |

This means:
- We engineer the *trait vocabulary* (what's possible)
- We let competencies *emerge* through evolution
- Selection operates on which trait combinations produce useful competencies

### 4.4 Complex Genomes May Need

For more evolved organisms, the genome might include:

**Regulatory genes** — when traits activate:
```yaml
regulations:
  when_stuck_for_n_experiments:
    boost: novelty_seeking
    reduce: patience
```

**Trait interactions** — epistasis:
```yaml
interactions:
  high_skepticism + low_patience: rapid_pivoting
  high_memory_depth + high_abstraction: wisdom_emergence
```

**Capability unlocks** — structural permissions:
```yaml
unlocks:
  when_regime_sensitivity > 0.6:
    allow: multi_timeframe_strategies
```

---

## 5. Guided Evolution: Director as Environment-Shaper

We considered three models:

| Model | Director Role | Problem |
|-------|---------------|---------|
| **Creationism** | Designs each generation | Director's imagination is the ceiling |
| **Natural selection** | No director, just environment | Too slow, undirected |
| **Guided evolution** | Shapes the fitness landscape | Balances direction with emergence |

**We chose guided evolution.**

The Director doesn't design organisms. It shapes the environment:
- Defines what "success" means (fitness function)
- Creates selection pressure (resource scarcity, escalating challenges)
- Grants capability unlocks when competencies are demonstrated
- Observes and labels (recognizes what stage an organism has reached)

Analogy: The Director is "god" for this world — not designing creatures, but designing the world they must survive in.

---

## 6. Three-Layer Mechanism

Evolution operates through three mechanisms at different timescales:

| Mechanism | Biological Analogue | Research System Implementation |
|-----------|---------------------|-------------------------------|
| **Variation** | Genetic diversity | Swarm of researchers with different genomes |
| **Selection** | Survival of the fittest | Resource scarcity, approach-level filtering |
| **Inheritance** | Genes passed to offspring | Successful traits persist, prompt evolution |

### 6.1 Layered Timescales

| Loop | Timescale | What Happens |
|------|-----------|--------------|
| **Inner** | Per experiment | Single researcher designs, trains, evaluates |
| **Middle** | Every N experiments | Selection (archive weak directions) + prompt injection (patterns observed) |
| **Outer** | Longer-term | Swarm dynamics, cross-pollination, new generations spawned |

The inner loop exists today. The middle and outer loops are what's missing.

---

## 7. Species Progression: Capability Jumps

From biology research (to be expanded):

| Transition | What Enabled It |
|------------|-----------------|
| Prokaryote → Eukaryote | Endosymbiosis (cooperation, not competition) |
| Single-cell → Multicellular | Specialization (cells doing one thing well) |
| Simple → Complex body plans | New sensory capabilities (more information) |

**Research system analogues**:

| Biological Enabler | Research System Analogue |
|--------------------|--------------------------|
| Endosymbiosis | Researchers sharing/building on each other |
| Specialization | Researchers focusing on domains (momentum vs mean-reversion) |
| New sensory capabilities | Access to richer information (multi-timeframe, cross-experiment patterns) |
| Energy availability | Compute budget, attention — what the system can afford to notice |

The jump from amoeba to bacteria isn't "better at the same thing" but "can do a new *kind* of thing."

---

## 8. Cost and Scale Concerns (Acknowledged, Deferred)

A swarm of researchers, each running experiments, each with their own genome — this could be expensive.

### Why It Might Be Manageable

- **The genome is cheap** — it's text (prompts, trait encodings), not neural network weights
- **Selection can be fast and brutal** — cheap to evaluate failure before expensive training
- **Recombination is nearly free** — mixing prompts is string manipulation
- **Populations can be small** — evolution works with dozens, not millions
- **Generations can be sequential** — run one amoeba until learnings suggest bacteria design, then spawn

### What We Decided

Set aside for now. The conceptual model should be right before optimizing for cost. If the model is sound, we can find ways to make it tractable. If the model is wrong, efficiency doesn't matter.

---

## 9. What We Have vs What We Need

### We Have (Pre-engineered)
- Competency vocabulary (from Neural Framework)
- Trait vocabulary (epistemic, action, meta, structural)
- Conceptual model of genomes, phenotypes, competencies
- Director-as-environment-shaper framing

### We Need
- Practical experience running researchers and observing behavior
- Mapping from genome traits → actual prompt construction
- Selection mechanism implementation
- Understanding of what makes an amoeba → bacteria transition happen

---

## 10. Open Questions

### Named
1. **What does genome → prompt translation look like?** How do traits become actual researcher behavior?
2. **What's the minimal selection mechanism?** Memory decay? Weighted referencing? Stricter gates?
3. **How do we detect competency emergence?** What signals indicate a capability is present?
4. **What triggers generation transitions?** When do we spawn bacteria-type researchers?

### Unnamed (The Nagging Thing)
Something about this model doesn't feel complete yet. We don't know what it is. This needs experimentation to surface.

Candidates for what might be nagging:
- Are we over-engineering the genome when simpler might work?
- Is the phylogeny framing actually right, or is there a third option?
- What's the role of memory in all this? (Barely discussed)
- How do researchers actually share/build on each other? (Assumed, not designed)

---

## 11. Next Steps

1. **Biology research**: Separate research thread on evolutionary transitions — what specifically enabled complexity jumps?

2. **Minimal experiment**: Run one amoeba researcher. Observe its behavior. Ask: what would need to change for bacteria-level behavior? Let reality inform theory.

3. **Revisit after experimentation**: Update this synthesis based on what we learn.

---

## 12. Relationship to Other Docs

```
BRAINSTORM.md                          neural_system_maturity_evolution_framework.md
(Selection pressure, forcing           (Capability lattice, competency
functions, Research Director)           spectrum, emergent stages)
            \                               /
             \                             /
              -----> THIS DOCUMENT <------
                    (Synthesis: Phylogeny,
                     Researcher Genome,
                     Guided Evolution)
                            |
                            v
                    [Future: Design Doc]
                    (After experimentation)
```

---

*Document Version: 0.1 (synthesis)*
*Date: February 2026*
*Status: Active — awaiting experimentation*
*Contributors: Karl + Claude*
