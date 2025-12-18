"""Telemetry setup for OpenTelemetry traces and metrics.

Configures tracing and metrics export to the KTRDR observability stack
(Jaeger for traces, Prometheus for metrics via OTLP).
"""

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from orchestrator.config import OrchestratorConfig

# Module-level metric counters (set by create_metrics)
tasks_counter: metrics.Counter
tokens_counter: metrics.Counter
cost_counter: metrics.Counter


def setup_telemetry(config: OrchestratorConfig) -> tuple[trace.Tracer, metrics.Meter]:
    """Initialize OpenTelemetry with OTLP export.

    Sets up tracing and metrics providers with exporters pointing to
    the configured OTLP endpoint (typically Jaeger/Prometheus collector).

    Args:
        config: Orchestrator configuration with OTLP endpoint and service name

    Returns:
        Tuple of (tracer, meter) for creating spans and recording metrics
    """
    # Set up tracing
    trace_provider = TracerProvider()
    trace_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=config.otlp_endpoint))
    )
    trace.set_tracer_provider(trace_provider)
    tracer = trace.get_tracer(config.service_name)

    # Set up metrics
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=config.otlp_endpoint)
    )
    meter_provider = MeterProvider(metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    meter = metrics.get_meter(config.service_name)

    return tracer, meter


def create_metrics(meter: metrics.Meter) -> None:
    """Create metric instruments for orchestrator tracking.

    Creates counters for tracking:
    - Tasks executed (by status)
    - Tokens used
    - Cost in USD

    Args:
        meter: OpenTelemetry meter for creating instruments
    """
    global tasks_counter, tokens_counter, cost_counter

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
