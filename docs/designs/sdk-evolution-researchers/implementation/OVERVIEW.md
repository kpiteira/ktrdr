# SDK-Based Agent Workers — Implementation Plan

## Reference Documents

- Design: `docs/designs/sdk-evolution-researchers/DESIGN.md`
- Architecture: `docs/designs/sdk-evolution-researchers/ARCHITECTURE.md`

## Milestone Summary

| # | Name | User Value | Tasks | E2E Test |
|---|------|-----------|-------|----------|
| M1 | MCP Server Agent Gap-Fill | Any Claude Code session can save validated strategies and assessments via MCP | 5 | MCP stdio tool invocation |
| M2 | AgentRuntime + Container Infrastructure (port from agent-memory) | A containerized Claude Code agent can interact with the full ktrdr system via MCP | 6 | SDK invocation inside container with MCP |
| M3 | Design Agent Worker | Trigger a design agent that explores your system autonomously via Claude Code's agentic loop | 5 | POST brief → agent explores via MCP → validated strategy saved |
| M4 | Assessment Agent Worker | Trigger an assessment agent that reasons deeply about results via Claude Code's agentic loop | 5 | POST strategy+metrics → structured assessment + memory updated |
| M5 | Evolution Integration + Cleanup | `ktrdr evolve start` runs with containerized Claude Code agents end-to-end | 5 | Full evolution generation with containerized agents |

**Total: 26 tasks across 5 milestones**

## Dependency Graph

```
M1 (MCP Gap-Fill) → M2 (Runtime + Infra) → M3 (Design Agent)  → M5 (Integration)
                                           → M4 (Assessment Agent) ↗
```

M3 and M4 can run in parallel after M2. M5 requires both M3 and M4.

## Existing E2E Test Coverage

| Milestone | Existing Test | Gap |
|-----------|--------------|-----|
| M1 | None | New: MCP stdio tool invocation test |
| M2 | `tests/e2e/container/` (7 tests) | New: Claude Code SDK in container |
| M3 | `agent/full-cycle.md` (stub workers) | New: design agent with real MCP |
| M4 | `agent/full-cycle.md` phase 4 (stubs) | New: assessment agent with real MCP |
| M5 | `evolution/single-generation.md` | Extend: containerized agents instead of stubs |
