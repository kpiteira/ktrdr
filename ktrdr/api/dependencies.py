"""
API dependencies module.

This module provides dependency injection functions for FastAPI routes.
These dependencies are used to provide services and configuration to API endpoints.
"""
from typing import Annotated
from fastapi import Depends

from ktrdr.api.config import APIConfig


def get_api_config() -> APIConfig:
    """
    Dependency for providing the API configuration.
    
    Returns:
        APIConfig: The current API configuration
    """
    return APIConfig()


# Define common dependencies with annotations for usage in route functions
ConfigDep = Annotated[APIConfig, Depends(get_api_config)]

# As additional services are implemented, add them as dependencies here
# Example:
# def get_data_service() -> DataService:
#     """Dependency for providing the data service."""
#     return DataService()
# 
# DataServiceDep = Annotated[DataService, Depends(get_data_service)]