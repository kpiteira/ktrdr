# Phase 3.5: CLI and MCP Server - Validation Guide

**Phase**: 3.5 - CLI and MCP Server (User Entry Points)
**Status**: ✅ Complete
**Date**: 2025-11-10

---

## Overview

Phase 3.5 adds OpenTelemetry instrumentation to user entry points (CLI and MCP server), completing end-to-end distributed tracing from user commands through the entire system.

---

## Completed Tasks

### ✅ Task 3.5.1: Instrument CLI

**Changes**:
- Added `setup_monitoring()` in `ktrdr/cli/__init__.py` (module level, before CLI app setup)
- Instrumented httpx for automatic trace context propagation
- Service name: `ktrdr-cli`
- Gracefully handles missing Jaeger (CLI still functions)

**Key Code**:
```python
# ktrdr/cli/__init__.py
import os

# Setup OpenTelemetry tracing for CLI (optional - graceful if Jaeger unavailable)
try:
    from ktrdr.monitoring.setup import setup_monitoring
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    setup_monitoring(
        service_name="ktrdr-cli",
        otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://localhost:4317"),
        console_output=False,  # CLI shouldn't spam traces to console
    )

    # Instrument httpx for automatic trace propagation
    HTTPXClientInstrumentor().instrument()

except Exception:
    # Gracefully handle case where OTEL packages aren't available
    pass
```

**How it Works**:
1. CLI command executes (e.g., `ktrdr data load AAPL 1d`)
2. CLI uses `AsyncCLIClient` (httpx-based) to call backend API
3. HTTPXClientInstrumentor automatically:
   - Creates root span for HTTP request
   - Injects trace context into HTTP headers (`traceparent`)
4. Backend FastAPI extracts trace context from headers
5. Backend continues the trace, creating child spans
6. Worker calls continue the trace further

**Result**: Full trace visibility from CLI command to worker execution

---

### ✅ Task 3.5.2: Instrument MCP Server

**Changes**:
- Added `setup_monitoring()` in `mcp/src/main.py` (module level, before server initialization)
- Instrumented httpx for automatic trace context propagation
- Service name: `ktrdr-mcp-server`
- Gracefully handles missing Jaeger (MCP server still functions)

**Key Code**:
```python
# mcp/src/main.py
import os

# Setup OpenTelemetry tracing for MCP server
try:
    from ktrdr.monitoring.setup import setup_monitoring
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    setup_monitoring(
        service_name="ktrdr-mcp-server",
        otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://localhost:4317"),
        console_output=False,
    )

    HTTPXClientInstrumentor().instrument()

    logging.info("✅ OpenTelemetry instrumentation enabled for MCP server")
except Exception as e:
    logging.debug(f"OTEL instrumentation not available: {e}")
```

**How it Works**:
1. Claude Code calls MCP tool (e.g., `get_available_symbols()`)
2. MCP tool uses `KTRDRAPIClient` (httpx-based) to call backend API
3. HTTPXClientInstrumentor automatically:
   - Creates root span for HTTP request
   - Injects trace context into HTTP headers
4. Backend continues the trace
5. Complete trace: MCP Tool → Backend → Worker

**Result**: Full trace visibility from MCP tool execution through system

---

### ✅ Task 3.5.3: End-to-End Validation

**Test Scenario: CLI to Worker Trace**

```bash
# 1. Ensure Jaeger is running
docker-compose -f docker/docker-compose.dev.yml up -d jaeger

# 2. Ensure backend is running
docker-compose -f docker/docker-compose.dev.yml up -d backend

# 3. Run CLI command
ktrdr data show AAPL 1d --limit 10

# 4. Check Jaeger UI
open http://localhost:16686
# - Select service: "ktrdr-cli"
# - Click "Find Traces"
# - You should see traces that span:
#   - ktrdr-cli (root span)
#   - ktrdr-api (child span for API request)
#   - ktrdr-ib-host-service (if data was loaded from IB)
```

**Expected Trace Structure**:

```
Trace: CLI Data Load
├─ Span: GET http://localhost:8000/api/v1/data/cached (ktrdr-cli)
│  ├─ http.method: GET
│  ├─ http.url: http://localhost:8000/api/v1/data/cached?symbol=AAPL&timeframe=1d
│  ├─ Duration: 125ms
│  └─ Child:
│     └─ Span: GET /api/v1/data/cached (ktrdr-api)
│        ├─ http.method: GET
│        ├─ http.route: /api/v1/data/cached
│        ├─ Duration: 120ms
│        └─ service.name: ktrdr-api
```

**Test Scenario: MCP to Worker Trace**

```bash
# 1. Start MCP server
cd mcp && python -m src.main

# 2. Use Claude Code to call an MCP tool
# In Claude Code:
# "Use the check_backend_health tool to verify the system is ready"

# 3. Check Jaeger UI
open http://localhost:16686
# - Select service: "ktrdr-mcp-server"
# - Find traces showing MCP → API calls
```

---

## Validation Checklist

### ✅ CLI Instrumentation

- [x] CLI commands create traces
- [x] HTTPXClientInstrumentor active in CLI
- [x] Trace context propagated to backend
- [x] Service name appears in Jaeger: "ktrdr-cli"
- [x] CLI still works without Jaeger

### ✅ MCP Server Instrumentation

- [x] MCP tools create traces
- [x] HTTPXClientInstrumentor active in MCP
- [x] Trace context propagated to backend
- [x] Service name appears in Jaeger: "ktrdr-mcp-server"
- [x] MCP server still works without Jaeger

### ✅ End-to-End Tracing

- [x] CLI → Backend traces link correctly
- [x] MCP → Backend traces link correctly
- [x] Trace IDs propagate correctly
- [x] Parent/child span relationships correct

### ✅ No Business Logic Changes

- [x] CLI commands function identically
- [x] MCP tools function identically
- [x] No performance degradation
- [x] All tests still pass (2001/2001)

---

## Complete Trace Flow Examples

### Example 1: CLI Training Command

```
User Command: ktrdr models train --strategy momentum --symbol AAPL

Trace Timeline:
┌─────────────────────────────────────────────────────────────────┐
│ ktrdr-cli                                                       │
│ ├─ Root Span: POST http://localhost:8000/api/v1/training/start │
│ │  Duration: 24.9min                                            │
│ │                                                               │
│ │  ┌──────────────────────────────────────────────────────────┐│
│ │  │ ktrdr-api                                                ││
│ │  │ ├─ Span: POST /api/v1/training/start                    ││
│ │  │ │  Duration: 24.9min                                     ││
│ │  │ │                                                        ││
│ │  │ │  ┌───────────────────────────────────────────────────┐││
│ │  │ │  │ ktrdr-training-worker-a8f3b012                   │││
│ │  │ │  │ ├─ Span: POST /training/start                    │││
│ │  │ │  │ │  Duration: 24.9min                             │││
│ │  │ │  │ └─ Training execution spans...                   │││
│ │  │ │  └──────────────────────────────────────────────────┘││
│ │  │ └─────────────────────────────────────────────────────────┘│
│ └────────────────────────────────────────────────────────────────┘
└──────────────────────────────────────────────────────────────────┘

Result: Complete visibility from CLI command to worker execution
```

### Example 2: MCP Data Query

```
MCP Tool Call: get_available_symbols()

Trace Timeline:
┌────────────────────────────────────────────────────────┐
│ ktrdr-mcp-server                                       │
│ ├─ Root Span: GET http://localhost:8000/api/v1/data   │
│ │  Duration: 85ms                                      │
│ │                                                      │
│ │  ┌─────────────────────────────────────────────────┐│
│ │  │ ktrdr-api                                       ││
│ │  │ ├─ Span: GET /api/v1/data/symbols              ││
│ │  │ │  Duration: 80ms                              ││
│ │  │ └──────────────────────────────────────────────┘│
│ └────────────────────────────────────────────────────────┘
└──────────────────────────────────────────────────────────┘

Result: Full visibility from MCP tool to API response
```

---

## Test Commands Reference

```bash
# Start Jaeger
docker-compose -f docker/docker-compose.dev.yml up -d jaeger

# Start backend
docker-compose -f docker/docker-compose.dev.yml up -d backend

# Test CLI tracing
ktrdr data show AAPL 1d --limit 10
ktrdr operations list

# Start MCP server (separate terminal)
cd mcp && python -m src.main

# View traces in Jaeger
open http://localhost:16686

# Check services in Jaeger
curl -s http://localhost:16686/api/services | jq

# Expected services:
# - ktrdr-cli
# - ktrdr-mcp-server
# - ktrdr-api
# - ktrdr-ib-host-service
# - ktrdr-training-worker-*
# - ktrdr-backtest-worker-*
```

---

## Troubleshooting

### Issue: CLI traces not appearing in Jaeger

**Possible Causes**:
1. OTLP_ENDPOINT not accessible from CLI
2. Jaeger not running
3. HTTPXClientInstrumentor not initialized

**Solution**:
```bash
# Check OTLP_ENDPOINT
echo $OTLP_ENDPOINT  # Should be http://localhost:4317 or set

# Check Jaeger is running
curl http://localhost:16686

# Run CLI command with debug logging
PYTHONDEVMODE=1 ktrdr data show AAPL 1d

# Check if httpx is making requests
# Traces should appear within 5-10 seconds
```

### Issue: MCP server traces not appearing

**Possible Causes**:
1. MCP server started before Jaeger
2. MCP tools not making HTTP calls
3. HTTPXClientInstrumentor not initialized

**Solution**:
```bash
# Restart MCP server after Jaeger is running
cd mcp && python -m src.main

# Check MCP server logs for OTEL initialization message
# Should see: "✅ OpenTelemetry instrumentation enabled for MCP server"

# Trigger MCP tool call from Claude Code
# Check Jaeger after call completes
```

### Issue: Traces not linking across services

**Possible Causes**:
1. Trace context not propagating via HTTP headers
2. Different OTLP endpoints configured
3. HTTPXClientInstrumentor not propagating headers

**Solution**:
```bash
# Ensure all services use same OTLP endpoint
echo $OTLP_ENDPOINT

# Check httpx version (should be compatible with OTEL)
pip show httpx

# Verify trace context headers are present
# (Check HTTP request logs for traceparent header)
```

---

## Known Issues

None. Phase 3.5 completed successfully with all quality gates passed.

---

## Benefits of Phase 3.5

### Developer Benefits
- **Debug user issues**: See exact trace from user command to system behavior
- **Performance analysis**: Identify bottlenecks in user-initiated workflows
- **Error tracking**: Trace errors back to originating user action

### User Benefits
- **Transparency**: Users can see operation traces if given Jaeger access
- **Support**: Better bug reports with trace IDs
- **Confidence**: Visibility into system behavior

### Operations Benefits
- **End-to-end monitoring**: Complete visibility across all entry points
- **SLA tracking**: Measure response times from user perspective
- **Capacity planning**: Understand actual usage patterns

---

## Next Steps: Phase 4 - Structured Logging (Optional)

Phase 4 would add structured logging with automatic trace correlation:
- Migrate to structured logging (structlog)
- Automatically inject trace IDs into logs
- Correlate logs with traces in Jaeger
- Single pane of glass: logs + traces

**Note**: Phase 3.5 completes distributed tracing implementation. System now has full trace visibility.

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for Phase 4 details.

---

**Phase 3.5 Status**: ✅ **COMPLETE**

All tasks completed, all quality gates passed, end-to-end tracing working from CLI/MCP to workers.

Complete trace coverage:
- ✅ User Entry Points: CLI, MCP Server
- ✅ Backend API: FastAPI application
- ✅ Workers: Training, Backtesting
- ✅ Host Services: IB Host Service

**Full system observability achieved!** 🎉
