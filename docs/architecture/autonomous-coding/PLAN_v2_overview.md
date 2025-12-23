# Orchestrator v2: Haiku Brain — Implementation Plan

## Overview

Replace brittle regex-based interpretation with Claude Haiku API calls. The Python orchestrator becomes thin coordination code while Haiku handles all understanding.

## Reference Documents

- Design: [DESIGN_v2_haiku_brain.md](DESIGN_v2_haiku_brain.md)
- Architecture: [ARCHITECTURE_v2_haiku_brain.md](ARCHITECTURE_v2_haiku_brain.md)

## Milestone Summary

| # | Name | Branch | Tasks | E2E Test |
|---|------|--------|-------|----------|
| M1 | Haiku Brain + Plan Parsing | `feature/orchestrator-v2-m1-haiku-brain` | 5 | Plan with code blocks → correct task count |
| M2 | Result Interpretation | `feature/orchestrator-v2-m2-interpretation` | 4 | Task without STATUS marker → detected as completed |
| M3 | Retry/Escalate via Haiku | `feature/orchestrator-v2-m3-retry-escalate` | 4 | Intelligent retry decisions with guidance |
| M4 | Consolidated Runner | `feature/orchestrator-v2-m4-consolidated` | 6 | Full milestone runs to completion |

## Dependency Graph

```
M1 (Plan Parsing)
 ↓
M2 (Result Interpretation)
 ↓
M3 (Retry/Escalate)
 ↓
M4 (Consolidated Runner)
```

Each milestone builds on the previous. M1 must complete before M2 can start.

## File Changes Summary

### Create

| File | Milestone | Purpose |
|------|-----------|---------|
| `orchestrator/haiku_brain.py` | M1 | Haiku API wrapper with prompts |
| `orchestrator/test_plans/parsing_edge_case.md` | M1 | Test plan for code block edge case |

### Modify

| File | Milestone | Change |
|------|-----------|--------|
| `orchestrator/milestone_runner.py` | M1 | Use HaikuBrain for task extraction |
| `orchestrator/task_runner.py` | M2 | Use HaikuBrain for interpretation |
| `orchestrator/task_runner.py` | M3 | Use HaikuBrain for retry decisions |
| `orchestrator/runner.py` | M4 | Consolidate all execution logic |
| `orchestrator/cli.py` | M4 | Update imports |

### Delete

| File | Milestone | Reason |
|------|-----------|--------|
| `orchestrator/plan_parser.py` | M1 | Replaced by HaikuBrain.extract_tasks() |
| `orchestrator/llm_interpreter.py` | M2 | Replaced by HaikuBrain.interpret_result() |
| `orchestrator/loop_detector.py` | M3 | Replaced by HaikuBrain.should_retry_or_escalate() |
| `orchestrator/task_runner.py` | M4 | Merged into runner.py |
| `orchestrator/e2e_runner.py` | M4 | Merged into runner.py |
| `orchestrator/escalation.py` | M4 | Merged into runner.py |

### Keep Unchanged

| File | Reason |
|------|--------|
| `orchestrator/sandbox.py` | Works well, just wire to new runner |
| `orchestrator/state.py` | State management unchanged |
| `orchestrator/config.py` | Configuration unchanged |
| `orchestrator/notifications.py` | Notification mechanism unchanged |
| `orchestrator/models.py` | Data models still useful |
| `orchestrator/telemetry.py` | Telemetry unchanged |

## Key Decisions

From design validation:

1. **No v1 backward compatibility** — Fresh start, delete old code
2. **Task extraction: minimal fields** — `{id, title, description}` only
3. **No output truncation** — Full sandbox output to Haiku
4. **Retry guidance from Haiku** — `guidance_for_retry` passed to retries
5. **Keep regex for E2E extraction** — Haiku for interpretation only
