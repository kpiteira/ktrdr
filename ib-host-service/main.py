#!/usr/bin/env python3
"""
IB Connector Host Service

A lightweight FastAPI service that runs on the host machine to provide
direct IB Gateway connectivity, bypassing Docker networking issues.

This service imports existing ktrdr.ib modules and exposes them via HTTP
endpoints that the containerized backend can call.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path so we can import ktrdr modules
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime
import logging

# Import existing ktrdr modules
from ktrdr.logging import get_logger

# Import endpoints
from endpoints.data import router as data_router
from endpoints.health import router as health_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="IB Connector Host Service",
    description="Direct IB Gateway connectivity service for KTRDR",
    version="1.0.0"
)

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
    logger.info(f"Service will listen on http://localhost:5001")
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
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "healthy": True,
        "service": "ib-connector",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "operational"
    }

if __name__ == "__main__":
    # Run the service
    uvicorn.run(
        "main:app",
        host="127.0.0.1",  # Localhost only for security
        port=5001,
        reload=True,
        log_level="info"
    )