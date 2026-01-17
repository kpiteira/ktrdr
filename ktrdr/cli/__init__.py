"""
Command Line Interface for KTRDR.

This module provides a CLI for interacting with the KTRDR application,
including commands for data inspection, indicator calculation, and visualization.
"""

import atexit
import os

# Skip heavy telemetry initialization in test mode for faster test execution
# PYTEST_CURRENT_TEST is set by pytest automatically
_is_testing = os.environ.get("PYTEST_CURRENT_TEST") is not None

# Track current OTLP endpoint for reconfiguration
_current_otlp_endpoint: str | None = None


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

    # Use sandbox-specific port if set, otherwise default
    port = os.environ.get("KTRDR_JAEGER_OTLP_GRPC_PORT", "4317")
    return f"http://localhost:{port}"


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


# Setup OpenTelemetry tracing for CLI (optional - graceful if Jaeger unavailable)
# Skip in test mode to avoid slow imports
if not _is_testing:
    try:
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

# CLI submodule imports - these must come after telemetry setup
# noqa: E402 because telemetry setup is intentionally before these imports
from ktrdr.cli.agent_commands import agent_app  # noqa: E402
from ktrdr.cli.async_model_commands import async_models_app as models_app  # noqa: E402
from ktrdr.cli.backtest_commands import backtest_app  # noqa: E402
from ktrdr.cli.checkpoints_commands import checkpoints_app  # noqa: E402
from ktrdr.cli.commands import cli_app  # noqa: E402

# New M2 commands - registered directly on cli_app
from ktrdr.cli.commands.backtest import backtest  # noqa: E402
from ktrdr.cli.commands.research import research  # noqa: E402
from ktrdr.cli.commands.status import status  # noqa: E402
from ktrdr.cli.commands.train import train  # noqa: E402
from ktrdr.cli.data_commands import data_app  # noqa: E402
from ktrdr.cli.deploy_commands import deploy_app  # noqa: E402
from ktrdr.cli.dummy_commands import dummy_app  # noqa: E402
from ktrdr.cli.fuzzy_commands import fuzzy_app  # noqa: E402
from ktrdr.cli.ib_commands import ib_app  # noqa: E402
from ktrdr.cli.indicator_commands import indicators_app  # noqa: E402
from ktrdr.cli.operations_commands import operations_app  # noqa: E402
from ktrdr.cli.sandbox import sandbox_app  # noqa: E402
from ktrdr.cli.strategy_commands import strategies_app  # noqa: E402

# Temporarily disabled while updating multi-timeframe for pure fuzzy
# from ktrdr.cli.multi_timeframe_commands import multi_timeframe_app

# Register new top-level commands (M1/M2 CLI restructure)
cli_app.command()(train)
cli_app.command()(backtest)
cli_app.command()(research)
cli_app.command()(status)

# Register command subgroups following industry best practices
cli_app.add_typer(agent_app, name="agent", help="Research agent management commands")
cli_app.add_typer(
    checkpoints_app, name="checkpoints", help="Checkpoint management commands"
)
cli_app.add_typer(data_app, name="data", help="Data management commands")
cli_app.add_typer(
    backtest_app, name="backtest", help="Backtesting commands for trading strategies"
)
cli_app.add_typer(
    dummy_app, name="dummy", help="Dummy service commands with beautiful UX"
)
cli_app.add_typer(
    operations_app, name="operations", help="Operations management commands"
)
cli_app.add_typer(
    indicators_app, name="indicators", help="Technical indicator commands"
)
cli_app.add_typer(ib_app, name="ib", help="Interactive Brokers integration commands")
cli_app.add_typer(
    models_app, name="models", help="Neural network model management commands"
)
cli_app.add_typer(
    strategies_app, name="strategies", help="Manage trading strategies (v3 format)"
)
cli_app.add_typer(fuzzy_app, name="fuzzy", help="Fuzzy logic operations commands")
cli_app.add_typer(
    deploy_app, name="deploy", help="Deploy KTRDR services to pre-production"
)
cli_app.add_typer(
    sandbox_app, name="sandbox", help="Manage isolated development sandbox instances"
)
# Temporarily disabled while updating multi-timeframe for pure fuzzy
# cli_app.add_typer(
#     multi_timeframe_app,
#     name="multi-timeframe",
#     help="Multi-timeframe trading decision commands",
# )

# Export the app for the CLI entry point
app = cli_app

__all__ = ["cli_app", "app"]
