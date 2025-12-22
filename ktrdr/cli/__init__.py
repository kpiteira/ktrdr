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

# Setup OpenTelemetry tracing for CLI (optional - graceful if Jaeger unavailable)
# Skip in test mode to avoid slow imports
if not _is_testing:
    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        from ktrdr.monitoring.setup import setup_monitoring

        # Setup monitoring for CLI
        # Uses OTLP_ENDPOINT env var if set, otherwise defaults to localhost
        # CLI doesn't spam console output
        # Use SimpleSpanProcessor for immediate export (CLI is short-lived)
        setup_monitoring(
            service_name="ktrdr-cli",
            otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://localhost:4317"),
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
from ktrdr.cli.commands import cli_app  # noqa: E402
from ktrdr.cli.data_commands import data_app  # noqa: E402
from ktrdr.cli.deploy_commands import deploy_app  # noqa: E402
from ktrdr.cli.dummy_commands import dummy_app  # noqa: E402
from ktrdr.cli.fuzzy_commands import fuzzy_app  # noqa: E402
from ktrdr.cli.ib_commands import ib_app  # noqa: E402
from ktrdr.cli.indicator_commands import indicators_app  # noqa: E402
from ktrdr.cli.operations_commands import operations_app  # noqa: E402
from ktrdr.cli.strategy_commands import strategies_app  # noqa: E402

# Temporarily disabled while updating multi-timeframe for pure fuzzy
# from ktrdr.cli.multi_timeframe_commands import multi_timeframe_app

# Register command subgroups following industry best practices
cli_app.add_typer(agent_app, name="agent", help="Research agent management commands")
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
    strategies_app, name="strategies", help="Trading strategy management commands"
)
cli_app.add_typer(fuzzy_app, name="fuzzy", help="Fuzzy logic operations commands")
cli_app.add_typer(
    deploy_app, name="deploy", help="Deploy KTRDR services to pre-production"
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
