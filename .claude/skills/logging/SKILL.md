---
name: logging
description: Use when working on logging configuration, structured logging, log context enrichment, OpenTelemetry tracing setup, or monitoring integration.
---

# Logging & Monitoring Setup

**When this skill is loaded, announce it to the user by outputting:**
`🛠️✅ SKILL logging loaded!`

Load this skill when working on:

- Logging configuration and initialization
- Structured logging (structlog)
- Log context enrichment
- OpenTelemetry tracing/metrics setup
- Helper decorators for logging patterns

---

## Key Files

### Logging

| File | Purpose |
|------|---------|
| `ktrdr/logging/config.py` | Centralized logging setup + rotation |
| `ktrdr/logging/context.py` | LogContext stack + ContextEnricher |
| `ktrdr/logging/helpers.py` | Logging decorator patterns |

### Monitoring / Observability

| File | Purpose |
|------|---------|
| `ktrdr/monitoring/setup.py` | OpenTelemetry tracing + metrics init |
| `ktrdr/monitoring/logging_helpers.py` | Operation-level structured logging |
| `ktrdr/monitoring/logging_fields.py` | Structured log field definitions |

---

## Logging Setup

**Frameworks:** Python `logging` + `structlog` (JSON structured output)

```python
from ktrdr.logging.config import configure_logging, get_logger

configure_logging()          # Initialize (console + rotating file)
logger = get_logger("my_module")
logger.info("message", extra={"key": "value"})
```

### Features

- **Console output:** Color-coded ANSI (blue=DEBUG, green=INFO, yellow=WARNING, red=ERROR)
- **File rotation:** SafeRotatingFileHandler with race-condition handling
- **Component-specific levels:** Per-module overrides (e.g., `"ib.connection"` → WARNING)
- **Debug mode:** `set_debug_mode()` / `is_debug_mode()` global toggle

---

## Context Enrichment

```python
from ktrdr.logging.context import LogContext, with_context

# Push context for a block of code
with with_context(LogContext(operation_id="op_123", module="training")):
    logger.info("Starting training")
    # All logs in this block automatically include operation_id and module
```

**LogContext fields:** `operation_id`, `user`, `module`, `function`, `extra: dict`

`ContextEnricher` is a logging filter that reads the context stack and adds fields to every log record.

---

## Helper Decorators

```python
from ktrdr.logging.helpers import log_entry_exit, log_performance, log_data_operation, log_error

@log_entry_exit()           # Logs function entry and exit
@log_performance()          # Logs execution time
@log_data_operation()       # Logs data operation lifecycle
@log_error()                # Logs exceptions with context
def my_function():
    pass
```

---

## OpenTelemetry Integration

**Location:** `ktrdr/monitoring/setup.py`

```python
from ktrdr.monitoring.setup import setup_telemetry

setup_telemetry(service_name="ktrdr-backend", service_version="1.0")
```

### Components

- **TracerProvider** — Distributed tracing (spans)
- **MeterProvider** — Metrics collection
- **Jaeger export** — OTLP gRPC (async batch processor)
- **Prometheus** — Metrics endpoint
- **Auto-instrumentation:** FastAPI + HTTPx

### Environment Variables

```bash
OTLP_ENDPOINT=http://localhost:4317     # Jaeger OTLP endpoint
OTEL_SERVICE_NAME=ktrdr-backend
LOG_LEVEL=INFO
```

---

## Gotchas

### Use get_logger(), not logging.getLogger()

`get_logger()` returns a logger with the correct module hierarchy and applies component-specific level overrides.

### Context is thread-local

LogContext uses a thread-local stack. Async code needs careful handling — context won't automatically propagate across await boundaries without explicit management.

### Structured logging produces JSON in production

Console output is human-readable with colors. In production/Docker, logs are JSON-structured for log aggregation tools.
