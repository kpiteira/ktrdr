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
    It imports all command modules and registers them on the app.
    """
    # Import the base app from commands module
    # Import all command modules
    from ktrdr.cli.agent_commands import agent_app
    from ktrdr.cli.async_model_commands import async_models_app as models_app
    from ktrdr.cli.backtest_commands import backtest_app
    from ktrdr.cli.checkpoints_commands import checkpoints_app
    from ktrdr.cli.commands import cli_app as base_app
    from ktrdr.cli.commands.backtest import backtest
    from ktrdr.cli.commands.cancel import cancel
    from ktrdr.cli.commands.follow import follow
    from ktrdr.cli.commands.list_cmd import list_app
    from ktrdr.cli.commands.migrate import migrate_cmd
    from ktrdr.cli.commands.ops import ops
    from ktrdr.cli.commands.research import research
    from ktrdr.cli.commands.resume import resume
    from ktrdr.cli.commands.show import show_app
    from ktrdr.cli.commands.status import status
    from ktrdr.cli.commands.train import train
    from ktrdr.cli.commands.validate import validate_cmd
    from ktrdr.cli.data_commands import data_app
    from ktrdr.cli.deploy_commands import deploy_app
    from ktrdr.cli.dummy_commands import dummy_app
    from ktrdr.cli.fuzzy_commands import fuzzy_app
    from ktrdr.cli.ib_commands import ib_app
    from ktrdr.cli.indicator_commands import indicators_app
    from ktrdr.cli.operations_commands import operations_app
    from ktrdr.cli.sandbox import sandbox_app
    from ktrdr.cli.strategy_commands import strategies_app

    # Register new top-level commands (M1/M2 CLI restructure)
    base_app.command()(train)
    base_app.command()(backtest)
    base_app.command()(research)
    base_app.command()(status)
    base_app.command()(follow)
    base_app.command()(ops)
    base_app.command()(cancel)
    base_app.command()(resume)

    # Register M3 information commands
    base_app.add_typer(list_app)  # ktrdr list strategies/models/checkpoints
    base_app.add_typer(show_app)  # ktrdr show data/features
    base_app.command("validate")(validate_cmd)  # ktrdr validate <name|path>
    base_app.command("migrate")(migrate_cmd)  # ktrdr migrate <path>

    # Register command subgroups following industry best practices
    base_app.add_typer(
        agent_app, name="agent", help="Research agent management commands"
    )
    base_app.add_typer(
        checkpoints_app, name="checkpoints", help="Checkpoint management commands"
    )
    base_app.add_typer(data_app, name="data", help="Data management commands")
    base_app.add_typer(
        backtest_app,
        name="backtest",
        help="Backtesting commands for trading strategies",
    )
    base_app.add_typer(
        dummy_app, name="dummy", help="Dummy service commands with beautiful UX"
    )
    base_app.add_typer(
        operations_app, name="operations", help="Operations management commands"
    )
    base_app.add_typer(
        indicators_app, name="indicators", help="Technical indicator commands"
    )
    base_app.add_typer(
        ib_app, name="ib", help="Interactive Brokers integration commands"
    )
    base_app.add_typer(
        models_app, name="models", help="Neural network model management commands"
    )
    base_app.add_typer(
        strategies_app, name="strategies", help="Manage trading strategies (v3 format)"
    )
    base_app.add_typer(fuzzy_app, name="fuzzy", help="Fuzzy logic operations commands")
    base_app.add_typer(
        deploy_app, name="deploy", help="Deploy KTRDR services to pre-production"
    )
    base_app.add_typer(
        sandbox_app,
        name="sandbox",
        help="Manage isolated development sandbox instances",
    )

    # Note: Telemetry is initialized lazily via init_telemetry_if_needed()
    # called from trace_cli_command decorator when commands execute.
    # This keeps --help fast by avoiding OTEL setup.

    return base_app


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


__all__ = [
    "cli_app",
    "app",
    "reconfigure_telemetry_for_url",
    "init_telemetry_if_needed",
]
