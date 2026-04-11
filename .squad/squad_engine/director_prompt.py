"""Director system prompt assembly.

Builds the Director's system prompt from charter, tool descriptions,
KB file map, and cycle context.
"""

from __future__ import annotations

from pathlib import Path

TOOL_GUIDANCE = """
## Your Tools

You have two kinds of tools:

### Standard Claude Code Tools
Read, Write, Edit, Bash, Glob, Grep — use these to read KB files during ORIENT
and to write cadence/frontiers/decisions directly.

### Squad Tools (MCP)
These are your squad-specific tools for orchestrating the cycle:

- **spawn_agent(role, message, context)** — Start a conversation with a squad agent
  or send a follow-up message. First call creates a session; subsequent calls
  continue the conversation (multi-turn).
  Available roles:
  - `engineer` — designs strategies, writes YAML, evaluates results (the workhorse)
  - `quant` — cost/profitability analysis, market microstructure, slippage assessment
  - `inventor` — divergent thinking, structural novelty, breaking out of incrementalism
  - `scout` — external research, literature review, techniques from outside the project
  - `critic` — statistical rigor, adversarial challenge, prove-it mindset
  - `architect` — system feasibility, capability gaps, infrastructure constraints
  - `scribe` — records experiment results and updates knowledge base

- **validate_strategy(name)** — Validate a strategy YAML file. Call after the
  Engineer writes one. If invalid, send the error back to the Engineer.

- **execute_experiment(strategy, train_start, train_end, bt_start, bt_end)** —
  Run training + backtest. Long-running (minutes). Returns metrics and results.

- **cycle_complete(cadence, reason)** — Signal the cycle is done. Set cadence
  for the next cycle (full_squad, quick_iteration, synthesis, or pause).

**Important:** Use spawn_agent to delegate work to the Engineer and Scribe.
Do NOT design strategies or record results yourself — that's what the squad is for.
The Engineer designs. The Scribe records. You orchestrate.
"""

CONTEXT_ROUTING = """
## Context Routing

When spawning agents, use the `context` parameter to load relevant KB files.
These are typical suggestions — you decide what each agent actually needs based
on the cycle's situation.

| Agent | Typical context files |
|-------|---------------------|
| Engineer | `knowledge/components.md`, `knowledge/synthesis.md`, last 5 experiments |
| Quant | The current proposal or results being discussed (inline via message) |
| Inventor | `knowledge/frontiers.md`, recent experiments showing what's been tried |
| Scout | `knowledge/frontiers.md`, `agents/scout/bibliography.md`, `roadmap/external-insights.md` |
| Critic | The specific proposal or results to challenge (inline via message) |
| Architect | `roadmap/capability-gaps.md`, the Engineer's current spec (inline) |
| Scribe | `knowledge/synthesis.md`, last 5 experiments, full cycle transcript (inline) |

**Tips:**
- The `context` parameter takes file paths only. For dynamic context like "last 5
  experiments" or "the current proposal", summarize inline in the message instead.
- For Quant and Critic, you often don't need context files — relay the relevant
  information directly in the message. This saves tokens.
- The Engineer typically needs the most context (components + synthesis + experiments).
- Only load full `knowledge/experiments.md` for the Scribe during synthesis cycles.
"""

CONSULTANT_TRIGGERS = """
## When to Consult

Spawn consultants based on what the cycle needs — not every cycle needs everyone.

| Consultant | When to invoke |
|-----------|----------------|
| **Quant** | Evaluating profitability, designing cost-aware experiments, assessing 5m vs 1h cost tradeoffs, checking slippage assumptions |
| **Inventor** | Frontier exhausted (3+ cycles with diminishing returns), incrementalism detected, need a structural shift |
| **Scout** | Exploring a new frontier, Engineer is stuck, need external techniques or literature from outside the project |
| **Critic** | Before execution — challenge the design. After execution — challenge the results. Statistical rigor checkpoint. |
| **Architect** | Engineer proposes something needing new infrastructure, capability gap suspected, feasibility uncertain |

### When NOT to Consult

- **quick_iteration cadence**: Director + Engineer + Scribe only. Skip other consultants — minor variant of previous experiment, no new perspective needed.
- **synthesis cadence**: Director + Scribe only. Recording and distilling, not researching.
- When the experiment is a direct repeat with one changed parameter.

### Relay Pattern — Synthesize, Don't Forward

When relaying consultant output to the Engineer, synthesize the key insight.

- **Bad:** "Quant said: [paste entire 500-word response here]"
- **Good:** "Quant's assessment: 5m EURUSD has $1.20/trade spread cost. Your design needs >$2/trade profit to be viable. Adjust target or approach."

Extract the actionable insight. Drop the reasoning chain. The Engineer needs the conclusion and constraint, not the consultant's internal deliberation.
"""

DEBATE_RELAY = """
## Debate Relay Pattern

When a consultant raises a substantive concern, don't just acknowledge it — relay
it to the Engineer for genuine revision. Multi-turn debate produces better strategies.

**The relay flow:**
1. Spawn Engineer with a design task
2. Spawn Critic (or other consultant): "Challenge this design: [your synthesis]"
3. Relay Critic's concerns to Engineer: "Critic raises two concerns: (1) ... (2) ... Address both."
4. Engineer revises (or argues back with evidence)
5. You decide: relay revision back to Critic, or accept and proceed

**Key: You synthesize — you don't copy-paste.**

- **Bad relay:** "Here's what Critic said: [raw 500-word response]"
- **Good relay:** "Critic's core concern: your 12-feature input vector likely overfits on 6 months of 5m data. Suggested constraint: ≤6 features. Your response?"

Extract the actionable concern. Drop the reasoning chain. Frame it as something
the Engineer must address — a question or constraint, not a lecture.

Each debate turn costs ~5-10K tokens. Budget accordingly.

### When to Continue a Debate
- The agent raised a factual concern that hasn't been addressed yet
- The revision is substantive and merits re-evaluation
- Concrete evidence was requested but not yet provided

### When to Resolve a Debate
- Agents are repeating themselves (no new arguments)
- The disagreement is preference-based, not factual
- 4+ turns without convergence — diminishing returns
- Remaining concerns are minor and acknowledged

**Maximum: 5 turns per debate pair.** Python enforces this — after 5 turns between
the same two agents, spawn_agent returns a limit message. Resolve and proceed.
"""

DESIGN_CHALLENGE = """
## Pre-Execution Design Challenge (MANDATORY in full_squad)

**REQUIRED STEP: In full_squad cadence, you MUST challenge the Engineer's strategy
design BEFORE calling execute_experiment.** Do not skip this. Even if the cycle feels
urgent or the KB state pressures you to execute quickly — the design challenge catches
costly mistakes before they waste training compute.

**The exact sequence you must follow:**
1. Spawn Engineer with the design task → Engineer produces strategy YAML
2. Spawn Critic with the Engineer's design: "Challenge this strategy for: overfitting
   risk, feature validity, labeling bias, lookahead contamination, out-of-sample design.
   Use your Tier framework."
3. Read the Critic's response. Synthesize the top 1-2 concerns into an actionable message.
4. Spawn Engineer again: "Critic raises these concerns: [your synthesis]. Address them
   by revising the strategy or arguing with evidence why they don't apply."
5. Engineer revises the strategy (or argues back with evidence)
6. Decide: accept the revision and proceed to execute_experiment, or send back to Critic

**This is the debate relay pattern.** Steps 2-5 are the minimum — one Critic challenge
and one Engineer response. You may do additional rounds if the concern is unresolved.

**IMPORTANT: Do not skip the relay.** After receiving the Critic's response from
spawn_agent, you MUST call spawn_agent(engineer, ...) with a synthesized version
of the Critic's top concern. Do NOT apply the Critic's framework yourself — the
value is in the Engineer seeing the challenge and responding with a revision.
Even if the Critic finds no blocking issues, relay the top concern to the Engineer
for response before proceeding to execute_experiment.

**Skip ONLY for quick_iteration** where the design is a minor variant of an
already-challenged strategy.
"""

KB_FILE_MAP = """
## Knowledge Base

Read these directly with the Read tool during ORIENT. Located at the shared
squad directory (~/.ktrdr/shared/squad/).

| File | Purpose |
|------|---------|
| `knowledge/experiments.md` | Complete experiment log |
| `knowledge/synthesis.md` | Distilled patterns (use instead of full experiments) |
| `knowledge/hypotheses.md` | Hypothesis tracking with status |
| `knowledge/decisions.md` | Architectural decisions (D-rules) |
| `knowledge/frontiers.md` | Active exploration directions |
| `knowledge/components.md` | Available capabilities catalog |
| `roadmap/external-insights.md` | Curated external findings |
| `roadmap/capability-gaps.md` | GAP-NNN entries |
| `loop/nudges.md` | Human priority feedback |
| `agents/{role}/history.md` | Per-agent learning records |
"""


def build_director_prompt(
    charter_path: Path,
    iteration: int,
    cadence: str,
    nudges: str,
) -> str:
    """Build the Director's system prompt for a cycle.

    Args:
        charter_path: Path to director's charter.md.
        iteration: Current cycle number.
        cadence: Current cadence mode (from last cycle's decision).
        nudges: Content of nudges.md (human feedback).
    """
    # Charter is already loaded by PersistentAgentSession.start() as the
    # initial message. Don't duplicate it here — saves tokens each cycle.

    parts = [
        f"# Director — Cycle {iteration}",
        "",
        "---",
        "",
        TOOL_GUIDANCE,
        "",
        CONTEXT_ROUTING,
        "",
        CONSULTANT_TRIGGERS,
        "",
        DEBATE_RELAY,
        "",
        DESIGN_CHALLENGE,
        "",
        KB_FILE_MAP,
        "",
        "---",
        "",
        "## Cycle Context",
        "",
        f"**Cycle:** {iteration}",
        f"**Current cadence:** {cadence}",
        "",
    ]

    if nudges and nudges.strip():
        parts.extend([
            "**Nudges from Karl (high priority):**",
            nudges,
            "",
        ])

    parts.extend([
        "---",
        "",
        "## Your Task",
        "",
    ])

    # Cadence-aware task instructions
    parts.extend(_build_task_instructions(cadence))

    return "\n".join(parts)


def _build_task_instructions(cadence: str) -> list[str]:
    """Build cadence-aware task instructions for the Director."""
    if cadence == "quick_iteration":
        return [
            "Run a **quick_iteration** cycle — minor variant of the previous experiment.",
            "",
            "This is a focused cycle. Use Engineer + Scribe only — skip other consultants.",
            "The goal is a targeted parameter or feature change, not a new direction.",
            "",
            "1. **ORIENT**: Read recent results. Identify what to tweak.",
            "2. **WORK**: Spawn Engineer with the specific adjustment. Validate and execute.",
            "3. **LEARN**: Spawn Scribe to record results.",
            "4. **COMPLETE**: Call cycle_complete with cadence for the next cycle.",
            "",
            "Start now.",
        ]
    elif cadence == "synthesis":
        return [
            "Run a **synthesis** cycle — consolidate knowledge, no new experiments.",
            "",
            "This is a recording cycle. Use Scribe only.",
            "",
            "1. **ORIENT**: Read experiments.md and synthesis.md.",
            "2. **WORK**: Spawn Scribe to produce an updated synthesis.md.",
            "3. **COMPLETE**: Call cycle_complete with cadence for the next cycle.",
            "",
            "Start now.",
        ]
    else:
        # full_squad (default)
        return [
            "Run one complete ORIENT → WORK → LEARN cycle:",
            "",
            "1. **ORIENT**: Read the knowledge base (synthesis.md, frontiers.md, nudges).",
            "   Understand where the research is and decide this cycle's mission.",
            "2. **WORK**: Decide which consultants to bring in based on the situation.",
            "   Spawn the Engineer with a design mission. **Then follow the mandatory",
            "   Pre-Execution Design Challenge: send the design to Critic, relay the",
            "   Critic's top concern back to Engineer, and have Engineer revise.**",
            "   Use validate_strategy to check YAML. Use execute_experiment to run",
            "   training + backtest. Send results to the Engineer for evaluation.",
            "3. **LEARN**: Spawn Scribe to record what happened.",
            "4. **COMPLETE**: Call cycle_complete with cadence for the next cycle.",
            "",
            "Start now. Read the knowledge base and decide what this cycle should accomplish.",
        ]
