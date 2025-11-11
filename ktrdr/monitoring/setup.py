"""OpenTelemetry setup and configuration."""

import logging
import os

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

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
