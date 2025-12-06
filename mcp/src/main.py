"""Entry point for MCP server"""

import logging
import os
import sys

# CRITICAL: MCP requires stdout to be clean for JSON-RPC protocol
# ktrdr imports trigger logging to stdout, which breaks JSON-RPC
# We must capture and redirect stdout BEFORE any ktrdr imports

# Save original stdout for MCP JSON-RPC output
_original_stdout = sys.stdout

# Temporarily redirect stdout to stderr during imports
# This ensures any log messages go to stderr, not stdout
sys.stdout = sys.stderr

# Now import MCP server components - logging will go to stderr
from .config import setup_logging  # noqa: E402
from .server import KTRDRMCPServer  # noqa: E402

# Restore stdout for JSON-RPC communication
sys.stdout = _original_stdout


def _fix_logging_for_mcp():
    """Remove stdout handlers and replace with stderr.

    ktrdr's logging initialization adds a StreamHandler(sys.stdout) which
    would break MCP's JSON-RPC protocol. We replace with stderr handlers.
    """
    root = logging.getLogger()

    # Remove all handlers that output to stdout
    for handler in root.handlers[:]:
        if isinstance(handler, logging.StreamHandler):
            # Check if this handler outputs to stdout (even after redirect)
            if handler.stream == _original_stdout or handler.stream == sys.stdout:
                root.removeHandler(handler)

    # Add a stderr handler if none exists
    has_stderr_handler = any(
        isinstance(h, logging.StreamHandler) and h.stream == sys.stderr
        for h in root.handlers
    )
    if not has_stderr_handler:
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.INFO)
        stderr_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root.addHandler(stderr_handler)


# Fix logging handlers (replace stdout with stderr)
_fix_logging_for_mcp()

logger = logging.getLogger(__name__)

# Setup OpenTelemetry tracing for MCP server (optional - graceful if Jaeger unavailable)
try:
    # Redirect stdout during imports again
    sys.stdout = sys.stderr

    from opentelemetry.instrumentation.httpx import (
        HTTPXClientInstrumentor,  # noqa: E402
    )

    from ktrdr.monitoring.setup import setup_monitoring  # noqa: E402

    # Restore stdout
    sys.stdout = _original_stdout
    _fix_logging_for_mcp()

    # Setup monitoring for MCP server
    setup_monitoring(
        service_name="ktrdr-mcp-server",
        otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://localhost:4317"),
        console_output=False,
    )

    # Instrument httpx for automatic trace propagation
    HTTPXClientInstrumentor().instrument()

    _fix_logging_for_mcp()
    logger.info("OpenTelemetry instrumentation enabled for MCP server")
except Exception as e:
    sys.stdout = _original_stdout  # Ensure stdout is restored
    logger.debug(f"OTEL instrumentation not available: {e}")


def main():
    """Main entry point"""
    _fix_logging_for_mcp()
    setup_logging()
    _fix_logging_for_mcp()

    logger.info("=" * 60)
    logger.info("KTRDR MCP Server Starting")
    logger.info("=" * 60)

    try:
        ktrdr_server = KTRDRMCPServer()
        logger.info("MCP server initialized successfully")
        logger.info("Waiting for Claude Desktop connections...")
        ktrdr_server.run()
    except KeyboardInterrupt:
        logger.info("KTRDR MCP Server Stopped")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error running MCP server: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
