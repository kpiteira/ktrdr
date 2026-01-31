"""
KTRDR Configuration Package - Configuration management for the KTRDR package.

This package provides access to configuration settings and metadata with
environment-specific overrides and environment variable support.
"""

from .. import metadata
from .deprecation import DEPRECATED_NAMES, warn_deprecated_env_vars
from .loader import ConfigLoader
from .settings import (
    APISettings,
    AuthSettings,
    DatabaseSettings,
    LoggingSettings,
    ObservabilitySettings,
    clear_settings_cache,
    deprecated_field,
    get_api_settings,
    get_auth_settings,
    get_db_settings,
    get_logging_settings,
    get_observability_settings,
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
    # Settings classes (M1 + M2)
    "APISettings",
    "AuthSettings",
    "DatabaseSettings",
    "LoggingSettings",
    "ObservabilitySettings",
    # Cached getters (M1 + M2)
    "get_api_settings",
    "get_auth_settings",
    "get_db_settings",
    "get_logging_settings",
    "get_observability_settings",
    # Utilities
    "clear_settings_cache",
    "deprecated_field",
    # Validation (M1.2)
    "validate_all",
    "detect_insecure_defaults",
    # Deprecation (M1.3)
    "warn_deprecated_env_vars",
    "DEPRECATED_NAMES",
]
