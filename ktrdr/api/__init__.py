"""
KTRDR API module.

This module provides the FastAPI-based REST API for the KTRDR trading system.

Note: We deliberately don't import app/create_application here to avoid
circular imports and to keep workers from loading unnecessary modules.
Import directly from ktrdr.api.main instead.
"""

# Re-export APISettings for backward compatibility
# Note: APIConfig was removed in M2.5 - use APISettings from ktrdr.config.settings
from ktrdr.config.settings import APISettings
from ktrdr.version import __version__

# Public API
__all__ = [
    "APISettings",
]
