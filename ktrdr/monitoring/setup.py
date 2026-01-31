"""OpenTelemetry setup and configuration."""

import logging
import os

from opentelemetry import metrics, trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from prometheus_client import make_asgi_app

logger = logging.getLogger(__name__)


def _is_testing() -> bool:
    """Check if running in test mode.

    Uses PYTEST_CURRENT_TEST (set per-test) or checks if pytest is loaded.
    This must be a function checked at runtime, not import time.
    """
    # PYTEST_CURRENT_TEST is set during test execution
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    # Also check if pytest module is loaded (covers collection phase)
    import sys

    return "pytest" in sys.modules


def setup_monitoring(
    service_name: str,
    otlp_endpoint: str | None = None,
    console_output: bool = False,
    use_simple_processor: bool = False,
) -> TracerProvider:
    """
    Setup OpenTelemetry tracing for a service.

    Args:
        service_name: Name of the service (e.g., "ktrdr-api", "ktrdr-training-worker")
        otlp_endpoint: OTLP gRPC endpoint (e.g., "http://jaeger:4317"). If None, console only.
        console_output: If True, also print traces to console (for debugging)
        use_simple_processor: If True, use SimpleSpanProcessor for immediate export (for CLI/short-lived processes)

    Returns:
        TracerProvider instance (no-op provider in test mode)
    """
    # Skip telemetry setup in test mode to avoid Jaeger connection attempts
    if _is_testing():
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        return provider

    # Create resource with service identification
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": os.getenv("APP_VERSION", "dev"),
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        }
    )

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add console exporter for development
    if console_output or otlp_endpoint is None:
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(console_exporter))
        logger.info(f"✅ Console trace export enabled for {service_name}")

    # Add OTLP exporter if endpoint provided
    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint, insecure=True  # Use TLS in production
        )

        # Use SimpleSpanProcessor for CLI/short-lived processes (immediate export)
        # Use BatchSpanProcessor for services (efficient batching)
        if use_simple_processor:
            provider.add_span_processor(SimpleSpanProcessor(otlp_exporter))
            logger.info(
                f"✅ OTLP trace export enabled for {service_name} → {otlp_endpoint} (immediate)"
            )
        else:
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(
                f"✅ OTLP trace export enabled for {service_name} → {otlp_endpoint}"
            )

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


def setup_metrics(service_name: str) -> MeterProvider:
    """
    Setup OpenTelemetry metrics for a service with Prometheus export.

    Args:
        service_name: Name of the service (e.g., "ktrdr-api")

    Returns:
        MeterProvider instance
    """
    # Create resource with service identification
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": os.getenv("APP_VERSION", "dev"),
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        }
    )

    # Create Prometheus metric reader
    reader = PrometheusMetricReader()

    # Create meter provider
    provider = MeterProvider(resource=resource, metric_readers=[reader])

    # Set as global meter provider
    metrics.set_meter_provider(provider)

    logger.info(f"✅ Prometheus metrics export enabled for {service_name}")

    return provider


def get_metrics_app():
    """
    Get Prometheus metrics ASGI app for mounting at /metrics endpoint.

    Returns:
        ASGI application that serves Prometheus metrics
    """
    return make_asgi_app()


# Track active CLI span processor for cleanup during reconfiguration
_cli_span_processor: SimpleSpanProcessor | None = None


def reconfigure_otlp_endpoint(new_endpoint: str) -> None:
    """
    Reconfigure the OTLP exporter to use a new endpoint.

    Used by CLI when --url flag points to a remote server, so traces
    are sent to the same Jaeger instance as the backend.

    Note: The caller should check if the endpoint actually changed before calling
    this function to avoid unnecessary processor churn.

    Args:
        new_endpoint: New OTLP gRPC endpoint (e.g., "http://remote-host:4317")
    """
    global _cli_span_processor

    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    provider = trace.get_tracer_provider()

    # Only works with SDK TracerProvider, not the default no-op provider
    if not isinstance(provider, TracerProvider):
        return

    # Shutdown previous processor to prevent duplicate exports
    # Note: The processor remains registered but stops exporting after shutdown
    if _cli_span_processor is not None:
        try:
            _cli_span_processor.shutdown()
        except Exception:
            pass  # Best effort cleanup

    # Create new exporter and processor
    otlp_exporter = OTLPSpanExporter(endpoint=new_endpoint, insecure=True)
    _cli_span_processor = SimpleSpanProcessor(otlp_exporter)

    # Add new processor (SimpleSpanProcessor for CLI)
    provider.add_span_processor(_cli_span_processor)

    logger.info(f"✅ OTLP trace export reconfigured → {new_endpoint}")
