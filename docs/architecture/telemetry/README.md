# KTRDR Observability & Telemetry

**Status**: Design Phase
**Last Updated**: 2025-11-11

---

## Overview

This directory contains the design and architecture for KTRDR's observability stack based on **OpenTelemetry (OTEL)**.

The primary goal is to provide **distributed tracing** and **structured logging** across KTRDR's distributed architecture (API backend, IB host service, training workers, backtesting workers) to enable rapid debugging of service communication failures, worker operations, and runtime issues.

---

## Documents

### [DESIGN.md](DESIGN.md) - High-Level Design

**Read This First** for:
- Design goals and motivation
- Problem statement (why we need this)
- Core design decisions (OTEL vs Prometheus alone, auto-instrumentation strategy)
- Implementation phases (6 phases from console output to production)
- Trade-offs and rationale

**Key Takeaway**: Auto-instrumentation gives 80% value for 5% effort. Start with traces + structured logs, add infrastructure incrementally.

---

### [ARCHITECTURE.md](ARCHITECTURE.md) - Technical Architecture

**Read This Second** for:
- System topology (services, collectors, backends)
- Core components (OTEL SDK, auto-instrumentation libraries, span processors)
- Instrumentation patterns (auto-instrumentation, custom spans, structured logging)
- Data flow (trace creation, log correlation)
- Service integration (API, IB host, training host, workers, CLI, MCP)
- Storage backends (Jaeger, Prometheus, Loki, Grafana)
- Performance and security considerations

**Key Takeaway**: Detailed technical specifications for implementing the observability stack.

---

### [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) - Step-by-Step Implementation

**Read This Third** before implementing:
- Detailed task-by-task implementation guide
- TDD approach with quality gates
- Specific code examples for each phase
- Validation and testing procedures
- Commit-by-commit breakdown

**Key Takeaway**: Follow this plan to implement observability incrementally with zero disruption to existing functionality.

---

## Quick Start

### Phase 1: Console Traces (30 minutes)

**Goal**: See traces printed to stdout with zero infrastructure

**Steps**:

1. **Add dependencies** (pyproject.toml):
   ```bash
   uv add opentelemetry-api \
          opentelemetry-sdk \
          opentelemetry-instrumentation-fastapi \
          opentelemetry-instrumentation-httpx \
          opentelemetry-instrumentation-logging \
          opentelemetry-exporter-otlp
   ```

2. **Create monitoring setup** (ktrdr/monitoring/setup.py):
   ```python
   from opentelemetry import trace
   from opentelemetry.sdk.trace import TracerProvider
   from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
   from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
   from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
   from opentelemetry.instrumentation.logging import LoggingInstrumentor

   def setup_monitoring(service_name: str):
       """Setup OTEL with console output."""
       provider = TracerProvider()
       provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
       trace.set_tracer_provider(provider)

   def instrument_app(app):
       """Auto-instrument FastAPI app."""
       FastAPIInstrumentor.instrument_app(app)
       HTTPXClientInstrumentor().instrument()
       LoggingInstrumentor().instrument(set_logging_format=True)
   ```

3. **Instrument API** (ktrdr/api/main.py):
   ```python
   from ktrdr.monitoring.setup import setup_monitoring, instrument_app

   setup_monitoring("ktrdr-api")
   app = FastAPI(...)
   instrument_app(app)
   ```

4. **Run and observe**:
   ```bash
   uv run python scripts/run_api_server.py
   ktrdr data load AAPL 1d
   # See traces in console!
   ```

**Expected Output**: JSON traces printed to stdout showing:
- API request (POST /api/v1/data/load or /api/v1/training/start)
- HTTP call to IB host service or worker selection
- Worker operation execution
- Logs with trace IDs across backend and workers

---

### Phase 2: Jaeger UI (1 hour)

**Goal**: Visual trace exploration

**Steps**:

1. **Add Jaeger to docker-compose.yml**:
   ```yaml
   services:
     jaeger:
       image: jaegertracing/all-in-one:latest
       ports:
         - "16686:16686"  # UI
         - "4317:4317"    # OTLP gRPC
       environment:
         - COLLECTOR_OTLP_ENABLED=true
   ```

2. **Update monitoring setup** (ktrdr/monitoring/setup.py):
   ```python
   from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
   from opentelemetry.sdk.trace.export import BatchSpanProcessor

   def setup_monitoring(service_name: str, otlp_endpoint: str):
       """Setup OTEL with Jaeger export."""
       provider = TracerProvider()
       exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
       provider.add_span_processor(BatchSpanProcessor(exporter))
       trace.set_tracer_provider(provider)
   ```

3. **Configure API** (docker-compose.yml):
   ```yaml
   services:
     api:
       environment:
         - OTLP_ENDPOINT=http://jaeger:4317
   ```

4. **Run and explore**:
   ```bash
   docker-compose up -d jaeger
   uv run python scripts/run_api_server.py
   ktrdr data load AAPL 1d
   # Open http://localhost:16686
   # Search for "ktrdr-api" service
   # Click trace to see timeline
   ```

**Expected Output**: Jaeger UI showing:
- Visual trace timeline (Gantt chart)
- Span details (attributes, timing)
- Service dependency graph

---

## Key Concepts

### Distributed Tracing

**What It Solves**: "Did the API call the host service? Where did it fail?"

**How It Works**:
1. API creates root span: `POST /api/v1/data/load`
2. API calls host service (httpx auto-instrumentation creates child span)
3. Host service continues trace (trace context propagated via HTTP headers)
4. All spans linked by `trace_id`

**Result**: Single trace showing full request flow across all services.

---

### Auto-Instrumentation

**What It Captures**:
- **FastAPI**: All API endpoints (method, route, status, duration)
- **httpx**: All HTTP calls (URL, status, errors)
- **Logging**: All logs (with trace_id and span_id)

**Code Required**: 3 lines
```python
FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()
LoggingInstrumentor().instrument(set_logging_format=True)
```

**Coverage**: 80-90% of debugging needs

---

### Structured Logging

**Before** (string formatting):
```python
logger.info(f"Training started for {symbol}")
```

**After** (structured):
```python
logger.info("Training started", extra={"symbol": symbol})
```

**Benefits**:
- Searchable: `symbol="AAPL"`
- Aggregatable: `avg(duration) by symbol`
- Machine-readable: Direct JSON access

---

### Trace-Log Correlation

**Automatic** (with LoggingInstrumentor):
```json
{
  "message": "Training started",
  "otelTraceID": "abc123...",
  "otelSpanID": "def456...",
  "symbol": "AAPL"
}
```

**Navigation**:
- Trace → Logs: Click span → see related logs
- Logs → Trace: Click log → see full trace

---

## KTRDR-Specific Use Cases

### 1. Debug Service Communication Failures

**Scenario**: "Data download failed"

**Old Way** (4-5 message rounds):
- Check if IB host service is running
- Check logs (scattered across services)
- Guess if API called host service
- Check environment variables
- Reconstruct flow manually

**With OTEL** (1 query):
```json
{
  "trace_id": "abc-123",
  "name": "POST /api/v1/data/load",
  "status": "ERROR",
  "spans": [
    {
      "name": "POST http://localhost:5001/download_historical_data",
      "status": "ERROR",
      "error.type": "ConnectionRefusedError"
    }
  ]
}
```

**Diagnosis**: "API tried to call localhost:5001, connection refused. IB host service not running."

---

### 2. Debug Worker Selection and Dispatch

**Scenario**: "Training operation not starting"

**Old Way**:
- Check worker registry manually
- Check worker health endpoints
- Guess if backend selected a worker
- Check worker logs individually

**With OTEL** (1 query):
```json
{
  "trace_id": "def-456",
  "name": "POST /api/v1/training/start",
  "status": "ERROR",
  "spans": [
    {
      "name": "worker_registry.select_worker",
      "attributes": {
        "worker_type": "training",
        "available_workers": 0,
        "required_capabilities": ["gpu"]
      },
      "status": "ERROR",
      "error.type": "NoAvailableWorkersError"
    }
  ]
}
```

**Diagnosis**: "No GPU training workers available. Need to start training workers with GPU capability."

---

### 3. Debug Distributed Worker Operations

**Scenario**: "Training is slow"

**With OTEL**:
```
Trace: train_model (25min)
├─ Backend: POST /api/v1/training/start (50ms)
│  └─ WorkerRegistry: select_worker (5ms)
├─ Training Worker: /api/v1/training/train (24.9min)
│  ├─ Data loading (45s)
│  ├─ Model init (5s)
│  └─ Training loop (24min) ← SLOW!
└─ Backend: Save results (10s)
```

**Diagnosis**: "Training loop is 2.4x slower than baseline. Check GPU utilization on worker node."

---

### 4. Debug Worker Health and Load Balancing

**Scenario**: "Operations queuing up despite multiple workers"

**With OTEL**:
```json
{
  "trace_id": "ghi-789",
  "name": "POST /api/v1/training/start",
  "spans": [
    {
      "name": "worker_registry.select_worker",
      "attributes": {
        "total_workers": 3,
        "available_workers": 0,
        "busy_workers": ["worker-1", "worker-2", "worker-3"],
        "selection_strategy": "least_busy"
      },
      "status": "QUEUED"
    }
  ]
}
```

**Diagnosis**: "All 3 workers busy. Consider adding more workers or optimizing operation duration."

---

### 5. Track Exceptions with Context

**Scenario**: Training fails with CUDA OOM

**With OTEL**:
```json
{
  "trace_id": "abc-123",
  "logs": [{
    "level": "ERROR",
    "message": "CUDA out of memory",
    "exception.type": "torch.cuda.OutOfMemoryError",
    "symbol": "AAPL",
    "batch_size": 512,
    "epochs": 100
  }]
}
```

**Diagnosis**: "batch_size=512 too large. Try batch_size=256."

---

### 6. Debug End-to-End CLI Operations

**Scenario**: "CLI training command not working"

**Old Way**:
- Check if API is running
- Try command with verbose flag
- Check logs manually
- Guess where it failed

**With OTEL** (1 trace showing full flow):
```
Trace: ktrdr train AAPL momentum (25min 350ms)
├─ CLI: cli.train (25min 350ms)
│  ├─ Attributes: cli.command="train", cli.symbol="AAPL", cli.strategy="momentum"
│  └─ POST http://localhost:8000/api/v1/training/start (25min 300ms)
│     ├─ Backend: POST /api/v1/training/start (25min 300ms)
│     │  └─ WorkerRegistry: select_worker (5ms)
│     │     └─ Selected: training-worker-gpu-01
│     └─ Training Worker: /api/v1/training/train (25min 250ms)
│        ├─ Data loading (45s)
│        ├─ Model init (5s)
│        └─ Training loop (24min 200s)
└─ CLI: Display results (50ms)
```

**Diagnosis**: "Complete end-to-end trace from user command to worker execution. Training completed successfully. Total time includes network latency and CLI overhead."

---

### 7. Debug MCP/LLM Agent Requests

**Scenario**: "LLM agent's training request failing"

**With OTEL**:
```json
{
  "trace_id": "mcp-789",
  "name": "mcp.tool.execute",
  "status": "ERROR",
  "spans": [
    {
      "name": "mcp.tool.execute",
      "attributes": {
        "mcp.tool": "start_training",
        "mcp.params": "{\"symbol\":\"AAPL\",\"strategy\":\"invalid_strategy\"}",
        "llm.agent": "claude-sonnet"
      },
      "children": [
        {
          "name": "POST /api/v1/training/start",
          "status": "ERROR",
          "error.type": "ValidationError",
          "error.message": "Unknown strategy: invalid_strategy"
        }
      ]
    }
  ]
}
```

**Diagnosis**: "LLM agent passed invalid strategy name 'invalid_strategy'. Backend validation caught the error. Need to update MCP tool schema or LLM prompt."

---

## Technology Stack Summary

| Component | Purpose | Required? |
|-----------|---------|-----------|
| **OTEL SDK** (Python) | Core instrumentation library | ✅ Always |
| **Auto-instrumentation** | FastAPI, httpx, logging | ✅ Always |
| **CLI Instrumentation** | Track user commands end-to-end | ✅ Recommended |
| **MCP Server Instrumentation** | Track LLM agent requests | ✅ Recommended |
| **Console Exporter** | Print traces to stdout | Dev only |
| **OTLP Exporter** | Send traces to backend | Production |
| **Jaeger** | Trace storage + UI | Recommended |
| **Prometheus** | Metrics collection | Optional |
| **Loki** | Log aggregation | Optional |
| **Grafana** | Unified UI | Optional |

---

## Implementation Timeline

| Phase | Goal | Effort | Value |
|-------|------|--------|-------|
| **1** | Console traces | 2 hours | Validate setup |
| **2** | Jaeger UI | 1 hour | Visual debugging |
| **3** | Workers + host services | 3 hours | End-to-end tracing across all workers |
| **3.5** | CLI + MCP server | 2 hours | Complete user-to-worker visibility |
| **4** | Structured logs | 4 hours | Searchable logs |
| **5** | Metrics + dashboards | 6 hours | Performance monitoring |
| **6** | Centralized aggregation | 8 hours | Production-ready |

**Total**: ~26 hours spread over 3 months

**ROI**: 3-5x reduction in debugging time for distributed issues

---

## Design Decisions Summary

### Why OTEL (not Prometheus alone)?

**KTRDR's primary debugging challenges are distributed service issues** (connection failures, routing, exceptions), not pure performance.

OTEL provides:
- ✅ Distributed tracing (see full request flow)
- ✅ Service communication visibility ("did API call host service?")
- ✅ Exception context (full stack + attributes)
- ✅ Auto-instrumentation (minimal code)

Prometheus alone:
- ❌ No distributed tracing
- ❌ No service communication visibility
- ❌ Limited exception context

---

### Why Auto-Instrumentation First?

**80/20 Rule**: Auto-instrumentation captures 80% of debugging needs with 5% of the effort.

**3 lines of code** gives:
- All API endpoints traced
- All host service calls traced
- All logs correlated with traces

**Custom instrumentation** can be added later for high-value code paths (training loops, data acquisition).

---

### Why Incremental Adoption?

**Minimize Risk**: Start simple (console output), prove value, then invest in infrastructure.

**Phase 1** (2 hours): Console traces → Validate setup works
**Phase 2** (1 hour): Jaeger UI → Visual debugging
**Phase 3+**: Add infrastructure based on demonstrated ROI

---

## FAQ

### Q: Will this slow down my operations?

**A**: No. Overhead is <5ms per request (negligible for operations lasting seconds to minutes). Export is async and batched.

### Q: Do I need to change my existing code?

**A**: Minimal changes. Auto-instrumentation requires ~10 lines of setup code in `main.py`. Business logic unchanged.

### Q: What about sensitive data in traces?

**A**: Use attribute filtering to exclude passwords, API keys. See ARCHITECTURE.md Security section.

### Q: Can I use this with existing logs?

**A**: Yes. Existing logs work as-is. LoggingInstrumentor adds trace context automatically.

### Q: Do I need all the infrastructure (Jaeger, Prometheus, Loki)?

**A**: No. Start with Phase 1 (console traces). Add infrastructure incrementally as needed.

---

## Next Steps

1. **Read DESIGN.md** for high-level design and rationale
2. **Read ARCHITECTURE.md** for technical implementation details
3. **Read IMPLEMENTATION_PLAN.md** for step-by-step instructions
4. **Start Phase 1** (console traces) to validate setup
5. **Add Jaeger** (Phase 2) for visual debugging
6. **Instrument workers and host services** (Phase 3) for end-to-end tracing across distributed operations

---

## References

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [OTEL Python Instrumentation](https://opentelemetry-python-contrib.readthedocs.io/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)

---

**Document End**
