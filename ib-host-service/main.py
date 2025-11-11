#!/usr/bin/env python3
"""
IB Connector Host Service

A lightweight FastAPI service that runs on the host machine to provide
direct IB Gateway connectivity, bypassing Docker networking issues.

This service imports existing ktrdr.ib modules and exposes them via HTTP
endpoints that the containerized backend can call.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add parent directory to path so we can import ktrdr modules
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Import local modules after sys.path is configured
try:
    # Import endpoints
    from endpoints.data import router as data_router
    from endpoints.health import router as health_router

    # Import configuration
    from config import get_host_service_config

    # Import existing ktrdr modules
    from ktrdr.logging import get_logger
    from ktrdr.monitoring.setup import instrument_app, setup_monitoring
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure the parent directory contains ktrdr modules")
    sys.exit(1)

# Get configuration
service_config = get_host_service_config()

# Configure logging
logging.basicConfig(level=getattr(logging, service_config.host_service.log_level))
logger = get_logger(__name__)

# Setup monitoring BEFORE creating app
otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://localhost:4317")
setup_monitoring(
    service_name="ktrdr-ib-host-service",
    otlp_endpoint=otlp_endpoint,
    console_output=os.getenv("ENVIRONMENT") == "development",
)

# Create FastAPI app
app = FastAPI(
    title="IB Connector Host Service",
    description="Direct IB Gateway connectivity service for KTRDR",
    version="1.0.0",
)

# Auto-instrument with OpenTelemetry
instrument_app(app)

# Add CORS middleware for Docker container communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for localhost development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(data_router)
app.include_router(health_router)


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    logger.info("Starting IB Connector Host Service...")
    logger.info(
        f"Service will listen on http://{service_config.host_service.host}:{service_config.host_service.port}"
    )
    logger.info("Available endpoints:")
    logger.info("  GET  /                     - Service info")
    logger.info("  GET  /health               - Basic health check")
    logger.info("  GET  /health/detailed      - Detailed health check")
    logger.info("  POST /data/historical      - Fetch historical data")
    logger.info("  POST /data/validate        - Validate symbol")
    logger.info("  GET  /data/head-timestamp  - Get head timestamp")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down IB Connector Host Service...")


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "IB Connector Host Service",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "healthy": True,
        "service": "ib-connector",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "operational",
    }


if __name__ == "__main__":
    # Run the service using configuration
    uvicorn.run(
        "main:app",
        host=service_config.host_service.host,
        port=service_config.host_service.port,
        reload=True,
        log_level=service_config.host_service.log_level.lower(),
    )
