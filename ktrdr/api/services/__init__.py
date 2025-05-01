"""
API services package.

This package contains service adapters that connect the API layer 
with core KTRDR modules.
"""

# Export the base service interface
from ktrdr.api.services.base import BaseService

# Public API
__all__ = [
    "BaseService",
]