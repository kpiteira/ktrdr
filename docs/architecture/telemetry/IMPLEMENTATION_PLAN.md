# Observability & Telemetry Implementation Plan

**Version**: 1.0
**Status**: 🎯 Ready for Implementation
**Date**: 2025-11-10
**Phases Covered**: 1-6 (Complete Observability Stack)

---

## 📋 Plan Navigation

- **This Document**: Complete implementation plan for OTEL-based observability
- **Design**: [DESIGN.md](DESIGN.md) - High-level design rationale
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md) - Technical specifications
- **Quick Start**: [README.md](README.md) - Getting started guide

---

## Overview

This implementation plan uses **Test-Driven Development** with **incremental adoption**. Each phase delivers working, testable observability features with **zero business logic disruption**.

**Quality Gates** (every phase):

- Write instrumentation tests
- Pass ALL unit tests: `make test-unit`
- Pass quality checks: `make quality`
- Validate traces in Jaeger UI
- Result in ONE commit per phase

**Incremental Approach**: Start simple (console traces), prove value, then invest in infrastructure.

All work will be done on a single feature branch: `feature/otel-observability`

---

## Phase Structure

- **Phase**: A complete **vertical slice** delivering end-to-end observability functionality
- **Task**: A single, testable unit of work building toward the phase goal
- **Key**: Each phase ends with something you can **actually see and use** (traces, logs, metrics)

---

## Phase 1: Console Traces (Foundation)

**Goal**: Get basic OTEL tracing working with console output - zero infrastructure required

**Why This First**: Validates that auto-instrumentation works without investing in Jaeger/infrastructure. You see traces immediately!

**End State**:
- OTEL SDK installed and configured
- FastAPI, httpx, logging auto-instrumented
- Traces printed to stdout in JSON format
- **TESTABLE**: Run API server, make request, see trace in console

**Effort**: ~2 hours

---

### Task 1.1: Add OTEL Dependencies

**Objective**: Install OpenTelemetry packages

**TDD Approach**: Verify imports work

**Implementation**:

1. Add to `pyproject.toml`:

```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "opentelemetry-api>=1.21.0",
    "opentelemetry-sdk>=1.21.0",
    "opentelemetry-instrumentation-fastapi>=0.42b0",
    "opentelemetry-instrumentation-httpx>=0.42b0",
    "opentelemetry-instrumentation-logging>=0.42b0",
    "opentelemetry-exporter-otlp>=1.21.0",
]
```

2. Install dependencies:

```bash
uv sync
```

**Validation**:

```bash
uv run python -c "from opentelemetry import trace; print('✅ OTEL installed')"
```

**Quality Gate**: All existing tests pass

**Commit**: `feat(telemetry): add OpenTelemetry dependencies`

---

### Task 1.2: Create Monitoring Setup Module

**Objective**: Create reusable OTEL configuration module

**TDD Approach**: Write unit tests for setup functions

**Implementation**:

1. Create `ktrdr/monitoring/__init__.py`:

```python
"""Observability and telemetry infrastructure."""
```

2. Create `ktrdr/monitoring/setup.py`:

```python
"""OpenTelemetry setup and configuration."""

import os
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    BatchSpanProcessor,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

logger = logging.getLogger(__name__)


def setup_monitoring(
    service_name: str,
    otlp_endpoint: str | None = None,
    console_output: bool = False,
) -> TracerProvider:
    """
    Setup OpenTelemetry tracing for a service.

    Args:
        service_name: Name of the service (e.g., "ktrdr-api", "ktrdr-training-worker")
        otlp_endpoint: OTLP gRPC endpoint (e.g., "http://jaeger:4317"). If None, console only.
        console_output: If True, also print traces to console (for debugging)

    Returns:
        TracerProvider instance
    """
    # Create resource with service identification
    resource = Resource.create({
        "service.name": service_name,
        "service.version": os.getenv("APP_VERSION", "dev"),
        "deployment.environment": os.getenv("ENVIRONMENT", "development"),
    })

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add console exporter for development
    if console_output or otlp_endpoint is None:
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(console_exporter))
        logger.info(f"✅ Console trace export enabled for {service_name}")

    # Add OTLP exporter if endpoint provided
    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=True  # Use TLS in production
        )
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        logger.info(f"✅ OTLP trace export enabled for {service_name} → {otlp_endpoint}")

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    return provider


def instrument_app(app):
    """
    Auto-instrument FastAPI app with OpenTelemetry.

    Args:
        app: FastAPI application instance
    """
    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)
    logger.info("✅ FastAPI auto-instrumentation enabled")

    # Instrument httpx (global)
    HTTPXClientInstrumentor().instrument()
    logger.info("✅ httpx auto-instrumentation enabled")

    # Instrument logging
    LoggingInstrumentor().instrument(set_logging_format=True)
    logger.info("✅ Logging auto-instrumentation enabled")
```

3. Create `tests/unit/monitoring/__init__.py`

4. Create `tests/unit/monitoring/test_setup.py`:

```python
"""Tests for OpenTelemetry setup."""

import pytest
from unittest.mock import MagicMock, patch
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from ktrdr.monitoring.setup import setup_monitoring, instrument_app


def test_setup_monitoring_console_only():
    """Test setup with console output only."""
    provider = setup_monitoring(
        service_name="test-service",
        console_output=True
    )

    assert isinstance(provider, TracerProvider)
    assert trace.get_tracer_provider() == provider


def test_setup_monitoring_with_otlp():
    """Test setup with OTLP endpoint."""
    with patch('ktrdr.monitoring.setup.OTLPSpanExporter') as mock_exporter:
        provider = setup_monitoring(
            service_name="test-service",
            otlp_endpoint="http://jaeger:4317"
        )

        assert isinstance(provider, TracerProvider)
        mock_exporter.assert_called_once()


def test_instrument_app():
    """Test FastAPI app instrumentation."""
    mock_app = MagicMock()

    with patch('ktrdr.monitoring.setup.FastAPIInstrumentor'), \
         patch('ktrdr.monitoring.setup.HTTPXClientInstrumentor'), \
         patch('ktrdr.monitoring.setup.LoggingInstrumentor'):

        instrument_app(mock_app)
        # Should not raise


def test_setup_monitoring_includes_service_name():
    """Test that service name is included in resource."""
    provider = setup_monitoring(
        service_name="my-test-service",
        console_output=True
    )

    resource = provider.resource
    assert resource.attributes.get("service.name") == "my-test-service"
```

**Validation**:

```bash
make test-unit
# Tests pass ✅
```

**Quality Gate**: All tests pass, no linting errors

**Commit**: `feat(telemetry): create OTEL monitoring setup module`

---

### Task 1.3: Instrument API Backend

**Objective**: Add OTEL instrumentation to main API

**TDD Approach**: Integration test to verify traces are created

**Implementation**:

1. Update `ktrdr/api/main.py`:

```python
# ... existing imports ...
from ktrdr.monitoring.setup import setup_monitoring, instrument_app
import os

# Setup monitoring BEFORE creating app
setup_monitoring(
    service_name="ktrdr-api",
    otlp_endpoint=os.getenv("OTLP_ENDPOINT"),  # None for Phase 1
    console_output=True  # Enable console traces for Phase 1
)

# Create FastAPI app
app = FastAPI(
    title="KTRDR API",
    # ... existing config ...
)

# Auto-instrument the app
instrument_app(app)

# ... rest of existing code ...
```

2. Create `tests/integration/test_api_tracing.py`:

```python
"""Integration tests for API tracing."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from opentelemetry import trace

from ktrdr.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_api_request_creates_trace(client):
    """Test that API requests create traces."""
    # Make request
    response = client.get("/health")

    # Should succeed
    assert response.status_code == 200

    # Trace should be active
    tracer = trace.get_tracer(__name__)
    assert tracer is not None


def test_api_request_with_trace_context(client):
    """Test that trace context is propagated."""
    # Make request with trace headers
    response = client.get(
        "/health",
        headers={
            "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        }
    )

    assert response.status_code == 200
```

**Validation**:

```bash
# Start API server
uv run python scripts/run_api_server.py

# In another terminal, make request
curl http://localhost:8000/health

# Check server logs - should see JSON traces printed!
```

**Quality Gate**:
- Tests pass
- Traces visible in console output
- No business logic changes

**Commit**: `feat(telemetry): instrument API backend with OTEL`

---

### Task 1.4: Test End-to-End Tracing

**Objective**: Verify complete trace from CLI → API

**TDD Approach**: Manual testing with real requests

**Implementation**:

1. Test data acquisition:

```bash
# Start API
uv run python scripts/run_api_server.py

# Make data request (generates trace)
ktrdr data show AAPL 1d --limit 5

# Check logs - should see trace with:
# - Root span: GET /api/v1/data/{symbol}/{timeframe}
# - HTTP attributes (method, path, status)
# - Timing information
```

2. Document example trace output in `docs/architecture/telemetry/examples/phase1-console-trace.json`:

```json
{
  "name": "GET /api/v1/data/{symbol}/{timeframe}",
  "context": {
    "trace_id": "0xabc123...",
    "span_id": "0xdef456...",
    "trace_state": "[]"
  },
  "kind": "SpanKind.SERVER",
  "parent_id": null,
  "start_time": "2025-11-10T10:00:00.000000Z",
  "end_time": "2025-11-10T10:00:01.234567Z",
  "status": {
    "status_code": "OK"
  },
  "attributes": {
    "http.method": "GET",
    "http.route": "/api/v1/data/{symbol}/{timeframe}",
    "http.status_code": 200,
    "http.url": "http://localhost:8000/api/v1/data/AAPL/1d"
  }
}
```

**Validation**:
- ✅ Traces appear in console
- ✅ Trace IDs are valid
- ✅ HTTP attributes captured
- ✅ No performance degradation

**Quality Gate**: All functionality works as before + traces visible

**Commit**: `docs(telemetry): add Phase 1 example traces`

---

## Phase 2: Jaeger UI

**Goal**: Visual trace exploration with Jaeger

**Why This Next**: Seeing traces in a UI is way better than JSON logs. Minimal infrastructure (one container).

**End State**:
- Jaeger running in Docker
- API sending traces to Jaeger
- Beautiful trace timeline in browser at http://localhost:16686
- **TESTABLE**: Make API request, open Jaeger UI, see trace

**Effort**: ~1 hour

---

### Task 2.1: Add Jaeger to Docker Compose

**Objective**: Run Jaeger alongside API

**TDD Approach**: Manual validation (infrastructure)

**Implementation**:

1. Update `docker/docker-compose.yml`:

```yaml
services:
  # ... existing services ...

  jaeger:
    image: jaegertracing/all-in-one:latest
    container_name: ktrdr-jaeger
    ports:
      - "16686:16686"  # Jaeger UI
      - "4317:4317"    # OTLP gRPC
      - "4318:4318"    # OTLP HTTP
    environment:
      - COLLECTOR_OTLP_ENABLED=true
      - LOG_LEVEL=info
    networks:
      - ktrdr-network
    restart: unless-stopped

  backend:
    # ... existing config ...
    environment:
      # Add OTLP endpoint
      - OTLP_ENDPOINT=http://jaeger:4317
      # ... other env vars ...
    depends_on:
      - jaeger
```

2. Update `docker_dev.sh` to mention Jaeger:

```bash
# Add to help text
echo "  Jaeger UI:     http://localhost:16686"
```

**Validation**:

```bash
docker-compose up jaeger
# Visit http://localhost:16686
# Should see Jaeger UI
```

**Quality Gate**: Jaeger starts successfully

**Commit**: `feat(telemetry): add Jaeger to Docker Compose`

---

### Task 2.2: Configure OTLP Export

**Objective**: Send traces from API to Jaeger

**TDD Approach**: Integration test with Jaeger

**Implementation**:

1. Update `.env.example`:

```bash
# Observability
OTLP_ENDPOINT=http://jaeger:4317  # For production
# OTLP_ENDPOINT=http://localhost:4317  # For local development
```

2. Update `README.md` with Jaeger usage:

```markdown
## Observability

KTRDR uses OpenTelemetry for distributed tracing.

### Viewing Traces

1. Start services:
   ```bash
   docker-compose up -d
   ```

2. Make some requests:
   ```bash
   ktrdr data load AAPL 1d
   ```

3. Open Jaeger UI:
   ```
   http://localhost:16686
   ```

4. Select "ktrdr-api" service and click "Find Traces"
```

**Validation**:

```bash
# Start everything
docker-compose up -d

# Make request
curl http://localhost:8000/health

# Open Jaeger UI
open http://localhost:16686

# Should see:
# 1. Service dropdown contains "ktrdr-api"
# 2. Traces appear in search results
# 3. Clicking trace shows timeline
```

**Quality Gate**: Traces visible in Jaeger UI

**Commit**: `feat(telemetry): configure OTLP export to Jaeger`

---

### Task 2.3: Create Trace Validation Script

**Objective**: Automated way to verify tracing works

**TDD Approach**: Script that checks Jaeger API

**Implementation**:

1. Create `scripts/validate_tracing.sh`:

```bash
#!/bin/bash
# Validate that tracing is working correctly

set -e

echo "🔍 Validating OpenTelemetry tracing..."

# Check if Jaeger is running
if ! curl -s http://localhost:16686/api/services > /dev/null; then
    echo "❌ Jaeger is not running at localhost:16686"
    exit 1
fi

echo "✅ Jaeger is running"

# Make test request
echo "Making test request to API..."
curl -s http://localhost:8000/health > /dev/null

# Wait for trace to be exported
sleep 2

# Check if traces exist
TRACES=$(curl -s "http://localhost:16686/api/traces?service=ktrdr-api&limit=1")

if echo "$TRACES" | grep -q "ktrdr-api"; then
    echo "✅ Traces found in Jaeger for ktrdr-api service"
    echo "🎉 OpenTelemetry tracing is working!"
    exit 0
else
    echo "❌ No traces found in Jaeger"
    exit 1
fi
```

2. Make executable:

```bash
chmod +x scripts/validate_tracing.sh
```

**Validation**:

```bash
./scripts/validate_tracing.sh
# Should output: 🎉 OpenTelemetry tracing is working!
```

**Quality Gate**: Script passes

**Commit**: `feat(telemetry): add tracing validation script`

---

## Phase 3: Workers and Host Services

**Goal**: End-to-end tracing across backend → workers → host services

**Why This Next**: Now we can see distributed traces across our entire system architecture

**End State**:
- IB host service instrumented
- Training workers instrumented
- Backtesting workers instrumented
- Single trace spans all services
- **TESTABLE**: Submit training job, see trace across backend → worker

**Effort**: ~3 hours

---

### Task 3.1: Instrument IB Host Service

**Objective**: Add OTEL to IB host service

**Implementation**:

1. Update `ib-host-service/main.py`:

```python
# ... existing imports ...
from ktrdr.monitoring.setup import setup_monitoring, instrument_app
import os

# Setup monitoring
setup_monitoring(
    service_name="ktrdr-ib-host-service",
    otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://localhost:4317"),
    console_output=os.getenv("ENVIRONMENT") == "development"
)

# Create app
app = FastAPI(...)

# Auto-instrument
instrument_app(app)

# ... rest of code ...
```

2. Update `ib-host-service/start.sh`:

```bash
#!/bin/bash
# Add OTLP endpoint
export OTLP_ENDPOINT=${OTLP_ENDPOINT:-"http://localhost:4317"}
export ENVIRONMENT=${ENVIRONMENT:-"development"}

# ... rest of script ...
```

**Validation**:

```bash
cd ib-host-service
./start.sh

# Make request
curl http://localhost:5001/health

# Check Jaeger - should see "ktrdr-ib-host-service"
```

**Commit**: `feat(telemetry): instrument IB host service`

---

### Task 3.2: Instrument Training Workers

**Objective**: Add OTEL to training workers

**Implementation**:

1. Update `ktrdr/training/training_worker.py`:

```python
# At module level, before WorkerAPIBase
from ktrdr.monitoring.setup import setup_monitoring
import os

# Setup monitoring for this worker
worker_id = os.getenv("WORKER_ID", "unknown")
setup_monitoring(
    service_name=f"ktrdr-training-worker-{worker_id}",
    otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://localhost:4317"),
    console_output=os.getenv("ENVIRONMENT") == "development"
)

# ... rest of implementation using WorkerAPIBase ...
```

2. Update worker startup to pass WORKER_ID:

```python
# In worker startup script
import uuid

worker_id = os.getenv("WORKER_ID") or str(uuid.uuid4())[:8]
os.environ["WORKER_ID"] = worker_id
```

3. Add worker-specific span attributes:

```python
from opentelemetry import trace

class TrainingWorker:
    def __init__(self):
        self.tracer = trace.get_tracer(__name__)
        # ... existing init ...

    async def train(self, request: TrainingRequest):
        """Execute training with tracing."""
        with self.tracer.start_as_current_span("worker.train") as span:
            # Add worker attributes
            span.set_attribute("worker.id", worker_id)
            span.set_attribute("worker.type", "training")
            span.set_attribute("worker.capabilities", ["gpu", "cpu"])
            span.set_attribute("training.symbol", request.symbol)
            span.set_attribute("training.strategy", request.strategy)

            # Execute training
            result = await self._execute_training(request)

            span.set_attribute("training.epochs_completed", result.epochs)
            span.set_attribute("training.final_loss", result.final_loss)

            return result
```

**Validation**:

```bash
# Start training worker
# Submit training job
# Check Jaeger - should see "ktrdr-training-worker-{id}" with attributes
```

**Commit**: `feat(telemetry): instrument training workers`

---

### Task 3.3: Instrument Backtesting Workers

**Objective**: Add OTEL to backtesting workers

**Implementation**:

Similar to training workers, update `ktrdr/backtesting/backtest_worker.py`:

```python
# Setup monitoring
worker_id = os.getenv("WORKER_ID", "unknown")
setup_monitoring(
    service_name=f"ktrdr-backtest-worker-{worker_id}",
    otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://localhost:4317")
)

# Add span attributes in execution
class BacktestWorker:
    async def run_backtest(self, request: BacktestRequest):
        with self.tracer.start_as_current_span("worker.backtest") as span:
            span.set_attribute("worker.id", worker_id)
            span.set_attribute("worker.type", "backtesting")
            span.set_attribute("worker.capabilities", ["cpu"])
            span.set_attribute("backtest.symbol", request.symbol)
            span.set_attribute("backtest.strategy", request.strategy)

            result = await self._execute_backtest(request)
            return result
```

**Validation**: Similar to training workers

**Commit**: `feat(telemetry): instrument backtesting workers`

---

### Task 3.4: Test Distributed Tracing

**Objective**: Verify traces span entire system

**Implementation**:

1. Create test script `scripts/test_distributed_trace.sh`:

```bash
#!/bin/bash
# Test end-to-end distributed tracing

echo "🧪 Testing distributed tracing..."

# Start training job
echo "Submitting training job..."
OPERATION_ID=$(ktrdr models train --symbol AAPL --strategy momentum --epochs 1 | grep "Operation ID" | cut -d: -f2 | tr -d ' ')

echo "Operation ID: $OPERATION_ID"

# Wait for completion
echo "Waiting for operation to complete..."
sleep 10

# Open Jaeger with operation ID
echo "✅ Check Jaeger for trace with operation_id=$OPERATION_ID"
echo "   URL: http://localhost:16686/search?service=ktrdr-api&tags=%7B%22operation_id%22%3A%22$OPERATION_ID%22%7D"
```

2. Validate trace shows:
   - CLI → Backend API call
   - Backend → Worker Registry (select worker)
   - Backend → Worker (dispatch training)
   - Worker → Training execution
   - All linked by trace_id

**Validation**: Trace timeline shows full flow

**Commit**: `test(telemetry): add distributed tracing validation`

---

## Phase 3.5: CLI and MCP Server

**Goal**: Complete user-to-worker visibility

**Why This Next**: Most valuable for end-users - see traces from their commands

**End State**:
- CLI commands create root spans
- MCP server requests traced
- Complete trace: User command → Worker → Result
- **TESTABLE**: Run `ktrdr train ...`, see trace from CLI to worker

**Effort**: ~2 hours

---

### Task 3.5.1: Instrument CLI

**Objective**: CLI commands create traces

**Implementation**:

1. Update `ktrdr/cli/main.py`:

```python
from ktrdr.monitoring.setup import setup_monitoring
from opentelemetry import trace
import os

# Setup CLI tracing
setup_monitoring(
    service_name="ktrdr-cli",
    otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://localhost:4317"),
    console_output=False  # CLI shouldn't spam traces
)

# Get tracer
tracer = trace.get_tracer(__name__)

# ... existing CLI setup ...
```

2. Add tracing to commands:

```python
@app.command()
def train(
    symbol: str,
    strategy: str,
    # ... other args ...
):
    """Start training operation."""
    with tracer.start_as_current_span("cli.train") as span:
        # Add CLI attributes
        span.set_attribute("cli.command", "train")
        span.set_attribute("cli.symbol", symbol)
        span.set_attribute("cli.strategy", strategy)

        try:
            # Execute command
            result = asyncio.run(train_model(symbol, strategy))

            span.set_attribute("cli.status", "success")
            span.set_attribute("cli.operation_id", result.operation_id)

            console.print(f"✅ Training started: {result.operation_id}")

        except Exception as e:
            span.set_attribute("cli.status", "error")
            span.set_attribute("cli.error", str(e))
            span.record_exception(e)
            raise
```

3. Update `ktrdr/cli/helpers/async_cli_client.py` to propagate trace context:

```python
# httpx already auto-instrumented, so trace context propagates automatically!
# No changes needed - just ensure HTTPXClientInstrumentor is active
```

**Validation**:

```bash
# Run CLI command
ktrdr train AAPL momentum

# Check Jaeger - should see:
# - Root span: cli.train (from ktrdr-cli service)
# - Child span: POST /api/v1/training/start (from ktrdr-api service)
# - Child span: worker.train (from ktrdr-training-worker service)
```

**Commit**: `feat(telemetry): instrument CLI commands`

---

### Task 3.5.2: Instrument MCP Server (If Applicable)

**Objective**: MCP tool calls create traces

**Implementation**:

1. Update MCP server entry point:

```python
from ktrdr.monitoring.setup import setup_monitoring, instrument_app

setup_monitoring(
    service_name="ktrdr-mcp-server",
    otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://localhost:4317")
)

app = FastAPI(...)
instrument_app(app)
```

2. Add span attributes to MCP tool handlers:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

@app.post("/tools/{tool_name}")
async def execute_tool(tool_name: str, params: dict):
    """Execute MCP tool with tracing."""
    with tracer.start_as_current_span("mcp.tool.execute") as span:
        span.set_attribute("mcp.tool", tool_name)
        span.set_attribute("mcp.params", json.dumps(params))

        result = await tool_executor.execute(tool_name, params)

        span.set_attribute("mcp.result.status", "success")
        return result
```

**Validation**: Test with LLM agent, check Jaeger

**Commit**: `feat(telemetry): instrument MCP server`

---

## Phase 4: Structured Logging

**Goal**: Migrate to structured logging with automatic trace correlation

**Why This Next**: Makes logs searchable and correlatable with traces

**End State**:
- ServiceOrchestrator uses structured logging
- Standard log fields defined
- Logs include trace IDs automatically
- **TESTABLE**: See logs with trace IDs in console

**Effort**: ~4 hours

---

### Task 4.1: Define Standard Log Fields

**Objective**: Create standard logging patterns

**Implementation**:

1. Create `ktrdr/monitoring/logging_fields.py`:

```python
"""Standard logging fields for structured logs."""

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class BaseLogFields:
    """Base fields for all logs."""

    def to_extra(self) -> dict[str, Any]:
        """Convert to extra dict for logging."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class OperationLogFields(BaseLogFields):
    """Standard fields for operation logs."""
    operation_id: str
    operation_type: str
    status: str | None = None


@dataclass
class DataLogFields(BaseLogFields):
    """Standard fields for data-related logs."""
    symbol: str
    timeframe: str
    provider: str | None = None
    start_date: str | None = None
    end_date: str | None = None


@dataclass
class TrainingLogFields(BaseLogFields):
    """Standard fields for training logs."""
    model_id: str | None = None
    strategy: str
    symbol: str
    epochs: int | None = None
    batch_size: int | None = None
```

2. Create `ktrdr/monitoring/logging_helpers.py`:

```python
"""Logging helper functions."""

import logging
from typing import Any

from ktrdr.monitoring.logging_fields import OperationLogFields


def log_operation_start(
    logger: logging.Logger,
    operation_id: str,
    operation_type: str,
    **context: Any
):
    """Log operation start with standard fields."""
    fields = OperationLogFields(
        operation_id=operation_id,
        operation_type=operation_type,
        status="started"
    )

    logger.info(
        "Operation started",
        extra={**fields.to_extra(), **context}
    )


def log_operation_complete(
    logger: logging.Logger,
    operation_id: str,
    duration_ms: float,
    **context: Any
):
    """Log operation completion with standard fields."""
    logger.info(
        "Operation completed",
        extra={
            "operation_id": operation_id,
            "status": "completed",
            "duration_ms": duration_ms,
            **context
        }
    )


def log_operation_error(
    logger: logging.Logger,
    operation_id: str,
    error: Exception,
    **context: Any
):
    """Log operation error with standard fields."""
    logger.error(
        "Operation failed",
        extra={
            "operation_id": operation_id,
            "status": "failed",
            "error_type": type(error).__name__,
            "error_message": str(error),
            **context
        },
        exc_info=True
    )
```

**Commit**: `feat(telemetry): add structured logging fields and helpers`

---

### Task 4.2: Update ServiceOrchestrator

**Objective**: Migrate ServiceOrchestrator to structured logging

**Implementation**:

1. Update `ktrdr/async_infrastructure/service_orchestrator.py`:

```python
from ktrdr.monitoring.logging_helpers import (
    log_operation_start,
    log_operation_complete,
    log_operation_error
)

class ServiceOrchestrator:
    async def start_operation(self, operation_type: OperationType, context: dict):
        """Start operation with structured logging."""
        operation_id = create_operation_id()

        # Structured log
        log_operation_start(
            self.logger,
            operation_id=operation_id,
            operation_type=operation_type.value,
            symbol=context.get("symbol"),
            strategy=context.get("strategy")
        )

        try:
            start_time = time.time()
            result = await self._execute_operation(context)
            duration_ms = (time.time() - start_time) * 1000

            log_operation_complete(
                self.logger,
                operation_id=operation_id,
                duration_ms=duration_ms,
                result_size=len(result) if result else 0
            )

            return result

        except Exception as e:
            log_operation_error(
                self.logger,
                operation_id=operation_id,
                error=e
            )
            raise
```

**Validation**:

```bash
# Run operation
# Check logs - should see JSON with fields:
# {
#   "message": "Operation started",
#   "operation_id": "...",
#   "operation_type": "training",
#   "otelTraceID": "...",  # <-- Automatically added by OTEL!
#   "otelSpanID": "..."
# }
```

**Commit**: `feat(telemetry): migrate ServiceOrchestrator to structured logging`

---

### Task 4.3: Update Other Services

**Objective**: Migrate DataAcquisitionService and TrainingManager

**Implementation**: Similar pattern to ServiceOrchestrator

**Commit**: `feat(telemetry): migrate services to structured logging`

---

## Phase 5: Metrics and Dashboards

**Goal**: Add Prometheus metrics and Grafana dashboards

**End State**:
- Prometheus collecting metrics
- Grafana dashboards showing operation stats
- **TESTABLE**: See metrics in Grafana at http://localhost:3000

**Effort**: ~6 hours

---

### Task 5.1: Add Prometheus

**Objective**: Set up Prometheus metrics collection

**Implementation**:

1. Add to `docker-compose.yml`:

```yaml
prometheus:
  image: prom/prometheus:latest
  container_name: ktrdr-prometheus
  ports:
    - "9090:9090"
  volumes:
    - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    - prometheus_data:/prometheus
  networks:
    - ktrdr-network

volumes:
  prometheus_data:
```

2. Create `monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'ktrdr-api'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics'
```

3. Add Prometheus exporter to API:

```python
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from prometheus_client import make_asgi_app

# Setup Prometheus metrics
reader = PrometheusMetricReader()
provider = MeterProvider(metric_readers=[reader])
metrics.set_meter_provider(provider)

# Add /metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

**Commit**: `feat(telemetry): add Prometheus metrics`

---

### Task 5.2: Add Grafana

**Objective**: Set up Grafana with datasources

**Implementation**:

1. Add to `docker-compose.yml`:

```yaml
grafana:
  image: grafana/grafana:latest
  container_name: ktrdr-grafana
  ports:
    - "3000:3000"
  environment:
    - GF_AUTH_ANONYMOUS_ENABLED=true
    - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
    - GF_DATABASE_TYPE=postgres
    - GF_DATABASE_HOST=postgres:5432
    - GF_DATABASE_NAME=grafana
    - GF_DATABASE_USER=${POSTGRES_USER}
    - GF_DATABASE_PASSWORD=${POSTGRES_PASSWORD}
  volumes:
    - ./monitoring/grafana/datasources.yml:/etc/grafana/provisioning/datasources/datasources.yml
    - ./monitoring/grafana/dashboards.yml:/etc/grafana/provisioning/dashboards/dashboards.yml
    - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards
  depends_on:
    - jaeger
    - prometheus
    - postgres
  networks:
    - ktrdr-network
```

2. Create `monitoring/grafana/datasources.yml`:

```yaml
apiVersion: 1

datasources:
  - name: Jaeger
    type: jaeger
    access: proxy
    url: http://jaeger:16686
    isDefault: false

  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

**Commit**: `feat(telemetry): add Grafana with datasources`

---

### Task 5.3: Create Dashboards

**Objective**: Build Grafana dashboards

**Implementation**:

1. Create `monitoring/grafana/dashboards/operations.json` (Grafana dashboard JSON)

2. Include panels for:
   - Operation duration by type
   - Operation success/failure rate
   - Active operations
   - Worker utilization

**Commit**: `feat(telemetry): add Grafana operation dashboards`

---

## Phase 6: Centralized Aggregation (Production)

**Goal**: Production-ready observability with Loki

**End State**:
- Loki for log aggregation
- Unified Grafana for logs + traces + metrics
- **TESTABLE**: See all telemetry in one place

**Effort**: ~8 hours

---

### Task 6.1: Add Loki

**Implementation**: Add Loki to docker-compose for log aggregation

**Commit**: `feat(telemetry): add Loki for log aggregation`

---

### Task 6.2: Configure Production

**Implementation**: TLS, authentication, retention policies

**Commit**: `feat(telemetry): configure production observability`

---

## Quality Gates Summary

**Every Phase Must Pass**:

1. ✅ All unit tests pass (`make test-unit`)
2. ✅ All quality checks pass (`make quality`)
3. ✅ Manual validation succeeds
4. ✅ No business logic changes
5. ✅ Documentation updated

**Final Acceptance Criteria**:

1. ✅ Traces visible in Jaeger for all services
2. ✅ Logs include trace IDs
3. ✅ Metrics in Prometheus
4. ✅ Dashboards in Grafana
5. ✅ <5% performance overhead
6. ✅ Zero disruption to existing functionality

---

## Rollback Plan

If any phase fails:

1. Revert instrumentation code
2. Keep OTEL dependencies (harmless if not used)
3. Document failure reason
4. Fix issues before retrying

---

## Next Steps

1. Create feature branch: `git checkout -b feature/otel-observability`
2. Start with Phase 1 (console traces)
3. Validate each phase before moving to next
4. Merge when Phase 2 complete (Jaeger working)
5. Phases 3-6 can be done incrementally

---

**Document End**
