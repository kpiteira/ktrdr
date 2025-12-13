# Reference: Observability Specifications

This document contains detailed specifications for telemetry integration.

---

## ⚠️ Architecture Update (December 2024)

**The agent now uses the Anthropic Python SDK directly instead of Claude Code CLI + MCP.**

**Key Simplifications:**

- **Single service** - Only backend to instrument (no separate MCP server or host service)
- **No cross-service tracing** - All spans are in one process
- **Single metrics endpoint** - Backend `:8000/metrics` (no MCP metrics endpoint)

See [ARCHITECTURE_DECISION_anthropic_api.md](ARCHITECTURE_DECISION_anthropic_api.md) for full details.

The MCP Server metrics section below is **no longer applicable** for the agent. Agent observability is now simpler - see Phase 3 plan for updated specifications.

---

## Stack Overview

KTRDR uses:

- **OTEL** - OpenTelemetry for instrumentation
- **Prometheus** - Metrics collection and storage
- **Jaeger** - Distributed tracing
- **Grafana** - Dashboards and visualization

The agent system must integrate with all of these.

---

## Prometheus Metrics

### Trigger Service Metrics

```python
# Trigger events
agent_trigger_total = Counter(
    'agent_trigger_total',
    'Total trigger events',
    ['reason', 'invoked']  # reason: start_new_cycle, training_completed, etc.
                           # invoked: true/false
)

# Quality gates
agent_gate_evaluations_total = Counter(
    'agent_gate_evaluations_total',
    'Gate evaluation results',
    ['gate_type', 'result']  # gate_type: training, backtest
                              # result: passed, failed
)

agent_gate_failure_reasons_total = Counter(
    'agent_gate_failure_reasons_total',
    'Gate failure breakdown',
    ['gate_type', 'reason']  # reason: accuracy_low, loss_high, etc.
)
```

### Cycle Metrics

```python
# Cycle outcomes
agent_cycle_total = Counter(
    'agent_cycle_total',
    'Completed cycles by outcome',
    ['outcome']  # success, failed_training_gate, etc.
)

# Cycle timing
agent_cycle_duration_seconds = Histogram(
    'agent_cycle_duration_seconds',
    'Total cycle duration',
    buckets=[60, 300, 600, 1800, 3600, 7200]  # 1m to 2h
)

agent_phase_duration_seconds = Histogram(
    'agent_phase_duration_seconds',
    'Duration per phase',
    ['phase'],  # designing, training, backtesting, assessing
    buckets=[10, 30, 60, 300, 600, 1800, 3600]
)
```

### Cost Metrics

```python
# Token usage
agent_tokens_total = Counter(
    'agent_tokens_total',
    'Total tokens used',
    ['direction']  # input, output
)

# Cost tracking
agent_cost_usd_total = Counter(
    'agent_cost_usd_total',
    'Total estimated cost in USD'
)

agent_budget_remaining_usd = Gauge(
    'agent_budget_remaining_usd',
    'Remaining daily budget in USD'
)

agent_budget_utilization_ratio = Gauge(
    'agent_budget_utilization_ratio',
    'Budget utilization (0-1)'
)
```

### MCP Server Metrics

```python
# Tool calls
mcp_tool_calls_total = Counter(
    'mcp_tool_calls_total',
    'MCP tool call count',
    ['tool', 'status']  # status: success, error
)

mcp_tool_duration_seconds = Histogram(
    'mcp_tool_duration_seconds',
    'MCP tool call duration',
    ['tool'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 5, 10]
)

mcp_tool_errors_total = Counter(
    'mcp_tool_errors_total',
    'MCP tool errors by type',
    ['tool', 'error_type']
)
```

---

## OTEL Traces

### Span Structure

```
trigger_check (root span)
├── check_active_session
├── check_operation_status (if active)
├── evaluate_gate (if operation complete)
│   └── gate_threshold_check
├── check_budget
└── invoke_agent (if work needed)
    ├── prepare_context
    ├── claude_code_execution
    │   ├── mcp_tool_call: get_recent_strategies
    │   ├── mcp_tool_call: save_strategy_config
    │   │   └── backend_api_call: POST /strategies
    │   ├── mcp_tool_call: start_training
    │   │   └── backend_api_call: POST /training/start
    │   └── mcp_tool_call: update_agent_state
    │       └── db_query: UPDATE agent_sessions
    └── record_metrics
```

### Span Attributes

**Trigger spans:**
```python
span.set_attribute("trigger.reason", "training_completed")
span.set_attribute("trigger.session_id", 42)
span.set_attribute("trigger.agent_invoked", True)
span.set_attribute("trigger.budget_remaining_usd", 3.45)
```

**Gate spans:**
```python
span.set_attribute("gate.type", "training")
span.set_attribute("gate.passed", True)
span.set_attribute("gate.accuracy", 0.523)
span.set_attribute("gate.threshold_accuracy", 0.45)
```

**MCP tool spans:**
```python
span.set_attribute("mcp.tool", "start_training")
span.set_attribute("mcp.success", True)
span.set_attribute("mcp.duration_ms", 234)
span.set_attribute("mcp.tokens_input", 1523)
span.set_attribute("mcp.tokens_output", 892)
```

### Context Propagation

Trace context must flow through:
1. Trigger service → Agent invocation (via environment or headers)
2. Agent → MCP server (via MCP protocol)
3. MCP server → KTRDR backend (via HTTP headers)

For Claude Code invocation, pass trace ID via environment variable:
```bash
OTEL_TRACE_ID=abc123 claude --mcp-config ...
```

MCP server extracts and continues the trace.

---

## Grafana Dashboard

### Agent Overview Panel

**Cycle Status** (Stat panel)
- Current phase
- Session ID
- Time in phase

**Recent Outcomes** (Pie chart)
- Success vs failure breakdown
- Last 24 hours

**Cycle Timeline** (Time series)
- Cycles completed per hour
- Colored by outcome

### Quality Gates Panel

**Gate Pass Rates** (Gauge)
- Training gate pass rate
- Backtest gate pass rate

**Failure Reasons** (Bar chart)
- Breakdown of why gates fail
- Last 7 days

### Cost Panel

**Daily Spend** (Time series)
- Cost per day
- Budget line overlay

**Budget Status** (Gauge)
- Current utilization
- Remaining budget

**Cost per Cycle** (Stat)
- Average cost
- Trend indicator

### Performance Panel

**Cycle Duration** (Histogram)
- Distribution of cycle times

**Phase Breakdown** (Stacked bar)
- Time spent in each phase
- Average over last 7 days

**Strategy Quality** (Time series)
- Average Sharpe of successful strategies
- Rolling 7-day average

### MCP Health Panel

**Tool Latency** (Heatmap)
- Response times by tool
- Highlight slow tools

**Error Rate** (Time series)
- Errors per hour
- By tool

---

## Alerting Rules

### Critical Alerts

```yaml
# Agent completely stuck
- alert: AgentNoActivity
  expr: increase(agent_trigger_total[1h]) == 0
  for: 1h
  labels:
    severity: critical
  annotations:
    summary: "Agent has no trigger activity for 1 hour"

# Budget exhausted early
- alert: AgentBudgetExhausted
  expr: agent_budget_remaining_usd < 0.10
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Agent budget exhausted for today"
```

### Warning Alerts

```yaml
# High failure rate
- alert: AgentHighFailureRate
  expr: rate(agent_cycle_total{outcome!="success"}[1h]) / rate(agent_cycle_total[1h]) > 0.8
  for: 30m
  labels:
    severity: warning
  annotations:
    summary: "Agent failure rate above 80%"

# MCP errors
- alert: MCPHighErrorRate
  expr: rate(mcp_tool_errors_total[5m]) > 0.1
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "MCP tool error rate elevated"
```

---

## Implementation Notes

### MCP Server Instrumentation

The MCP server needs OTEL SDK integration:

```python
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import Counter, Histogram

# Initialize tracer
tracer = trace.get_tracer(__name__)

# Wrap each tool handler
@mcp.tool()
async def start_training(...):
    with tracer.start_as_current_span("mcp_tool_call") as span:
        span.set_attribute("mcp.tool", "start_training")
        
        # Increment counter
        mcp_tool_calls_total.labels(tool="start_training", status="started").inc()
        
        start_time = time.time()
        try:
            result = await _do_start_training(...)
            mcp_tool_calls_total.labels(tool="start_training", status="success").inc()
            span.set_attribute("mcp.success", True)
            return result
        except Exception as e:
            mcp_tool_calls_total.labels(tool="start_training", status="error").inc()
            mcp_tool_errors_total.labels(tool="start_training", error_type=type(e).__name__).inc()
            span.set_attribute("mcp.success", False)
            span.record_exception(e)
            raise
        finally:
            duration = time.time() - start_time
            mcp_tool_duration_seconds.labels(tool="start_training").observe(duration)
            span.set_attribute("mcp.duration_ms", duration * 1000)
```

### Metrics Endpoint

Add Prometheus metrics endpoint to MCP server:

```python
from prometheus_client import make_asgi_app

# Mount at /metrics
metrics_app = make_asgi_app()
```
