# Agent E2E Testing Guide

This document describes how to run end-to-end tests for the KTRDR research agent system, including tests that invoke the real Anthropic API.

## Overview

The agent E2E tests verify the complete flow:

```
CLI → API → TriggerService → AnthropicAgentInvoker → Anthropic API → ToolExecutor → Strategy
```

There are two levels of E2E testing:

1. **Mock E2E Tests** (`test_agent_e2e.py`) - Use mock invokers, test the trigger/database/strategy flow
2. **Real E2E Tests** (`test_agent_real_e2e.py`) - Call the real Anthropic API, test full integration

## Prerequisites

### Database

All E2E tests require PostgreSQL:

```bash
# Start the database (via Docker Compose)
docker compose up -d db

# Verify connection
psql postgresql://ktrdr:localdev@localhost:5432/ktrdr -c "SELECT 1"
```

### Anthropic API Key (Real Tests Only)

For real E2E tests, you need a valid Anthropic API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
```

## Running Mock E2E Tests

Mock tests use `MockAgentInvoker` or `MockDesignAgentInvoker` to simulate Claude's behavior without calling the API.

```bash
# Set database URL
export DATABASE_URL="postgresql://ktrdr:localdev@localhost:5432/ktrdr"

# Run all mock E2E tests
uv run pytest tests/integration/agent_tests/test_agent_e2e.py -v

# Run specific test
uv run pytest tests/integration/agent_tests/test_agent_e2e.py::TestAgentDesignPhaseE2E::test_full_design_phase_flow -v
```

### What Mock Tests Verify

- Session creation and state transitions
- Database operations (create, update, complete)
- Strategy validation and saving
- Trigger service logic (skip when active session, etc.)

## Running Real E2E Tests

Real E2E tests invoke the actual Anthropic API. They are:
- **Expensive**: Each invocation costs $0.05-0.20
- **Slow**: 30-120 seconds per invocation
- **Rate-limited**: May fail if hitting API limits

### Enable Real Tests

Real tests are skipped by default. Enable with:

```bash
export AGENT_E2E_REAL_INVOKE=true
```

### Full Command

```bash
# All required environment variables
export DATABASE_URL="postgresql://ktrdr:localdev@localhost:5432/ktrdr"
export ANTHROPIC_API_KEY="sk-ant-api03-..."
export AGENT_E2E_REAL_INVOKE=true

# Run real E2E tests with output
uv run pytest tests/integration/agent_tests/test_agent_real_e2e.py -v -s
```

### Run Specific Real Test

```bash
# Main design cycle test (most comprehensive)
uv run pytest tests/integration/agent_tests/test_agent_real_e2e.py::TestAgentRealE2E::test_full_design_cycle_with_real_anthropic -v -s

# Token tracking test
uv run pytest tests/integration/agent_tests/test_agent_real_e2e.py::TestAgentRealE2E::test_token_tracking_accuracy -v -s

# Tool execution test
uv run pytest tests/integration/agent_tests/test_agent_real_e2e.py::TestAgentToolExecution::test_tool_executor_integrates_with_invoker -v -s
```

### What Real Tests Verify

| Test | Verifies |
|------|----------|
| `test_full_design_cycle_with_real_anthropic` | Complete flow: session → Claude → tools → strategy → DESIGNED state |
| `test_real_api_via_service_trigger` | API endpoint path works correctly |
| `test_token_tracking_accuracy` | Token counts captured from API response |
| `test_tool_executor_integrates_with_invoker` | Tool execution works in real loop |

### Expected Output

```
============================================================
STARTING REAL ANTHROPIC API INVOCATION
Model: claude-sonnet-4-20250514
Max tokens: 4096
This will take 30-120 seconds...
============================================================

...

============================================================
INVOCATION COMPLETE (45.2s)
Result: {'triggered': True, 'session_id': 42, ...}
============================================================

✅ Session 42 in DESIGNED state
   Strategy name: momentum_rsi_v1
✅ Strategy file created: momentum_rsi_v1.yaml
✅ Strategy file validates successfully
   Strategy type: mlp
   Indicators: ['rsi', 'macd']
✅ Token usage captured:
   Input tokens: 3842
   Output tokens: 1256
```

## Test File Locations

```
tests/integration/agent_tests/
├── test_agent_e2e.py          # Mock E2E tests (no API calls)
├── test_agent_real_e2e.py     # Real E2E tests (Anthropic API)
└── conftest.py                # Shared fixtures
```

## Troubleshooting

### "DATABASE_URL not set"

```bash
export DATABASE_URL="postgresql://ktrdr:localdev@localhost:5432/ktrdr"
```

### "ANTHROPIC_API_KEY not set"

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
```

### "Could not connect to database"

Ensure PostgreSQL is running:

```bash
docker compose up -d db
docker compose ps  # Should show 'ktrdr-db' running
```

### Tests Taking Too Long

Real tests take 30-120 seconds. This is normal due to:
- Claude's response generation time
- Tool execution loop (multiple API calls)
- Network latency

### API Rate Limits

If you see rate limit errors, wait a few minutes and retry. The API has request-per-minute limits.

### Strategy Validation Failures

If the generated strategy fails validation:
1. Check the error messages in test output
2. Look at the generated YAML file
3. The prompt may need adjustment for edge cases

## Cost Considerations

| Model | Approx. Cost per Test |
|-------|----------------------|
| claude-sonnet-4 | $0.05-0.10 |
| claude-opus-4 | $0.15-0.30 |

Typical full design cycle uses:
- Input: 3000-5000 tokens
- Output: 500-2000 tokens

**Recommendation**: Run real tests sparingly. Use mock tests for development.

## CI/CD Integration

Real E2E tests should NOT run in CI by default due to cost and flakiness.

For scheduled nightly tests:

```yaml
# .github/workflows/agent-e2e.yml
name: Agent Real E2E Tests

on:
  schedule:
    - cron: '0 0 * * *'  # Nightly

jobs:
  real-e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Real E2E Tests
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          AGENT_E2E_REAL_INVOKE: 'true'
        run: |
          uv run pytest tests/integration/agent_tests/test_agent_real_e2e.py -v -s
```

## Manual Testing via CLI

You can also test manually via the CLI:

```bash
# Enable the agent (if needed)
export AGENT_ENABLED=true

# Trigger via CLI (requires running backend)
ktrdr agent trigger

# Check status
ktrdr agent status --verbose

# List recent sessions
ktrdr agent sessions
```

## Related Documentation

- [Phase 1 Implementation Plan](../agentic/mvp/PLAN_phase1_strategy_design.md)
- [Agent Tools](../../ktrdr/agents/tools.py)
- [ToolExecutor](../../ktrdr/agents/executor.py)
- [AnthropicAgentInvoker](../../ktrdr/agents/invoker.py)
