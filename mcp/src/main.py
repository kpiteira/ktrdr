"""Entry point for MCP server"""

import logging
import sys

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
