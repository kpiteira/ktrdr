"""
KTRDR Configuration Package - Configuration management for the KTRDR package.

This package provides access to configuration settings and metadata with
environment-specific overrides and environment variable support.
"""

from .. import metadata
from .deprecation import DEPRECATED_NAMES, warn_deprecated_env_vars
from .loader import ConfigLoader
from .settings import (
    DatabaseSettings,
    clear_settings_cache,
    deprecated_field,
    get_db_settings,
)
from .strategy_validator import StrategyValidator
from .validation import (
    InputValidator,
    detect_insecure_defaults,
    sanitize_parameter,
    sanitize_parameters,
    validate_all,
)

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
    # Validation (M1.2)
    "validate_all",
    "detect_insecure_defaults",
    # Deprecation (M1.3)
    "warn_deprecated_env_vars",
    "DEPRECATED_NAMES",
]
