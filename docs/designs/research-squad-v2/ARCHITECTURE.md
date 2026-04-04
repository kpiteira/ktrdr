# Conversational Squad Orchestrator: Architecture

## System Boundary

```
┌─────────────────────────────────────────────────────────────────────┐
│                     DIRECTOR SESSION (LLM Coordinator)               │
│                                                                       │
│  Persistent Claude Code session with orchestration tools.             │
│  Reads KB state. Decides mission. Spawns consultants.                 │
│  Delegates all domain work to Engineer. Never does research itself.   │
│                                                                       │
│  Tools:                                                               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                 │
│  │ spawn_agent  │ │   validate   │ │   execute    │                 │
│  │              │ │   _strategy  │ │  _experiment │                 │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘                 │
│         │                │                │                          │
│  + standard Claude Code tools (Read, Edit, Write, Bash, Glob, Grep)  │
└─────────┼────────────────┼────────────────┼──────────────────────────┘
          │                │                │
          ▼                ▼                ▼
   ┌──────────────┐ ┌──────────┐    ┌──────────────┐
   │ Agent        │ │  ktrdr   │    │ executor.sh  │
   │ Sessions     │ │ validate │    │ (train +     │
   │              │ │          │    │  backtest)   │
   │ Engineer     │ └──────────┘    └──────────────┘
   │ Quant        │
   │ Inventor     │
   │ Scout        │
   │ Critic       │
   │ Architect    │
   │ Scribe       │
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │ Knowledge    │
   │ Base         │
   │ (~/.ktrdr/   │
   │  shared/     │
   │  squad/)     │
   └──────────────┘
```

The Director is the coordinator — an LLM session that orchestrates the cycle by calling tools. Python provides the tool implementations, not the decision-making.

---

## Component Responsibilities

| Component | Responsibility | Does NOT do |
|-----------|---------------|-------------|
| **Director Session** (LLM coordinator) | Reads KB state. Decides cycle mission. Spawns agents via `spawn_agent` tool. Routes work by deciding what to tell each agent. Triggers validation and execution via tools. Synthesizes agent outputs. Decides cadence. | Domain research work. Strategy design. Result evaluation. Writing KB files (except decisions.md, frontiers.md). |
| **Python Tool Layer** | Implements tools the Director calls: session management, subprocess execution, validation. Manages ClaudePersistentRuntime lifecycle. Runs the outer loop (iteration, cadence, synthesis triggering). | Make research decisions. Decide which agents to consult. Parse natural language intent. Route messages. |
| **Engineer Session** | Designs strategies. Writes YAML. Evaluates results. Synthesizes consultant input. The workhorse. | Decide strategic direction. Choose consultants. Manage the cycle. |
| **Consultant Sessions** | Provide domain-specific perspective when spawned. Challenge, ground, or expand the Engineer's thinking. | Initiate conversation. Drive the cycle. |
| **Scribe Session** | Records experiment results. Updates experiments.md, hypotheses.md, agent histories. Produces synthesis. | Participate in research discussion. |
| **Execution Layer** | Validates YAML. Runs training + backtest. Returns summarized results. | Make decisions. Access agent sessions. |

---

## Director's Tool Interface

The Director orchestrates by calling tools, not by producing text that Python parses.

### spawn_agent

Starts a new agent session or sends a message to an existing one.

```
spawn_agent(
    role: str,           # engineer, quant, inventor, scout, critic, architect, scribe
    message: str,        # what to tell the agent
    context: list[str],  # additional KB files to load (beyond charter + history)
) → AgentResult          # {output: str, cost_usd: float, turns: int, transcript: list}
```

- First call for a role within a cycle: creates a new `ClaudePersistentRuntime` session with the agent's charter as system prompt, history + requested context loaded
- Subsequent calls to same role: sends message to existing session (multi-turn)
- Director decides what context each agent needs by specifying files
- Agent response returned as `AgentResult` (reuses `ktrdr.agents.runtime.protocol.AgentResult`) — `.output` is the text, plus cost/turn tracking

### validate_strategy

Runs `ktrdr validate` on a strategy file.

```
validate_strategy(
    name: str,           # strategy name
) → ValidationResult    # {valid: bool, error: str | None, path: str | None}
```

Mechanical — no LLM involved. The Director calls this after the Engineer writes a YAML file, and feeds the result back to the Engineer if validation fails.

### execute_experiment

Runs training + backtest via executor.sh.

```
execute_experiment(
    strategy: str,       # strategy name
    train_start: str,    # training date range
    train_end: str,
    bt_start: str,       # backtest date range
    bt_end: str,
) → ExperimentResult    # {status: str, training: dict, backtest: dict} or {status: "FAILED", error: str}
```

Calls executor.sh as a subprocess. Long-running (minutes to hours). Returns summarized JSON results.

### Standard Claude Code Tools

The Director also has Read, Edit, Write, Bash, Glob, Grep — it reads KB files directly during ORIENT. It writes cadence decisions to `loop/cadence.md` and updates `knowledge/frontiers.md` and `knowledge/decisions.md`.

---

## Data Flow

### Within a Cycle

```
┌──────────┐
│Knowledge │──── reads directly ────► DIRECTOR
│  Base    │                            │
└──────────┘                            │
                                        │ spawn_agent(engineer, mission)
                                        ▼
                                   ┌──────────┐
                                   │ ENGINEER  │
                                   └────┬─────┘
                                        │
                        ┌───────────────┼───────────────┐
                        │               │               │
           Director spawns consultants as needed:
                        │               │               │
                        ▼               ▼               ▼
                   ┌────────┐     ┌────────┐     ┌────────┐
                   │ QUANT  │     │ CRITIC │     │INVENTOR│
                   └───┬────┘     └───┬────┘     └───┬────┘
                       │              │              │
                       └──────────────┼──────────────┘
                           responses  │
                                      ▼
                                  DIRECTOR
                                      │
                                      │ relays perspectives to Engineer
                                      │ spawn_agent(engineer, "Quant says X, Critic says Y")
                                      ▼
                                 ┌──────────┐
                                 │ ENGINEER  │── writes YAML ──► strategy file
                                 └──────────┘
                                      │
                              Director calls validate_strategy()
                                      │
                              Director calls execute_experiment()
                                      │
                              Director relays results to Engineer
                                      │
                                      ▼
                                  DIRECTOR
                                      │
                                      │ spawn_agent(scribe, "Record this cycle")
                                      ▼
                                 ┌──────────┐
                                 │  SCRIBE  │── writes ──► Knowledge Base
                                 └──────────┘
```

All routing decisions are the Director's. Python never decides what message goes where — it just implements `spawn_agent` by managing `ClaudePersistentRuntime` sessions.

### The Director Loops, Not Pipelines

The diagram above shows one possible path through a cycle. The Director is not constrained to follow it linearly. It calls tools in whatever order and frequency it judges necessary:

- **Multiple design passes:** Director spawns Engineer → Engineer produces a design → Director spawns Critic to challenge it → Director relays critique to Engineer → Engineer revises → Director spawns Quant to check costs → Director relays to Engineer → Engineer revises again → Director validates
- **Evaluation with iteration:** Results come back → Director spawns Engineer to evaluate → Engineer says "inconclusive, need Quant's cost analysis" → Director spawns Quant → Director relays to Engineer → Engineer produces final assessment
- **Pivot mid-cycle:** Director spawns Engineer with a plan → Architect says BLOCKED → Director spawns Inventor for alternative approach → Director gives Engineer the new direction → cycle continues with different experiment
- **Scout-driven exploration:** Director spawns Scout + Inventor together for new directions → Director synthesizes their output → Director gives Engineer a brief informed by both

The WORK phase is a loop, not a sequence. The Director decides when it's done — there is no predetermined number of passes or fixed order of agent consultation.

### Between Cycles

The only state that persists between cycles is the knowledge base. All agent sessions are torn down. The next cycle's Director reads fresh KB state and makes new decisions.

Agent `history.md` files are how individual agents "learn" across cycles without persistent sessions.

---

## State Machines

### Agent Session Lifecycle

```
                    ┌─────────┐
                    │  NONE   │
                    └────┬────┘
                         │ Director calls spawn_agent(role, ...)
                         │ Python creates ClaudePersistentRuntime
                         ▼
                    ┌─────────┐
              ┌────►│  ALIVE  │◄────┐
              │     └────┬────┘     │
              │          │ spawn_agent(same role, ...) │
              │          │ (multi-turn query)          │
              │          ▼          │
              │     ┌─────────┐    │
              │     │RESPONDING│   │ response returned to Director
              │     └────┬────┘    │
              │          │         │
              │          └─────────┘
              │
              │ cycle ends
              ▼
         ┌─────────┐
         │  NONE   │  (session torn down, history.md persists)
         └─────────┘
```

### Cycle Phases

```
ORIENT ──► WORK ──► LEARN ──► COMPLETE
             │  ▲
             │  │
             └──┘  (Director loops: spawn agents, build, validate, execute, evaluate)
```

ORIENT: Director reads KB directly (Read tool). No agents spawned.

WORK: Director calls tools in whatever order it decides. May spawn Engineer, then consultants, then validate, then execute, then spawn Engineer again to evaluate — or any other sequence. The Director drives.

LEARN: Director spawns Scribe. Scribe records the cycle.

### Outer Loop

```
                  ┌──────────┐
                  │  CHECK   │
                  │ CADENCE  │◄─────────────────────┐
                  └────┬─────┘                      │
                       │                            │
            ┌──────────┼──────────┐                 │
            ▼          ▼          ▼                 │
       ┌────────┐ ┌────────┐ ┌────────┐            │
       │ PAUSE  │ │SYNTHES.│ │ START  │            │
       │ (stop) │ │ CYCLE  │ │DIRECTOR│            │
       └────────┘ └───┬────┘ │SESSION │            │
                      │      └───┬────┘            │
                      │          │                  │
                      │     Director runs cycle     │
                      │     (calls tools)           │
                      │          │                  │
                      │     ┌────▼─────┐            │
                      │     │  CYCLE   │            │
                      │     │ COMPLETE │            │
                      │     └────┬─────┘            │
                      │          │                  │
                      └────┬─────┘                  │
                           │                        │
                      ┌────▼─────┐                  │
                      │  STALL   │──► STOP          │
                      │  CHECK   │                  │
                      └────┬─────┘                  │
                           │ ok                     │
                           └────────────────────────┘
```

The outer loop is Python. It creates the Director session, lets it run a cycle, tears it down, checks stall/cadence/synthesis, and repeats. This is the one place Python makes decisions — but they're mechanical (is iteration count > max? did cadence say pause? are 3 cycles stalled?).

---

## Context Assembly

### What Each Agent Sees

The Director decides what context each agent gets by passing file paths in the `context` parameter of `spawn_agent`. The Python tool layer loads those files into the session's initial context.

Defaults (loaded automatically for every agent):

| Agent | System Prompt | Always Loaded |
|-------|--------------|---------------|
| All agents | `charter.md` for that role | `agents/{role}/history.md` |

The Director adds context per-call. Typical patterns:

| Agent | Director typically requests |
|-------|---------------------------|
| Engineer | `components.md`, `synthesis.md`, last 5 experiments |
| Quant | The current proposal or results being discussed |
| Inventor | Current frontier, what's been tried |
| Scout | `frontiers.md`, `agents/scout/bibliography.md`, `roadmap/external-insights.md` |
| Critic | The proposal or results to challenge |
| Architect | Engineer's spec, `capability-gaps.md` |
| Scribe | Full cycle transcript, `synthesis.md`, last 5 experiments |

This is not hardcoded. The Director is an LLM — it reads the situation and decides what each agent needs to see. The tool layer just loads whatever files the Director requests.

### Scaling

- Synthesis.md replaces full experiments.md for most agents
- Scribe during synthesis gets full experiments.md
- Emergency synthesis triggers at 80% of 200K context budget
- Python estimates context size before creating sessions, triggers synthesis if needed

---

## Integration Points

### With agent-memory

Single dependency: `ClaudePersistentRuntime`. The `spawn_agent` tool implementation wraps it:
- Creates runtime with charter as system prompt
- Loads requested context files
- Provides `query()` for multi-turn
- Handles async locks and auto-recovery

### With ktrdr

| Integration | Tool | Mechanism |
|-------------|------|-----------|
| Strategy validation | `validate_strategy` | `ktrdr validate <name>` (subprocess) |
| Training + backtest | `execute_experiment` | `executor.sh` (subprocess) |
| Strategy files | Agent Write tool | Engineer writes to `~/.ktrdr/shared/strategies/` |

### With GitHub

Architect agent uses Bash tool to call `gh issue create` for capability gaps. This happens inside the Architect's Claude Code session — no special integration needed.

---

## Failure Modes and Recovery

| Failure | Detection | Recovery | Escalation |
|---------|-----------|----------|------------|
| Agent session won't start | `spawn_agent` tool returns error | Director sees error, can retry or skip that consultant | Director decides whether to proceed without that agent |
| YAML validation fails | `validate_strategy` returns invalid | Director sends error to Engineer, Engineer retries | After 5 failures, Director decides to abort or redesign |
| executor.sh fails | `execute_experiment` returns error | Director sends failure to Engineer for analysis | Engineer records failure. Cycle can still complete with LEARN. |
| Scribe can't update a KB file | Edit tool fails in Scribe session | Scribe retries (has real Claude Code tools) | After 3 failures per file, Director logs and proceeds |
| Context budget exceeded | Python checks before Director session creation | Trigger emergency synthesis cycle instead of research cycle | If synthesis also exceeds, stop loop |
| Stall (3 non-productive cycles) | Python tracks in outer loop | Stop loop | Write `fatal-error.md`. Human review needed. |
| Director session crashes | `ClaudePersistentRuntime` auto-recovery | Transparent retry | If recovery fails, outer loop catches exception, writes fatal error |

Key difference from previous design: the Director handles most recovery decisions itself. Python only intervenes for mechanical failures (session crash, budget exceeded, stall detection).

---

## File Layout

```
.squad/
  orchestrator/
    __init__.py
    tools.py              # Tool implementations: spawn_agent, validate_strategy, execute_experiment
    session.py            # AgentSession — wraps ClaudePersistentRuntime
    context.py            # Context loading (reads KB files, estimates tokens)
    loop.py               # Outer loop — creates Director, checks cadence/stall/synthesis
    director_prompt.py    # Director's system prompt (charter + tool descriptions + KB paths)

  executor.sh             # UNCHANGED — training + backtest execution
  loop_runner.sh          # DEPRECATED — replaced by orchestrator/loop.py
  loop_lib.sh             # DEPRECATED — replaced by orchestrator/context.py

  agents/                 # UNCHANGED
    {role}/charter.md     # 8 agent charters

~/.ktrdr/shared/squad/    # UNCHANGED — all knowledge base files
  knowledge/              # experiments, synthesis, hypotheses, decisions, frontiers, components
  roadmap/                # external-insights, capability-gaps, build-queue
  loop/                   # cadence, iteration-count, nudges, current-experiment
  agents/{role}/          # per-agent history.md
```

---

## Milestones

### M1: Core + First Cycle
Director session with `spawn_agent`, `validate_strategy`, `execute_experiment` tools. Engineer session only (no consultants). Engineer build loop with validation retry. executor.sh integration. Scribe LEARN phase.
**E2E test:** one cycle completes — Director spawns Engineer, YAML validates, training runs, Scribe records results.

### M2: Director-Driven Consultation
Director spawns consultants on demand. Multi-turn: Director sends consultant response to Engineer, Engineer responds, Director may send back to consultant.
**E2E test:** Director invokes different agent combinations across 3+ cycles based on KB state.

### M3: Multi-Turn Debate
Director orchestrates Engineer ↔ Critic debate by relaying messages. Director controls depth (decides when debate is resolved).
**E2E test:** a multi-turn exchange produces a strategy revision, not just acknowledgment.

### M4: Full Loop Automation
Outer loop with cadence, synthesis, stall detection. All loop_runner.sh features in Python.
**E2E test:** 5 cycles run unattended, knowledge base grows, cadence changes observed.

### M5: Lux Integration
Squad orchestrator as a Lux capability. Integration with Lux's memory and reflection systems.
