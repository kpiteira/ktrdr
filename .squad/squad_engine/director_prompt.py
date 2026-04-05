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
  or send a follow-up message. Available roles: `engineer` (designs strategies,
  writes YAML, evaluates results) and `scribe` (records results to KB).
  First call creates a session; subsequent calls continue the conversation.

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
    charter = charter_path.read_text()

    parts = [
        f"# Director — Cycle {iteration}",
        "",
        charter,
        "",
        "---",
        "",
        TOOL_GUIDANCE,
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
        "Run one complete ORIENT → WORK → LEARN cycle:",
        "",
        "1. **ORIENT**: Read the knowledge base (synthesis.md, frontiers.md, nudges).",
        "   Understand where the research is and decide this cycle's mission.",
        "2. **WORK**: Use spawn_agent to give the Engineer a mission. The Engineer",
        "   will design a strategy and write the YAML. Use validate_strategy to check it.",
        "   If invalid, send errors back to the Engineer via spawn_agent. Once valid,",
        "   use execute_experiment to run training + backtest. Send results to the",
        "   Engineer for evaluation via spawn_agent.",
        "3. **LEARN**: Use spawn_agent to tell the Scribe what happened. The Scribe",
        "   records results in experiments.md and updates hypotheses.",
        "4. **COMPLETE**: Call cycle_complete with cadence for the next cycle.",
        "",
        "Start now. Read the knowledge base and decide what this cycle should accomplish.",
    ])

    return "\n".join(parts)
