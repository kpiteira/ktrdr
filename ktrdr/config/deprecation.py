"""
Deprecation module for KTRDR configuration.

This module provides utilities to detect and warn about deprecated
environment variable names that are still supported for backward
compatibility.

Deprecated name mappings:
- M1: DB_* → KTRDR_DB_* (database settings)
- M2: OTLP_ENDPOINT → KTRDR_OTEL_OTLP_ENDPOINT (observability)
- M3: IB_* → KTRDR_IB_* (IB settings)
- M3: USE_IB_HOST_SERVICE → KTRDR_IB_HOST_ENABLED
- M3: USE_TRAINING_HOST_SERVICE → KTRDR_TRAINING_HOST_ENABLED
"""

import os
import warnings

# Mapping of deprecated env var names to their new names.
# The deprecated names are still supported but emit warnings at startup.
DEPRECATED_NAMES: dict[str, str] = {
    # M1: Database settings
    "DB_HOST": "KTRDR_DB_HOST",
    "DB_PORT": "KTRDR_DB_PORT",
    "DB_NAME": "KTRDR_DB_NAME",
    "DB_USER": "KTRDR_DB_USER",
    "DB_PASSWORD": "KTRDR_DB_PASSWORD",
    "DB_ECHO": "KTRDR_DB_ECHO",
    # M2: Observability settings
    "OTLP_ENDPOINT": "KTRDR_OTEL_OTLP_ENDPOINT",
    # M3: IB settings
    "IB_HOST": "KTRDR_IB_HOST",
    "IB_PORT": "KTRDR_IB_PORT",
    "IB_CLIENT_ID": "KTRDR_IB_CLIENT_ID",
    "IB_TIMEOUT": "KTRDR_IB_TIMEOUT",
    "IB_READONLY": "KTRDR_IB_READONLY",
    "IB_RATE_LIMIT": "KTRDR_IB_RATE_LIMIT",
    "IB_RATE_PERIOD": "KTRDR_IB_RATE_PERIOD",
    "IB_MAX_RETRIES": "KTRDR_IB_MAX_RETRIES",
    "IB_RETRY_DELAY": "KTRDR_IB_RETRY_BASE_DELAY",
    "IB_RETRY_MAX_DELAY": "KTRDR_IB_RETRY_MAX_DELAY",
    "IB_PACING_DELAY": "KTRDR_IB_PACING_DELAY",
    "IB_MAX_REQUESTS_10MIN": "KTRDR_IB_MAX_REQUESTS_PER_10MIN",
    # M3: IB host service settings
    "USE_IB_HOST_SERVICE": "KTRDR_IB_HOST_ENABLED",
    # M3: Training host service settings
    "USE_TRAINING_HOST_SERVICE": "KTRDR_TRAINING_HOST_ENABLED",
}


def warn_deprecated_env_vars() -> list[str]:
    """Check os.environ for deprecated env var names and emit warnings.

    This function should be called at application startup to alert users
    that they are using deprecated environment variable names.

    For each deprecated env var found in os.environ:
    - Emits a DeprecationWarning with migration guidance
    - Adds the name to the returned list

    Returns:
        List of deprecated env var names that were found in the environment.
        Empty list if no deprecated vars are set.

    Example:
        >>> # With DB_PASSWORD set in environment
        >>> found = warn_deprecated_env_vars()
        >>> print(found)
        ['DB_PASSWORD']
        >>> # Warning: Environment variable 'DB_PASSWORD' is deprecated.
        >>> #          Use 'KTRDR_DB_PASSWORD' instead.
    """
    found: list[str] = []

    for old_name, new_name in DEPRECATED_NAMES.items():
        if old_name in os.environ:
            found.append(old_name)
            warnings.warn(
                f"Environment variable '{old_name}' is deprecated. "
                f"Use '{new_name}' instead.",
                DeprecationWarning,
                stacklevel=2,
            )

    return found
