"""Entry point for MCP server"""

import sys
from .server import KTRDRMCPServer
from .config import setup_logging


def main():
    """Main entry point"""
    setup_logging()

    try:
        # Initialize and run the server
        ktrdr_server = KTRDRMCPServer()
        ktrdr_server.run()
    except KeyboardInterrupt:
        print("\nShutting down MCP server...")
        sys.exit(0)
    except Exception as e:
        print(f"Error running MCP server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
