"""
KTRDR Configuration Package - Configuration management for the KTRDR package.

This package provides access to configuration settings with environment-specific
overrides and environment variable support.
"""

from .deprecation import DEPRECATED_NAMES, warn_deprecated_env_vars
from .loader import ConfigLoader
from .settings import (
    AgentGateSettings,
    # M5 Settings classes
    AgentSettings,
    ApiServiceSettings,
    # M1 + M2 Settings classes
    APISettings,
    AuthSettings,
    DatabaseSettings,
    DataSettings,
    LoggingSettings,
    ObservabilitySettings,
    # M4 Settings classes
    WorkerSettings,
    # Utilities
    clear_settings_cache,
    deprecated_field,
    get_agent_gate_settings,
    # M5 Getters
    get_agent_settings,
    get_api_service_settings,
    # M1 + M2 Getters
    get_api_settings,
    get_auth_settings,
    get_data_settings,
    get_db_settings,
    get_logging_settings,
    get_observability_settings,
    # M4 Getters
    get_worker_settings,
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
    # Settings classes (M4)
    "WorkerSettings",
    "ApiServiceSettings",
    # Settings classes (M5)
    "AgentSettings",
    "AgentGateSettings",
    "DataSettings",
    # Cached getters (M1 + M2)
    "get_api_settings",
    "get_auth_settings",
    "get_db_settings",
    "get_logging_settings",
    "get_observability_settings",
    # Cached getters (M4)
    "get_worker_settings",
    "get_api_service_settings",
    # Cached getters (M5)
    "get_agent_settings",
    "get_agent_gate_settings",
    "get_data_settings",
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
