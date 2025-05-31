"""
KTRDR API module.

This module provides the FastAPI-based REST API for the KTRDR trading system.
"""

# Import version from centralized version module
from ktrdr.version import __version__

# Export key API components
from ktrdr.api.main import app, create_application
from ktrdr.api.config import APIConfig

# Public API
__all__ = [
    "app",
    "create_application",
    "APIConfig",
]
