"""
KTRDR Configuration Package - Configuration management for the KTRDR package.

This package provides access to configuration settings and metadata with
environment-specific overrides and environment variable support.
"""

from .. import metadata
from .loader import ConfigLoader
from .settings import (
    DatabaseSettings,
    clear_settings_cache,
    deprecated_field,
    get_db_settings,
)
from .strategy_validator import StrategyValidator
from .validation import InputValidator, sanitize_parameter, sanitize_parameters

__all__ = [
    "metadata",
    "ConfigLoader",
    "InputValidator",
    "sanitize_parameter",
    "sanitize_parameters",
    "StrategyValidator",
    # New config system (M1)
    "DatabaseSettings",
    "get_db_settings",
    "clear_settings_cache",
    "deprecated_field",
]
