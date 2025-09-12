"""
API router module.

This module defines the main API router with versioned endpoints.
"""

from fastapi import APIRouter, Depends

from ktrdr.api.config import APIConfig
from ktrdr.api.dependencies import get_api_config
from ktrdr.api.endpoints.backtesting import router as backtesting_router
from ktrdr.api.endpoints.data import router as data_router
from ktrdr.api.endpoints.dummy import router as dummy_router
from ktrdr.api.endpoints.fuzzy import router as fuzzy_router
from ktrdr.api.endpoints.gap_analysis import router as gap_analysis_router
from ktrdr.api.endpoints.ib import router as ib_router
from ktrdr.api.endpoints.indicators import router as indicators_router
from ktrdr.api.endpoints.models import router as models_router
from ktrdr.api.endpoints.operations import router as operations_router
from ktrdr.api.endpoints.strategies import router as strategies_router
from ktrdr.api.endpoints.training import router as training_router

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
    return {"status": "ok", "version": config.version}


# Import and include other endpoint routers
# Temporarily disabled: System endpoints need updating for new architecture
# from ktrdr.api.endpoints.system import router as system_router

# Temporarily disabled while updating multi-timeframe for pure fuzzy
# from ktrdr.api.endpoints.multi_timeframe_decisions import (
#     router as multi_timeframe_decisions_router,
# )

# Include routers with appropriate prefixes
# Removed the "/v1" prefix since the data router endpoints already include this prefix
api_router.include_router(data_router, tags=["Data"])
api_router.include_router(dummy_router, tags=["Dummy"])
# Use lowercase tag to match the one defined in indicators.py
api_router.include_router(indicators_router, tags=["indicators"])
api_router.include_router(fuzzy_router, tags=["Fuzzy"])
api_router.include_router(ib_router, prefix="/ib", tags=["IB"])
# Temporarily disabled: System endpoints need updating for new architecture
# api_router.include_router(system_router, prefix="/system", tags=["System"])
api_router.include_router(backtesting_router, tags=["Backtesting"])
api_router.include_router(strategies_router, tags=["Strategies"])
api_router.include_router(gap_analysis_router, tags=["Gap Analysis"])
api_router.include_router(training_router, tags=["Training"])
api_router.include_router(models_router, tags=["Models"])
api_router.include_router(operations_router, tags=["Operations"])
# Temporarily disabled while updating multi-timeframe for pure fuzzy
# api_router.include_router(
#     multi_timeframe_decisions_router, tags=["Multi-Timeframe Decisions"]
# )
