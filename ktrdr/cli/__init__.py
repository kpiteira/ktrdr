"""
Command Line Interface for KTRDR.

This module provides a CLI for interacting with the KTRDR application,
including commands for data inspection, indicator calculation, and visualization.

PERFORMANCE NOTE: This module uses lazy loading to achieve <100ms CLI startup.
Heavy imports (command modules, telemetry) are deferred until first access.
"""

import os
from typing import TYPE_CHECKING

# Skip heavy telemetry initialization in test mode for faster test execution
# PYTEST_CURRENT_TEST is set by pytest automatically
_is_testing = os.environ.get("PYTEST_CURRENT_TEST") is not None

# Track current OTLP endpoint for reconfiguration
_current_otlp_endpoint: str | None = None

# Flag to track if telemetry has been initialized
_telemetry_initialized = False


def _derive_otlp_endpoint_from_url(api_url: str | None) -> str:
    """Derive OTLP endpoint from API URL.

    Args:
        api_url: The API URL to derive from (e.g., http://backend.example.com:8000)

    Returns:
        OTLP endpoint URL (same host, port 4317)
    """
    # Explicit OTLP endpoint always takes priority
    if otlp := os.getenv("OTLP_ENDPOINT"):
        return otlp

    # Derive from provided API URL
    if api_url:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(api_url)
            if parsed.hostname and parsed.hostname not in ("localhost", "127.0.0.1"):
                return f"http://{parsed.hostname}:4317"
        except Exception:
            pass  # Best-effort derivation; fall back to localhost

    # Use sandbox-specific port (checks os.environ -> .env.sandbox -> default)
    try:
        from ktrdr.cli.sandbox_detect import get_sandbox_var

        port = get_sandbox_var("KTRDR_JAEGER_OTLP_GRPC_PORT", "4317")
        return f"http://localhost:{port}"
    except Exception:
        return "http://localhost:4317"


def reconfigure_telemetry_for_url(api_url: str) -> None:
    """Reconfigure telemetry to send traces to the same host as the API.

    Called when --url flag is used to target a remote server.
    This ensures CLI traces appear in the remote Jaeger alongside backend traces.

    Args:
        api_url: The API URL being targeted
    """
    global _current_otlp_endpoint

    if _is_testing:
        return

    new_endpoint = _derive_otlp_endpoint_from_url(api_url)

    # Skip if endpoint hasn't changed
    if new_endpoint == _current_otlp_endpoint:
        return

    try:
        from ktrdr.monitoring.setup import reconfigure_otlp_endpoint

        reconfigure_otlp_endpoint(new_endpoint)
        _current_otlp_endpoint = new_endpoint
    except Exception:
        pass  # Telemetry reconfiguration is best-effort


def _setup_telemetry() -> None:
    """Initialize OpenTelemetry tracing for CLI (lazy, called on first command execution).

    This is called lazily when the app is first accessed, not at import time.
    This keeps CLI startup fast for --help and other quick commands.
    """
    global _telemetry_initialized, _current_otlp_endpoint

    if _telemetry_initialized or _is_testing:
        return

    _telemetry_initialized = True

    try:
        import atexit

        from opentelemetry import trace
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        from ktrdr.monitoring.setup import setup_monitoring

        # Setup monitoring for CLI with initial endpoint
        # Will be reconfigured if --url flag points to remote server
        _current_otlp_endpoint = _derive_otlp_endpoint_from_url(
            os.getenv("KTRDR_API_URL")
        )
        setup_monitoring(
            service_name="ktrdr-cli",
            otlp_endpoint=_current_otlp_endpoint,
            console_output=False,  # CLI shouldn't spam traces to console
            use_simple_processor=True,  # Immediate export for short-lived CLI process
        )

        # Instrument httpx for automatic trace propagation
        # This ensures CLI -> API calls include trace context in HTTP headers
        HTTPXClientInstrumentor().instrument()

        # Force flush spans before CLI exit (fixes short-lived process issue)
        # BatchSpanProcessor buffers spans (5s/512 spans) - CLI exits before flush
        def flush_spans():
            """Force flush all pending spans before CLI exit."""
            try:
                trace_provider = trace.get_tracer_provider()
                if hasattr(trace_provider, "force_flush"):
                    trace_provider.force_flush(timeout_millis=1000)
            except Exception:
                pass  # Ignore errors during shutdown

        atexit.register(flush_spans)

    except Exception:
        # Gracefully handle case where OTEL packages aren't available
        # or Jaeger isn't running - CLI should still work
        pass


def _get_cli_app():
    """Get the fully configured CLI app with all commands registered.

    This is called lazily when `cli_app` or `app` is accessed from this module.
    The app is now defined in ktrdr.cli.app and this module just re-exports it.

    Uses get_app_with_subgroups() to ensure all subgroups (sandbox, ib, deploy,
    data, checkpoints) are registered. This is slower than just importing app,
    but necessary for the CLI to have all commands available.
    """
    # Import the fully configured app from app.py
    # app.py is the single source of truth for command registration
    from ktrdr.cli.app import get_app_with_subgroups

    return get_app_with_subgroups()


# Cache for the lazily-loaded app
_cached_app = None


def __getattr__(name: str):
    """Lazy loading for heavy module attributes.

    This allows `from ktrdr.cli import cli_app` to work while deferring
    the heavy imports until the attribute is actually accessed.
    """
    global _cached_app

    if name in ("cli_app", "app"):
        if _cached_app is None:
            _cached_app = _get_cli_app()
        return _cached_app

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Type hints for IDE support (not executed at runtime due to TYPE_CHECKING)
if TYPE_CHECKING:
    from typer import Typer

    cli_app: Typer
    app: Typer


def init_telemetry_if_needed() -> None:
    """Initialize telemetry if not already initialized.

    Called lazily from trace_cli_command decorator when commands execute.
    This keeps --help fast by avoiding OTEL setup until actual commands run.
    """
    _setup_telemetry()


def main() -> None:
    """Entry point for the ktrdr CLI.

    This function is used as the entry point in pyproject.toml.
    It ensures the app with all subgroups is loaded and executed.
    """
    cli_app = _get_cli_app()
    cli_app()


__all__ = [
    "cli_app",
    "app",
    "main",
    "reconfigure_telemetry_for_url",
    "init_telemetry_if_needed",
]
