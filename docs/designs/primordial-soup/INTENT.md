# Primordial Soup: Agent Evolution v0 Experiment

## What We Want to Build

A **generation harness** that runs populations of researcher agents through evolutionary cycles. Each researcher has a simple genome (3 traits, 3 levels each) that shapes how it designs strategies. Selection pressure (brutal 50% kill rate) operates on fitness, survivors reproduce with mutation, and we observe whether meaningful patterns emerge across generations.

This is the first concrete step toward agent evolution in KTRDR.

---

## Why Now

We just completed a long arc of infrastructure work that makes this possible:

| Prerequisite | Status | Why It Matters |
|---|---|---|
| Strategy Grammar v3 | Done | Agents design strategies in structured v3 YAML |
| Multi-research concurrency (v2.6) | Done | Can run multiple researchers in parallel |
| Backtesting pipeline refactor | Done | Reliable train-on-GPU → backtest-on-CPU pipeline |
| Config system consolidation | Done | Clean settings, no env var chaos |
| CLI restructure | Done | `ktrdr research --strategy` works end-to-end |
| Container optimization | Done | Split images, faster builds |

**Proven 2026-02-18**: Full research cycle completed — rhythm_dancer_mtf_momentum_sync trained on MPS GPU, backtested on CPU Docker worker, assessed. 4:12 end-to-end. The pipeline works.

---

## Prior Thinking (Read These)

Four documents in `docs/agentic/evolution/` capture months of design thinking:

1. **BRAINSTORM.md** — Identifies the "Baby forever" problem. Why the current system doesn't evolve: no selection pressure, no escalating challenge, no complexity incentive. Proposes three mechanisms: resource scarcity, environmental pressure (Research Director), internal drive (curiosity).

2. **neural_system_maturity_evolution_framework.md** — Defines what evolution *looks like*: capability lattice, competency spectrum from foundational (infant) through adult. Key insight: evolution via capabilities, not strategies. Stages are labels applied after the fact, not gates.

3. **03_synthesis_researcher_genome_evolution.md** — Unifies the two brainstorms. **Key reframe**: phylogeny not ontogeny — populations evolve, not individuals. The unit of evolution is the researcher genome (traits like skepticism, novelty_seeking, memory_depth), not strategies. Strategies are phenotypes. Director-as-environment-shaper (guided evolution).

4. **04_primordial_soup_experiment_design.md** — Concrete v0 experiment design. This is the document closest to what we're implementing. Status: "ready for implementation."

5. **04_reflection_from_synthesis_to_experiment.md** — Captures the reasoning bridge from abstract model to concrete experiment. Karl's instinct: stop theorizing, start with something brutal and simple, observe what emerges.

---

## The Experiment Design (from doc 04)

### Genome (v0 — deliberately minimal)

3 traits, 3 levels each = 27 possible genomes:

```yaml
amoeba_genome_v0:
  novelty_seeking: [off, low, high]
    # off = systematic, low = mild randomness, high = creative/random
  skepticism: [off, low, high]
    # off = accepts results, low = basic checks, high = demands robustness
  memory_depth: [off, low, high]
    # off = starts fresh, low = last 2-3 experiments, high = full history synthesis
```

### Population Dynamics

| Parameter | Value |
|---|---|
| Population size | 9-12 researchers per generation |
| Experiments per researcher | 1-2 |
| Selection | Bottom 50% die |
| Reproduction | 2 offspring per survivor |
| Mutation | 1 random trait per offspring, shifted +/-1 level |
| Generations | 5-10 |
| Total experiments | ~45-240 |

### Fitness Function

**Layer A — Gates (instant death):**
- Minimum 30 trades in eval window
- Maximum drawdown < 35%
- Action diversity (not trivially all-long or all-short)
- Cost-aware (spread/slippage/fees applied)

**Layer B — Performance score:**
Evaluated across 3 non-overlapping time slices:
```
fitness = mean(Sharpe_i) - lambda_dd * mean(DD_i) - lambda_var * std(Sharpe_i) - lambda_cmp * complexity
```
Where lambda_dd=1.0, lambda_var=1.0, lambda_cmp=0.1.

### Generation Lifecycle

```
Generation N:
  1. Each researcher designs 1-2 strategies (genome shapes the design prompt)
  2. Each strategy is trained + backtested (via existing research pipeline)
  3. Fitness evaluated per researcher
  4. Bottom 50% die
  5. Each survivor spawns 2 offspring (1 mutated trait each)
  6. Generation N+1 begins
```

### What We're Measuring

- **Per generation**: genome distribution, mean/max/min fitness, which genomes survived
- **Across generations**: fitness trend, trait convergence, diversity, surprises
- **End state**: Did trait combinations get selected for? Did fitness improve? Did patterns emerge?

---

## What Needs to Be Built

### 1. Genome Model
Data structure representing researcher traits. Simple — a dict or dataclass with 3 fields.

### 2. Genome-to-Prompt Translation
**This is the core design challenge.** How do genome traits (novelty_seeking=high, skepticism=low, memory_depth=off) translate into actual differences in the design prompt sent to the LLM?

Options to explore:
- Prompt injection (add trait-specific instructions to the design worker prompt)
- System prompt modifiers (prepend personality to existing design prompt)
- Temperature/sampling parameter adjustments (less deterministic)
- Memory filtering (memory_depth controls how much experiment history is included)

The translation must produce *meaningfully different* researcher behavior, not just cosmetic prompt differences.

### 3. Generation Harness
Orchestration loop that:
- Seeds initial population (random or systematic genome coverage)
- Runs each researcher's experiments (using existing `POST /api/v1/agent/trigger`)
- Collects results and computes fitness
- Applies selection (kill bottom 50%)
- Applies reproduction (clone + mutate)
- Tracks lineage and metrics per generation
- Produces a generation report

### 4. Fitness Evaluator
Takes backtest results and computes the multi-layer fitness score. Needs access to:
- Trade count, drawdown, Sharpe ratio per time slice
- Strategy complexity (indicator count, NN size)
- Gate checks

### 5. Experiment Tracker
Records the full evolutionary history:
- Every genome, every generation
- Which genomes survived/died
- Fitness scores
- Lineage (parent → children with mutations)
- Aggregate statistics per generation

### 6. CLI Interface
Something like:
```bash
ktrdr evolve start --population 12 --generations 5 --symbol EURUSD --timeframe 1h
ktrdr evolve status
ktrdr evolve report
```

---

## Existing Infrastructure to Build On

### Research Pipeline (working, proven)
- `ktrdr/agents/workers/research_worker.py` — Coordinator loop, phase state machine
- `ktrdr/agents/workers/design_worker.py` — LLM-based strategy design
- `ktrdr/agents/workers/assessment_worker.py` — LLM-based result assessment
- `ktrdr/agents/memory.py` — Experiment records, hypothesis tracking
- `ktrdr/agents/gates.py` — Performance thresholds per maturity stage
- `ktrdr/agents/prompts.py` — Design/assessment prompt templates
- `ktrdr/agents/budget.py` — Budget tracking

### API Endpoints
- `POST /api/v1/agent/trigger` — Start a research cycle
- `GET /api/v1/agent/status` — Multi-research status
- `GET /api/v1/operations/{id}` — Operation tracking with progress
- `DELETE /api/v1/operations/{id}` — Cancel specific research

### Multi-Research (v2.6)
- Coordinator loop iterates active researches, advances each per poll cycle
- Capacity-based limiting (worker pool size + buffer)
- Individual cancel, error isolation, restart recovery
- All 6 milestones implemented and merged

### CLI
- `ktrdr research -m haiku -s <strategy_name> --follow` — Run research with existing strategy
- `ktrdr research -m haiku -f "<brief>" --follow` — Run research from brief
- `ktrdr agent status` — Show active researches, workers, budget

---

## Design Decisions Already Made

These are settled and should not be revisited:

1. **Phylogeny, not ontogeny** — Populations evolve. Individual researchers have fixed genomes.
2. **Guided evolution** — Director shapes the fitness landscape, doesn't design creatures.
3. **Traits, not competencies, are the genes** — Competencies emerge from traits + environment.
4. **Brutal selection** — 50% die. Simple, fast, no mercy.
5. **Coarse genome for v0** — 3 traits × 3 levels. If patterns don't emerge here, continuous won't help.
6. **Cost from day one** — No fake edges. Spread/slippage/fees included in fitness.
7. **v0 = amoeba only** — No cross-researcher sharing (that's the bacteria transition).

## Open Design Questions

1. **Genome → prompt translation**: The hardest question. How do traits become meaningfully different research behavior?
2. **Orchestration architecture**: New service? Extension of research_worker? Standalone script?
3. **Data slicing**: Which 3 time periods for fitness evaluation? Configurable or fixed?
4. **Concurrency model**: Run all researchers in a generation in parallel (v2.6 supports this) or sequential?
5. **Where does generation state live?** Database? File? Memory?
6. **Observability**: How do we watch evolution happen? CLI dashboard? Logs? Traces?
7. **Budget management**: How does the experiment budget relate to per-research budget?

---

## Constraints

- **LLM costs**: Each research cycle involves 1-2 LLM calls (design + assessment). With haiku, this is cheap (~$0.01-0.05 per call). 240 experiments = ~$5-25 in LLM costs. Acceptable.
- **Compute time**: Training + backtesting is the bottleneck (~2-5 min per experiment). 240 experiments at 3 min = ~12 hours. Should run unattended.
- **Data**: EURUSD 1h data available from 2005-03-14 to 2025-09-12. Plenty for 3 non-overlapping slices.
- **Workers**: Local-prod has 4 workers. With v2.6 concurrency, can run ~3-4 researches in parallel.

---

## Success Criteria

The experiment succeeds if:
1. Selection has teeth (some researchers die each generation)
2. Fitness improves across generations (mean gen 5 > gen 0)
3. Trait patterns emerge (some values over-represented in survivors)
4. We learn something (even null results are informative)

Exceeds expectations if:
5. Emergent behavior (researchers do something we didn't prompt for)
6. Clear winners (specific trait combos consistently outperform)
7. The "nagging thing" from the synthesis doc clarifies

---

## Scope Boundary

**In scope for this design:**
- Generation harness and evolutionary loop
- Genome model and prompt translation
- Fitness evaluation
- Experiment tracking and reporting
- CLI interface for running and monitoring

**Out of scope (future work):**
- Research Director agent (observes and labels stages)
- Bacteria transition (cross-researcher sharing)
- Complex genomes (regulatory genes, epistasis)
- Novelty bonus (add only if we observe monoculture)
- Capability unlocks (structural permissions at higher stages)
