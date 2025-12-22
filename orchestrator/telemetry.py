"""Telemetry setup for OpenTelemetry traces and metrics.

Configures tracing and metrics export to the KTRDR observability stack
(Jaeger for traces, Prometheus for metrics via OTLP).

When OTLP endpoint is not available, falls back to no-op telemetry.
"""

import logging
import os

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider

from orchestrator.config import OrchestratorConfig

# Suppress gRPC warnings when collector is unavailable
logging.getLogger("opentelemetry.exporter.otlp.proto.grpc").setLevel(logging.ERROR)

# Module-level metric instruments (set by create_metrics)
tasks_counter: metrics.Counter
tokens_counter: metrics.Counter
cost_counter: metrics.Counter
task_duration: metrics.Histogram
escalations_counter: metrics.Counter
loops_counter: metrics.Counter


def setup_telemetry(config: OrchestratorConfig) -> tuple[trace.Tracer, metrics.Meter]:
    """Initialize OpenTelemetry with OTLP export.

    Sets up tracing and metrics providers with exporters pointing to
    the configured OTLP endpoint (typically Jaeger/Prometheus collector).

    If OTLP_ENABLED=false or endpoint is not configured, uses no-op providers.

    Args:
        config: Orchestrator configuration with OTLP endpoint and service name

    Returns:
        Tuple of (tracer, meter) for creating spans and recording metrics
    """
    otlp_enabled = os.getenv("OTLP_ENABLED", "false").lower() == "true"

    if otlp_enabled and config.otlp_endpoint:
        # Import OTLP exporters only when needed
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # Set up tracing with OTLP export
        trace_provider = TracerProvider()
        trace_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=config.otlp_endpoint))
        )
        trace.set_tracer_provider(trace_provider)

        # Set up metrics with OTLP export
        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=config.otlp_endpoint)
        )
        meter_provider = MeterProvider(metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)
    else:
        # Use no-op providers (in-memory, no export)
        trace.set_tracer_provider(TracerProvider())
        metrics.set_meter_provider(MeterProvider())

    tracer = trace.get_tracer(config.service_name)
    meter = metrics.get_meter(config.service_name)

    return tracer, meter


def create_metrics(meter: metrics.Meter) -> None:
    """Create metric instruments for orchestrator tracking.

    Creates counters for tracking:
    - Tasks executed (by status)
    - Tokens used
    - Cost in USD
    - Escalations to human (by task_id)
    - Loops detected (by type: task or e2e)

    And histograms for:
    - Task duration distribution (for P50/P95/P99 percentiles)

    Args:
        meter: OpenTelemetry meter for creating instruments
    """
    global tasks_counter, tokens_counter, cost_counter, task_duration
    global escalations_counter, loops_counter

    tasks_counter = meter.create_counter(
        "orchestrator_tasks_total",
        description="Total tasks executed",
    )

    tokens_counter = meter.create_counter(
        "orchestrator_tokens_total",
        description="Total tokens used",
    )

    cost_counter = meter.create_counter(
        "orchestrator_cost_usd_total",
        description="Total cost in USD",
    )

    task_duration = meter.create_histogram(
        "orchestrator_task_duration_seconds",
        description="Task execution duration",
        unit="s",
    )

    escalations_counter = meter.create_counter(
        "orchestrator_escalations_total",
        description="Total escalations to human",
    )

    loops_counter = meter.create_counter(
        "orchestrator_loops_detected_total",
        description="Total loops detected",
    )
