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
from ktrdr.api.services.fuzzy_service import FuzzyService
from ktrdr.api.services.operations_service import (
    get_operations_service,
    OperationsService,
)
from ktrdr.data.data_manager import DataManager


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


# Fuzzy service dependency
def get_fuzzy_service() -> FuzzyService:
    """
    Dependency for providing the fuzzy service.

    Returns:
        FuzzyService: Initialized fuzzy service instance
    """
    return FuzzyService()


# Data manager dependency
def get_data_manager() -> DataManager:
    """
    Dependency for providing the data manager.

    Returns:
        DataManager: Initialized data manager instance with IB integration
    """
    return DataManager()


# Operations service dependency
def get_operations_service_dep() -> OperationsService:
    """
    Dependency for providing the operations service.

    Returns:
        OperationsService: Global operations service instance
    """
    return get_operations_service()


# Define common dependencies with annotations for usage in route functions
ConfigDep = Annotated[APIConfig, Depends(get_api_config)]
DataServiceDep = Annotated[DataService, Depends(get_data_service)]
IndicatorServiceDep = Annotated[IndicatorService, Depends(get_indicator_service)]
FuzzyServiceDep = Annotated[FuzzyService, Depends(get_fuzzy_service)]
DataManagerDep = Annotated[DataManager, Depends(get_data_manager)]
OperationsServiceDep = Annotated[OperationsService, Depends(get_operations_service_dep)]
