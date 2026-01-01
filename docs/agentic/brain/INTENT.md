# Agent Claude Integration - Decision Record

## Decision: 100% API-Based Agent

**Date:** 2026-01-01

## Context

The agent system had **two separate ways** to call Claude:

1. **HaikuBrain** (`ktrdr/llm/haiku_brain.py`) - Claude CLI via subprocess
2. **AnthropicAgentInvoker** (`ktrdr/agents/invoker.py`) - Anthropic Python SDK

The assessment worker was using HaikuBrain (CLI) while design used the API.

## Problem

Using Claude CLI as a backend is a **workaround, not a solution**:

- **Fragile**: Subprocess calls parsing stdout, breaks on CLI changes
- **Slow**: Process spawn overhead vs HTTP call
- **Undocumented**: CLI output isn't a stable API contract
- **Auth complexity**: Session credentials not designed for containers
- **Wrong tool**: Claude Code is for humans at terminals, not programmatic backends

## Decision

**Make the agent 100% API-based.**

- All agent Claude calls use `ANTHROPIC_API_KEY`
- Remove HaikuBrain dependency from agent code
- Accept API billing as legitimate production cost
- Budget tracking already exists to manage costs

## What Changes

### Remove from Agent

- `assessment_worker.py` - Replace `HaikuBrain.parse_assessment()` with API call

### Keep HaikuBrain For

- `orchestrator/` - Local dev tool, CLI usage is fine there
- Any interactive/local tooling

### Deploy Changes

- Add `ANTHROPIC_API_KEY` to 1Password
- Update deploy script to inject it to backend container

## Success Criteria

1. Agent runs end-to-end with only `ANTHROPIC_API_KEY`
2. No Claude CLI dependency in agent code
3. Works in Docker containers
4. Budget tracking continues to work

## References

- Current Invoker: `ktrdr/agents/invoker.py`
- Assessment Worker: `ktrdr/agents/workers/assessment_worker.py`
- HaikuBrain (keep for orchestrator): `ktrdr/llm/haiku_brain.py`
