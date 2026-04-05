# Handoff — M1: Core + First Cycle

## Status: COMPLETE — All 6 tasks done, E2E validated

## What Was Built

### .squad/squad_engine/ (new package — 6 modules)

**session.py** — `PersistentAgentSession`
- Multi-turn wrapper over `ClaudeSDKClient` (connect → query → receive_response → disconnect)
- All spike gotchas handled: connect() with no args, CancelledError on disconnect, CLAUDECODE env var, mcp shadowing via temp work dir + sys.path manipulation in _get_sdk()
- Charter loaded as system prompt, history + context files in initial message
- Accepts `mcp_servers` parameter for custom tool registration
- Cost and turn tracking accumulates across queries

**context.py** — `ContextLoader`
- Reads KB files from `~/.ktrdr/shared/squad/` (or `SQUAD_SHARED_DIR` env override)
- `load_recent_experiments(n)` parses by `## ` headers, returns last N
- Token estimation (~4 chars/token) for budget monitoring
- Emergency synthesis detection at 80% of 200K budget

**tools.py** — `validate_strategy` + `execute_experiment`
- `validate_strategy`: wraps `uv run ktrdr validate <name>`, returns `ValidationResult`
- `execute_experiment`: wraps `executor.sh` subprocess, parses JSON output, returns `ExperimentResult`
- Both return dataclasses with structured errors, never crash

**agent_manager.py** — `AgentManager`
- First `spawn_agent(role, msg)` creates `PersistentAgentSession` with charter + history
- Subsequent calls reuse existing session (multi-turn within cycle)
- `teardown_all()` stops all sessions at cycle end
- Cost aggregation across all active sessions
- `allowed_roles` parameter restricts which agents can be spawned (M1: engineer + scribe)

**squad_tools.py** — `create_squad_mcp_server`
- Defines spawn_agent, validate_strategy, execute_experiment, cycle_complete as `@sdk.tool` MCP tools
- Bundles into an MCP server via `sdk.create_sdk_mcp_server("squad")`
- Uses `CycleState` dataclass to track what happened during the cycle (agents spawned, experiment result, cadence)
- MCP server passed to Director's `ClaudeAgentOptions.mcp_servers` — tools are native, not JSON-parsed

**director_prompt.py** — `build_director_prompt`
- Assembles system prompt from: charter, tool guidance (native + squad MCP), KB file map, cycle context
- Explicitly instructs Director to delegate: "Do NOT design strategies yourself — use spawn_agent"

**loop.py** — `run_cycle` + `CycleResult`
- Entry point: `run_cycle(iteration, shared_dir, charter_dir)`
- Creates MCP server with squad tools, passes to Director session
- Director runs autonomously — SDK dispatches tool calls natively
- Cost tracking is additive: Director cost + agent_manager cost
- Returns `CycleResult` with iteration, status, cost, agents spawned, experiment results, cadence

### tests/unit/squad/ (40 tests)

| File | Tests | What it covers |
|------|-------|----------------|
| test_session.py | 8 | Session lifecycle, connect/query/stop, CLAUDECODE, context loading |
| test_context.py | 10 | KB file loading, recent experiments, token estimation, synthesis detection |
| test_tools.py | 7 | validate_strategy + execute_experiment with mocked subprocesses |
| test_agent_manager.py | 7 | spawn/reuse/teardown, role restriction, cost aggregation |
| test_cycle.py | 6 | Director prompt assembly, cycle loop, additive cost tracking |
| test_squad_tools.py | 2 | CycleState defaults, MCP server creation |

### Infrastructure Changes

- `tests/conftest.py`: Added `.squad/` to sys.path for `squad_engine` imports
- `pytest.ini`: Added `.squad` to `norecursedirs` (prevent pytest collecting from .squad/)

## Gotchas

1. **Module name collision.** The project has an existing `orchestrator/` package at root. Renamed squad package to `squad_engine` to avoid collision.

2. **mcp/ package shadowing.** `import claude_agent_sdk` fails because local `mcp/` directory shadows the pip `mcp` package. Fixed in `_get_sdk()` by temporarily removing project root from sys.path during import.

3. **Director autonomy problem.** First E2E run: Director did everything itself (78 turns, $5.16) because squad tools weren't registered as callable MCP tools. It used native Bash/Write to design strategies and run executor.sh directly. Fixed by registering squad tools via `@sdk.tool` + `create_sdk_mcp_server`.

4. **Session teardown RuntimeError.** `RuntimeError: Attempted to exit cancel scope in a different task` during disconnect. Cosmetic — doesn't affect results. SDK anyio integration issue.

5. **Cost tracking bug.** Original `loop.py` overwrote Director cost with agent_manager cost in the finally block. Fixed: cost is now additive (Director + agents).

## E2E Validation Results

**Cycle 100 (E2E test):**
- Director spawned Engineer (designed GRU strategy for EURUSD 1h with MACD histogram features)
- validate_strategy called — validated
- execute_experiment called — 99 epochs, early stopped at 41, 565 trades OOS
- Director spawned Scribe — recorded 49 lines to experiments.md
- cycle_complete called — cadence: quick_iteration
- Total cost: $5.18 (Director + Engineer + Scribe)
- Duration: ~32 minutes
- All CycleResult fields populated correctly

## Key Design Decisions

- **squad_engine instead of orchestrator** — Avoids collision with existing root `orchestrator/` package
- **MCP tools for squad operations** — `@sdk.tool` + `create_sdk_mcp_server` registers squad tools as native callable tools. Director has both native Claude Code tools AND squad MCP tools.
- **Director has full Claude Code tools** — reads KB with Read, writes cadence with Write, AND delegates via spawn_agent MCP tool. These are not exclusive.
- **CycleState as shared mutable state** — tool handlers update CycleState; loop.py reads it after Director completes to populate CycleResult.

## Next: M2 (Director-Driven Consultation)

M2 adds consultant roles (Quant, Inventor, Scout, Critic, Architect) to `allowed_roles`. The Director already knows how to use `spawn_agent` — M2 validates that it selects different agent combinations based on KB state.
