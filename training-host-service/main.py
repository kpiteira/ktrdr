#!/usr/bin/env python3
"""
Training Host Service

A lightweight FastAPI service that runs on the host machine to provide
GPU acceleration for training, bypassing Docker GPU access limitations.

This service imports existing ktrdr.training modules and exposes them via HTTP
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
from endpoints.training import router as training_router
from endpoints.health import router as health_router

# Import configuration
from config import get_host_service_config

# Get configuration
service_config = get_host_service_config()

# Configure logging
logging.basicConfig(level=getattr(logging, service_config.host_service.log_level))
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Training Host Service",
    description="GPU-accelerated training service for KTRDR",
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
app.include_router(training_router)
app.include_router(health_router)

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    logger.info("Starting Training Host Service...")
    logger.info(f"Service will listen on http://{service_config.host_service.host}:{service_config.host_service.port}")
    logger.info("Available endpoints:")
    logger.info("  GET  /                     - Service info")
    logger.info("  GET  /health               - Basic health check")
    logger.info("  GET  /health/detailed      - Detailed health check") 
    logger.info("  POST /training/start       - Start training session")
    logger.info("  POST /training/stop        - Stop training session")
    logger.info("  GET  /training/status      - Get training status")
    logger.info("  POST /training/evaluate    - Evaluate model")

@app.on_event("shutdown") 
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Training Host Service...")
    
    # Cleanup training service
    try:
        from services.training_service import get_training_service
        service = get_training_service()
        await service.shutdown()
        logger.info("Training service shutdown completed")
    except Exception as e:
        logger.error(f"Error during training service shutdown: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint with service info."""
    import torch
    
    gpu_available = torch.cuda.is_available()
    gpu_device_count = torch.cuda.device_count() if gpu_available else 0
    
    return {
        "service": "Training Host Service",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "gpu_available": gpu_available,
        "gpu_device_count": gpu_device_count
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "healthy": True,
        "service": "training-host",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "operational"
    }

if __name__ == "__main__":
    # Run the service using configuration
    uvicorn.run(
        "main:app",
        host=service_config.host_service.host,
        port=service_config.host_service.port,
        reload=True,
        log_level=service_config.host_service.log_level.lower()
    )