# Primordial Soup: Agent Evolution v0

## Problem Statement

KTRDR's research pipeline runs individual experiments but nothing selects for improvement across experiments. Strategies don't accumulate useful patterns because there's no selection pressure. The system designs, trains, backtests, and assesses in isolation — each cycle starts roughly fresh. The result: the agent stays a "baby forever."

The primordial soup experiment introduces population-based evolution to the research pipeline. A generation harness runs cohorts of genome-parameterized researchers through evolutionary cycles: design strategies, evaluate fitness, kill the weak, reproduce the strong, mutate, repeat. The goal is to observe whether meaningful trait patterns emerge under selection pressure.

## Goals

1. **Run a population-based evolutionary experiment** using the existing research pipeline as the execution engine
2. **Test whether selection pressure on researcher genomes produces meaningful evolution** — fitness improvement across generations, trait convergence, emergent patterns
3. **Build reusable infrastructure** (genome model, fitness evaluation, generation tracking) for future evolution work
4. **Learn from the experiment** — even null results (traits don't matter, noise dominates) are informative

## Non-Goals

- Finding a winning trading strategy (strategies are phenotypes, not the point)
- Research Director agent (future — observes and labels evolutionary stages)
- Cross-researcher sharing / bacteria transition (future — requires shared memory across population)
- Complex genomes (regulatory genes, epistasis, continuous traits)
- Novelty bonus (add only if monoculture observed)
- Modifying the existing research pipeline internals

## Prior Thinking

Five documents in `docs/agentic/evolution/` capture the intellectual progression:

1. `neural_system_maturity_evolution_framework.md` — Competency lattice, stages as emergent plateaus
2. `BRAINSTORM.md` — "Baby forever" problem, three selection pressure mechanisms
3. `03_synthesis_researcher_genome_evolution.md` — **Phylogeny reframe**: populations evolve, not individuals. Genome model introduced
4. `04_reflection_from_synthesis_to_experiment.md` — Bridge from abstract to concrete. Coarse buckets over continuous traits
5. `04_primordial_soup_experiment_design.md` — Complete v0 experiment design (ready for implementation)

---

## Design Decisions

### D1: External Harness, Not Pipeline Modification

**Decision:** The generation harness is a standalone module (`ktrdr/evolution/`) that orchestrates evolution by calling the existing research pipeline API. It does not modify the research worker, design worker, or any pipeline internals.

**Why:** The research pipeline (v2.6) is proven and tested. The harness is an experiment layer on top. If the experiment fails, we delete the module with zero impact on the pipeline. The API boundary (`POST /api/v1/agent/trigger`, `GET /api/v1/operations/{id}`, `POST /api/v1/backtests/start`) provides clean integration.

**Trade-off:** Less control over pipeline internals (can't modify experiment memory per-researcher, can't control training parameters directly). Accepted for v0 — genome influence flows through the brief parameter only.

### D2: Genome-to-Prompt Translation via Brief Parameter

**Decision:** Each researcher's genome translates to a `brief` string that gets injected into the design prompt. The `brief` parameter already flows through the entire research pipeline: `trigger()` → operation metadata → design worker → prompt template.

**Why:** Zero pipeline changes needed. The brief appears at the top of the user prompt as a "Research Brief" section with the instruction "Follow this brief carefully." LLMs demonstrably change behavior based on prompt framing. Each trait maps to specific instructions about design approach, risk tolerance, and memory usage.

**Trade-off:** Relies on the LLM following instructions (which it generally does with haiku/sonnet). No hard enforcement of trait behavior — a "skeptical" researcher might still produce aggressive strategies. This is acceptable: the fitness function is the real selector, not prompt compliance.

### D3: Brief-Instructed Date Windows

**Decision:** The brief specifies training and backtest date ranges. The LLM puts these into the strategy YAML. No API changes needed.

**Why:** Simplest approach. The fitness function needs consistent evaluation windows across all researchers in a generation. The brief already controls the LLM's strategy design choices.

**Trade-off:** If the LLM ignores date instructions, fitness comparison is compromised. Accepted risk — haiku follows explicit date instructions reliably, and the multi-slice fitness function catches overfitting regardless.

### D4: File-Based State (YAML)

**Decision:** Generation state persisted as YAML files in `data/evolution/run_<id>/`. One directory per generation, containing population, results, and operation tracking.

**Why:** Matches existing patterns (`memory/experiments/*.yaml`). Inspectable, diffable, doesn't require the database. The evolution run is an experiment, not a production service.

**Trade-off:** No concurrent write safety (only one harness runs at a time). No query capability (can't ask "which genomes survived across all runs" without loading files). Both acceptable for v0.

### D5: Population Size 12

**Decision:** Fixed population of 12 researchers per generation. 6 survive (50% kill rate), each produces 2 offspring = 12 for the next generation. Stable.

**Why:** Even number avoids population drift. 12 covers ~44% of the 27-genome space per generation (enough diversity). Clean 50% split: bottom 6 die, top 6 reproduce.

### D6: Three-Slice Fitness Evaluation

**Decision:** Each researcher is evaluated on 3 non-overlapping time slices. The first slice comes from the research pipeline's standard backtest. The harness runs 2 additional backtests via the backtest API using the same trained model on different date ranges.

**Why:** Single-slice fitness rewards overfitting. Cross-slice consistency (penalizing Sharpe variance across slices) selects for robust strategies. Three slices is the minimum for meaningful variance measurement.

**Proposed default slices** (with EURUSD 1h, training on 2015-2020):
- Slice 1: 2021-01-01 to 2022-06-30
- Slice 2: 2022-07-01 to 2023-12-31
- Slice 3: 2024-01-01 to 2025-06-30

### D7: Haiku Model for Cost Efficiency

**Decision:** All research cycles use haiku for LLM calls (design + assessment). Configurable per-run.

**Why:** 240 experiments × ~$0.02/experiment = ~$5 total. Haiku is sufficient for v3 strategy design (proven in production research cycles). The experiment tests evolutionary dynamics, not LLM creativity.

---

## Fitness Function

### Layer A — Gates (Instant Death)

| Gate | Threshold | Rationale |
|---|---|---|
| Minimum trades | 30 per slice | No coward strategies |
| Maximum drawdown | 35% | No exploding candidates |
| Action diversity | Not >90% same direction | No trivially all-long/all-short |
| Cost awareness | Spread + slippage applied | No fake edges |

A researcher failing any gate on any slice gets minimum fitness and dies at selection.

### Layer B — Performance Score

Evaluated across 3 slices:

```
fitness = mean(Sharpe_i) - λ_dd * mean(MaxDD_i) - λ_var * std(Sharpe_i) - λ_cmp * complexity
```

| Parameter | Value | Purpose |
|---|---|---|
| λ_dd | 1.0 | Penalize drawdown |
| λ_var | 1.0 | Anti-lottery-ticket (penalize cross-slice variance) |
| λ_cmp | 0.1 | Mild complexity penalty |
| complexity | indicator_count/10 + nn_param_bucket | Crude scalar |

Where `nn_param_bucket` maps parameter count to 0-1 range: <100 → 0.1, <500 → 0.3, <2000 → 0.5, <10000 → 0.7, ≥10000 → 1.0.

---

## Key Scenarios

### Happy Path: Full Generation

1. Harness creates 12 researchers with diverse genomes
2. Triggers researchers via API (respecting worker capacity, retrying on "at_capacity")
3. Polls operations until all 12 complete
4. Runs 2 additional backtests per researcher (24 total, via backtest API)
5. Evaluates fitness: gates → scoring → ranking
6. Bottom 6 die, top 6 each produce 2 offspring (1 mutated trait)
7. Generation state saved, next generation begins

### Researcher Failure

- **Design fails** (LLM error): operation status=FAILED → minimum fitness → dies
- **Training gate rejects**: pipeline routes to assessment (existing behavior) → no backtest result → gate failure → dies
- **Backtest gate rejects**: pipeline completes with gate_rejected status → limited metrics → gate failure → dies
- **Additional backtest fails**: harness retries once, then assigns minimum fitness for that slice

### Harness Crash and Resume

1. Harness persists operation IDs immediately after each trigger (before polling)
2. On resume, loads last generation state, checks operation statuses
3. Completed operations: read results. Still running: resume polling. Orphaned (>30 min): re-trigger
4. Once all researchers scored, continues with selection/reproduction

### Budget Exhaustion

Trigger API returns `{triggered: false, reason: "budget_exhausted"}`. Harness aborts the current generation, saves partial state, logs warning. User sets higher budget and resumes.

---

## Success Criteria

**The experiment works if:**
1. Selection has teeth — some researchers die each generation
2. Fitness improves across generations (mean gen 5 > mean gen 0)
3. Trait patterns emerge — some trait values over-represented in survivors
4. We learn something — even null results are informative

**Exceeds expectations if:**
5. Emergent behavior — researchers do something we didn't prompt for
6. Clear winners — specific trait combos consistently outperform
7. The "nagging thing" from the synthesis documents clarifies

---

## Milestone Structure

### M1: Single Generation End-to-End

Prove the architecture works by running one generation of researchers through the pipeline and scoring them.

**Delivers:** Genome model, brief translator, population seeding, generation harness (1 gen), basic fitness (single-slice), state persistence, CLI entry point.

**E2E test:** Run 1 generation with 3 researchers in local-prod, verify results are collected and scored.

### M2: Evolution Loop

Add selection pressure and multi-generation dynamics.

**Delivers:** Selection (kill bottom 50%), reproduction (clone + mutate), multi-generation loop, resume capability, status CLI.

**E2E test:** Run 3 generations with 6 researchers, verify population evolves and state persists across generations.

### M3: Full Fitness + Reporting

Add robust fitness evaluation and experiment analysis.

**Delivers:** Multi-slice backtesting (2 additional per researcher), full fitness function (gates + cross-slice scoring + complexity), monoculture detection, report CLI with genome distribution/fitness trends/lineage.

**E2E test:** Full 5-generation run with 12 researchers, verify multi-slice scoring and report accuracy.
