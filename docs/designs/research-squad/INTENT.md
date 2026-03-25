# Research Squad: Collaborative Architecture Discovery

## Status: Intent
## Date: 2026-03-24
## Contributors: Karl + Lux

---

## What We're Building

A squad of specialized AI agents that collaboratively discover trading system architectures through structured experimentation. Not auto-research that swaps indicators — a team that reasons about *why* things work, proposes structural innovations, debates trade-offs, and compounds knowledge across hundreds of experiments.

## Why

### The Journey So Far

We built a trading research platform (ktrdr) with comprehensive infrastructure: data acquisition, indicator computation, fuzzy encoding, neural network training, backtesting, ensemble composition, regime classification, temporal models (LSTM/GRU). The infrastructure works.

We then tried multiple approaches to automate the *discovery* of what to build:

1. **Manual research** — hand-designed every experiment. Too slow, too narrow.
2. **Autonomous researcher** (v2.0-v2.6) — single agent designs strategies, trains, backtests, assesses. Produces basic strategies with standard indicators. Never makes qualitative leaps. "Baby forever" problem.
3. **Auto-research** (Karpathy-inspired) — single agent iterates on a strategy YAML. Same limitation: parameter tweaks, no structural innovation.
4. **Primordial soup** — population-based evolution of researcher genomes. Designed but never built. Evolves personalities, not architectures.
5. **Signal model evolution** (M1-M5) — systematic fix of training pipeline. Proved the pipeline works but standard indicators carry no signal for MLP. Then LSTM showed temporal signal exists (H_003 confirmed) but isn't profitable yet.

Every approach failed at the same point: **the discovery mechanism doesn't compound**. Each experiment is essentially independent. There's no force that drives the system toward increasingly sophisticated architectures.

### What's Missing

The missing piece isn't infrastructure — it's **collaborative reasoning with memory**. A single agent designing strategies is like a lone inventor in a garage. What we need is a research lab — specialists who bring different perspectives, argue productively, and build on accumulated knowledge.

Specifically:
- **No tension between perspectives** — a single agent agrees with itself. It needs a Quant challenging its market assumptions, a Critic demanding statistical rigor, an Inventor pushing beyond obvious approaches.
- **No strategic direction** — the agent optimizes locally (this indicator vs that one) instead of identifying macro frontiers (we need cross-asset data, we need temporal modeling, we need regime-conditional architectures).
- **No compounding knowledge** — experiment #50 should leverage insights from experiments #1-49, not just the last 3. The system needs synthesized understanding, not a log.

## What It Involves

A **squad** of AI agents, each with a defined specialty and persistent memory, iterating through a structured research loop:

1. **Squad roles** — Director (strategy), Inventor (innovation), Quant (market expertise), Engineer (feasibility), Critic (rigor), Architect (capability gaps), Scout (external research), Scribe (memory)
2. **Shared knowledge base** — experiment history, hypothesis tracker, component catalog, architectural decisions, synthesized insights, external research bibliography
3. **Research loop** — squad discusses → designs experiment → executes (train + backtest) → evaluates → records → iterates
4. **Backpressure from reality** — real backtests on real OOS data. No experiment counts as successful without surviving the Critic's scrutiny.
5. **Compounding memory** — the Scribe synthesizes patterns from experiment history. After 100 experiments, the squad's shared knowledge should be qualitatively richer than a log of 100 results.

## What Success Looks Like

After running for weeks:
- The squad has explored multiple architectural frontiers (not just indicator swaps)
- Experiments show qualitative progression: simple → multi-model → cross-asset → novel compositions
- The shared knowledge base contains synthesized insights ("temporal patterns exist in standard indicators but don't cover costs — cross-asset context is the most promising unexplored direction")
- At least one architecture that outperforms any single-agent-designed strategy
- The squad can articulate *why* its best architecture works, not just that it does

## Connection to Prior Work

- **Squad framework** (Brady Gaster) — multi-agent collaboration model with persistent memory, Ralph loop iteration
- **Evolution brainstorm** (docs/agentic/evolution/) — selection pressure, forcing functions, behavioral signals
- **Vision north star** (docs/agentic/vision_north_star.md) — the dream of autonomous research that compounds
- **Predictive features INTENT** (docs/designs/predictive-features/) — the "brain regions" concept: regime brain + context brain + signal brain
- **H_003 experiment** — proved LSTM finds signal MLP can't, validating that architectural choices matter

## Open Questions (resolved in DESIGN.md and ARCHITECTURE.md)

1. ~~How do agent roles map to Claude sessions?~~ → Separate sessions per agent, Coordinator hub pattern (like Squad framework)
2. ~~What's the right iteration cadence?~~ → Director controls; full squad vs quick iteration vs synthesis session
3. ~~How do we prevent convergence?~~ → Inventor's charter demands novelty; Director monitors breadth
4. ~~What capabilities beyond ktrdr?~~ → Architect identifies gaps, files GitHub issues; Scout searches external research
5. ~~How does the component catalog evolve?~~ → Architect proposes, Karl/Lux builds, components.md updated on completion
