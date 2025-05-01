"""
API dependencies module.

This module provides dependency injection functions for FastAPI routes.
These dependencies are used to provide services and configuration to API endpoints.
"""
from typing import Annotated
from fastapi import Depends

from ktrdr.api.config import APIConfig
from ktrdr.api.services.data_service import DataService
from ktrdr.api.services.indicator_service import IndicatorService


def get_api_config() -> APIConfig:
    """
    Dependency for providing the API configuration.
    
    Returns:
        APIConfig: The current API configuration
    """
    return APIConfig()


# Data service dependency
def get_data_service() -> DataService:
    """
    Dependency for providing the data service.
    
    The service is instantiated per-request to ensure fresh configurations
    are applied and resources are properly managed.
    
    Returns:
        DataService: Initialized data service instance
    """
    return DataService()


# Indicator service dependency
def get_indicator_service() -> IndicatorService:
    """
    Dependency for providing the indicator service.
    
    Returns:
        IndicatorService: Initialized indicator service instance
    """
    return IndicatorService()


# Define common dependencies with annotations for usage in route functions
ConfigDep = Annotated[APIConfig, Depends(get_api_config)]
DataServiceDep = Annotated[DataService, Depends(get_data_service)]
IndicatorServiceDep = Annotated[IndicatorService, Depends(get_indicator_service)]