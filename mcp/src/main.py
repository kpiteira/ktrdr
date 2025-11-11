"""Entry point for MCP server"""

import logging
import os
import sys

# Setup OpenTelemetry tracing for MCP server (optional - graceful if Jaeger unavailable)
try:
    from ktrdr.monitoring.setup import setup_monitoring
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    # Setup monitoring for MCP server
    # Uses OTLP_ENDPOINT env var if set, otherwise defaults to localhost
    setup_monitoring(
        service_name="ktrdr-mcp-server",
        otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://localhost:4317"),
        console_output=False,  # MCP server shouldn't spam traces to console
    )

    # Instrument httpx for automatic trace propagation
    # This ensures MCP tool calls -> API calls include trace context
    HTTPXClientInstrumentor().instrument()

    logging.info("✅ OpenTelemetry instrumentation enabled for MCP server")
except Exception as e:
    # Gracefully handle case where OTEL packages aren't available
    # or Jaeger isn't running - MCP server should still work
    logging.debug(f"OTEL instrumentation not available: {e}")

from .config import setup_logging
from .server import KTRDRMCPServer

logger = logging.getLogger(__name__)


def main():
    """Main entry point"""
    setup_logging()

    logger.info("=" * 60)
    logger.info("KTRDR MCP Server Starting")
    logger.info("=" * 60)

    try:
        # Initialize and run the server
        ktrdr_server = KTRDRMCPServer()
        logger.info("MCP server initialized successfully")
        logger.info("Waiting for Claude Desktop connections...")
        ktrdr_server.run()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal (KeyboardInterrupt)")
        logger.info("KTRDR MCP Server Stopped")
        logger.info("=" * 60)
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error running MCP server: {e}", exc_info=True)
        logger.error("KTRDR MCP Server Failed")
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
