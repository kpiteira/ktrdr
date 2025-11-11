# KTRDR Observability & Telemetry Design

**Version**: 1.0
**Status**: Design Phase
**Date**: 2025-11-11

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Design Goals](#design-goals)
3. [Problem Statement](#problem-statement)
4. [Core Design Decisions](#core-design-decisions)
5. [Telemetry Approach](#telemetry-approach)
6. [Implementation Phases](#implementation-phases)
7. [Technology Stack](#technology-stack)
8. [Trade-offs & Rationale](#trade-offs--rationale)
9. [Success Criteria](#success-criteria)

---

## Executive Summary

This design introduces **OpenTelemetry (OTEL)-based observability** to KTRDR, enabling comprehensive visibility into distributed operations across the API backend, IB host service, training workers, and backtesting workers. The primary goal is to provide **structured telemetry data** that enables rapid debugging of service communication failures, worker operations, distributed operation issues, and runtime exceptions.

### Key Design Principles

**Auto-instrumentation First**: Leverage OTEL's automatic instrumentation for FastAPI, httpx, and logging to gain immediate value with minimal code changes

**Incremental Adoption**: Start with traces and structured logs, add metrics and dashboards as needed

**LLM-Friendly Data**: Structured JSON telemetry enables AI coding assistants to diagnose issues from trace data without guesswork

**Distributed-First**: Design for KTRDR's multi-service architecture (API + host services)

---

## Design Goals

### Functional Goals

✅ **Service Communication Visibility**: See exactly which service called which endpoint and what happened
✅ **Distributed Tracing**: Track operations across API → IB Host → IB Gateway and API → Training Host
✅ **Automatic Trace Correlation**: Link logs to traces via trace IDs (no manual correlation)
✅ **Exception Tracking**: Capture structured exception data with full context (trace ID, span, attributes)
✅ **Operation Lifecycle Tracking**: Correlate KTRDR operation IDs with distributed traces

### Non-Functional Goals

✅ **Minimal Code Changes**: Auto-instrumentation handles 90% of telemetry needs
✅ **Fast Time-to-Value**: See traces in console within 30 minutes
✅ **Low Overhead**: Async exporters, sampling strategies, minimal performance impact
✅ **Developer-Friendly**: Easy local development with Jaeger UI
✅ **Production-Ready**: Support for centralized log/trace aggregation (Loki, Tempo/Jaeger)

---

## Problem Statement

### Current State: Blind to Service Interactions

KTRDR's distributed architecture creates debugging challenges:

```
CLI Command
  ↓
API Backend (Docker)
  ↓
  ├─ IB Host Service (port 5001) → IB Gateway (port 4002)
  ├─ Training Workers (multiple nodes) → GPU/PyTorch
  └─ Backtesting Workers (multiple nodes) → CPU computation
```

**Debugging Scenario**: "Data download failed"

**Current Process** (requires 4-5 message rounds):
1. Check if IB host service is running (`lsof -i :5001`)
2. Check IB host service logs (parse unstructured strings)
3. Determine if API called host service (no visibility)
4. Check environment variables (`USE_IB_HOST_SERVICE`)
5. Check if IB Gateway is running (`lsof -i :4002`)
6. Reconstruct flow manually from scattered logs

**Problems**:
- ❌ No visibility into whether HTTP calls succeeded
- ❌ Logs scattered across multiple services and workers
- ❌ No correlation between operation IDs and service calls
- ❌ String parsing required to extract context
- ❌ Manual detective work to reconstruct flow
- ❌ No visibility into worker selection and load balancing decisions
- ❌ Cannot trace operations across backend → worker boundary

### Desired State: X-Ray Vision

**With OTEL** (single query):

```json
{
  "trace_id": "abc-123",
  "operation_id": "op-xyz-789",
  "name": "POST /api/v1/data/load",
  "status": "ERROR",
  "duration_ms": 125,
  "spans": [
    {
      "name": "POST http://localhost:5001/download_historical_data",
      "status": "ERROR",
      "error.type": "ConnectionRefusedError",
      "http.url": "http://localhost:5001/download_historical_data",
      "http.method": "POST"
    }
  ],
  "logs": [
    {
      "level": "ERROR",
      "message": "Failed to connect to IB host service",
      "trace_id": "abc-123"
    }
  ]
}
```

**Immediate diagnosis**: "API tried to call IB host service at localhost:5001, got connection refused. Service not running."

**Benefits**:
- ✅ See full request flow in one trace
- ✅ Logs automatically correlated with traces
- ✅ Structured data (no string parsing)
- ✅ Diagnosis in first response (no iteration)

---

## Core Design Decisions

### Decision 1: OpenTelemetry (Not Prometheus Alone)

**Choice**: OTEL + Prometheus + Grafana (full observability stack)

**Alternative Considered**: Prometheus alone

**Rationale**:

| Requirement | Prometheus Alone | OTEL + Prometheus |
|-------------|------------------|-------------------|
| Service communication visibility | ❌ No distributed tracing | ✅ Full request path |
| "Did API call host service?" | ❌ Infer from metrics | ✅ See exact HTTP call |
| Exception context | ❌ Counter metrics only | ✅ Full stack + attributes |
| LLM debugging support | ❌ Metrics hard to interpret | ✅ Structured trace JSON |
| Auto-instrumentation | ❌ Manual metrics | ✅ FastAPI/httpx auto-traced |

**Key Insight**: KTRDR's primary debugging challenges are **distributed service issues** (connection failures, routing misconfigurations, exceptions), not performance optimization. OTEL's distributed tracing addresses the root problems.

---

### Decision 2: Auto-Instrumentation First

**Choice**: Start with OTEL auto-instrumentation, add custom spans later

**Instrumented Automatically**:
- FastAPI (all API endpoints)
- httpx (all HTTP calls to host services)
- logging (all log statements get trace context)

**Custom Instrumentation** (future):
- ServiceOrchestrator operations
- Data acquisition flows
- Training loops

**Rationale**:

**Low-Hanging Fruit**: 3 lines of code → traces + logs for all service interactions

```python
# This is ALL you need:
FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()
LoggingInstrumentor().instrument(set_logging_format=True)
```

**Immediate Value**:
- See all API requests (method, path, status, duration)
- See all host service calls (URL, status, errors)
- Logs include trace IDs (click log → view full trace)

**80/20 Rule**: Auto-instrumentation captures 80% of debugging needs with 5% of the effort.

---

### Decision 3: Structured Logging Pattern

**Choice**: Migrate from string formatting to structured logging

**Before** (string interpolation):
```python
logger.info(f"Training started for {symbol} with {epochs} epochs")
```

**After** (structured fields):
```python
logger.info(
    "Training started",
    extra={
        "symbol": symbol,
        "epochs": epochs,
        "strategy": strategy_name,
        "operation_id": operation_id
    }
)
```

**Rationale**:

| Aspect | String Logs | Structured Logs |
|--------|-------------|-----------------|
| **Searchability** | Regex parsing | Field queries: `symbol="AAPL"` |
| **Aggregation** | Impossible | Metrics: avg(duration) by symbol |
| **LLM Parsing** | String manipulation | Direct JSON access |
| **Context** | Lost in formatting | Preserved as attributes |

**Migration Strategy**: Incremental, starting with ServiceOrchestrator base class (affects all operations).

---

### Decision 4: Phased Infrastructure Rollout

**Choice**: Start simple (console output), add infrastructure incrementally

**Phase 1** (Week 1): Console traces + structured logs
- See traces printed to stdout
- Validate auto-instrumentation works
- No infrastructure required

**Phase 2** (Week 2): Jaeger UI
- Add Jaeger container (docker-compose)
- Visual trace timeline
- Easy debugging interface

**Phase 3** (Month 2): Prometheus + Grafana
- Add metrics collection
- Build dashboards
- Alerting (optional)

**Phase 4** (Future): Centralized aggregation
- Loki for log aggregation
- Tempo for trace storage
- Grafana for unified UI

**Rationale**: Prove value quickly (Phase 1), then invest in infrastructure based on demonstrated ROI.

---

### Decision 5: Trace Context in Operation IDs

**Choice**: Integrate OTEL trace IDs with KTRDR operation IDs

**Pattern**: Store trace context in OperationsService

```python
# When creating operation
operation = await operations_service.create_operation(
    operation_type=OperationType.DATA_DOWNLOAD,
    metadata={
        "trace_id": trace.get_current_span().get_span_context().trace_id,
        "span_id": trace.get_current_span().get_span_context().span_id
    }
)
```

**Benefits**:
- ✅ Users can query: "Show me trace for operation abc-123"
- ✅ Click operation ID → jump to trace
- ✅ Bidirectional navigation (trace ↔ operation)

**Rationale**: Operations are KTRDR's core abstraction; linking them to traces makes telemetry immediately useful for users.

---

## Telemetry Approach

### Three Pillars of Observability

#### 1. Distributed Traces (Primary Focus)

**Purpose**: Understand request flow across services

**KTRDR Use Cases**:
- "Did API call IB host service?"
- "Which worker did the backend select?"
- "Where did training fail?" (Backend, worker, GPU, network)
- "Why did data download time out?" (network, IB Gateway, data volume)
- "Are workers receiving operations from the backend?"
- "Why is load balancing not distributing evenly?"
- "Did the CLI command reach the backend?" (CLI → Backend connectivity)
- "Why did the LLM agent's request fail?" (MCP server → Backend validation)

**Auto-Captured Data**:
```json
{
  "trace_id": "abc-123",
  "spans": [
    {
      "name": "POST /api/v1/data/load",
      "service": "ktrdr-api",
      "duration_ms": 15234,
      "attributes": {
        "http.method": "POST",
        "http.route": "/api/v1/data/load",
        "http.status_code": 200
      },
      "children": [
        {
          "name": "POST http://localhost:5001/download_historical_data",
          "service": "ktrdr-api",
          "duration_ms": 15100,
          "attributes": {
            "http.url": "http://localhost:5001/download_historical_data",
            "http.status_code": 200
          }
        }
      ]
    }
  ]
}
```

**Custom Spans** (future):
```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def download_data(...):
    with tracer.start_as_current_span("data_acquisition") as span:
        span.set_attribute("symbol", symbol)
        span.set_attribute("timeframe", timeframe)
        span.set_attribute("provider", "ib_host_service")

        # Business logic
```

#### 2. Structured Logs (Correlated)

**Purpose**: Debug statements with automatic trace correlation

**Pattern**:
```python
logger.info(
    "Operation started",
    extra={
        "operation_id": operation_id,
        "operation_type": operation_type.value
    }
)
```

**OTEL Auto-Adds**:
```json
{
  "timestamp": "2025-11-11T10:00:00.000Z",
  "level": "INFO",
  "message": "Operation started",
  "trace_id": "abc-123",
  "span_id": "def-456",
  "service.name": "ktrdr-api",
  "operation_id": "op-xyz-789",
  "operation_type": "data_download"
}
```

**Unified Queries** (in Grafana):
- "Show all logs for trace abc-123" (across all services)
- "Show all traces with ERROR logs for symbol=AAPL"
- Click log → jump to trace → see full context

#### 3. Metrics (Performance)

**Purpose**: Aggregate statistics, alerting

**KTRDR Metrics** (future):
- Data download duration by symbol/timeframe
- Training duration by strategy
- IB host service request rate/latency
- GPU utilization
- Operation failure rate

**Collection**: Prometheus scrapes OTEL metrics endpoint

**Visualization**: Grafana dashboards

---

## Implementation Phases

### Phase 1: Auto-Instrumentation (Week 1)

**Goal**: Capture traces and logs with minimal code

**Tasks**:
1. Add OTEL dependencies to pyproject.toml
2. Create `ktrdr/monitoring/setup.py` with auto-instrumentation
3. Instrument API (FastAPI, httpx, logging)
4. Use ConsoleSpanExporter (print traces to stdout)
5. Test with CLI commands, observe traces

**Deliverables**:
- Traces printed to console for all API requests
- Logs include trace IDs
- Zero changes to business logic

**Validation**: Run `ktrdr data load AAPL 1d`, see full trace in console output.

**Effort**: ~2 hours

---

### Phase 2: Jaeger UI (Week 2)

**Goal**: Visual trace exploration

**Tasks**:
1. Add Jaeger to docker-compose.yml
2. Switch from ConsoleSpanExporter to OTLPSpanExporter
3. Configure OTEL to send traces to Jaeger
4. Test trace visualization

**Deliverables**:
- Jaeger UI at http://localhost:16686
- Visual trace timelines
- Service dependency graph

**Validation**: Open Jaeger, search for traces, click trace → see full timeline.

**Effort**: ~1 hour

---

### Phase 3: Worker and Host Service Instrumentation (Week 3)

**Goal**: End-to-end tracing across backend, workers, and host services

**Tasks**:
1. Add auto-instrumentation to IB host service
2. Add auto-instrumentation to training workers
3. Add auto-instrumentation to backtesting workers
4. Configure trace context propagation (HTTP headers)
5. Test cross-service traces including worker dispatch

**Deliverables**:
- Single trace spanning Backend → Worker → Host Service
- See exact latency breakdown by component
- Worker selection visible in traces

**Validation**:
- Data download shows: Backend (50ms) → IB Host (20ms) → IB Gateway (15s) → Parse (50ms)
- Training shows: Backend (50ms) → Worker Selection (5ms) → Worker (24.9min) → Result (10s)

**Effort**: ~3 hours

---

### Phase 3.5: CLI and MCP Server Instrumentation (Week 4)

**Goal**: End-to-end tracing from user entry points (CLI, LLM agents)

**Tasks**:
1. Add OTEL instrumentation to CLI commands
2. Add custom spans for CLI operations
3. Instrument MCP server (if applicable)
4. Test full trace: CLI → Backend → Worker or MCP → Backend → Worker

**Deliverables**:
- CLI commands create root spans
- Complete trace from `ktrdr train` command to worker completion
- MCP tool calls tracked with attributes

**Validation**:
- CLI trace shows: `ktrdr train AAPL momentum` → Backend API → Worker Selection → Worker Execution → CLI Result Display
- MCP trace shows: LLM Request → MCP Tool → Backend API → Worker

**Effort**: ~2 hours

---

### Phase 4: Structured Logging Migration (Month 2)

**Goal**: Searchable, aggregatable logs

**Tasks**:
1. Update ServiceOrchestrator to use structured logging
2. Update DataAcquisitionService structured logging
3. Update TrainingManager structured logging
4. Define standard log fields (operation_id, symbol, timeframe, etc.)

**Deliverables**:
- Consistent structured logs across all services
- Standard fields for correlation

**Validation**: Query logs by operation_id, symbol, see all related logs.

**Effort**: ~4 hours (incremental)

---

### Phase 5: Metrics + Dashboards (Month 3)

**Goal**: Performance monitoring and alerting

**Tasks**:
1. Add Prometheus to docker-compose.yml
2. Configure OTEL metrics exporter
3. Add custom metrics (operation duration, failure rate)
4. Build Grafana dashboards

**Deliverables**:
- Prometheus metrics at http://localhost:9090
- Grafana dashboards at http://localhost:3000
- Visual operation statistics

**Effort**: ~6 hours

---

### Phase 6: Centralized Aggregation (Future)

**Goal**: Production-ready observability

**Tasks**:
1. Add Loki for log aggregation
2. Add Tempo for trace storage (or continue with Jaeger)
3. Unified Grafana for logs + traces + metrics
4. Retention policies

**Deliverables**:
- Single UI for all telemetry
- Historical trace/log search
- Long-term storage

**Effort**: ~8 hours

---

## Technology Stack

### Core Components

**OpenTelemetry SDK**:
- `opentelemetry-api` - Core API
- `opentelemetry-sdk` - SDK implementation
- `opentelemetry-instrumentation-fastapi` - Auto-instrument FastAPI
- `opentelemetry-instrumentation-httpx` - Auto-instrument httpx
- `opentelemetry-instrumentation-logging` - Auto-instrument Python logging

**Exporters**:
- `opentelemetry-exporter-otlp` - OTLP protocol (standard)
- Console exporter (dev/testing)

**Infrastructure** (optional, incremental):
- **Jaeger**: Trace visualization UI
- **Prometheus**: Metrics collection
- **Grafana**: Unified dashboards (logs + traces + metrics)
- **Loki**: Log aggregation (future)
- **Tempo**: Trace storage (alternative to Jaeger)

### Why OTLP (OpenTelemetry Protocol)?

**Vendor-Neutral**: Switch backends without changing instrumentation
- Today: Jaeger for traces
- Tomorrow: Tempo or Datadog or Honeycomb (same code)

**Standard**: CNCF project, widely supported

---

## Trade-offs & Rationale

### Trade-off 1: OTEL vs Prometheus Alone

**Decision**: OTEL (traces + metrics + logs)

**Trade-offs**:
- ❌ More complex setup (3 components vs 1)
- ❌ Steeper learning curve
- ✅ Distributed tracing (critical for KTRDR)
- ✅ Service communication visibility
- ✅ Auto-instrumentation (minimal code)

**Rationale**: KTRDR's debugging challenges are **distributed system issues** (service failures, routing, exceptions), not pure performance optimization. OTEL addresses the root problems.

---

### Trade-off 2: Auto-Instrumentation vs Manual Spans

**Decision**: Start with auto-instrumentation, add custom spans later

**Trade-offs**:
- ❌ Less control over span details initially
- ❌ Generic span names (HTTP method + route)
- ✅ 80% value for 5% effort
- ✅ No business logic changes
- ✅ Fast time-to-value

**Rationale**: KTRDR needs **immediate debugging value**. Auto-instrumentation provides this without disrupting development. Custom spans can be added incrementally to high-value code paths.

---

### Trade-off 3: Console Output vs Jaeger (Phase 1)

**Decision**: Start with console output, add Jaeger in Phase 2

**Trade-offs**:
- ❌ No visual timeline initially
- ❌ JSON harder to read than UI
- ✅ Zero infrastructure required
- ✅ Validate instrumentation works
- ✅ Easy to debug OTEL setup

**Rationale**: Minimize initial friction. Seeing traces in console proves setup works before investing in infrastructure.

---

### Trade-off 4: Structured Logging Migration Effort

**Decision**: Incremental migration starting with ServiceOrchestrator

**Trade-offs**:
- ❌ Mixed logging styles during transition
- ❌ Requires updating existing code
- ✅ High-value paths migrated first
- ✅ Non-disruptive (existing logs still work)
- ✅ Template for other modules

**Rationale**: ServiceOrchestrator affects all operations (training, data, backtesting), so updating it provides maximum leverage. Other modules can migrate gradually.

---

### Trade-off 5: Sampling Strategy

**Decision**: Start with 100% sampling, add sampling later if needed

**Trade-offs**:
- ❌ Higher storage/bandwidth in production
- ✅ Complete trace coverage in development
- ✅ No missed traces during debugging
- ✅ Simpler initial setup

**Rationale**: KTRDR is not a high-traffic web service. Training/backtesting operations are low-volume, high-value. Capturing every trace is acceptable. Sampling can be added if storage becomes an issue.

---

## Success Criteria

### Phase 1: Auto-Instrumentation

✅ **All API requests generate traces** (visible in console)
✅ **httpx calls to host services captured** as child spans
✅ **Logs include trace IDs** (automatic correlation)
✅ **Zero changes to business logic**

### Phase 2: Jaeger UI

✅ **Visual trace timeline** in Jaeger UI
✅ **Service dependency graph** shows API → host services
✅ **Click trace → see all spans** with timing breakdown

### Phase 3: Worker and Host Service Instrumentation

✅ **Single trace spans Backend + Worker + Host Service**
✅ **Cross-service trace context propagation** works (including workers)
✅ **Worker selection visible** in traces with attributes
✅ **See exact latency breakdown**: Backend (50ms) → Worker Selection (5ms) → Worker (24.9min) → Host (20ms)

### Phase 3.5: CLI and MCP Server Instrumentation

✅ **CLI commands create root spans** with command attributes
✅ **Complete end-to-end trace**: CLI → Backend → Worker → CLI Result
✅ **MCP tool calls tracked** with tool name and parameters
✅ **LLM agent requests visible** in traces with error details

### Phase 4: Structured Logging

✅ **ServiceOrchestrator uses structured logging**
✅ **Standard fields defined** (operation_id, symbol, strategy)
✅ **Logs searchable by field** (e.g., "show logs where symbol=AAPL")

### Phase 5: Metrics + Dashboards

✅ **Prometheus collecting metrics**
✅ **Grafana dashboard** showing operation statistics
✅ **Alert on operation failures** (optional)

### Overall Success Metrics

✅ **Debugging time reduced 3x-5x** for distributed issues
✅ **LLM agents diagnose issues in first response** (no iteration)
✅ **Service communication failures identified in <1 minute**
✅ **Exception context captured automatically** (no manual log parsing)
✅ **End-to-end visibility** from CLI command or LLM request to worker completion
✅ **MCP/LLM integration issues** debuggable from traces (parameter validation, routing)

---

## Next Steps

1. **Review & Approve** this design document
2. **Review ARCHITECTURE.md** for technical implementation specifications
3. **Create Phase 1 Implementation** (auto-instrumentation proof of concept)
4. **Validate Value** before investing in infrastructure

**Related Documents**:
- **ARCHITECTURE.md** - Technical implementation specifications
- **IMPLEMENTATION.md** - Step-by-step implementation guide (future)

---

**Document End**
