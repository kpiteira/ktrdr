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
from typing import Dict, Any

from ktrdr.api.config import APIConfig
from ktrdr.api.models import (
    OHLCVData,
    IndicatorConfig,
    FuzzyConfig,
)  # Import our models

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger("ktrdr.api.run")


def parse_args():
    """Parse command line arguments."""
    config = APIConfig()  # Load default config

    parser = argparse.ArgumentParser(description="Run the KTRDR API server")
    parser.add_argument(
        "--host",
        default=config.host,
        help=f"Host to bind the server (default: {config.host})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config.port,
        help=f"Port to bind the server (default: {config.port})",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=config.reload,
        help="Enable auto-reload for development (default: enabled in development mode)",
    )
    parser.add_argument(
        "--log-level",
        default=config.log_level.lower(),
        choices=["debug", "info", "warning", "error", "critical"],
        help=f"Logging level (default: {config.log_level.lower()})",
    )
    parser.add_argument(
        "--env",
        default=config.environment,
        choices=["development", "staging", "production"],
        help=f"Deployment environment (default: {config.environment})",
    )
    parser.add_argument(
        "--docs-path",
        default="/docs",
        help="Path for Swagger UI documentation (default: /docs)",
    )
    parser.add_argument(
        "--redoc-path",
        default="/redoc",
        help="Path for ReDoc documentation (default: /redoc)",
    )
    parser.add_argument(
        "--workers", type=int, default=1, help="Number of worker processes (default: 1)"
    )
    parser.add_argument(
        "--cors-origins", help="Comma-separated list of allowed CORS origins"
    )

    return parser.parse_args()


def main():
    """Run the API server."""
    args = parse_args()

    # Create environment variables dictionary for configuration
    env_vars: Dict[str, str] = {}

    if hasattr(args, "host") and args.host:
        env_vars["KTRDR_API_HOST"] = args.host

    if hasattr(args, "port") and args.port:
        env_vars["KTRDR_API_PORT"] = str(args.port)

    if hasattr(args, "reload"):
        env_vars["KTRDR_API_RELOAD"] = str(args.reload).lower()

    if hasattr(args, "log_level") and args.log_level:
        env_vars["KTRDR_API_LOG_LEVEL"] = args.log_level.upper()

    if hasattr(args, "env") and args.env:
        env_vars["KTRDR_API_ENVIRONMENT"] = args.env

    if hasattr(args, "cors_origins") and args.cors_origins:
        env_vars["KTRDR_API_CORS_ORIGINS"] = args.cors_origins

    # Apply configuration overrides
    try:
        config = APIConfig.from_env(env_vars)
    except Exception as e:
        logger.error(f"Failed to load configuration: {str(e)}")
        sys.exit(1)

    # Log startup information
    logger.info(f"Starting KTRDR API server: host={args.host}, port={args.port}")
    logger.info(f"Environment: {args.env}, Log level: {args.log_level}")
    logger.info(f"Auto-reload: {'enabled' if args.reload else 'disabled'}")
    if args.workers > 1:
        logger.info(f"Running with {args.workers} workers")

    # Additional information about available API models
    logger.debug("API initialized with the following models:")
    logger.debug("- Data models: OHLCVData, SymbolInfo, TimeframeInfo")
    logger.debug("- Indicator models: IndicatorConfig, IndicatorCalculateRequest")
    logger.debug("- Fuzzy models: FuzzyConfig, FuzzyEvaluateRequest")

    # Run the server
    try:
        uvicorn.run(
            "ktrdr.api.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level,
            workers=args.workers,
        )
    except Exception as e:
        logger.error(f"Failed to start API server: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
