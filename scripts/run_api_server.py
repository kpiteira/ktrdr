#!/usr/bin/env python
"""
Run KTRDR API server.

This script provides a convenient way to start the KTRDR API server
with the ability to override configuration via command line arguments.
"""
import argparse
import logging
import sys
import uvicorn

from ktrdr.api.config import APIConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("ktrdr.api.run")

def parse_args():
    """Parse command line arguments."""
    config = APIConfig()  # Load default config
    
    parser = argparse.ArgumentParser(description="Run the KTRDR API server")
    parser.add_argument(
        "--host", 
        default=config.host,
        help=f"Host to bind the server (default: {config.host})"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=config.port,
        help=f"Port to bind the server (default: {config.port})"
    )
    parser.add_argument(
        "--reload", 
        action="store_true", 
        default=config.reload,
        help="Enable auto-reload for development (default: enabled in development mode)"
    )
    parser.add_argument(
        "--log-level", 
        default=config.log_level.lower(),
        choices=["debug", "info", "warning", "error", "critical"],
        help=f"Logging level (default: {config.log_level.lower()})"
    )
    parser.add_argument(
        "--env", 
        default=config.environment,
        choices=["development", "staging", "production"],
        help=f"Deployment environment (default: {config.environment})"
    )
    
    return parser.parse_args()

def main():
    """Run the API server."""
    args = parse_args()
    
    logger.info(f"Starting KTRDR API server: host={args.host}, port={args.port}")
    logger.info(f"Environment: {args.env}, Log level: {args.log_level}")
    
    # Run the server
    try:
        uvicorn.run(
            "ktrdr.api.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level,
        )
    except Exception as e:
        logger.error(f"Failed to start API server: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()