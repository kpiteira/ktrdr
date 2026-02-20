# Primordial Soup: Architecture

## Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    ktrdr evolve start                        │
│                    (CLI entry point)                         │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│              GenerationHarness                               │
│  (orchestration loop — runs as long-lived CLI process)       │
│                                                              │
│  ┌──────────────┐  ┌────────────────┐  ┌─────────────────┐  │
│  │ Genome       │  │ BriefTranslator│  │ EvolutionTracker│  │
│  │ (3×3 traits) │  │ (genome→prompt)│  │ (YAML state)    │  │
│  └──────────────┘  └────────────────┘  └─────────────────┘  │
│                                                              │
│  ┌──────────────────────┐  ┌───────────────────────────────┐ │
│  │ FitnessEvaluator     │  │ PopulationManager             │ │
│  │ (gates + scoring)    │  │ (seed + select + reproduce)   │ │
│  └──────────────────────┘  └───────────────────────────────┘ │
└─────────┬────────────────────────────┬──────────────────────┘
          │ HTTP                        │ HTTP
          ▼                            ▼
┌──────────────────┐         ┌──────────────────┐
│ Research Pipeline │         │ Backtest API     │
│ POST /agent/     │         │ POST /backtests/ │
│   trigger        │         │   start          │
│ GET /operations/ │         │ GET /operations/  │
│   {id}           │         │   {id}           │
└──────────────────┘         └──────────────────┘
```

| Component | Responsibility |
|---|---|
| **Genome** | Data model: 3 traits (novelty_seeking, skepticism, memory_depth) × 3 levels (off, low, high). 27 possible combinations. Supports mutation (shift 1 random trait ±1 level with clamping). |
| **BriefTranslator** | Converts a genome + run config into a design brief string. The brief includes trait-derived personality instructions, training/backtest date windows, and symbol/timeframe. This is the genome-to-phenotype mechanism. |
| **FitnessEvaluator** | Two-layer evaluation: gate checks (instant death for min trades, max drawdown, action diversity) then performance scoring across 3 time slices. Pure function — takes backtest results in, returns fitness score out. |
| **PopulationManager** | Manages population lifecycle: initial seeding (systematic coverage of genome space), selection (sort by fitness, kill bottom 50%), reproduction (each survivor spawns 2 offspring with 1 mutation each). |
| **EvolutionTracker** | Persists all state as YAML files: run config, population per generation, results per generation, cross-generation summary. Enables resume after crash and post-run analysis. |
| **GenerationHarness** | The orchestrator. Drives the generation loop: translate genomes → trigger researches via API → poll for completion → run additional backtests → evaluate fitness → select → reproduce → save state → next generation. |

---

## Execution Model

The harness runs as a **long-lived CLI process** (not an API operation). It orchestrates by calling the existing KTRDR APIs over HTTP. If it crashes, it resumes from the last completed generation using persisted state.

This is deliberately external to the research pipeline. The pipeline runs each individual experiment (design → train → backtest → assess). The harness manages populations and generations on top.

### Concurrency

The harness triggers multiple researchers in parallel, respecting worker capacity. When the trigger API returns `at_capacity`, the harness backs off and retries. With 4 workers in local-prod, a 12-researcher generation runs in 3-4 waves.

Within a generation, all researchers run independently — no shared state between them (this is the amoeba model; cross-researcher sharing is the bacteria transition, out of scope).

---

## Data Flow: One Generation

```
1. Population ready (12 researchers with genomes)
   │
2. For each researcher: genome → BriefTranslator → brief string
   │
3. Trigger via POST /api/v1/agent/trigger {model: "haiku", brief: <brief>}
   │  Operation ID persisted to disk immediately (crash safety)
   │
4. Research pipeline runs autonomously: design → train → backtest → assess
   │  (genome influences design only, via the brief)
   │
5. Poll GET /api/v1/operations/{id} until COMPLETED or FAILED
   │
6. Extract model_path + first-slice backtest_result from operation metadata
   │
7. Run 2 additional backtests via POST /api/v1/backtests/start
   │  (same model, different date ranges — slices 2 and 3)
   │
8. FitnessEvaluator: gate checks → performance scoring → single fitness value
   │
9. PopulationManager: sort by fitness, kill bottom 6, top 6 each spawn 2 offspring
   │
10. EvolutionTracker: save generation state + update cross-generation summary
    │
11. → Next generation (or final report)
```

---

## State Management

All state lives in YAML files under `data/evolution/run_<id>/`. One directory per generation.

```
data/evolution/run_<id>/
  config.yaml              # immutable run parameters
  generation_00/
    population.yaml        # researchers: [{id, genome, parent_id, mutation}]
    operations.yaml        # {researcher_id → operation_id} (written immediately on trigger)
    results.yaml           # [{researcher_id, fitness, gate_passed, slice_results, ...}]
  generation_01/
    ...
  summary.yaml             # per-generation aggregates (mean/max/min fitness, diversity, survivors)
```

**Crash safety:** Operation IDs are persisted to `operations.yaml` immediately after each trigger call, before polling begins. On resume, the harness loads this file, checks each operation's status, and either reads results (completed), resumes polling (still running), or re-triggers (orphaned >30 min).

**No database dependency.** The evolution module reads and writes files only. It accesses the research pipeline and backtest engine exclusively through HTTP APIs.

---

## Integration with Existing Systems

### APIs Used (no modifications needed)

| Endpoint | What the harness does with it |
|---|---|
| `POST /api/v1/agent/trigger` | Launch a research cycle. Brief parameter carries genome-derived personality + date instructions. |
| `GET /api/v1/operations/{id}` | Poll for research completion. Read `model_path` and `backtest_result` from operation metadata. |
| `GET /api/v1/agent/status` | Check capacity before triggering (optional optimization). |
| `POST /api/v1/backtests/start` | Run additional backtests on slices 2 and 3 using the trained model. |

### Key Data Extracted from Pipeline

- **model_path** — from `operation.metadata.parameters["model_path"]`. Used to run additional backtests.
- **backtest_result** — from `operation.metadata.parameters["backtest_result"]`. Contains Sharpe, drawdown, trade count, win rate for the first evaluation slice.
- **strategy_name** — from `operation.metadata.parameters["strategy_name"]`. For tracking and analysis.

### How Genome Reaches the LLM

```
genome → BriefTranslator.translate() → brief string
  → POST /api/v1/agent/trigger {brief: ...}
    → operation.metadata.parameters["brief"]
      → design_worker.run(brief=...)
        → get_strategy_designer_prompt(brief=...)
          → "## Research Brief" section at top of user prompt
```

The brief is the only injection point. The system prompt is shared across all researchers.

---

## Error Handling Strategy

| Error | Response |
|---|---|
| Trigger: `at_capacity` | Exponential backoff, retry (max 5 min between attempts) |
| Trigger: `budget_exhausted` | Abort generation, save partial state, log warning |
| Research operation: FAILED | Minimum fitness → dies at selection |
| Training/backtest gate rejection | Pipeline handles gracefully → no backtest metrics → gate failure → minimum fitness |
| Additional backtest fails | Retry once; if still fails, score using available slices only |
| Harness crash | Resume from last completed generation via persisted state |
| Operation stuck >30 min | Mark failed, re-trigger with same genome |
| All researchers fail in one generation | Abort run (no meaningful selection possible) |

Failed researchers are not retried — they get minimum fitness and die. This is evolution working correctly: genomes that produce broken strategies get selected out.

---

## Module Structure

```
ktrdr/evolution/
  __init__.py
  genome.py           # Genome, TraitLevel, Researcher
  brief.py            # BriefTranslator
  fitness.py          # FitnessEvaluator
  population.py       # PopulationManager
  tracker.py          # EvolutionTracker
  harness.py          # GenerationHarness
  config.py           # EvolutionConfig, DateRange

ktrdr/cli/evolve.py   # CLI: ktrdr evolve start/status/report

tests/unit/evolution/  # Unit tests (mocked API calls)
```

---

## Configuration Defaults

| Parameter | Default | Rationale |
|---|---|---|
| population_size | 12 | Even number, stable reproduction. Covers ~44% of genome space per gen. |
| generations | 5 | Enough to see trends without excessive compute. |
| symbol / timeframe | EURUSD / 1h | Proven pipeline, plenty of data (2005-2025). |
| model | haiku | ~$0.02/experiment. 240 experiments ≈ $5. |
| training_window | 2015-01-01 to 2020-12-31 | 6 years, diverse market regimes. |
| fitness_slices | 2021-H1, 2022-H2/2023, 2024-H1/2025-H1 | 3 non-overlapping post-training windows. |
| kill_rate | 0.5 | Brutal but not extinction. |
| mutations_per_offspring | 1 | Slow drift, not chaos. |
| budget_cap | $50 | Safety net for the entire run. |
| poll_interval | 30s | Balance between responsiveness and API load. |
| stale_operation_timeout | 30 min | Long enough for training; short enough to detect orphans. |

---

## Brief Translation Examples

### novelty=off, skepticism=high, memory=high

> You are a systematic, conservative researcher. Build on proven patterns from experiment history. Use well-understood indicator combinations — vary only one parameter from what has worked before. Be extremely conservative: use maximum 2 indicators, start with the smallest viable network ([8, 4]), and prefer strategies that show consistency. Carefully synthesize all experiment history before designing. Explicitly reference what has and hasn't worked.
>
> Training window: 2015-01-01 to 2020-12-31. Backtest window: 2021-01-01 to 2022-06-30. Symbol: EURUSD, Timeframe: 1h.

### novelty=high, skepticism=off, memory=off

> You are a creative, experimental researcher. Actively seek the most different approach from any recent strategy. Try unusual indicator combinations and unconventional parameter choices. Avoid anything that looks similar to what's been tried before. Accept results as-is — don't over-constrain your design with conservative parameters. Ignore any experiment history shown below. Design as if starting completely fresh.
>
> Training window: 2015-01-01 to 2020-12-31. Backtest window: 2021-01-01 to 2022-06-30. Symbol: EURUSD, Timeframe: 1h.

### novelty=low, skepticism=low, memory=low

> You are an exploratory researcher. Prefer indicators not heavily used in recent strategies, but keep the overall architecture conservative. Prefer simpler strategies with fewer indicators. Use conservative zigzag thresholds (0.01-0.02) and small-to-medium networks ([16, 8] or [32, 16]). Consider only the most recent 2-3 experiments when designing.
>
> Training window: 2015-01-01 to 2020-12-31. Backtest window: 2021-01-01 to 2022-06-30. Symbol: EURUSD, Timeframe: 1h.
