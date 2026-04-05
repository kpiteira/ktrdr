# Conversational Squad Orchestrator: Design

## Problem Statement

The research squad runs 8 specialist AI agents through autonomous trading research cycles. The current implementation uses `claude -p` (one-shot CLI invocations) orchestrated by shell scripts. This produces:

1. **75% YAML failure rate** — Engineer gets one shot, no retry on validation errors
2. **~50% evaluate failure** — one-shot mode means no error recovery on file writes
3. **~230K tokens/cycle** — all 8 agents loaded regardless of need
4. **No real conversation** — agents can't debate, revise, or iterate
5. **Linear pipeline** — agents speak in fixed order, producing committee consensus instead of evolution

A validated spike (`.squad/spikes/conversational_squad.py`) proved that `ClaudePersistentRuntime` from agent-memory solves the mechanical problems: persistent multi-turn sessions, 0% YAML failure via validation loop, ~50-80K tokens/cycle.

But the deeper problem is conceptual, not mechanical. The linear pipeline treats all agents as equal participants in a sequence. The real model is: **an Engineer who does the work, a Director who orchestrates which expertise to bring in, and specialist consultants who provide lenses the Engineer looks through.**

## Goals

1. **Replace `claude -p` with persistent SDK sessions** — agents use real Claude Code tools with retry capability
2. **Replace the linear pipeline with Director-driven orchestration** — the Director decides who speaks, when, and about what
3. **Make the Engineer the workhorse** — designs strategies, evaluates results, iterates on experiments
4. **Enable multi-turn conversation** — agents debate, challenge, revise
5. **Enable evolution** — the squad produces increasingly sophisticated research, not incremental parameter tweaks
6. **Preserve existing infrastructure** — charters, knowledge base, executor.sh, loop state
7. **Build on agent-memory** — use `ClaudePersistentRuntime` as the session runtime

## Non-Goals

- Building a new training or backtest engine (use what exists)
- Replacing human oversight (Karl reviews periodically, nudges via loop state)
- General-purpose multi-agent framework (purpose-built for trading architecture discovery)
- Rewriting executor.sh (it works — call it from Python)

---

## The Squad

### The Protagonist: Engineer

The Engineer is the workhorse. It designs strategies, evaluates results, iterates on experiments. If you could only have one agent, it would be the Engineer. It knows the v3 strategy grammar, the available components (30 indicators, 3 model types, 5 labeling methods), and the system constraints. It composes existing components creatively and suggests practical approximations when ideal components don't exist.

The Engineer's session is persistent throughout the entire cycle. It's where the work happens.

### The Orchestrator: Director

The Director sees patterns across the research program. It decides which frontier to explore, which expertise the Engineer needs, and when to pivot. It doesn't do the work — it decides what work to do and who should inform it.

The Director's key power in the conversational model: **it decides who the Engineer talks to.** Not every cycle needs every agent. Sometimes the Engineer just needs the Critic. Sometimes it needs Inventor + Scout for a new direction. The Director reads the state and makes that call.

### The Consultants (on-demand, Director-invoked)

| Role | Lens | When Director invokes |
|------|------|----------------------|
| **Quant** | "Will this make money?" — cost, slippage, market microstructure | When evaluating profitability, designing cost-aware experiments |
| **Inventor** | "What if we tried something structurally different?" — divergent thinking | When the frontier is exhausted, when incrementalism sets in |
| **Scout** | "Here's what the outside world knows" — external research | When exploring a new frontier, when the Engineer is stuck |
| **Critic** | "Prove it" — statistical validity, adversarial rigor | When evaluating results, challenging designs before execution |
| **Architect** | "Can the system do this?" — feasibility, capability gaps | When the Engineer proposes something that might need new infra |

### The Recorder: Scribe

The Scribe doesn't participate in the work cycle. It activates during LEARN — recording results, updating experiments.md, hypotheses.md, and agent histories. Periodically it produces synthesis.md, the distilled knowledge that prevents context overflow.

### Why This Structure Produces Evolution

The linear pipeline produced committee consensus — 8 agents speaking in order, each adding their perspective, converging on a safe middle-ground experiment. That's how you get parameter tweaks.

The conversational model produces evolution because:
- **The Inventor** pushes toward structural novelty the Engineer wouldn't reach alone
- **The Scout** brings external breakthroughs that reframe the problem
- **The Critic** prevents self-deception, forcing honest assessment
- **The Director** recognizes when a frontier is exhausted and pivots
- **Multi-turn debate** means the Engineer can push back, ask clarifying questions, and synthesize perspectives rather than just accumulating input

Without the consultants, the Engineer would incrementally optimize the same approach forever. With them, the research program evolves.

---

## The Cycle

Three phases, not six. The old ORIENT → STRATEGIZE → DESIGN → EXECUTE → EVALUATE → LEARN was a rigid sequence. The new model:

### ORIENT

The Director reads the knowledge base (synthesis.md, recent experiments, nudges, frontiers.md) and decides what this cycle should accomplish. It sets the mission and decides which agents the Engineer needs.

No separate Scribe briefing — the Director reads the state directly. Having both the Scribe prepare a briefing AND the Director read it is redundant work.

### WORK

This replaces STRATEGIZE + DESIGN + EXECUTE + EVALUATE as separate rigid phases.

The Director orchestrates by calling tools: `spawn_agent` to bring in agents, `validate_strategy` to check YAML, `execute_experiment` to run training + backtest. The Engineer works. Consultants come and go as the Director decides:

- Director spawns Engineer with mission: "Explore frontier X, here's why"
- Director spawns Inventor and Scout for new directions, relays their perspectives to Engineer
- Director spawns Quant: "Would this survive costs?" → relays to Engineer → Engineer adjusts
- Director spawns Critic: "Challenge this design" → relays to Engineer → Engineer revises
- Engineer builds strategy YAML → Director calls `validate_strategy` → feeds error back to Engineer if needed
- Director calls `execute_experiment` → results come back → Director sends to Engineer for evaluation
- Director may spawn Quant/Critic again to assess results alongside Engineer
- Director decides: iterate (another pass through WORK), pivot, or commit

The key insight: **the Director is the coordinator LLM — it drives the cycle by calling tools.** Python provides the tool implementations but makes no routing decisions. There is no fixed sequence of who speaks when. The Director may loop through multiple design-validate-execute passes before committing.

### LEARN

The Scribe records what happened: experiment details, results, hypothesis status changes, agent learnings. The Scribe uses real Claude Code tools (Read, Edit, Write) with retry capability — the exact thing that was unreliable with one-shot `claude -p`.

The Director sets cadence for the next cycle.

---

## Agent Identity and Memory

Each agent is defined by two files:

**Charter (`charter.md`)** — static identity: who they are, how they think, what they own, how they interact. Written once, rarely changed.

**History (`history.md`)** — growing project-specific memory: what they've learned from experiments, positions they've taken, patterns they've noticed. Updated after every cycle by the Scribe.

The charter is the system prompt. The history is loaded as context. Between cycles, agent sessions are torn down — but history.md carries forward what they learned.

---

## Shared Knowledge Base

All state lives in `~/.ktrdr/shared/squad/`. Unchanged from the current system:

| File | Owner | Purpose |
|------|-------|---------|
| `knowledge/experiments.md` | Scribe | Complete experiment log |
| `knowledge/synthesis.md` | Scribe | Distilled patterns (replaces full history for most agents) |
| `knowledge/hypotheses.md` | Scribe | Hypothesis tracking with status |
| `knowledge/decisions.md` | Director | Architectural decisions (D-rules) |
| `knowledge/frontiers.md` | Director | Active exploration directions |
| `knowledge/components.md` | Architect | Available capabilities catalog |
| `roadmap/external-insights.md` | Scout | Curated external findings |
| `roadmap/capability-gaps.md` | Architect | GAP-NNN entries |
| `roadmap/build-queue.md` | Architect | Infrastructure work queue |
| `loop/cadence.md` | Director | Next cycle mode |
| `loop/iteration-count.txt` | Python outer loop | Cycle counter |
| `loop/nudges.md` | Human | Priority feedback |
| `agents/{role}/history.md` | Scribe | Per-agent learning records |

### Context Scaling

Synthesis.md replaces full experiments.md for most agents. The Scribe during synthesis gets full history; everyone else gets synthesis + last 5 experiments. Emergency synthesis triggers at 80% context budget.

This mechanism is unchanged — it works well.

---

## Integration

### What Already Exists and Is Preserved

| Component | Status |
|-----------|--------|
| Agent charters (8) | Preserved as-is |
| Knowledge base files | Preserved as-is |
| `executor.sh` | Called from Python via subprocess |
| `loop_lib.sh` | Context assembly functions rewritten in Python |
| Loop state files | Format preserved |

### New Dependency: agent-memory

The orchestrator imports `ClaudePersistentRuntime` from agent-memory for persistent agent sessions. Added via `uv add --path ../agent-memory`.

Long-term, the squad orchestrator becomes part of Lux's capabilities — Lux orchestrating the research squad.

### What Gets Replaced

| Old | New |
|-----|-----|
| `claude -p` invocations in loop_runner.sh | `ClaudePersistentRuntime` sessions |
| Shell-based loop (loop_runner.sh) | Python outer loop + Director LLM coordinator |
| Fixed 6-phase pipeline | Dynamic Director-driven WORK phase |
| All 8 agents every cycle | Director decides who to spawn |
| Claude writes state files via one-shot | Agents write via persistent sessions with retry |

---

## Key Scenarios

### Scenario 1: Standard Research Cycle

Director reads state: synthesis says standard indicators are exhausted on 1h, 5m shows promise. Nudges say to use LSTM/GRU. Director spawns Quant to discuss 5m cost assumptions, then spawns Engineer with the mission and Quant's cost assessment.

Engineer designs strategy YAML. Director calls `validate_strategy` — passes. Director calls `execute_experiment`. Results come back. Director sends results to Engineer for evaluation: -$18/trade, better than 1h but not profitable. Director writes cadence: quick_iteration for next cycle, try different features.

### Scenario 2: Frontier Exhaustion

After 5 cycles on 5m with diminishing returns, Director recognizes the pattern. Invokes Inventor + Scout: "We need a structural shift. Inventor, propose something we haven't tried. Scout, search for techniques relevant to multi-timeframe FX prediction."

Scout finds papers on temporal fusion transformers. Inventor proposes regime-conditional feature selection. Engineer synthesizes both perspectives into a concrete experiment. Critic challenges: "How will you validate this isn't overfitting to the selection criterion?" Engineer revises.

This is the kind of qualitative leap that can't happen in a parameter-optimization loop.

### Scenario 3: YAML Validation Loop

Engineer produces a strategy YAML. Director calls `validate_strategy` — fails: "fuzzy_set 'rsi_momentum' references indicator 'rsi_14' which doesn't exist in indicators dict." Director sends the error to Engineer via `spawn_agent(engineer, "Validation failed: ...")`. Engineer fixes the reference. Director validates again — passes.

With `claude -p`, this was a 75% failure rate. With persistent sessions and a Director-driven retry loop, it's a conversation.

### Scenario 4: Capability Gap

Engineer wants to use DXY as a cross-asset feature. Architect says BLOCKED — no cross-asset feature pipeline exists. Architect files a GAP, creates a GitHub issue, proposes a fallback experiment using available features. Director adjusts the frontier: "Use what we have now. DXY goes on the build queue."

---

## Operational Model

### Model Selection

All squad agents use the best available model (currently Claude Opus). These are deep thinking tasks — the Inventor needs genuine creativity, the Critic needs rigorous statistical reasoning, the Quant needs deep domain knowledge. No agent should use a smaller model.

### Human-in-the-Loop

Karl's involvement:
- **Reviews:** Periodic, not every cycle. Read synthesis.md, check frontiers, look at best results.
- **Nudges:** Written to `loop/nudges.md`. High priority — Director reads first.
- **Capability building:** When Architect files issues, Karl (or Lux) builds the infrastructure.
- **Not required for:** Individual experiment design, execution, or evaluation.

### Cost

- Typical cycle (Director + Engineer + 2-3 consultants): ~55-80K tokens
- Full cycle (all agents consulted): ~90-120K tokens
- Current pipeline: ~230K tokens
- Reduction: 50-75%

---

## Milestone Structure

### M1: Orchestrator Core + First Cycle

Build the Python tool layer (`spawn_agent`, `validate_strategy`, `execute_experiment`) and the Director session that calls them. Execute one full cycle: Director reads state → spawns Engineer → validation loop → execution → Engineer evaluates → Director spawns Scribe to record.

Validate: cycle completes end-to-end, YAML validates, results recorded.

### M2: Director-Driven Agent Selection

Director spawns consultants on demand via `spawn_agent`. Multi-turn: Director relays consultant perspectives to Engineer and vice versa.

Validate: Director invokes different agent combinations across cycles based on context.

### M3: Multi-Turn Debate

Engineer ↔ Critic debate. Engineer ↔ Inventor brainstorming. Real back-and-forth that produces better experiments than single-shot input.

Validate: conversation produces a revision (not just acknowledgment).

### M4: Loop Automation

Python owns the full iteration loop: cadence, synthesis triggering, stall detection, de-duplication. Runs N cycles unattended.

Validate: 5 cycles run without human intervention.

### M5: Lux Integration

Squad orchestrator becomes part of Lux's capabilities. Lux runs the squad, Karl reviews periodically.
