"""
API dependencies module.

This module provides dependency injection functions for FastAPI routes.
These dependencies are used to provide services and configuration to API endpoints.
"""

from typing import Annotated, Optional

from fastapi import Depends

from ktrdr.api.config import APIConfig
from ktrdr.api.services.data_service import DataService
from ktrdr.api.services.fuzzy_service import FuzzyService
from ktrdr.api.services.indicator_service import IndicatorService
from ktrdr.api.services.operations_service import (
    OperationsService,
    get_operations_service,
)
from ktrdr.checkpoint.service import CheckpointService
from ktrdr.data.acquisition.acquisition_service import DataAcquisitionService


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


# Data acquisition service dependency (singleton)
_acquisition_service: Optional[DataAcquisitionService] = None


def get_acquisition_service() -> DataAcquisitionService:
    """
    Dependency for providing the data acquisition service (singleton).

    Returns same instance across requests to maintain internal state
    and avoid multiple service initializations.

    Returns:
        DataAcquisitionService: Singleton data acquisition service instance
    """
    global _acquisition_service
    if _acquisition_service is None:
        _acquisition_service = DataAcquisitionService()
    return _acquisition_service


# Operations service dependency
def get_operations_service_dep() -> OperationsService:
    """
    Dependency for providing the operations service.

    Returns:
        OperationsService: Global operations service instance
    """
    return get_operations_service()


# Checkpoint service dependency (singleton)
_checkpoint_service: Optional[CheckpointService] = None


def get_checkpoint_service() -> CheckpointService:
    """
    Dependency for providing the checkpoint service (singleton).

    Returns same instance across requests to maintain database connection pool.

    Returns:
        CheckpointService: Singleton checkpoint service instance
    """
    global _checkpoint_service
    if _checkpoint_service is None:
        _checkpoint_service = CheckpointService()
    return _checkpoint_service


# Define common dependencies with annotations for usage in route functions
ConfigDep = Annotated[APIConfig, Depends(get_api_config)]
DataServiceDep = Annotated[DataService, Depends(get_data_service)]
IndicatorServiceDep = Annotated[IndicatorService, Depends(get_indicator_service)]
FuzzyServiceDep = Annotated[FuzzyService, Depends(get_fuzzy_service)]
AcquisitionServiceDep = Annotated[
    DataAcquisitionService, Depends(get_acquisition_service)
]
OperationsServiceDep = Annotated[OperationsService, Depends(get_operations_service_dep)]
CheckpointServiceDep = Annotated[CheckpointService, Depends(get_checkpoint_service)]
