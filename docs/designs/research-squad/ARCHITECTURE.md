# Research Squad: Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      COORDINATOR (Lux / Loop Runner)                     │
│  Spawns agents via Agent tool, routes context, collects responses        │
└────────┬────────────────────────────┬───────────────────────────────────┘
         │                            │
         ▼                            ▼
┌─────────────────────┐    ┌─────────────────────────────────────────────┐
│ SQUAD AGENTS         │    │              EXPERIMENT EXECUTION           │
│ (Separate sessions)  │    │                                             │
│                      │    │  1. Engineer writes strategy YAML            │
│ ┌──────────────────┐ │    │  2. ktrdr train <strategy> --start --end    │
│ │ Director         │ │    │  3. ktrdr backtest <strategy> --start --end │
│ │ Inventor         │ │    │  4. Parse results (JSON metrics)            │
│ │ Quant            │ │    │                                             │
│ │ Engineer         │ │    │  (No agent involvement — pure infra)        │
│ │ Critic           │ │    │                                             │
│ │ Architect        │ │    └─────────────────────────────────────────────┘
│ │ Scout            │ │
│ │ Scribe           │ │    ┌─────────────────────────────────────────────┐
│ └──────────────────┘ │    │           EXTERNAL RESEARCH                  │
│                      │    │                                             │
│ Each agent gets:     │    │  Scout agent with WebSearch + WebFetch       │
│ - own charter        │    │  Searches based on frontiers.md              │
│ - own history        │    │  Writes to: bibliography.md,                │
│ - targeted context   │    │             external-insights.md             │
│   (not everything)   │    │                                             │
│                      │    └─────────────────────────────────────────────┘
│ Coordinator routes:  │
│ - proposals          │    ┌─────────────────────────────────────────────┐
│ - assessments        │    │           CAPABILITY BUILDING                │
│ - critiques          │    │                                             │
│ - specs              │    │  Architect → GitHub issues                   │
│                      │    │  Karl / Lux → implementation                 │
└──────────────────────┘    │  New capability → components.md updated      │
                            │                                             │
                            │  (Async, human-paced, not in the loop)      │
                            └─────────────────────────────────────────────┘
```

Three parallel tracks:
1. **The research loop** — squad discusses, designs experiments, evaluates results (fast: hours)
2. **External research** — Scout searches for papers and techniques (medium: days)
3. **Capability building** — Architect identifies gaps, work gets done (slow: days-weeks)

The research loop never blocks on the other two. It works with what's available. When new capabilities or external insights arrive, they flow into the next squad session naturally through the shared knowledge base.

---

## Component Details

### 1. Loop Runner

The orchestrator. A Python script (or shell script) that:
1. Assembles the prompt for a squad session
2. Calls Claude with the assembled prompt
3. Parses the output (experiment spec, state updates, capability requests)
4. Executes the experiment (train + backtest via ktrdr CLI)
5. Formats results for the next session
6. Updates shared state files
7. Decides whether to loop again or wait

```
loop_runner.py

  assemble_prompt()
    → Reads: all charter files, all history files, shared knowledge files
    → Reads: last experiment results (if any)
    → Reads: Scout's latest external insights (if new)
    → Reads: newly available capabilities (if any)
    → Builds: structured prompt with phase indicator (ORIENT/STRATEGIZE/DESIGN/EVALUATE/LEARN)
    → Returns: prompt string

  run_squad_cycle()
    → Executes the agent flow described above (ORIENT → STRATEGIZE → DESIGN)
    → Each agent spawned via Claude Code Agent tool with targeted context
    → Agents resumed via SendMessage where context continuity needed
    → Collects all agent outputs
    → Returns: experiment spec, hypothesis, capability requests, cycle transcript

  execute_experiment(spec)
    → Writes strategy YAML to file
    → Copies to shared strategies dir
    → Runs: ktrdr train <name> --start <date> --end <date>
    → Polls operation status until complete
    → Runs: ktrdr backtest <name> --start <date> --end <date> --model-path <path>
    → Polls until complete
    → Returns: training metrics + backtest results

  update_state(session_output, experiment_results)
    → Appends to experiments.md
    → Updates hypotheses.md
    → Updates agent history.md files
    → Updates components.md if new component created
    → Updates frontiers.md
    → Creates GitHub issues for capability requests
    → Increments iteration count

  should_continue()
    → Checks: iteration count < max
    → Checks: Director hasn't called for pause
    → Checks: no fatal errors
    → Returns: bool
```

**Execution model:** The loop runner is a long-lived process (like the Ralph loop). It can run unattended for N iterations. It's stateless — all state is on disk. If it crashes, restart it and it picks up from the last completed iteration.

### 2. Squad Session — Separate Agents, Coordinated by Hub

**Design Decision D4 (revised): Separate sessions per agent.**

Each squad member runs as a separate Claude Code Agent with its own context window. A Coordinator (the main session or loop runner) orchestrates the flow — deciding who speaks when, what context each agent sees, and how responses route between agents.

This mirrors the Squad framework's architecture: the Coordinator dispatches via the Agent tool, collects responses, and routes follow-ups via SendMessage. Agents never talk to each other directly — all communication flows through the Coordinator.

**Why separate sessions:**
- Each agent genuinely has its own perspective (no consensus drift within a shared context)
- The Critic evaluates the Inventor's proposal without being influenced by the Inventor's enthusiasm
- Each agent's context is lean — only its charter + history + the specific input it needs
- SendMessage preserves agent context across rounds within a cycle (the Critic can be asked follow-up questions)

**Execution flow for one cycle:**

```
Coordinator (main Claude Code session / loop runner)
│
│  ── ORIENT ──
├── spawn Agent "scribe"
│     Context: charter + experiment history + synthesis
│     Task: "Present current state: what we know, recent results, open hypotheses"
│     Returns: state briefing
│
│  ── STRATEGIZE ──
├── spawn Agent "scout"
│     Context: charter + frontiers.md + bibliography.md
│     Task: "Search for relevant external research for our current frontiers"
│     Tools: WebSearch, WebFetch
│     Returns: external insights (or "nothing new")
│
├── spawn Agent "director"
│     Context: charter + history + scribe briefing + scout findings
│     Task: "Propose the next exploration frontier and explain why"
│     Returns: frontier proposal
│
├── spawn Agent "inventor"
│     Context: charter + history + director proposal + scout findings
│     Task: "Propose a specific experiment. Push for something novel."
│     Returns: experiment idea
│
├── spawn Agent "quant"
│     Context: charter + history + inventor proposal
│     Task: "Evaluate from a trading perspective. What's realistic? What's missing?"
│     Returns: market assessment
│
├── spawn Agent "critic"
│     Context: charter + history + inventor proposal + quant assessment
│     Task: "Find flaws. What could go wrong? What would make this rigorous?"
│     Returns: critique + required validations
│
│  ── DESIGN ──
├── spawn Agent "engineer"
│     Context: charter + history + components.md + approved plan (director + inventor + quant + critic)
│     Task: "Translate into an executable experiment: strategy YAML + specific hypothesis"
│     Returns: strategy YAML + hypothesis statement
│
├── spawn Agent "architect"
│     Context: charter + history + capability-gaps.md + engineer's spec
│     Task: "Can we run this? What's missing? File issues for gaps."
│     Returns: feasibility assessment + capability requests (if any)
│
│  ── EXECUTE ──
│  [No agents — ktrdr train + backtest via CLI]
│  [Coordinator polls until complete]
│
│  ── EVALUATE ──
├── SendMessage to "critic" (resumes with prior context)
│     Input: experiment results (training metrics + backtest metrics)
│     Task: "Evaluate these results. Statistical validity? Comparison to baselines?"
│     Returns: honest assessment
│
├── SendMessage to "quant" (resumes with prior context)
│     Input: experiment results + critic assessment
│     Task: "Is this tradeable? What would it take to make it profitable?"
│     Returns: trading assessment
│
│  ── LEARN ──
├── spawn Agent "scribe"
│     Context: charter + FULL cycle output (all agent responses + results)
│     Task: "Record: experiment details, results, hypothesis status, agent learnings"
│     Returns: state updates (experiments.md entry, hypothesis updates, agent history updates)
│
│  Coordinator writes all state updates to disk
│  Loop continues or pauses (based on Director's cadence decision)
```

**What each agent sees (context budget):**

| Agent | Reads | Doesn't Read |
|-------|-------|-------------|
| Director | Scribe briefing, scout findings, own history, frontiers | Individual experiment details (synthesis only) |
| Inventor | Director proposal, scout findings, own history, components | Critic's prior objections (fresh perspective) |
| Quant | Inventor proposal, own history | Engineer implementation details |
| Critic | Inventor proposal, quant assessment, own history | Inventor's reasoning process |
| Engineer | Approved plan (all perspectives combined), components, own history | Rejected alternatives |
| Architect | Engineer's spec, capability gaps, own history | Squad debate |
| Scout | Frontiers, bibliography, own history | Experiment details |
| Scribe | Everything from the cycle | Nothing excluded |

This selective context is key — the Critic doesn't see the Inventor's enthusiasm, only the proposal. The Engineer doesn't see rejected ideas, only the approved plan.

**Agent persistence within a cycle:**

Agents spawned early in the cycle can be resumed via SendMessage later. The Critic is spawned during STRATEGIZE and resumed during EVALUATE — it remembers the proposal it critiqued and can evaluate results against its own predictions. The Quant similarly carries context from assessment to evaluation.

Between cycles, agents start fresh but their `history.md` carries forward what they learned.

### 3. Shared Knowledge Base

All markdown files in `.squad/knowledge/`. The loop runner reads and writes these. The Scribe manages synthesis.

**Key design principle:** Files are append-friendly. Experiments are added, never removed. Hypotheses change status but are never deleted. This makes merge conflicts unlikely and preserves the full audit trail.

**Synthesis cycle:** Every N experiments (configurable, default 10), the Scribe produces a fresh `synthesis.md` that distills the full experiment history into:
- Established facts (things we know with high confidence)
- Active frontiers (where experiments are currently focused)
- Dead ends (approaches that have been thoroughly explored and failed)
- Open questions (things we don't know and should investigate)

This synthesis is what prevents context overflow — instead of reading 100 experiment entries, the squad reads a 2-page synthesis plus the last 5 detailed entries.

### 4. Scout's Research Process

The Scout operates **asynchronously** from the squad loop. Between squad sessions, the Scout:

1. Reviews `frontiers.md` to understand what the squad is working on
2. Searches the web for relevant papers, techniques, approaches
3. Reads and summarizes findings
4. Writes to `bibliography.md` (references) and `external-insights.md` (actionable findings)
5. Prioritizes findings by relevance to current frontiers

**Implementation:** The Scout can be a separate Claude session (with web search enabled) that runs periodically (e.g., before each synthesis session). Or it can be a phase within the squad session where the Scout agent is explicitly asked "what have you found?"

**Scout's output format in `external-insights.md`:**

```markdown
## Insight: Temporal Fusion Transformers for Multi-Horizon FX Prediction
- **Source:** "Temporal Fusion Transformers for Interpretable Multi-Horizon Time Series Forecasting" (Lim et al., 2021)
- **Relevance:** Direct — proposes attention over mixed-frequency inputs, which maps to our multi-TF architecture
- **Key finding:** TFT outperforms LSTM by 12-15% on volatility and return prediction tasks
- **Actionable for squad:** Requires attention mechanism (capability gap). If Architect builds this, we can test H_092.
- **Added:** 2026-03-25
```

### 5. Architect's Capability Pipeline

The Architect identifies gaps and produces **GitHub issues** with enough detail for implementation.

**Issue format:**

```markdown
## Capability Request: DXY/VIX/Yields Feature Pipeline

**Requested by:** Research Squad Architect (experiment 43 discussion)
**Priority:** High — blocks 5 queued hypotheses (H_087, H_088, H_091, H_093, H_094)

### What's Needed
A feature provider that:
- Fetches DXY, US 10Y yield, VIX daily data via IB Gateway
- Computes derived features: DXY momentum (ROC), yield spread, VIX level/change
- Integrates with FeatureCache for backtest and FuzzyNeuralProcessor for training
- Supports multi-timeframe alignment (daily features aligned to hourly bars)

### Integration Points
- New data provider in ktrdr/data/context/
- Strategy YAML supports context_data entries for these sources
- Model metadata stores context features for reproducibility

### Success Criteria
- Squad can reference DXY/VIX/yield features in nn_inputs
- Training and backtest pipelines handle the features end-to-end
- At least one experiment uses the features successfully

Labels: squad:architect, capability-gap
```

---

## Data Flow: One Full Cycle

```
1. Loop runner calls assemble_prompt(phase=ORIENT)
   │  Reads all .squad/ files
   │  Includes last experiment results
   │
2. Loop runner calls Claude with assembled prompt
   │  Squad session runs (~5-15 min of reasoning)
   │  Agents debate, design experiment, update state
   │
3. Loop runner parses output
   │  Extracts: strategy YAML, hypothesis, history updates
   │  Extracts: capability requests (if any)
   │
4. Loop runner calls execute_experiment()
   │  Writes strategy YAML → ~/.ktrdr/shared/strategies/
   │  Runs: ktrdr train <name> --start 2015-01-01 --end 2020-12-31
   │  Polls until complete (~5-60 min depending on model type)
   │  Runs: ktrdr backtest <name> --start 2021-01-01 --end 2025-01-01
   │        --model-path models/<name>/5m_latest
   │  Polls until complete (~1-5 min)
   │
5. Loop runner calls update_state()
   │  Appends experiment to experiments.md
   │  Updates hypotheses.md
   │  Writes agent history updates
   │  Creates GitHub issues for capability requests
   │
6. Loop runner checks should_continue()
   │  If yes → goto 1 (with phase=EVALUATE to process results)
   │  If no → exit
```

---

## State Management

### File Lifecycle

| File | Created | Updated | Read By |
|------|---------|---------|---------|
| `charter.md` (per agent) | Once, at squad creation | Rarely (role refinement) | Every squad session |
| `history.md` (per agent) | Squad creation (empty) | Every cycle | Every squad session |
| `experiments.md` | Squad creation (seeded with prior history) | Every cycle (append) | Every squad session (via synthesis) |
| `hypotheses.md` | Squad creation (seeded from existing) | Every cycle | Every squad session |
| `components.md` | Squad creation (current catalog) | When new components built | Every squad session |
| `decisions.md` | Squad creation (empty) | When decisions made | Every squad session |
| `synthesis.md` | After first synthesis cycle | Every N cycles | Every squad session |
| `frontiers.md` | First strategize session | When Director updates | Squad + Scout |
| `bibliography.md` | Scout's first research | When Scout finds new sources | Squad sessions |
| `external-insights.md` | Scout's first research | When Scout has new insights | Squad sessions |
| `capability-gaps.md` | First Architect analysis | When gaps identified/resolved | Squad + Karl |
| `build-queue.md` | First capability request | When items added/completed | Karl / Lux |

### Seeding the Knowledge Base

The squad doesn't start from zero. We seed it with everything we've learned:

- **experiments.md:** Synthesized history of signal model evolution (M1-M5), H_003 experiment, prior v1.5 experiments
- **hypotheses.md:** Curated from existing `memory/hypotheses.yaml` — keep the investigated ones (H_INV_001-005), the original thoughtful ones (H_001-006), discard the 300+ auto-generated noise
- **components.md:** Current catalog of what works (regime classifier, LSTM, ensemble runner, etc.)
- **decisions.md:** Key architectural decisions already made (D: MLP is dead for signal prediction, D: temporal modeling required, D: standard indicators have a ceiling)

---

## Error Handling

| Error | Response |
|-------|----------|
| Squad session produces unparseable output | Retry with stricter format instructions. After 3 failures, log and skip to next cycle. |
| Training fails (operation error) | Record failure in experiments.md with error details. Squad evaluates in next session — may indicate infra problem or invalid strategy. |
| Backtest fails | Same as training failure — record and evaluate. |
| Squad proposes experiment requiring unavailable capability | Architect files GitHub issue. Squad designs alternative experiment using available components. |
| Context window exceeded | Scribe produces emergency synthesis. Oldest agent histories trimmed. |
| Squad converges on single approach for >10 experiments | Director's charter includes explicit instruction to diversify. Inventor forced to propose something orthogonal. |
| Scout finds no relevant research | Normal — not every frontier has published research. Scout documents the search and moves on. |
| Loop runner crashes | Restart. All state is on disk. Pick up from last completed iteration. |

---

## Integration with ktrdr

### APIs Used (no modifications needed)

| Endpoint / Command | Purpose |
|-------------------|---------|
| `ktrdr train <strategy> --start --end` | Execute training |
| `ktrdr backtest <strategy> --start --end --model-path` | Execute backtest |
| `ktrdr status <operation_id>` | Poll operation progress |
| Strategy YAML files in `~/.ktrdr/shared/strategies/` | Experiment specifications |
| Model artifacts in `~/.ktrdr/shared/models/` | Trained models |

### GitHub Integration

| Action | Mechanism |
|--------|-----------|
| File capability request | `gh issue create --title "..." --body "..." --label squad:architect` |
| Track build progress | Squad checks issue status in capability-gaps.md |
| Notify squad of new capability | Loop runner checks for closed issues with `squad:architect` label |

---

## Milestone Structure

### M1: Squad Bootstrap + First Manual Cycle
- Write all 8 agent charters
- Create shared knowledge templates
- Seed knowledge base with existing experiment history
- Build minimal loop runner (prompt assembly + output parsing)
- Execute ONE manual cycle: assemble prompt → run Claude → parse output → execute experiment → evaluate
- Validate: the squad produces an experiment that makes sense given the history

### M2: Automated Loop
- Loop runner executes N cycles unattended (Ralph loop pattern)
- Automatic state updates after each cycle
- Director controls cadence (full squad vs quick iteration)
- Validate: 5 experiments run without human intervention

### M3: Scout Integration
- Scout agent with web search capability
- Bibliography and external insights pipeline
- Integrated into squad session (Scout presents findings during STRATEGIZE)
- Validate: Scout brings an external insight that influences experiment design

### M4: Architect + GitHub Pipeline
- Architect produces capability gap analysis
- Automatic GitHub issue creation for capability requests
- Capability availability detection (closed issues → components.md update)
- Validate: Architect identifies a gap, issue is created, capability is built, squad uses it

### M5: Synthesis + Long-Run Evaluation
- Scribe synthesis cycle (every 10 experiments)
- Context management (trim old histories, rely on synthesis)
- Evaluate after 20-30 experiments: are experiments getting more sophisticated?
- Document what works and what doesn't about the squad model
