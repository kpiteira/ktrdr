# KTRDR Observability & Telemetry Architecture

**Version**: 1.0
**Status**: Architecture Design
**Date**: 2025-11-11

---

## Table of Contents

1. [System Context](#system-context)
2. [Architectural Overview](#architectural-overview)
3. [Core Components](#core-components)
4. [Instrumentation Patterns](#instrumentation-patterns)
5. [Data Flow](#data-flow)
6. [Service Integration](#service-integration)
7. [Storage & Backends](#storage--backends)
8. [Trace Context Propagation](#trace-context-propagation)
9. [Structured Logging Architecture](#structured-logging-architecture)
10. [Performance & Overhead](#performance--overhead)
11. [Security Considerations](#security-considerations)

---

## System Context

### Purpose

The telemetry architecture provides **comprehensive observability** for KTRDR's distributed system, capturing traces, logs, and metrics across the API container, IB host service, and training host service.

### Key Requirements

- **Distributed Tracing**: Track requests across service boundaries (API → host services → IB Gateway/GPU)
- **Auto-Instrumentation**: Capture telemetry with minimal code changes
- **Trace-Log Correlation**: Automatically link logs to traces via trace IDs
- **Structured Data**: Machine-readable telemetry for programmatic analysis
- **Low Overhead**: <5% performance impact on operations
- **Developer Experience**: Easy local development with console/UI tools

### Architecture Drivers

1. **Distributed Architecture**: KTRDR spans 3+ services (API, IB host, training host)
2. **Service Communication Failures**: Primary debugging challenge is "did the call happen?"
3. **Exception Context**: Need full context (trace, span, attributes) for errors
4. **LLM-Friendly**: Structured data enables AI assistants to diagnose issues directly
5. **Incremental Adoption**: Must work without disrupting existing code

---

## Architectural Overview

### Telemetry Stack

```
┌────────────────────────────────────────────────────────────────┐
│                     KTRDR Services                              │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  API         │  │ IB Host      │  │ Training     │         │
│  │  Container   │  │ Service      │  │ Host Service │         │
│  │              │  │              │  │              │         │
│  │ OTEL SDK     │  │ OTEL SDK     │  │ OTEL SDK     │         │
│  │ - FastAPI    │  │ - FastAPI    │  │ - FastAPI    │         │
│  │ - httpx      │  │ - httpx      │  │ - PyTorch    │         │
│  │ - logging    │  │ - logging    │  │ - logging    │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                 │                 │                 │
│         └─────────────────┼─────────────────┘                 │
│                           │                                   │
└───────────────────────────┼───────────────────────────────────┘
                            │ OTLP (gRPC/HTTP)
                            ▼
                   ┌─────────────────┐
                   │ OTEL Collector  │
                   │  (Optional)     │
                   └────────┬────────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
   ┌───────────┐     ┌───────────┐    ┌───────────┐
   │  Jaeger   │     │Prometheus │    │   Loki    │
   │  (Traces) │     │ (Metrics) │    │  (Logs)   │
   └─────┬─────┘     └─────┬─────┘    └─────┬─────┘
         │                 │                 │
         └─────────────────┼─────────────────┘
                           ▼
                    ┌────────────┐
                    │  Grafana   │
                    │ (Unified)  │
                    └────────────┘
```

### Architectural Layers

#### 1. Instrumentation Layer (In-Process)

**Location**: Within each KTRDR service (API, host services)

**Components**:
- OTEL SDK (Python)
- Auto-instrumentation libraries
- Custom span creation (future)
- Trace context propagation

**Responsibilities**:
- Capture traces (spans)
- Enrich logs with trace context
- Collect metrics (future)
- Export to collector/backend

#### 2. Collection Layer (Optional)

**Location**: OTEL Collector (standalone container)

**Responsibilities**:
- Receive traces/metrics/logs from services
- Buffer and batch telemetry
- Transform and enrich data
- Route to multiple backends

**When to Use**:
- Production (centralized collection)
- Multi-backend export (e.g., Jaeger + Datadog)
- Advanced filtering/sampling

**When to Skip**:
- Development (direct export to Jaeger/console)
- Single backend (simpler configuration)

#### 3. Storage Layer

**Backends**:
- **Jaeger**: Trace storage and UI
- **Prometheus**: Metrics storage
- **Loki**: Log aggregation (future)
- **Tempo**: Alternative trace storage (future)

#### 4. Visualization Layer

**Grafana**: Unified UI for traces + metrics + logs

**Features**:
- Trace timeline visualization
- Service dependency graphs
- Log-to-trace correlation
- Custom dashboards
- Alerting

---

## Core Components

### 1. OTEL SDK (Python)

**Package**: `opentelemetry-sdk`

**Architecture**:

```python
# Conceptual structure
TracerProvider
  ├─> Resource (service.name, service.version, ...)
  ├─> SpanProcessor
  │   └─> BatchSpanProcessor
  │       └─> SpanExporter (Console, OTLP, Jaeger)
  └─> Sampler (AlwaysOn, TraceIdRatioBased, ...)

MeterProvider
  ├─> Resource
  ├─> MetricReader
  │   └─> PrometheusMetricReader
  └─> View (aggregation, filtering)
```

**Configuration** (ktrdr/monitoring/setup.py):

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

def setup_tracing(service_name: str, otlp_endpoint: str):
    """Configure OTEL tracing for a service."""

    # Resource identifies the service
    resource = Resource.create({
        "service.name": service_name,
        "service.version": get_version(),
        "deployment.environment": get_environment()
    })

    # Tracer provider
    provider = TracerProvider(resource=resource)

    # Export spans to OTLP endpoint (Jaeger, Collector)
    span_exporter = OTLPSpanExporter(
        endpoint=otlp_endpoint,
        insecure=True  # Use TLS in production
    )

    # Batch processor (async, low overhead)
    processor = BatchSpanProcessor(span_exporter)
    provider.add_span_processor(processor)

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    return provider
```

**Key Properties**:
- **Resource**: Identifies service (service.name, deployment.environment)
- **BatchSpanProcessor**: Batches spans for efficient export (async, configurable)
- **Sampler**: Controls trace sampling (100% by default, configurable)

---

### 2. Auto-Instrumentation Libraries

#### FastAPI Instrumentation

**Package**: `opentelemetry-instrumentation-fastapi`

**What It Captures**:
- Every HTTP request (method, route, status, duration)
- Request/response headers (configurable)
- Exceptions (automatically captured as span events)

**Usage**:

```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

app = FastAPI(...)

# Instrument the entire app (one line!)
FastAPIInstrumentor.instrument_app(app)
```

**Captured Span Attributes**:
- `http.method`: GET, POST, etc.
- `http.route`: `/api/v1/data/load`
- `http.status_code`: 200, 500, etc.
- `http.url`: Full request URL
- `http.target`: Path + query string
- `net.host.name`: Hostname
- `net.host.port`: Port

**Span Name**: `{http.method} {http.route}`

Example: `POST /api/v1/data/load`

#### httpx Instrumentation

**Package**: `opentelemetry-instrumentation-httpx`

**What It Captures**:
- Every HTTP client request (to host services, external APIs)
- Request/response headers
- Network errors (connection refused, timeouts)
- DNS resolution time

**Usage**:

```python
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

# Instrument all httpx clients globally
HTTPXClientInstrumentor().instrument()
```

**Captured Span Attributes**:
- `http.method`: POST
- `http.url`: `http://localhost:5001/download_historical_data`
- `http.status_code`: 200 (or null if connection failed)
- `error.type`: `ConnectionRefusedError` (on failure)
- `net.peer.name`: Destination hostname
- `net.peer.port`: Destination port

**Critical for KTRDR**: This automatically captures all API → host service calls!

#### Logging Instrumentation

**Package**: `opentelemetry-instrumentation-logging`

**What It Does**:
- Injects trace context into log records
- Adds `trace_id` and `span_id` to every log statement
- Enables log-to-trace correlation

**Usage**:

```python
from opentelemetry.instrumentation.logging import LoggingInstrumentor

# Instrument Python logging
LoggingInstrumentor().instrument(
    set_logging_format=True,  # Add trace fields to log format
    log_level=logging.INFO
)
```

**Injected Fields**:
- `otelTraceID`: Trace ID (hex string)
- `otelSpanID`: Span ID (hex string)
- `otelServiceName`: Service name

**Example Log** (after instrumentation):

```json
{
  "timestamp": "2025-11-11T10:00:00.000Z",
  "level": "INFO",
  "message": "Training started",
  "otelTraceID": "1234567890abcdef",
  "otelSpanID": "abcdef123456",
  "otelServiceName": "ktrdr-api",
  "symbol": "AAPL",
  "epochs": 100
}
```

---

### 3. Span Processors

**Purpose**: Control how spans are exported (batching, filtering, transformation)

#### BatchSpanProcessor (Recommended)

**Behavior**:
- Buffers spans in memory
- Exports in batches (default: 512 spans or 5s interval)
- Async export (non-blocking)

**Configuration**:

```python
from opentelemetry.sdk.trace.export import BatchSpanProcessor

processor = BatchSpanProcessor(
    span_exporter=exporter,
    max_queue_size=2048,      # Max spans in buffer
    schedule_delay_millis=5000,  # Export interval
    max_export_batch_size=512,   # Spans per batch
    export_timeout_millis=30000  # Export timeout
)
```

**Trade-offs**:
- ✅ Low overhead (async, batched)
- ✅ Production-ready
- ❌ Spans delayed up to 5s (not real-time)

#### SimpleSpanProcessor (Dev Only)

**Behavior**:
- Exports spans immediately (synchronous)
- No batching

**Use Case**: Console debugging (see traces instantly)

**Trade-offs**:
- ✅ Immediate feedback
- ❌ High overhead (sync I/O on every span)
- ❌ Not for production

---

### 4. Trace Exporters

#### Console Exporter (Development)

**Purpose**: Print traces to stdout for debugging

**Usage**:

```python
from opentelemetry.sdk.trace.export import ConsoleSpanExporter

exporter = ConsoleSpanExporter()
```

**Output Format**: JSON (each span printed)

**Use Case**: Phase 1 (validate auto-instrumentation works)

#### OTLP Exporter (Production)

**Purpose**: Export traces to OTLP-compatible backend (Jaeger, Collector, Tempo)

**Protocols**:
- **gRPC**: Higher performance, binary protocol
- **HTTP**: Simpler, firewall-friendly

**Usage**:

```python
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

exporter = OTLPSpanExporter(
    endpoint="http://jaeger:4317",  # gRPC
    insecure=True  # Use TLS in production
)
```

**Or HTTP**:

```python
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

exporter = OTLPSpanExporter(
    endpoint="http://jaeger:4318/v1/traces",  # HTTP
)
```

---

## Instrumentation Patterns

### Pattern 1: Auto-Instrumentation (Primary)

**When to Use**: 90% of cases (API endpoints, HTTP calls, logs)

**Setup** (ktrdr/monitoring/setup.py):

```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

def instrument_app(app: FastAPI):
    """Auto-instrument FastAPI app."""
    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)

    # Instrument httpx (global)
    HTTPXClientInstrumentor().instrument()

    # Instrument logging
    LoggingInstrumentor().instrument(set_logging_format=True)

    logger.info("✅ Auto-instrumentation enabled")
```

**Call Once** (ktrdr/api/main.py):

```python
from ktrdr.monitoring.setup import setup_monitoring, instrument_app

# Setup OTEL SDK
setup_monitoring(
    service_name="ktrdr-api",
    otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://localhost:4317")
)

# Auto-instrument
instrument_app(app)
```

**Benefits**:
- ✅ Zero business logic changes
- ✅ Comprehensive coverage (all endpoints, all HTTP calls)
- ✅ Consistent span naming

---

### Pattern 2: Custom Spans (High-Value Paths)

**When to Use**: Add business context to traces (symbol, strategy, operation_id)

**Pattern** (ServiceOrchestrator):

```python
from opentelemetry import trace

class ServiceOrchestrator:
    def __init__(self):
        self.tracer = trace.get_tracer(__name__)

    async def start_operation(self, operation_type: OperationType, context: dict):
        """Start operation with tracing."""

        # Create custom span
        with self.tracer.start_as_current_span("operation.start") as span:
            # Add business attributes
            span.set_attribute("operation.type", operation_type.value)
            span.set_attribute("operation.id", context.get("operation_id"))
            span.set_attribute("symbol", context.get("symbol"))
            span.set_attribute("strategy", context.get("strategy"))

            # Business logic (auto-traced HTTP calls nest within this span)
            result = await self._execute_operation(context)

            # Add result attributes
            span.set_attribute("operation.status", "success")
            span.set_attribute("operation.duration_ms", result.duration_ms)

            return result
```

**Span Hierarchy**:

```
operation.start (custom)
  ├─ POST /api/v1/data/load (auto-instrumented)
  │   └─ POST http://localhost:5001/... (auto-instrumented)
  └─ operation.complete (custom)
```

**Benefits**:
- ✅ Business context preserved in traces
- ✅ Easy filtering (show me all traces for symbol=AAPL)
- ✅ Nests with auto-instrumented spans

---

### Pattern 3: Structured Logging

**Pattern**: Use `extra` parameter for structured fields

**Before** (string formatting):

```python
logger.info(f"Training started for {symbol} with {epochs} epochs")
```

**After** (structured):

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

**Combined with OTEL** (automatic trace correlation):

```json
{
  "timestamp": "2025-11-11T10:00:00.000Z",
  "level": "INFO",
  "message": "Training started",
  "otelTraceID": "abc123...",
  "otelSpanID": "def456...",
  "symbol": "AAPL",
  "epochs": 100,
  "strategy": "momentum",
  "operation_id": "op-xyz-789"
}
```

**Query Examples** (in Loki/Grafana):
- `{service="ktrdr-api"} | json | symbol="AAPL"`
- `{service="ktrdr-api"} | json | otelTraceID="abc123..."`
- `{service="ktrdr-api"} | json | operation_id="op-xyz-789" | level="ERROR"`

---

### Pattern 4: Exception Tracking

**Automatic** (with auto-instrumentation):

```python
# Exceptions automatically captured as span events
@app.get("/data/load")
async def load_data(symbol: str):
    # If this raises, OTEL captures:
    # - Exception type
    # - Exception message
    # - Stack trace
    # - Span marked as error (status=ERROR)
    data = await data_manager.load_data(symbol)
    return data
```

**Span Attributes on Exception**:
- `exception.type`: `ValueError`
- `exception.message`: "Invalid symbol"
- `exception.stacktrace`: Full stack trace
- `otel.status_code`: ERROR

**Manual Exception Context** (add business context):

```python
from opentelemetry import trace

try:
    result = await train_model(symbol, strategy)
except Exception as e:
    span = trace.get_current_span()
    span.set_attribute("error.symbol", symbol)
    span.set_attribute("error.strategy", strategy)
    span.record_exception(e)
    span.set_status(Status(StatusCode.ERROR, str(e)))
    raise
```

---

## Data Flow

### Trace Creation Flow

```
User Request
  │
  ▼
FastAPI Endpoint (auto-instrumented)
  │
  ├─ Create root span: "POST /api/v1/data/load"
  │  └─ Attributes: http.method, http.route, ...
  │
  ▼
DataAcquisitionService.download_data()
  │
  ├─ (Optional) Create custom span: "data.download"
  │  └─ Attributes: symbol, timeframe, provider
  │
  ▼
httpx.post("http://localhost:5001/...") (auto-instrumented)
  │
  ├─ Create child span: "POST http://localhost:5001/..."
  │  └─ Attributes: http.url, http.status_code, ...
  │
  ▼
IB Host Service (separate process)
  │
  ├─ Receive trace context (HTTP headers)
  ├─ Create continuation span: "POST /download_historical_data"
  │  └─ Parent: API's httpx span
  │
  ▼
Response flows back, spans complete
  │
  ▼
BatchSpanProcessor
  │
  ├─ Buffer spans (up to 512 or 5s)
  ├─ Batch export to OTLP endpoint
  │
  ▼
Jaeger (storage + UI)
```

**Key Properties**:
- **Hierarchical**: Child spans nest within parents
- **Distributed**: Spans across services linked by trace_id
- **Async**: Export doesn't block request processing

---

### Log Correlation Flow

```
Logger.info("Training started", extra={...})
  │
  ▼
LoggingInstrumentor (intercepts log record)
  │
  ├─ Get current span context
  ├─ Inject trace_id and span_id into log record
  │
  ▼
Log Record (enriched)
  {
    "message": "Training started",
    "otelTraceID": "abc123...",
    "otelSpanID": "def456...",
    ...
  }
  │
  ▼
Log Handler (stdout, file, Loki)
  │
  ▼
Grafana
  │
  ├─ Query logs by trace_id
  └─ Click "View Trace" → Jump to Jaeger
```

**Bidirectional Navigation**:
- Trace → Logs: Click span → see related logs
- Logs → Trace: Click log → see full trace

---

## Service Integration

### API Container

**Configuration** (ktrdr/api/main.py):

```python
from ktrdr.monitoring.setup import setup_monitoring, instrument_app

# Setup OTEL
setup_monitoring(
    service_name="ktrdr-api",
    otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://jaeger:4317")
)

# Create FastAPI app
app = FastAPI(...)

# Auto-instrument
instrument_app(app)
```

**Environment Variables** (docker-compose.yml):

```yaml
services:
  api:
    environment:
      - OTLP_ENDPOINT=http://jaeger:4317
      - OTEL_SERVICE_NAME=ktrdr-api
      - OTEL_LOG_LEVEL=info
```

---

### IB Host Service

**Configuration** (ib-host-service/main.py):

```python
from ktrdr.monitoring.setup import setup_monitoring, instrument_app

# Setup OTEL
setup_monitoring(
    service_name="ktrdr-ib-host-service",
    otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://jaeger:4317")
)

# Create FastAPI app
app = FastAPI(...)

# Auto-instrument
instrument_app(app)
```

**Key**: Same pattern as API (code reuse)

---

### Training Host Service

**Configuration** (training-host-service/main.py):

```python
from ktrdr.monitoring.setup import setup_monitoring, instrument_app

# Setup OTEL
setup_monitoring(
    service_name="ktrdr-training-host-service",
    otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://jaeger:4317")
)

# Create FastAPI app
app = FastAPI(...)

# Auto-instrument
instrument_app(app)

# Future: PyTorch instrumentation
# from opentelemetry.instrumentation.pytorch import PyTorchInstrumentor
# PyTorchInstrumentor().instrument()
```

---

## Storage & Backends

### Jaeger (Trace Storage + UI)

**Deployment** (docker-compose.yml):

```yaml
services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # UI
      - "4317:4317"    # OTLP gRPC
      - "4318:4318"    # OTLP HTTP
    environment:
      - COLLECTOR_OTLP_ENABLED=true
```

**Features**:
- Trace search by service, operation, tags
- Visual timeline (Gantt chart)
- Service dependency graph
- Trace comparison

**Storage**:
- **Default**: In-memory (ephemeral, lost on restart)
- **Production**: Elasticsearch, Cassandra, Badger (persistent)

---

### Prometheus (Metrics)

**Deployment** (docker-compose.yml):

```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
```

**Configuration** (monitoring/prometheus.yml):

```yaml
scrape_configs:
  - job_name: 'ktrdr-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

**OTEL Integration**:

```python
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider

# Expose /metrics endpoint for Prometheus
reader = PrometheusMetricReader()
provider = MeterProvider(metric_readers=[reader])
metrics.set_meter_provider(provider)
```

---

### Loki (Log Aggregation)

**Deployment** (docker-compose.yml):

```yaml
services:
  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"
    volumes:
      - ./monitoring/loki-config.yaml:/etc/loki/loki-config.yaml
```

**Log Shipping** (from services):

**Option 1**: Docker log driver (automatic)

```yaml
services:
  api:
    logging:
      driver: loki
      options:
        loki-url: "http://loki:3100/loki/api/v1/push"
        labels: "service=ktrdr-api"
```

**Option 2**: OTEL Collector (recommended)

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
      http:

exporters:
  loki:
    endpoint: http://loki:3100/loki/api/v1/push

service:
  pipelines:
    logs:
      receivers: [otlp]
      exporters: [loki]
```

---

### Grafana (Unified UI)

**Deployment** (docker-compose.yml):

```yaml
services:
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
    volumes:
      - ./monitoring/grafana/datasources.yml:/etc/grafana/provisioning/datasources/datasources.yml
      - ./monitoring/grafana/dashboards.yml:/etc/grafana/provisioning/dashboards/dashboards.yml
```

**Datasources** (monitoring/grafana/datasources.yml):

```yaml
apiVersion: 1

datasources:
  - name: Jaeger
    type: jaeger
    access: proxy
    url: http://jaeger:16686

  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
```

**Features**:
- View traces from Jaeger datasource
- View logs from Loki datasource
- Click trace ID in logs → jump to trace
- Click "View Logs" in trace → filter logs by trace_id

---

## Trace Context Propagation

### How Distributed Tracing Works

**Problem**: How does IB host service know to continue the trace from API?

**Solution**: **Trace context propagation** via HTTP headers

### W3C Trace Context Standard

**Headers**:
- `traceparent`: `00-{trace_id}-{span_id}-{flags}`
- `tracestate`: Vendor-specific data (optional)

**Example**:

```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
             │   │                                │                │
             │   └─ trace_id (128-bit)           └─ span_id       └─ sampled
             └─ version
```

### Auto-Propagation

**httpx instrumentation automatically**:
1. Gets current span context
2. Serializes to `traceparent` header
3. Adds header to outgoing request

**Receiving service automatically**:
1. Extracts `traceparent` header
2. Deserializes to span context
3. Creates child span with extracted context as parent

**Code** (happens automatically):

```python
# API service (sending)
async with httpx.AsyncClient() as client:
    response = await client.post("http://localhost:5001/download")
    # httpx instrumentation adds traceparent header automatically

# IB host service (receiving)
@app.post("/download")
async def download_data(request: Request):
    # FastAPI instrumentation extracts traceparent automatically
    # Creates span with API's span as parent
    ...
```

**Validation**: Check with curl:

```bash
curl -v http://localhost:8000/api/v1/data/load \
  -H "traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
```

Response should include same trace_id in logs/traces.

---

## Structured Logging Architecture

### Standard Fields

**Define standard fields** for consistent querying:

```python
# ktrdr/monitoring/logging_fields.py
from dataclasses import dataclass

@dataclass
class OperationLogFields:
    """Standard fields for operation logs."""
    operation_id: str
    operation_type: str
    status: str  # started, in_progress, completed, failed

@dataclass
class DataLogFields:
    """Standard fields for data-related logs."""
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    provider: str  # ib_host_service, local

@dataclass
class TrainingLogFields:
    """Standard fields for training logs."""
    model_id: str
    strategy: str
    symbol: str
    epochs: int
    batch_size: int
```

### Logging Helper

```python
# ktrdr/monitoring/logging_helpers.py
from typing import Any

def log_operation_start(logger, operation_id: str, operation_type: str, **context):
    """Standard log for operation start."""
    logger.info(
        "Operation started",
        extra={
            "operation_id": operation_id,
            "operation_type": operation_type,
            "status": "started",
            **context
        }
    )

def log_operation_complete(logger, operation_id: str, duration_ms: float, **context):
    """Standard log for operation completion."""
    logger.info(
        "Operation completed",
        extra={
            "operation_id": operation_id,
            "status": "completed",
            "duration_ms": duration_ms,
            **context
        }
    )
```

**Usage**:

```python
from ktrdr.monitoring.logging_helpers import log_operation_start, log_operation_complete

async def download_data(symbol: str, timeframe: str):
    operation_id = create_operation()

    log_operation_start(
        logger,
        operation_id=operation_id,
        operation_type="data_download",
        symbol=symbol,
        timeframe=timeframe
    )

    start = time.time()
    result = await _do_download()
    duration_ms = (time.time() - start) * 1000

    log_operation_complete(
        logger,
        operation_id=operation_id,
        duration_ms=duration_ms,
        bars_downloaded=len(result)
    )
```

---

## Performance & Overhead

### Overhead Measurements

**Instrumentation Overhead** (per operation):

| Component | Overhead | Notes |
|-----------|----------|-------|
| FastAPI auto-instrumentation | <1ms | Per request |
| httpx auto-instrumentation | <1ms | Per HTTP call |
| Logging instrumentation | <0.1ms | Per log statement |
| Custom span creation | <0.5ms | Per span |
| BatchSpanProcessor | <0.1ms | Async, batched export |

**Total Overhead**: <5ms per request (negligible for KTRDR operations lasting seconds to minutes)

### Optimization Strategies

#### 1. Batch Processing

**BatchSpanProcessor** (default):
- Buffers spans in memory
- Exports in batches every 5s or 512 spans
- Async export (doesn't block requests)

#### 2. Sampling

**For High-Volume Services** (not needed for KTRDR):

```python
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

# Sample 10% of traces
sampler = TraceIdRatioBased(0.1)

provider = TracerProvider(sampler=sampler)
```

**KTRDR**: Use 100% sampling (operations are low-volume, high-value)

#### 3. Attribute Limits

**Prevent unbounded span attributes**:

```python
from opentelemetry.sdk.trace import SpanLimits

limits = SpanLimits(
    max_attributes=128,
    max_events=128,
    max_links=128,
    max_attribute_length=1024
)

provider = TracerProvider(span_limits=limits)
```

---

## Security Considerations

### Sensitive Data

**Problem**: Avoid leaking secrets in traces/logs

**Solutions**:

1. **Attribute Filtering**: Don't log passwords, API keys, tokens

```python
# Bad
span.set_attribute("api_key", api_key)

# Good
span.set_attribute("api_key_present", bool(api_key))
```

2. **Log Scrubbing**: Filter sensitive patterns

```python
import re

def scrub_sensitive_data(log_message: str) -> str:
    # Scrub API keys
    log_message = re.sub(r'api_key=\w+', 'api_key=***', log_message)
    # Scrub passwords
    log_message = re.sub(r'password=\S+', 'password=***', log_message)
    return log_message
```

3. **OTEL Collector Processing**: Centralized filtering

```yaml
# otel-collector-config.yaml
processors:
  attributes:
    actions:
      - key: http.request.header.authorization
        action: delete
      - key: password
        action: delete
```

### Network Security

**Production Deployment**:

1. **TLS for OTLP**: Encrypt trace data in transit

```python
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

exporter = OTLPSpanExporter(
    endpoint="https://jaeger:4317",
    credentials=ChannelCredentials(root_certificates)
)
```

2. **Jaeger Access Control**: Restrict UI access

```yaml
services:
  jaeger:
    environment:
      - JAEGER_AUTH_TYPE=basic
      - JAEGER_AUTH_USERNAME=admin
      - JAEGER_AUTH_PASSWORD=${JAEGER_PASSWORD}
```

3. **Private Network**: Keep telemetry backends internal (no public access)

---

## Summary

This architecture provides **comprehensive observability** for KTRDR with:

1. **Auto-Instrumentation**: 90% coverage with 3 lines of code
2. **Distributed Tracing**: Full visibility across API + host services
3. **Structured Logging**: Machine-readable logs with automatic trace correlation
4. **Low Overhead**: <5ms per operation, async export
5. **Incremental Adoption**: Start simple (console), add infrastructure as needed

**Key Architectural Principles**:
- **LLM-Friendly**: Structured JSON enables AI-assisted debugging
- **Service-Communication-First**: Designed for distributed debugging (connection failures, routing issues)
- **Developer Experience**: Easy local development with Jaeger UI
- **Production-Ready**: Scalable backends (Jaeger, Prometheus, Loki)

For implementation steps, see **DESIGN.md** (Phase 1-6).

For getting started, see **IMPLEMENTATION.md** (future).

---

**Document End**
