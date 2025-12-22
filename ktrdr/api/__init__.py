"""
KTRDR API module.

This module provides the FastAPI-based REST API for the KTRDR trading system.

Note: We deliberately don't import app/create_application here to avoid
circular imports and to keep workers from loading unnecessary modules.
Import directly from ktrdr.api.main instead.
"""

# Import version from centralized version module
from ktrdr.api.config import APIConfig
from ktrdr.version import __version__

# Public API
__all__ = [
    "APIConfig",
]
