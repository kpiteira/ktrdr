"""
API router module.

This module defines the main API router with versioned endpoints.
"""
from fastapi import APIRouter

# Create main API router
api_router = APIRouter()

# Define API endpoints
@api_router.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        dict: Health status information
    """
    return {
        "status": "ok",
        "version": "1.0.5"
    }

# Import and include other endpoint routers here as they are implemented
# Example:
# from ktrdr.api.endpoints.data import router as data_router
# from ktrdr.api.endpoints.indicators import router as indicators_router
# 
# api_router.include_router(data_router, prefix="/data", tags=["Data"])
# api_router.include_router(indicators_router, prefix="/indicators", tags=["Indicators"])