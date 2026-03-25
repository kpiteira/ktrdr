# Research Squad: Design

## Problem Statement

ktrdr has comprehensive trading research infrastructure but no mechanism for *compounding discovery*. Individual experiments are automated (design → train → backtest → assess) but the process of deciding *what* to experiment on is either manual or shallow (parameter tweaks by a single agent). The system needs collaborative multi-agent reasoning that drives toward increasingly sophisticated trading architectures over time.

## Goals

1. **Compound knowledge across experiments** — experiment #100 should leverage synthesized insights from #1-99, not just the last few
2. **Drive qualitative leaps** — from "swap RSI for Stochastic" to "add cross-asset DXY context to an LSTM signal model filtered by regime classification"
3. **Maintain productive tension** — multiple perspectives (innovation vs rigor, feasibility vs ambition) prevent convergence on local optima
4. **Run autonomously** — the squad iterates without human intervention, with humans reviewing periodically
5. **Integrate with existing ktrdr infrastructure** — use the training pipeline, backtest engine, and ensemble composition that already work

## Non-Goals

- Building a new training or backtest engine (use what exists)
- Replacing human oversight (the squad proposes, Karl reviews)
- General-purpose multi-agent framework (purpose-built for trading architecture discovery)
- Real-time trading system (discovery happens offline, deployment is separate)

---

## The Squad

### Design Decision D1: Agent Roles

The squad is a fixed team of specialists. Each agent has a **charter** (identity, expertise, thinking style), **persistent memory** (what it has learned about this specific project), and a **voice** (how it contributes to discussions).

| Role | Charter | Thinking Style | Voice in Discussions |
|------|---------|---------------|---------------------|
| **Director** | Strategic research leadership. Sees the full experiment history. Identifies exploration frontiers. Prioritizes what to investigate next. Controls cadence. | Top-down, strategic, pattern-matching across experiments. Thinks in terms of research programs, not individual experiments. | "We've spent 20 experiments on indicator combinations with diminishing returns. The frontier is cross-asset data — that's where unexploited information lives." |
| **Inventor** | Novel architectures and unconventional approaches. Challenges assumptions. Proposes structural innovations that others wouldn't consider. | Divergent, creative, cross-domain. Draws analogies from other fields. Comfortable with ideas that might fail. | "What if instead of predicting direction, we predicted regime transitions? The model doesn't need to know WHERE the market goes, just WHEN it changes character." |
| **Quant** | Trading domain expertise. Market microstructure, cost models, regime behavior, what actually matters for profitability. Bridges ML and finance. | Domain-grounded, practical, skeptical of theoretical improvements that don't survive transaction costs. | "25% win rate with 0.41 profit factor means every winning trade needs to be 2.4x the average loss. That's not a signal problem — it's a position sizing and exit problem." |
| **Engineer** | ktrdr architecture expertise. Knows what's buildable, what components exist, what integrations are feasible. Translates ideas into executable specifications. | Bottom-up, pragmatic, systems-thinking. Knows the codebase and its constraints. | "We have LSTM training, ensemble backtesting, and regime classification. A regime-conditional LSTM is feasible — I can compose these. But cross-asset data needs a new data provider." |
| **Critic** | Experimental rigor and statistical validity. Challenges results, identifies confounds, demands proper validation. Prevents self-deception. | Adversarial, precise, evidence-based. Won't accept claims without proper OOS validation. | "61% val accuracy is meaningless with this label distribution. Show me the calibration curve. And 289 trades over 4 years is not statistically significant for Sharpe estimation." |
| **Architect** | Capability gap identification. Looks at the distance between what the squad wants to test and what it can test. Proposes new components, data sources, model types. Designs infrastructure work. | Gap-analysis, forward-looking, systems-level. Sees the toolbox, sees what's missing. | "The squad keeps proposing cross-asset experiments but we have no feature pipeline for external data. I'm designing a DXY/VIX/yields provider — here's what it needs to do and how it integrates." |
| **Scout** | External knowledge acquisition. Actively searches the internet for relevant publications, techniques, and approaches from quantitative finance and ML. Brings back concrete, actionable insights — not background knowledge. | Investigative, curious, always reading. Maintains a bibliography. Brings external evidence to debates. | "I found 3 recent papers on temporal fusion transformers for financial forecasting. Key finding: multi-horizon attention over mixed-frequency inputs outperforms LSTM by 12% on FX. The architecture is feasible with our infrastructure. Here are the references." |
| **Scribe** | Knowledge management. Synthesizes experiment results into patterns. Maintains the shared knowledge base. Ensures nothing is forgotten or repeated. | Synthetic, organizational, longitudinal. Sees patterns across time that individual agents miss. | Doesn't participate in debates. Observes, records, and periodically presents synthesized insights. |

**Why these roles:** Each role addresses a specific failure mode we've observed:
- Director prevents "random walk" exploration (no strategic direction)
- Inventor prevents "local optima" (only trying obvious things)
- Quant prevents "academic solutions" (impressive metrics, unprofitable trading)
- Engineer prevents "impossible designs" (architectures that can't be built)
- Critic prevents "self-deception" (overfitting, statistical insignificance, data leakage)
- Architect prevents "toolbox stagnation" (squad limited by missing infrastructure, keeps proposing experiments it can't run)
- Scout prevents "closed-world thinking" (squad only knows what it has tried, never imports external knowledge)
- Scribe prevents "amnesia" (repeating experiments, losing insights)

### Design Decision D2: Agent Identity and Memory

Each agent is defined by two files:

**Charter (`charter.md`)** — static identity:
- Who they are and how they think
- Their domain expertise
- How they interact with other roles
- What they own (Director owns prioritization, Critic owns validation standards, etc.)

**History (`history.md`)** — growing project-specific memory:
- What they've learned from experiments in THIS project
- Positions they've taken and whether they were vindicated
- Patterns they've noticed
- Updated after every squad session

The charter is written once and rarely changes. The history grows continuously and is the mechanism by which agents get smarter over time.

---

## The Research Loop

### Design Decision D3: Iteration Structure

Each research cycle follows a structured loop inspired by the Ralph pattern (disk-based state, fresh context per iteration, backpressure from real validation):

```
┌─────────────────────────────────────────────────────────┐
│                    RESEARCH CYCLE                         │
│                                                           │
│  1. ORIENT                                                │
│     Scribe presents: current state, recent results,       │
│     open hypotheses, synthesized patterns                 │
│                                                           │
│  2. STRATEGIZE                                            │
│     Scout presents: external research findings relevant    │
│     to current frontiers (new techniques, papers, data)    │
│     Director proposes exploration frontier                 │
│     Team debates: Inventor pushes novelty,                │
│     Quant grounds in market reality,                      │
│     Engineer checks feasibility,                          │
│     Architect flags capability gaps                        │
│                                                           │
│  3. DESIGN                                                │
│     Engineer translates consensus into executable spec:    │
│     strategy YAML, model config, data requirements,       │
│     specific hypothesis being tested                      │
│                                                           │
│  4. EXECUTE                                               │
│     Run the experiment: train + backtest via ktrdr CLI     │
│     (No agent involvement — pure infrastructure)           │
│                                                           │
│  5. EVALUATE                                              │
│     Critic leads: statistical validity, OOS performance,   │
│     comparison to baselines, confound analysis             │
│     Quant assesses: tradability, cost impact, regime bias  │
│                                                           │
│  6. LEARN                                                 │
│     Scribe records: what was tried, what happened, why,    │
│     hypothesis status updates, new hypotheses generated    │
│     Each agent updates their history.md                    │
│                                                           │
│  7. SYNTHESIZE (every N cycles)                           │
│     Scribe presents macro patterns across all experiments  │
│     Director recalibrates research program                 │
│     Team identifies capability gaps                        │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

**Why this structure:**
- ORIENT ensures the team starts from shared understanding, not stale assumptions
- STRATEGIZE separates "what frontier to explore" from "what specific experiment to run"
- DESIGN produces a concrete, executable specification (not vague ideas)
- EXECUTE has zero agent involvement — backpressure comes from reality, not self-assessment
- EVALUATE is led by the Critic, not the experiment designer — independent review
- LEARN updates persistent state so the next cycle builds on this one
- SYNTHESIZE prevents local optimization by periodically zooming out

### Design Decision D4: Squad Execution Model

**Separate sessions per agent, coordinated by a hub.** Each squad member runs as a separate Claude Code Agent with its own context window. A Coordinator (the main session or loop runner) orchestrates the flow — deciding who speaks when, what context each agent sees, and how responses route between agents.

This mirrors the Squad framework (Brady Gaster): the Coordinator dispatches via the Agent tool, collects responses, and routes follow-ups via SendMessage. Agents never talk to each other directly — all communication flows through the Coordinator.

**Why separate sessions:**
- Each agent genuinely has its own perspective (no consensus drift within a shared context)
- The Critic evaluates the Inventor's proposal without being influenced by the Inventor's enthusiasm
- Each agent's context is lean — only its charter + history + the specific input it needs
- SendMessage preserves agent context across rounds within a cycle (Critic carries context from STRATEGIZE to EVALUATE)
- Between cycles, agents start fresh but their `history.md` carries forward what they learned

**All agents use the best available model** (currently Claude Opus). These are deep thinking tasks — no place for smaller models. The subscription covers this.

See ARCHITECTURE.md for the detailed execution flow showing which agents are spawned in which order with what context.

### Design Decision D5: The Cadence

The Director decides when to convene the full squad vs when to just iterate.

**Full squad session** (ORIENT through LEARN): When the team needs to change direction, evaluate a frontier, or after a significant result.

**Quick iteration** (just DESIGN → EXECUTE → EVALUATE → LEARN): When the team has agreed on a frontier and is exploring within it. The Engineer designs the next variant, the Critic evaluates the result, the Scribe records it. No strategic debate needed.

**Synthesis session** (SYNTHESIZE): Every 5-10 experiments, or when the Scribe identifies that accumulated results warrant a macro review. The Director can also call this when they sense diminishing returns.

---

## Shared Knowledge Base

### Design Decision D6: Knowledge Architecture

All state lives in markdown files, committed to the repo. Simple, inspectable, diffable.

```
.squad/
  team.md                    # Roster and role descriptions
  agents/
    director/
      charter.md             # Static identity
      history.md             # What Director has learned
    inventor/
      charter.md
      history.md
    quant/
      charter.md
      history.md
    engineer/
      charter.md
      history.md
    critic/
      charter.md
      history.md
    architect/
      charter.md
      history.md
    scout/
      charter.md
      history.md
      bibliography.md         # Papers, articles, techniques found
      reading-queue.md        # What to investigate next
    scribe/
      charter.md
      history.md

  knowledge/
    experiments.md            # Structured experiment log
    hypotheses.md             # Hypothesis tracker (replaces memory/hypotheses.yaml)
    components.md             # What's in the toolbox (models, features, compositions)
    decisions.md              # Architectural decisions and rationale
    synthesis.md              # Scribe's macro pattern analysis
    frontiers.md              # Active exploration directions

  roadmap/
    capability-gaps.md        # Architect's gap analysis: what the squad needs but can't do
    build-queue.md            # Infrastructure work items (new data providers, model types, etc.)
    external-insights.md      # Scout's curated findings from external research

  loop/
    current-experiment.md     # What's being run right now
    last-result.md            # Most recent experiment results
    iteration-count.txt       # How many cycles we've done
```

### The Experiment Log (`experiments.md`)

Not a raw dump — a structured, synthesized record:

```markdown
## Experiment 47: Regime-Conditional LSTM with DXY Context

**Hypothesis:** Adding DXY momentum as a cross-asset feature to the LSTM signal model improves OOS Sharpe by filtering trades that go against USD macro flow.

**Architecture:**
- Regime classifier (existing, MLP, 72% accuracy)
- LSTM signal model (seq_length=20, hidden=64) with 6 additional DXY-derived features
- Ensemble: route to LSTM only in trending regime

**Results:**
- Train: val_accuracy 63.2% (vs 61% baseline LSTM without DXY)
- Backtest (2021-2025 OOS): 312 trades, 28.4% win rate, -0.08% return, Sharpe -0.31
- Improvement over baseline LSTM: Sharpe -0.31 vs -0.75 (+0.44)

**Assessment (Critic):** Marginal improvement. DXY adds information but not enough to cross profitability threshold. The regime filter helped (312 vs 289 trades with better win rate). Direction is promising but needs stronger cross-asset features.

**Hypotheses generated:**
- H_087: Rate differential (US-EU 2Y spread) may be stronger than DXY alone
- H_088: Combining DXY + VIX as dual context might capture both direction and volatility regime

**Status:** Promising direction — continue exploring cross-asset features
```

### The Hypothesis Tracker (`hypotheses.md`)

Replaces the current `memory/hypotheses.yaml` (which devolved into 300+ low-quality auto-generated entries). Maintained by the Scribe, curated by the Critic:

```markdown
## Active Hypotheses

### H_087: Rate differential stronger than DXY alone
- **Source:** Experiment 47 (DXY showed marginal improvement)
- **Rationale (Quant):** EURUSD is fundamentally driven by EUR-USD rate differential. DXY measures broad dollar strength which includes non-EUR effects. Direct rate spread is a purer signal.
- **Status:** Queued for testing
- **Priority (Director):** High — most theoretically grounded cross-asset feature

### H_088: DXY + VIX dual context
- **Source:** Experiment 47
- **Rationale (Inventor):** DXY captures directional pressure, VIX captures risk regime. Together they might separate "trending because of fundamentals" from "trending because of panic."
- **Status:** Queued for testing
- **Priority (Director):** Medium — creative but speculative
```

### The Component Catalog (`components.md`)

What the squad has available to compose with:

```markdown
## Available Components

### Models
| Component | Type | Performance | Notes |
|-----------|------|-------------|-------|
| Regime Classifier | MLP (classification) | 72% accuracy | Works. Distinguishes trend/range/volatile. |
| LSTM Signal (standard indicators) | LSTM (classification) | 61% val accuracy, -0.75 OOS Sharpe | Finds temporal signal but not profitable. |
| MLP Signal (standard indicators) | MLP (classification) | ~35% (random) | Dead. Cannot learn from point-in-time values. |

### Features
| Feature Set | Source | Status | Notes |
|-------------|--------|--------|-------|
| Standard indicators (RSI, ADX, MACD, ROC) | EURUSD OHLCV | Available | Gaussian fuzzy + raw hybrid encoding |
| CFTC COT data | External API | Provider built (M9) | Weekly, positioning data |
| Cross-asset (DXY, yields, VIX) | IB Gateway | Data available, not integrated | Needs feature pipeline integration |

### Compositions
| Composition | Components | Result | Notes |
|-------------|-----------|--------|-------|
| Regime-gated ensemble (MLP signals) | Regime classifier + MLP signals | 0 effective trades | Signal models are dead |
| Direct LSTM | LSTM alone, no gating | -0.21% return, 289 trades | Has signal, not profitable |

## Capability Gaps (identified by squad)
- No cross-asset feature pipeline for signal models
- No attention mechanism available
- No position sizing beyond fixed
- No multi-symbol training
```

---

## The Critic's Evaluation Framework

The Critic is the squad's quality gate. Current backtest evaluation (Sharpe + win rate + drawdown) is insufficient. The Critic demands:

### Tier 1: Basic Metrics (every experiment)
- Sharpe ratio, Sortino ratio, Calmar ratio
- Win rate, profit factor, avg win / avg loss
- Total trades, max drawdown, total return
- Comparison to baseline (previous best and random)

### Tier 2: Statistical Rigor (when results look promising)
- **Statistical significance:** Is the Sharpe significantly different from zero? (Bootstrap confidence intervals, minimum 200 trades for meaningful estimation)
- **Walk-forward validation:** Does the result hold across multiple non-overlapping test windows? (e.g., 2021-2022, 2022-2023, 2023-2024 separately)
- **Parameter sensitivity:** Does ±20% on key parameters (confidence threshold, sequence length, hidden size) destroy the result? Robust strategies survive perturbation.
- **Regime-conditional performance:** Does the strategy work in trending AND ranging markets, or just one? Single-regime strategies are fragile.

### Tier 3: Trading Reality (when approaching profitability)
- **Cost sensitivity:** At what spread + slippage does the strategy break even?
- **Capacity:** Can you trade enough volume without moving the market?
- **Drawdown profile:** Is the max drawdown one catastrophic event or distributed? Single-event drawdowns indicate tail risk.
- **Time in market:** What percentage of time is capital deployed? Long idle periods reduce risk-adjusted returns.
- **Correlation with existing strategies:** Does this add diversification or duplicate existing approaches?

The Critic's charter includes these tiers. They don't all apply to every experiment — Tier 1 is mandatory, Tier 2 triggers when a result beats the current best, Tier 3 triggers when a result approaches positive Sharpe.

### What the Critic DOESN'T Do
- Judge ideas before they're tested (that kills innovation)
- Require Tier 3 validation for early-stage experiments
- Compare to unrealistic benchmarks

## How The Squad Gets Smarter

### The Compounding Mechanism

The critical difference between this and a single-agent loop is **how knowledge accumulates**:

1. **Agent histories grow** — the Quant remembers "we tried cost-aware thresholds in experiments 12-18 and found that cost matters more than signal strength." This shapes future discussions.

2. **Hypotheses are curated** — unlike the current system where 300+ hypotheses accumulate unfiltered, the Critic evaluates and the Director prioritizes. Bad hypotheses are marked dead. Good ones get tested.

3. **Synthesis reveals macro patterns** — the Scribe periodically identifies patterns like "every experiment with standard indicators plateaus at ~61% val accuracy regardless of architecture. The ceiling is in the features, not the model." This drives strategic pivots.

4. **The component catalog grows** — each successful component is documented and available for future compositions. The squad builds its own toolbox over time.

5. **Decisions compound** — architectural decisions (e.g., "D14: We will use LSTM for all signal models going forward, MLP is dead for this task") create a ratchet that prevents regression to known-bad approaches.

### Preventing Failure Modes

| Failure Mode | Prevention Mechanism |
|-------------|---------------------|
| Going in circles | Scribe tracks what's been tried; Critic flags repetition |
| Converging too quickly | Inventor's charter explicitly demands novel approaches; Director monitors exploration breadth |
| Ignoring negative results | Critic won't let the team cherry-pick; failed experiments are recorded with equal weight |
| Context window overflow | Scribe synthesizes — 100 experiments become 2 pages of patterns, not 100 pages of logs |
| Losing strategic direction | Director maintains `frontiers.md` — explicit list of what's being explored and why |
| Over-engineering | Engineer grounds every idea in what's buildable with existing infrastructure |
| Academic solutions | Quant evaluates every result through the lens of real trading (costs, slippage, liquidity) |
| Toolbox stagnation | Architect identifies gaps between what the squad wants to test and what it can test; proposes infrastructure work |
| Closed-world thinking | Scout actively searches external publications for techniques, data sources, and approaches the squad hasn't considered |
| Reinventing the wheel | Scout's bibliography prevents the squad from building what already exists in the literature |

---

## Integration with ktrdr

### What Already Exists

The squad uses ktrdr's existing infrastructure without modification:

| Capability | How the Squad Uses It |
|-----------|----------------------|
| Strategy YAML (v3 grammar) | Engineer writes experiment specs as strategy files |
| `ktrdr train` CLI | Execute phase — train models |
| `ktrdr backtest` CLI | Execute phase — backtest models |
| Ensemble runner | Composition testing — multiple models together |
| Model metadata | Track what was trained, with what features, what results |
| Data acquisition (IB + CFTC) | Data for standard and cross-asset features |
| LSTM/GRU models | Temporal architecture (just added) |
| Regime classifier | Component in the toolbox |

### What Needs Building

| Component | Purpose | Complexity |
|-----------|---------|-----------|
| Squad charter files | Define 8 agent identities | Low (markdown) |
| Coordinator logic | Orchestrate agent spawning, context routing, response collection | Medium (Claude Code session or Python) |
| Loop runner | Ralph-loop: Coordinator → execute experiment → update state → repeat | Medium (script/Python) |
| Shared knowledge templates | Experiment log, hypothesis tracker, component catalog, etc. | Low (markdown) |
| Result parser | Extract metrics from ktrdr output for the squad | Low (parse JSON) |

### What Might Need Building Later

| Component | Trigger |
|-----------|---------|
| Cross-asset feature pipeline | When squad identifies cross-asset as a priority frontier |
| Attention mechanism model | When squad wants to try attention architectures |
| Position sizing module | When squad identifies exit/sizing as a bottleneck |
| MCP knowledge server | When markdown files become too large for context |
| Advanced evaluation tools | Walk-forward analysis, parameter sensitivity, regime-conditional metrics |

---

## Key Scenarios

### Scenario 1: First Research Cycle

Squad starts with the full history of what we've done (signal model evolution M1-M5, H_003 experiment). Scribe presents the current state. Director identifies frontiers. The team debates and designs the first experiment.

Expected first experiment: likely cross-asset features with LSTM, since this is the most theoretically grounded unexplored direction (Quant advocates, Engineer confirms feasibility, Director prioritizes).

### Scenario 2: Diminishing Returns on a Frontier

After 10 experiments on cross-asset features, results plateau. The Critic flags that the last 5 experiments showed no improvement. The Scribe's synthesis confirms: "Cross-asset features improve Sharpe from -0.75 to -0.30 but can't cross into profitability."

Director calls a synthesis session. The team debates: pivot to a new frontier (attention mechanisms? multi-symbol training? novel indicators?) or dig deeper into cross-asset (are we using the wrong features? wrong composition?).

The Inventor proposes something unexpected: "What if the problem isn't the features or the model — what if it's the labeling? Triple barrier assumes symmetric TP/SL, but EURUSD trends are asymmetric."

This is the kind of qualitative leap that can't happen in a parameter-optimization loop.

### Scenario 3: A Breakthrough

Experiment 34 shows a Sharpe of +0.3 on 4 years OOS. The Critic demands:
- Is this statistically significant with only 200 trades?
- What's the drawdown profile — any single catastrophic event?
- Does it work across different 4-year windows (walk-forward)?
- Is the result robust to ±20% parameter variation?

The team runs additional validation. The Scribe documents the architecture in detail. The component catalog is updated. The Director sets the next frontier: "Can we improve this further, or should we diversify into a second uncorrelated strategy?"

### Scenario 4: Knowledge Accumulation Over 100 Experiments

After 100 experiments, the Scribe's synthesis reveals:
- "Standard indicators have a ceiling at ~61% val accuracy regardless of model architecture"
- "Cross-asset features add ~15pp to backtest metrics consistently"
- "Regime conditioning improves Sharpe by ~0.3 on average by avoiding ranging markets"
- "LSTM outperforms MLP on every comparison, but attention hasn't been tested yet"
- "The biggest single improvement came from experiment 34 (cross-asset + regime-gated LSTM)"

This synthesis becomes the shared context for future cycles. New experiments build on these established facts rather than re-discovering them.

---

## Milestone Structure

### M1: Squad Bootstrap + First Cycle
Build the squad definition, shared state templates, and loop runner. Execute one full manual cycle to prove the mechanics work.

### M2: Autonomous Iteration
Ralph-loop automation: the squad iterates N times unattended. Director controls cadence. Scribe auto-updates state.

### M3: Cross-Asset Integration
Based on expected squad priority — build the cross-asset feature pipeline for DXY/yields/VIX so the squad can explore this frontier.

### M4: Synthesis and Adaptation
After 20-30 experiments, evaluate: is the squad compounding knowledge? Are experiments getting more sophisticated? What's working and what's not? Adapt the loop/roles based on evidence.

### M5: Advanced Architecture Support
Based on squad requests — attention mechanisms, multi-symbol training, position sizing, or whatever the squad identifies as the next capability gap.

---

## Operational Model

### The Coordinator Role

The Coordinator is not a squad member — it's the orchestration layer that spawns agents, routes context, and manages the loop.

**For MVP (M1-M2):** The Coordinator is a Claude Code session run by Karl + Lux. Manual orchestration, learning what works.

**Beyond MVP (M3+):** Lux runs the Coordinator autonomously. Karl gets periodic updates (via Lux) and can nudge, redirect, or provide ideas. The squad runs without Karl needing to drive each cycle.

**Long-term:** The Coordinator could be a standalone process (Python script using the Anthropic SDK or Claude CLI) that runs continuously, triggered by cron or event-driven.

### Model Selection

All squad agents use the best available model (currently Claude Opus). These are deep thinking tasks:
- The Inventor needs genuine creativity, not pattern-matching
- The Critic needs rigorous reasoning about statistical validity
- The Quant needs deep domain knowledge about market microstructure
- The Scout needs strong reading comprehension for academic papers

No agent in the squad should use a smaller model. The subscription covers this — the squad is not cost-constrained on model quality.

### Human-in-the-Loop

Karl's involvement:
- **Reviews:** Periodic, not every cycle. Read the Scribe's synthesis, check frontiers, look at the best results.
- **Nudges:** "Have you considered X?" or "Stop exploring Y, it's a dead end" — fed as input to the next Director briefing.
- **Capability building:** When the Architect files issues, Karl (or Lux) builds the new infrastructure.
- **Not required for:** Individual experiment design, execution, or evaluation. The squad handles these autonomously.

## Open Questions

### Resolved
- ~~Agent voice consistency~~ → Resolved: separate sessions per agent, no consensus drift
- ~~Experiment specification format~~ → Resolved: Engineer writes YAML, Architect files issues for missing capabilities
- ~~Human-in-the-loop~~ → Resolved: Karl reviews periodically, nudges via Director input, builds capabilities when needed. Lux coordinates beyond MVP.
- ~~Cost~~ → Resolved: subscription-based, best model for all agents, not cost-constrained

### Still Open
1. **Context budget:** How much shared state fits per agent? Scribe synthesis helps, but after 100+ experiments we may need MCP or retrieval. Monitor and adapt.

2. **Evaluation gaps:** Critic's Tier 2/3 metrics (walk-forward, parameter sensitivity, regime-conditional) don't exist in ktrdr yet. Build as the squad needs them — Architect files issues.

3. **Scout quality filters:** How does the Scout distinguish high-quality research from noise? Charter should include skepticism about academic claims (no transaction costs, in-sample only, synthetic data, etc.).
