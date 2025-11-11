# CLI Span Flushing Issue & Solution

**Issue Discovered**: 2025-11-11
**Status**: 🐛 Known Issue with Solution
**Priority**: Medium (affects trace visibility, not functionality)

## Problem

CLI command decorator spans (e.g., `cli.data_range`) are **not appearing in Jaeger** even though:
- ✅ Decorator code is correct
- ✅ `ktrdr-cli` service is registered in Jaeger
- ✅ httpx auto-instrumentation spans ARE appearing

**Root Cause**: `BatchSpanProcessor` buffers spans for efficiency (flushes every 5s or 512 spans). CLI commands exit before spans are flushed.

## Evidence

```bash
# Jaeger shows these services:
curl http://localhost:16686/api/services
# ["ktrdr-api", "jaeger-all-in-one", "ktrdr-cli"]  ✅ CLI registered!

# But CLI traces only show httpx spans:
curl "http://localhost:16686/api/traces?service=ktrdr-cli"
# Operations: ["POST", "POST /api/v1/data/range", ...]  ❌ No cli.* spans
```

## Solutions

### Option 1: SimpleSpanProcessor for CLI (Quick Fix)
Use `SimpleSpanProcessor` instead of `BatchSpanProcessor` for CLI - flushes immediately:

```python
# ktrdr/cli/__init__.py
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# Change setup_monitoring call:
provider = setup_monitoring(
    service_name="ktrdr-cli",
    otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://localhost:4317"),
    console_output=False,
    use_simple_processor=True,  # Add this parameter
)
```

**Pros**: Simple, immediate span export
**Cons**: Slightly higher overhead (~1-2ms per span)

### Option 2: Force Flush on Exit (Better)
Add `atexit` handler to flush spans before CLI exit:

```python
# ktrdr/cli/__init__.py
import atexit
from opentelemetry import trace

# After setup_monitoring call:
provider = setup_monitoring(...)

# Register flush on exit
def flush_spans():
    """Force flush all pending spans before CLI exit."""
    trace_provider = trace.get_tracer_provider()
    if hasattr(trace_provider, 'force_flush'):
        trace_provider.force_flush(timeout_millis=1000)

atexit.register(flush_spans)
```

**Pros**: Keeps batch efficiency, ensures spans exported
**Cons**: Adds ~100-1000ms to CLI exit time

### Option 3: Hybrid Approach (Recommended)
Combine both: Use `SimpleSpanProcessor` for CLI decorator spans, keep `BatchSpanProcessor` for httpx spans:

```python
# ktrdr/monitoring/setup.py
def setup_monitoring(..., cli_mode: bool = False):
    provider = TracerProvider(resource=resource)

    if cli_mode:
        # CLI: Use SimpleSpanProcessor for immediate export of decorator spans
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(SimpleSpanProcessor(otlp_exporter))
    else:
        # Services: Use BatchSpanProcessor for efficiency
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
```

## Implementation Plan

1. **Quick Fix** (5 minutes): Add `atexit` handler in `ktrdr/cli/__init__.py`
2. **Better Fix** (15 minutes): Add `cli_mode` parameter to `setup_monitoring()`
3. **Test**: Run `ktrdr data range AAPL --timeframe 1d` and verify `cli.data_range` span appears in Jaeger

## Testing Validation

After fix, should see in Jaeger:
```json
{
  "traceID": "...",
  "spans": [
    {
      "operationName": "cli.data_range",  // ✅ CLI decorator span
      "tags": [
        {"key": "cli.command", "value": "data_range"},
        {"key": "cli.args", "value": "{\"symbol\": \"AAPL\", ...}"}
      ]
    },
    {
      "operationName": "POST /api/v1/data/range",  // httpx span
      "tags": [...]
    }
  ]
}
```

## Workaround (Current)

Until fixed, verify CLI instrumentation is working by:
1. Check service registration: `ktrdr-cli` appears in Jaeger ✅
2. Check logs: See "OTLP trace export enabled for ktrdr-cli" ✅
3. Trust unit tests: `test_cli_command_creates_span` passes ✅

## Related

- Task 6.1: Entry Point Instrumentation (COMPLETE except for this)
- Similar issue may affect MCP tools (also short-lived)
- Not blocking: Instrumentation code is correct, just needs flush timing

## References

- [OpenTelemetry BatchSpanProcessor Docs](https://opentelemetry.io/docs/specs/otel/trace/sdk/#batching-processor)
- [Python SDK Span Processor](https://opentelemetry-python.readthedocs.io/en/latest/sdk/trace.html#span-processor)
