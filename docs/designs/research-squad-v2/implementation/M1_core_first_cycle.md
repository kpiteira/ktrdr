---
design: docs/designs/research-squad-v2/DESIGN.md
architecture: docs/designs/research-squad-v2/ARCHITECTURE.md
---

# M1: Core + First Cycle

**When this works:** The squad produces one real experiment end-to-end — strategy designed by the Engineer, YAML validated with retry, trained and backtested via executor.sh, results recorded by the Scribe — without the 75% YAML failure rate or 230K token cost of v1.

**Scenario (from design doc — "Standard Research Cycle"):** Director reads KB state: synthesis says standard indicators are exhausted on 1h, 5m shows promise. Director spawns Engineer with the mission. Engineer designs strategy YAML. Director validates — passes. Director executes via executor.sh. Results come back. Director spawns Scribe to record. One cycle, three agents (Director + Engineer + Scribe), ~55-80K tokens.

**Scope:** Director + Engineer + Scribe only. No consultants (M2). No multi-turn debate (M3). No loop automation (M4). Single cycle proves the architecture.

**v1 is dead:** v1 shell scripts stay in the repo as reference but will not be run again. v2 owns the state directory from this milestone onward.

---

## Task 1.1: PersistentAgentSession

**File(s):** `.squad/orchestrator/session.py`, `.squad/orchestrator/__init__.py`
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Build a multi-turn session wrapper over `claude_agent_sdk` for persistent agent conversations. The existing `ClaudeAgentRuntime` (`ktrdr/agents/runtime/claude.py`) handles one-shot invocations via `sdk.query()`. The squad needs multi-turn: `connect()` → repeated `query()` calls maintaining conversation context → `disconnect()`. This is a new class, not a modification of the existing runtime.

**Implementation Notes:**
- **Reuse from existing runtime:**
  - `AgentResult` from `ktrdr/agents/runtime/protocol.py` — return type for `query()` responses
  - CLAUDECODE env var pattern from `ktrdr/agents/runtime/claude.py:111` — `os.environ.pop("CLAUDECODE", None)` in try/finally
  - Lazy SDK import pattern from `ktrdr/agents/runtime/claude.py:29-33` — `_get_sdk()` avoids mcp shadowing
- **New persistent session pattern (from spike `.squad/spikes/conversational_squad.py`):**
  - `connect()` with no arguments (passing prompt to connect hangs — spike gotcha)
  - `query(prompt)` sends message to existing session
  - `receive_response()` async iterator collects response
  - `disconnect()` tears down — throws CancelledError, must wrap in try/except
- Charter loaded from `.squad/agents/{role}/charter.md` as system prompt
- History loaded from `~/.ktrdr/shared/squad/agents/{role}/history.md` as initial context
- Working directory: temp dir per session (avoids mcp/ shadowing — spike gotcha)
- Model: Opus for all agents (configurable but defaulting to best)

**Interface:**
```python
class PersistentAgentSession:
    def __init__(self, role: str, charter_path: Path, history_path: Path | None = None)
    async def start(self, context_files: list[str] | None = None) -> None
    async def query(self, message: str) -> AgentResult  # reuses existing AgentResult
    async def stop(self) -> None
    @property
    def is_alive(self) -> bool
    @property
    def total_cost_usd(self) -> float
    @property
    def total_turns(self) -> int
```

**Testing Requirements:**
- [ ] Unit test: initializes with correct charter path for each of 8 roles
- [ ] Unit test: `start()` calls SDK `connect()` with no args, then sends charter+history via `query()`
- [ ] Unit test: `query()` collects full response from `receive_response()` iterator, returns `AgentResult`
- [ ] Unit test: `stop()` handles CancelledError from `disconnect()` gracefully
- [ ] Unit test: CLAUDECODE env var removed during session, restored in finally
- [ ] Unit test: `is_alive` reflects session state
- [ ] Unit test: cost and turns accumulate across multiple `query()` calls

**Acceptance Criteria:**
- [ ] Multi-turn: consecutive `query()` calls maintain conversation context
- [ ] Returns `AgentResult` (reuses existing type, not a new one)
- [ ] All spike gotchas handled (CLAUDECODE, connect args, disconnect error, mcp shadowing)
- [ ] Clean teardown with no exceptions

---

## Task 1.2: Context Assembly

**File(s):** `.squad/orchestrator/context.py`
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Build the context loading layer that reads knowledge base files and estimates token usage. Replaces the shell-based context assembly in `loop_lib.sh` (`.squad/loop_lib.sh`).

**Implementation Notes:**
- KB root: `~/.ktrdr/shared/squad/` (respect `SQUAD_SHARED_DIR` env override — v1 uses this for isolated runs)
- Token estimation: ~4 chars per token for budget checks
- Emergency synthesis detection: flag when estimated context > 80% of 200K budget
- Recent experiments: parse `experiments.md` by `## Experiment:` headers, return last N
- Missing files: return empty string + warning log (don't crash — KB may be sparse early on)
- **Ported from v1:** `loop_lib.sh:get_context_for_agent()` and `needs_synthesis()` — same logic, Python instead of bash

**Interface:**
```python
class ContextLoader:
    def __init__(self, shared_dir: str | None = None)
    def load_file(self, relative_path: str) -> str
    def load_files(self, paths: list[str]) -> dict[str, str]
    def load_recent_experiments(self, n: int = 5) -> str
    def estimate_tokens(self, text: str) -> int
    def needs_synthesis(self, loaded_context: dict[str, str]) -> bool
    @property
    def shared_dir(self) -> Path
```

**Testing Requirements:**
- [ ] Unit test: loads file from shared_dir correctly
- [ ] Unit test: returns empty string for missing files (no crash)
- [ ] Unit test: respects SQUAD_SHARED_DIR env override
- [ ] Unit test: recent experiments extraction parses correct count from representative experiments.md
- [ ] Unit test: token estimation within 20% of actual for representative text
- [ ] Unit test: needs_synthesis returns True when context exceeds 80% of 200K budget

**Acceptance Criteria:**
- [ ] Loads KB files by relative path from shared directory
- [ ] Handles missing files gracefully (squad may be starting fresh)
- [ ] Token estimation enables budget decisions
- [ ] Functionally equivalent to v1's `loop_lib.sh` context assembly

---

## Task 1.3: Execution Tools — validate_strategy + execute_experiment

**File(s):** `.squad/orchestrator/tools.py`
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Wrap the two mechanical operations — strategy validation and experiment execution — as Python functions. These call existing ktrdr infrastructure via subprocess. No LLM involved.

**Implementation Notes:**
- **validate_strategy:** runs `uv run ktrdr validate <name>` subprocess
  - Strategy files live at `~/.ktrdr/shared/strategies/` (same as v1)
  - Parse exit code + stderr for structured result
  - This replaces the shell-based validation in `loop_runner.sh` which used marker extraction (fragile)
- **execute_experiment:** runs `.squad/executor.sh` subprocess
  - executor.sh path: absolute, resolved from `.squad/` directory
  - Long-running (minutes to hours) — subprocess with streaming output
  - executor.sh already returns structured JSON: `{experiment, training: {operation_id, summary}, backtest: {operation_id, summary}}`
  - Parse JSON output directly — no marker extraction needed
  - v1 handoff: executor.sh handles its own 34MB→1KB result summarization
- Both return dataclasses, not raw strings

**Interface:**
```python
@dataclass
class ValidationResult:
    valid: bool
    error: str | None
    path: str | None

@dataclass
class ExperimentResult:
    status: str  # "SUCCESS" | "FAILED"
    training: dict | None
    backtest: dict | None
    error: str | None

async def validate_strategy(name: str) -> ValidationResult
async def execute_experiment(
    strategy: str,
    train_start: str, train_end: str,
    bt_start: str, bt_end: str,
) -> ExperimentResult
```

**Testing Requirements:**
- [ ] Unit test: validate_strategy returns valid=True for exit code 0
- [ ] Unit test: validate_strategy captures stderr on failure, returns structured error
- [ ] Unit test: execute_experiment parses executor.sh JSON output correctly
- [ ] Unit test: execute_experiment returns FAILED with error on non-zero exit
- [ ] Unit test: execute_experiment handles subprocess timeout gracefully
- [ ] Integration test (needs sandbox): validate_strategy against a known-good v3 strategy YAML
- [ ] Integration test (needs sandbox): execute_experiment runs a short training cycle

**Acceptance Criteria:**
- [ ] validate_strategy wraps `uv run ktrdr validate` with structured result
- [ ] execute_experiment wraps `executor.sh` with structured result
- [ ] Subprocess failures produce clear error messages, not crashes
- [ ] executor.sh called with absolute path, respects working directory

---

## Task 1.4: spawn_agent Tool + AgentManager

**File(s):** `.squad/orchestrator/tools.py` (extend)
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Build the AgentManager that creates and reuses agent sessions, implementing the `spawn_agent` tool. First call for a role creates a new PersistentAgentSession; subsequent calls send messages to the existing session (multi-turn within a cycle).

**Implementation Notes:**
- Active sessions dict: `dict[str, PersistentAgentSession]`
- For M1: only `engineer` and `scribe` roles needed (M2 opens all roles)
- Charter paths: `.squad/agents/{role}/charter.md` (all 8 exist in repo)
- History paths: `~/.ktrdr/shared/squad/agents/{role}/history.md` (may not exist yet)
- Context files loaded via ContextLoader and injected into initial session prompt
- **Reuse SafetyGuard** from `ktrdr/agents/runtime/safety.py` for budget tracking per cycle
- Return `AgentResult` from queries (same type as existing runtime)
- `teardown_all()` at end of cycle — clean up all sessions

**Interface:**
```python
class AgentManager:
    def __init__(self, context_loader: ContextLoader, allowed_roles: set[str] | None = None)
    async def spawn_agent(self, role: str, message: str, context: list[str] | None = None) -> AgentResult
    async def teardown_all(self) -> None
    @property
    def active_sessions(self) -> dict[str, PersistentAgentSession]
    @property
    def total_cost_usd(self) -> float
```

**Testing Requirements:**
- [ ] Unit test: first spawn creates new PersistentAgentSession for role
- [ ] Unit test: second spawn to same role reuses existing session (query, not start)
- [ ] Unit test: invalid role raises ValueError (M1: only engineer, scribe allowed)
- [ ] Unit test: context files loaded via ContextLoader and passed to session
- [ ] Unit test: teardown_all stops all active sessions, resets dict
- [ ] Unit test: total_cost_usd aggregates across all active sessions
- [ ] Unit test: spawn after teardown creates fresh session

**Acceptance Criteria:**
- [ ] First call creates session with charter + history + context
- [ ] Subsequent calls reuse session (multi-turn within a cycle)
- [ ] Returns AgentResult (reuses existing type)
- [ ] Budget tracking via SafetyGuard integration
- [ ] Clean teardown of all sessions at cycle end

---

## Task 1.5: Director Session + Single Cycle

**File(s):** `.squad/orchestrator/director_prompt.py`, `.squad/orchestrator/loop.py`
**Type:** CODING
**Estimated time:** 3-4 hours

**Description:**
Build the Director's system prompt and the minimal loop that runs one ORIENT → WORK → LEARN cycle. The Director is a Claude session that calls tools. Python dispatches tool calls and feeds results back. This is the architecture's core: the Director drives, Python implements.

**Implementation Notes:**

**director_prompt.py:**
- Assemble Director's system prompt from:
  - Director charter (`.squad/agents/director/charter.md`)
  - Tool descriptions: `spawn_agent(role, message, context)`, `validate_strategy(name)`, `execute_experiment(strategy, dates...)`
  - KB file map: what files exist and their purposes (so Director knows what to Read)
  - Cycle context: iteration number, last cadence from `loop/cadence.md`, nudges from `loop/nudges.md`
- For M1: restrict tool descriptions to Director + Engineer + Scribe roles

**loop.py — Director tool dispatch:**
- The Director is itself a PersistentAgentSession (or uses the one-shot `ClaudeAgentRuntime` pattern — decide during implementation based on which SDK API supports tool calling)
- **Critical design decision:** how Director invokes tools:
  - **Option A:** Director uses Claude's native tool_use (structured tool calls in response) — preferred if SDK supports it in persistent sessions
  - **Option B:** Director outputs JSON tool requests, Python parses — fallback if tool_use not available in persistent session API
  - **Option C:** Director is a one-shot `ClaudeAgentRuntime.invoke()` with custom MCP tools — leverage existing runtime + MCP tool registration
  - Investigate during implementation. The spike used plain text, but the existing runtime already handles `ToolUseBlock` in transcripts (`ktrdr/agents/runtime/claude.py:163-169`)
- Dispatch loop: create Director session → send "Begin cycle N" → parse response for tool calls → execute tool → feed result back → repeat until Director signals COMPLETE
- Entry point: `async def run_cycle(iteration: int) -> CycleResult`

**Testing Requirements:**
- [ ] Unit test: Director prompt includes tool descriptions, KB file map, cycle context
- [ ] Unit test: tool dispatch routes spawn_agent → AgentManager, validate_strategy → tools, execute_experiment → tools
- [ ] Unit test: cycle completes when Director signals COMPLETE
- [ ] Unit test: CycleResult captures experiment outcome, agents spawned, token usage, cost
- [ ] Integration test: mock Director issues spawn_agent → validate_strategy → execute_experiment → spawn_agent(scribe) sequence

**Acceptance Criteria:**
- [ ] Director system prompt has all context needed for autonomous cycle decisions
- [ ] Tool dispatch loop handles all three tools correctly
- [ ] One cycle runs: ORIENT (Director reads KB) → WORK (Engineer designs+validates+executes) → LEARN (Scribe records)
- [ ] CycleResult provides structured output for monitoring

---

## Task 1.6: VALIDATION — First Complete Cycle

**Type:** VALIDATION
**Estimated time:** 2-3 hours

**Description:**
Run one complete cycle end-to-end against real infrastructure. This is the proof that the conversational architecture works: Director orchestrates, Engineer designs, YAML validates with retry, training runs, backtest completes, Scribe records.

**Scenario under test (design doc "Standard Research Cycle"):** Director reads synthesis.md and frontiers.md. Decides a mission based on current KB state. Spawns Engineer with context. Engineer writes strategy YAML. Director calls validate_strategy — if it fails, sends error back to Engineer (this is the 75% failure fix). Director calls execute_experiment via executor.sh. Results come back. Director spawns Scribe to record in experiments.md. Cycle completes.

**Validation Steps:**

1. **Load the `ke2e` skill** before designing any validation
2. **Invoke ke2e-test-scout** with: "Squad v2 first cycle: Director reads KB, spawns Engineer with mission, Engineer writes strategy YAML, validate_strategy succeeds (with retry if needed), execute_experiment runs train+backtest via executor.sh, Scribe records results in experiments.md. Validates against real sandbox with real Claude sessions."
3. **Invoke ke2e-test-runner** with the identified test recipe
4. **Tests must exercise real running infrastructure** — real Claude sessions, real ktrdr validate, real executor.sh

**Success Criteria:**
- [ ] Director session creates and reads KB state during ORIENT
- [ ] Director spawns Engineer with a mission derived from KB context
- [ ] Engineer produces a valid strategy YAML (retry count ≤ 3 if needed)
- [ ] execute_experiment runs training+backtest via executor.sh to completion
- [ ] Director spawns Scribe; Scribe updates experiments.md with new entry
- [ ] Token usage < 100K (target: 55-80K, vs v1's 230K)
- [ ] No unhandled exceptions during entire cycle

**Evidence Required:**
- Tool call sequence log (Director's spawn_agent, validate, execute calls with timestamps)
- Strategy YAML file produced by Engineer
- Validation result (pass/retry count)
- Training + backtest summary from executor.sh
- experiments.md diff showing new entry by Scribe
- Token usage breakdown per agent
