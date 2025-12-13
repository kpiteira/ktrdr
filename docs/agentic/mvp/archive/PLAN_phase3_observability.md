# Phase 3: Observability & Cost Control

**Objective:** Full visibility and budget enforcement for production operation

**Duration:** 2-3 days

**Prerequisites:** Phase 2 complete (full cycle works)

---

## ⚠️ Architectural Context (Simplified - Single Service)

**With Anthropic API direct integration, observability is simpler - only ONE service to instrument:**

```text
┌──────────────────────────────────────────────────────────────────┐
│                    COMPONENTS TO INSTRUMENT                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                   Backend (Docker:8000)                      │ │
│  │                                                              │ │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐ │ │
│  │  │  Agent System  │  │  API Metrics   │  │  Budget/Cost   │ │ │
│  │  │                │  │                │  │                │ │ │
│  │  │  • Trigger     │  │  • Request     │  │  • Token       │ │ │
│  │  │    metrics     │  │    latency     │  │    tracking    │ │ │
│  │  │  • Anthropic   │  │  • Error       │  │  • Daily       │ │ │
│  │  │    invocation  │  │    rates       │  │    budget      │ │ │
│  │  │    traces      │  │  • Operation   │  │  • Cost per    │ │ │
│  │  │  • Tool calls  │  │    tracking    │  │    cycle       │ │ │
│  │  └────────────────┘  └────────────────┘  └────────────────┘ │ │
│  │                                                              │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                               │                                  │
│                               ▼                                  │
│                    ┌─────────────────────┐                      │
│                    │  Observability Stack │                      │
│                    │                     │                      │
│                    │  Prometheus → Grafana                      │
│                    │  Jaeger (OTEL traces)                      │
│                    └─────────────────────┘                      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Key Simplifications:**

- **Single service** - Only backend to instrument (no host service, no MCP for agent)
- **Cost tracking in-process** - Token counts from Anthropic API response
- **Single metrics endpoint** - Backend (:8000/metrics)
- **Unified traces** - All spans in one service (no cross-service correlation needed)

---

## Branch Strategy

**Branch:** `feature/agent-mvp`

Continue on the same branch from Phase 2. All MVP phases (0-3) use this single branch.

---

## ⚠️ Implementation Principles

**Check Before Creating:**
KTRDR has extensive observability infrastructure. Before implementing:
1. **Review** existing OTEL, Prometheus, Grafana setup
2. **Follow** existing patterns for metrics naming, span creation
3. **Integrate** with existing dashboards where possible
4. **Create new** only for agent-specific visibility

**Existing Observability to Check:**
- `ktrdr/monitoring/` - monitoring utilities
- `monitoring/grafana/dashboards/` - existing dashboards
- `config/prometheus/` - Prometheus config
- OTEL instrumentation patterns in existing code

**Follow existing conventions** for:
- Metric naming (e.g., `ktrdr_agent_*` prefix)
- Span naming and attributes
- Dashboard organization
- Alert severity levels

---

## Success Criteria

- [ ] Cost tracked per invocation and per cycle
- [ ] Daily budget enforced ($5 limit)
- [ ] MCP server instrumented with OTEL
- [ ] Prometheus metrics exposed
- [ ] Grafana dashboard shows system status
- [ ] Alerts fire for critical issues
- [ ] Full CLI for visibility and control

---

## Tasks

### 3.1 Add Remaining Database Tables

**Goal:** Complete the schema for metrics and budget

**Tables to add:**
- `agent_triggers` - Log every trigger check
- `agent_metrics` - Aggregated metrics per cycle
- `agent_budget` - Daily budget tracking

**File:** `research_agents/database/schema.py`

**Reference:** See `ref_database_schema.md` for full definitions

**Acceptance:**
- Tables created via migration
- Queries work correctly

**Effort:** 2-3 hours

---

### 3.2 Implement Cost Tracking

**Goal:** Track tokens and cost for every agent invocation

**Architecture Note (Simplified):** Everything runs in the backend - no HTTP calls needed.

**Implementation:**

Token counts come directly from Anthropic API response in `AnthropicAgentInvoker`:

```python
# In AnthropicAgentInvoker.run() - tokens already captured
return AgentResult(
    success=True,
    output=self._extract_text(response),
    input_tokens=total_input_tokens,   # From response.usage
    output_tokens=total_output_tokens  # From response.usage
)

# Cost calculation (same process)
def calculate_cost(tokens_in: int, tokens_out: int) -> float:
    # Opus 4.5 pricing
    return (tokens_in * 5.0 / 1_000_000) + (tokens_out * 25.0 / 1_000_000)
```

**Files:**

- `ktrdr/agents/invoker.py` - Already captures tokens from API response
- `research_agents/services/cost_tracker.py` - Calculate and store costs

**Acceptance:**

- Token counts captured from Anthropic API response
- Costs stored in database
- Running totals maintained

**Effort:** 1-2 hours (simplified - no HTTP calls)

---

### 3.3 Implement Budget Enforcement

**Goal:** Stop invoking agent when budget exhausted

**Logic in trigger service:**
```python
async def check_budget() -> tuple[bool, float]:
    """
    Check if budget allows invocation.
    Returns (allowed, remaining_usd)
    """
    today = date.today()
    budget = await get_daily_budget(today)
    
    remaining = DAILY_BUDGET_USD - budget.spent_usd
    
    # Keep $0.10 buffer
    if remaining < 0.10:
        return False, remaining
    
    return True, remaining
```

**Budget resets at midnight UTC.**

**File:** `research_agents/services/budget.py`

**Acceptance:**
- Budget checked before each invocation
- Agent not invoked when budget exhausted
- Budget resets daily

**Effort:** 2-3 hours

---

### 3.4 Instrument Agent System with OTEL

**Goal:** Traces for agent invocations and tool calls

**Architecture Note (Simplified):** Only ONE service to instrument - the backend. No cross-service tracing needed.

**Implementation:**

Add OTEL tracing to agent components in backend:

```python
from opentelemetry import trace

tracer = trace.get_tracer("ktrdr.agents")

class AnthropicAgentInvoker:
    async def run(self, prompt: str, tools: list, system_prompt: str):
        with tracer.start_as_current_span("agent.invocation") as span:
            span.set_attribute("agent.model", self.model)
            span.set_attribute("agent.prompt_length", len(prompt))

            # ... invoke Claude ...

            span.set_attribute("agent.tokens_in", total_input_tokens)
            span.set_attribute("agent.tokens_out", total_output_tokens)
            return result

class ToolExecutor:
    async def execute(self, tool_name: str, tool_input: dict):
        with tracer.start_as_current_span(f"agent.tool.{tool_name}") as span:
            span.set_attribute("tool.name", tool_name)
            result = await self._execute(tool_name, tool_input)
            span.set_attribute("tool.success", "error" not in result)
            return result
```

**Spans to create:**

- `agent.trigger_cycle` - Full trigger cycle
- `agent.invocation` - Single Claude API call
- `agent.tool.{name}` - Individual tool executions

**Files:**

- `ktrdr/agents/invoker.py` - Add OTEL tracing
- `ktrdr/agents/executor.py` - Add OTEL tracing
- `research_agents/services/trigger.py` - Add trigger cycle span

**Acceptance:**

- Traces visible in Jaeger
- Spans have correct attributes (tokens, duration, success)
- Full trace from trigger → invocation → tools

**Effort:** 2-3 hours (simplified - single service)

---

### 3.5 Add Agent Prometheus Metrics to Backend

**Goal:** Expose agent-specific metrics on backend's existing `/metrics` endpoint

**Architecture Note (Simplified):** Single metrics endpoint on backend (:8000/metrics). No separate MCP or host service metrics.

**Agent Metrics to Add:**

- `ktrdr_agent_trigger_total{reason, invoked}` - Trigger attempts
- `ktrdr_agent_invocation_duration_seconds` - Claude API call duration
- `ktrdr_agent_tokens_total{direction}` - Input/output tokens
- `ktrdr_agent_tool_calls_total{tool, status}` - Tool executions
- `ktrdr_agent_errors_total{error_type}` - Agent errors

**Implementation:**

```python
from prometheus_client import Counter, Histogram

agent_trigger_total = Counter(
    'ktrdr_agent_trigger_total',
    'Agent trigger attempts',
    ['reason', 'invoked']
)

agent_invocation_duration = Histogram(
    'ktrdr_agent_invocation_duration_seconds',
    'Claude API invocation duration'
)

agent_tokens_total = Counter(
    'ktrdr_agent_tokens_total',
    'Agent tokens used',
    ['direction']  # input/output
)
```

**Files:**

- `ktrdr/agents/metrics.py` - NEW: Agent metrics definitions
- `ktrdr/agents/invoker.py` - MODIFY: Instrument with metrics
- `ktrdr/agents/executor.py` - MODIFY: Instrument tool calls

**Acceptance:**

- Agent metrics visible at `/metrics`
- Prometheus can scrape
- Metrics accurate

**Effort:** 2-3 hours (simplified - single service)

---

### 3.6 Add Prometheus Metrics to Trigger Service

**Goal:** Expose agent-specific metrics

**Metrics to add:**
- `agent_trigger_total{reason, invoked}`
- `agent_gate_evaluations_total{gate_type, result}`
- `agent_cycle_total{outcome}`
- `agent_cycle_duration_seconds`
- `agent_tokens_total{direction}`
- `agent_cost_usd_total`
- `agent_budget_remaining_usd`

**File:** `research_agents/services/trigger.py` (add metrics)

**Acceptance:**
- All metrics exposed
- Updated correctly during operation
- Prometheus can scrape

**Effort:** 2-3 hours

---

### 3.7 Create Grafana Dashboard

**Goal:** Visual monitoring of agent system

**Panels:**
1. **Status Overview**
   - Current cycle state
   - Recent outcomes pie chart
   - Cycles per hour

2. **Quality Gates**
   - Pass/fail rates (gauges)
   - Failure reasons (bar chart)

3. **Cost Tracking**
   - Daily spend (time series)
   - Budget utilization (gauge)
   - Cost per cycle (stat)

4. **Performance**
   - Cycle duration histogram
   - Phase breakdown
   - MCP tool latencies

5. **System Health**
   - Error rates
   - Active sessions
   - Trigger frequency

**File:** `monitoring/grafana/dashboards/agent.json`

**Acceptance:**
- Dashboard loads in Grafana
- All panels show data
- Useful for monitoring

**Effort:** 3-4 hours

---

### 3.8 Implement Alert Rules

**Goal:** Get notified of critical issues

**Critical alerts:**
- Agent no activity for 1 hour
- Budget exhausted
- High failure rate (>80%)

**Warning alerts:**
- MCP error rate elevated
- Cycle duration unusually long
- Gate failure rate high

**File:** `config/prometheus/rules/agent_alerts.yml`

**Acceptance:**
- Alerts defined in Prometheus
- Fire correctly when conditions met
- Integrate with notification system

**Effort:** 2 hours

---

### 3.9 Implement Full CLI

**Goal:** Complete CLI for visibility and control

**⚠️ Architecture Note:** CLI commands call Backend API (Task 1.9 pattern). The CLI does NOT directly call services.

```
CLI → Backend API → (proxy to Host Service if needed)
```

**Commands:**

```bash
# Status and monitoring (call GET /api/v1/agent/*)
ktrdr agent status              # Current state + recent history + budget
ktrdr agent history [--limit N] # Detailed cycle history
ktrdr agent session <id>        # Full session details
ktrdr agent budget              # Budget status

# Control (call POST /api/v1/agent/*)
ktrdr agent trigger             # Manual trigger (testing)
ktrdr agent pause               # Pause automatic triggers
ktrdr agent resume              # Resume automatic triggers

# Debugging
ktrdr agent logs [--session ID] # View logs for session
```

**Implementation:**

- Extend CLI from Task 1.9 (which established basic trigger/status)
- Use `AsyncCLIClient` pattern (like data, training commands)
- All commands call backend API endpoints

**File:** `ktrdr/cli/agent_commands.py` (extend from Task 1.9)

**Reference:** See `ref_cli_commands.md` for specifications

**Acceptance:**

- All commands work via API
- Output is clear and useful
- Help text accurate
- No direct service calls (API only)

**Effort:** 3-4 hours (reduced since Task 1.9 establishes base)

---

### 3.10 Add Trigger Logging Table

**Goal:** Log every trigger check for debugging

**What to log:**
- Timestamp
- Trigger reason
- Whether agent was invoked
- Skip reason (if not invoked)
- Budget remaining
- Active session (if any)

**File:** `research_agents/services/logging.py`

**Acceptance:**
- Every trigger logged
- Queryable via CLI
- Useful for debugging

**Effort:** 1-2 hours

---

### 3.11 Metrics Aggregation Job

**Goal:** Populate agent_metrics for easy querying

**Job runs after each cycle completes:**
```python
async def aggregate_cycle_metrics(session_id: int):
    """
    Aggregate metrics from completed cycle into agent_metrics table.
    """
    session = await get_session(session_id)
    actions = await get_session_actions(session_id)
    
    metrics = AgentMetrics(
        session_id=session_id,
        total_tokens_in=sum(a.tokens_in for a in actions),
        total_tokens_out=sum(a.tokens_out for a in actions),
        total_cost_usd=sum(a.cost_usd for a in actions),
        total_duration_seconds=(session.ended_at - session.started_at).seconds,
        design_duration_seconds=...,
        training_duration_seconds=...,
        backtest_duration_seconds=...,
        training_accuracy=...,
        backtest_sharpe=...,
        outcome=session.outcome
    )
    await save_metrics(metrics)
```

**File:** `research_agents/metrics/aggregator.py`

**Acceptance:**
- Metrics aggregated after each cycle
- Easy to query performance trends
- Dashboard can use this data

**Effort:** 2-3 hours

---

### 3.12 End-to-End Observability Test

**Goal:** Verify full observability stack works

**Test scenario:**
1. Run several cycles
2. Verify traces in Jaeger
3. Verify metrics in Prometheus
4. Verify dashboard shows data
5. Trigger alert condition, verify alert fires

**File:** `tests/integration/research_agents/test_observability.py`

**Acceptance:**
- All observability components work
- Data flows correctly
- Useful for production monitoring

**Effort:** 2-3 hours

---

## Task Summary

| Task | Description | Effort | Dependencies |
|------|-------------|--------|--------------|
| 3.1 | Remaining DB tables | 2-3h | Phase 2 |
| 3.2 | Cost tracking | 1-2h | 3.1 |
| 3.3 | Budget enforcement | 2-3h | 3.2 |
| 3.4 | Agent OTEL instrumentation | 2-3h | None |
| 3.5 | Agent Prometheus metrics | 2-3h | None |
| 3.6 | Trigger Prometheus metrics | 2-3h | 3.2 |
| 3.7 | Grafana dashboard | 3-4h | 3.5, 3.6 |
| 3.8 | Alert rules | 2h | 3.6 |
| 3.9 | Full CLI | 3-4h | 3.1 |
| 3.10 | Trigger logging | 1-2h | 3.1 |
| 3.11 | Metrics aggregation | 2-3h | 3.1 |
| 3.12 | E2E observability test | 2-3h | All above |

**Total estimated effort:** 24-33 hours (2-3 days)

*Note: Effort reduced - single service to instrument (no MCP/host service), no HTTP calls for cost tracking.*

---

## Files to Create/Modify

**Note:** Simplified architecture - all instrumentation in backend (no MCP/host service files).

```text
ktrdr/
├── agents/
│   ├── invoker.py                  # 3.4, 3.5 - MODIFY: Add OTEL & metrics
│   ├── executor.py                 # 3.4, 3.5 - MODIFY: Add OTEL & metrics
│   └── metrics.py                  # 3.5 - NEW: Agent metrics definitions
└── cli/
    └── agent_commands.py           # 3.9 - MODIFY: Expand commands

research_agents/
├── database/
│   └── schema.py                   # 3.1 (add remaining tables)
├── services/
│   ├── trigger.py                  # 3.4, 3.6 - MODIFY: Add OTEL & metrics
│   ├── cost_tracker.py             # 3.2 - NEW
│   ├── budget.py                   # 3.3 - NEW
│   └── logging.py                  # 3.10 - NEW
└── metrics/
    ├── __init__.py
    └── aggregator.py               # 3.11

monitoring/
└── grafana/
    └── dashboards/
        └── agent.json              # 3.7 (new)

config/
└── prometheus/
    └── rules/
        └── agent_alerts.yml        # 3.8 (new)

tests/
└── integration/
    └── agent_tests/
        └── test_observability.py   # 3.12
```

**No longer needed:**

- `mcp/src/telemetry.py` - Agent doesn't use MCP
- `mcp/src/metrics.py` - Agent doesn't use MCP
- `agent-host-service/` - Agent runs in backend

---

## Configuration

**Environment variables for Phase 3:**

```bash
# Agent (from Phase 1)
ANTHROPIC_API_KEY=sk-ant-...
AGENT_ENABLED=true
AGENT_MODEL=claude-sonnet-4-20250514

# Budget
AGENT_DAILY_BUDGET_USD=5.0
AGENT_BUDGET_BUFFER_USD=0.10

# Pricing (Opus 4.5)
AGENT_COST_PER_MTOK_INPUT=5.0
AGENT_COST_PER_MTOK_OUTPUT=25.0

# Observability (uses existing KTRDR stack)
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
# Note: Metrics use existing backend /metrics endpoint
```

---

## Definition of Done

Phase 3 is complete when:
1. Cost tracked accurately
2. Budget enforced ($5/day)
3. Traces visible in Jaeger
4. Metrics in Prometheus
5. Dashboard operational
6. Alerts configured
7. Full CLI working
8. E2E test passes

**MVP is complete after Phase 3!**

---

## Post-MVP Roadmap

With MVP complete, future versions can add:

**v2: Learning & Memory**
- Agent remembers what worked
- Patterns extracted from successful strategies
- Suggestions improve over time

**v3: Knowledge Base**
- Structured storage of discoveries
- Hypothesis tracking
- Cross-strategy insights

**v4: Multi-Agent**
- Specialized agents (Researcher, Assistant, Coordinator)
- Collaborative strategy development
- Board-level oversight
