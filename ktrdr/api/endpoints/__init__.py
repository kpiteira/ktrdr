"""
API router module.

This module defines the main API router with versioned endpoints.
"""
from fastapi import APIRouter, Depends
from ktrdr.api.config import APIConfig
from ktrdr.api.dependencies import get_api_config

# Create main API router
api_router = APIRouter()

# Define API endpoints
@api_router.get("/health")
async def health_check(config: APIConfig = Depends(get_api_config)):
    """
    Health check endpoint.
    
    Returns:
        dict: Health status information
    """
    return {
        "status": "ok",
        "version": config.version
    }

# Import and include other endpoint routers
from ktrdr.api.endpoints.data import router as data_router
from ktrdr.api.endpoints.indicators import router as indicators_router
from ktrdr.api.endpoints.fuzzy import router as fuzzy_router

# Include routers with appropriate prefixes
# Removed the "/v1" prefix since the data router endpoints already include this prefix
api_router.include_router(data_router, tags=["Data"])
# Use lowercase tag to match the one defined in indicators.py
api_router.include_router(indicators_router, tags=["indicators"])
api_router.include_router(fuzzy_router, tags=["Fuzzy"])
