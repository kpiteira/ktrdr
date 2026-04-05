---
design: docs/designs/research-squad-v2/DESIGN.md
architecture: docs/designs/research-squad-v2/ARCHITECTURE.md
---

# Conversational Squad Orchestrator — Implementation Plan

## Design Reference
- **Design:** `docs/designs/research-squad-v2/DESIGN.md`
- **Architecture:** `docs/designs/research-squad-v2/ARCHITECTURE.md`
- **Spike:** `.squad/spikes/conversational_squad.py` (validated pattern)
- **V1 Handoffs:** `docs/designs/research-squad/implementation/HANDOFF_*.md`

## Milestone Summary

| Milestone | Name | Tasks | Deps | When someone can... |
|-----------|------|-------|------|---------------------|
| M1 | Core + First Cycle | 6 | None | The squad produces one real experiment end-to-end — designed, validated, trained, backtested, recorded — without the 75% YAML failure rate or 230K token cost of v1 |
| M2 | Director-Driven Consultation | 4 | M1 | The squad's experiments improve because the Director brings in the right expertise — Quant catches a cost problem before training, Critic catches overfitting before execution — instead of always consulting all 8 agents |
| M3 | Multi-Turn Debate | 4 | M2 | The squad produces experiments the Engineer wouldn't reach alone — a Critic challenge forces genuine redesign, an Inventor brainstorm opens a new frontier, through real back-and-forth rather than single-pass input |
| M4 | Loop Automation | 5 | M1 | Karl starts the squad and walks away — it runs 5+ cycles, manages its own cadence, detects when it's stuck, compounds knowledge, and replaces loop_runner.sh entirely |
| M5 | Lux Integration | 3 | M4 | Lux runs the squad autonomously — starts cycles, steers via nudges, reflects on findings, stores insights — Karl reviews periodically, not every cycle |

**Total:** 22 tasks across 5 milestones

## Dependency Graph

```
M1 (Core + First Cycle)
     │
     ├─────────────────┐
     ▼                 ▼
M2 (Consultation)   M4 (Loop Automation)
     │                 │
     ▼                 ▼
M3 (Debate)         M5 (Lux Integration)
```

M1 gates everything. M2→M3 is sequential (debate builds on consultation). M4 can start in parallel with M2. M5 requires M4.

## Branch Strategy

Each milestone gets its own branch:
- M1: `impl/squad-v2-M1-core`
- M2: `impl/squad-v2-M2-consultation`
- M3: `impl/squad-v2-M3-debate`
- M4: `impl/squad-v2-M4-loop`
- M5: `impl/squad-v2-M5-lux`

## What Exists Today (v1 Inventory)

### Preserved as-is
| Component | Location | Notes |
|-----------|----------|-------|
| 8 agent charters | `.squad/agents/{role}/charter.md` | System prompts. Well-tested across 40+ cycles. |
| executor.sh | `.squad/executor.sh` | Train+backtest pipeline. Robust JSON handling, stall detection. |
| Knowledge base | `~/.ktrdr/shared/squad/` | experiments.md (43KB, ~120 entries), synthesis.md, frontiers.md, agent histories |
| Shared strategies dir | `~/.ktrdr/shared/strategies/` | Where agents write YAML files |

### Reused — existing runtime types
| Component | Location | How v2 uses it |
|-----------|----------|---------------|
| `AgentResult` | `ktrdr/agents/runtime/protocol.py` | Return type from agent queries — reuse for squad agent responses |
| `AgentRuntimeConfig` | `ktrdr/agents/runtime/protocol.py` | Config dataclass — extend for squad-specific settings |
| `SafetyGuard` | `ktrdr/agents/runtime/safety.py` | Budget + tool allowlist checks — use for squad cost control |
| `BudgetChecker` protocol | `ktrdr/agents/runtime/safety.py` | Budget interface — squad implements for per-cycle tracking |
| CLAUDECODE env var management | `ktrdr/agents/runtime/claude.py:111` | Pattern: `os.environ.pop("CLAUDECODE", None)` in finally block |
| Lazy SDK import | `ktrdr/agents/runtime/claude.py:29-33` | `_get_sdk()` avoids mcp package shadowing in dev |

### NOT reused — different API pattern
| Component | Why not |
|-----------|---------|
| `ClaudeAgentRuntime.invoke()` | One-shot `sdk.query()` pattern. Squad needs multi-turn `connect()` → `query()` → `receive_response()` (persistent sessions). |
| `AgentRuntime` protocol | Defined for one-shot `invoke()`. Squad agents need `start()` / `query()` / `stop()` lifecycle. |

### Replaced by v2
| v1 Component | v2 Replacement |
|-------------|---------------|
| `loop_runner.sh` (810 lines) | `.squad/orchestrator/loop.py` |
| `loop_lib.sh` (150 lines) | `.squad/orchestrator/context.py` |
| `monitor.sh` (44 lines) | Replaced or removed in M4 |
| `test_synthesis.sh` (220 lines) | Python unit tests |
| `claude -p` invocations | `claude_agent_sdk` persistent sessions |

### v1 is dead
v1 doesn't work — 75% YAML failure, 50% evaluate failure, 230K tokens/cycle. It's not a fallback. v1 shell scripts stay in the repo as reference during implementation but will not be run again. v2 owns the state directory from M1 onward.

### current-experiment.md
v1 used `loop/current-experiment.md` to track the active experiment. v2 supersedes this with `loop/cycle-history.json` which tracks all cycles. v2 does not read or write current-experiment.md.

## Key Architectural Constraints

Every task must respect:
1. **Director is the LLM coordinator** — calls tools to orchestrate; Python never makes routing decisions
2. **claude_agent_sdk persistent sessions** — `connect()` → `query()` → `receive_response()` pattern (spike-validated)
3. **Reuse existing runtime types** — `AgentResult`, `SafetyGuard`, `BudgetChecker` from `ktrdr/agents/runtime/`
4. **Disk-based state only** — all knowledge in `~/.ktrdr/shared/squad/` markdown files
5. **executor.sh preserved** — call via subprocess, don't rewrite
6. **Charters preserved** — 8 agent charters as system prompts, unchanged
7. **Best model for all agents** — Opus for every squad member
8. **Context routing is Director-decided** — not hardcoded per role
9. **Sessions torn down between cycles** — history.md carries forward learning

## File Layout

```
.squad/
  orchestrator/
    __init__.py
    session.py            # PersistentAgentSession — multi-turn wrapper over claude_agent_sdk
    context.py            # Context loading, token estimation, synthesis detection
    tools.py              # AgentManager + validate_strategy + execute_experiment
    director_prompt.py    # Director's system prompt assembly
    loop.py               # Outer loop: create Director, check cadence/stall/synthesis

  executor.sh             # UNCHANGED — train+backtest pipeline
  loop_runner.sh          # v1 DEAD — reference only, not executed
  loop_lib.sh             # v1 DEAD — logic ported to context.py
  monitor.sh              # v1 DEAD — replaced in M4
  agents/*/charter.md     # UNCHANGED — 8 agent charters
```

## Cost Targets (tokens per cycle)

| Cycle Mode | Token Budget | Agents Involved |
|------------|-------------|-----------------|
| `quick_iteration` | 50-80K tokens | Director + Engineer |
| `full_squad` | 80-120K tokens | Director + Engineer + 2-3 consultants + Scribe |
| `synthesis` | <30K tokens | Director + Scribe |
| v1 baseline | ~230K tokens | All 8 agents every cycle |

Validation targets use tokens, not dollars (dollar costs depend on model pricing which changes).

## Spike Gotchas (Must Respect)

From `.squad/spikes/SPIKE_RESULTS.md`:
- `connect(prompt)` hangs — must be `connect()` then `query(prompt)`
- Unset `CLAUDECODE` env var to avoid nested session errors (existing pattern at `ktrdr/agents/runtime/claude.py:111`)
- `disconnect()` throws CancelledError — wrap in try/except
- Use system claude (2.1.89+), not bundled
- Run from clean directory to avoid local `mcp/` shadowing pip package (existing pattern at `ktrdr/agents/runtime/claude.py:29`)
