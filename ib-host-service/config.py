"""
Configuration for IB Connector Host Service

Imports and re-exports existing IB configuration from ktrdr.config
to maintain consistency with existing settings.
"""

import os
from typing import Optional

# Import existing IB configuration
try:
    from ktrdr.config.ib_config import (
        IB_HOST,
        IB_PORT, 
        IB_CLIENT_ID_BASE,
        IB_CONNECTION_TIMEOUT,
        IB_REQUEST_TIMEOUT,
        IB_MAX_RETRIES
    )
except ImportError:
    # Fallback defaults if config not available
    IB_HOST = os.getenv("IB_HOST", "localhost")
    IB_PORT = int(os.getenv("IB_PORT", "4002"))
    IB_CLIENT_ID_BASE = int(os.getenv("IB_CLIENT_ID_BASE", "100"))
    IB_CONNECTION_TIMEOUT = int(os.getenv("IB_CONNECTION_TIMEOUT", "10"))
    IB_REQUEST_TIMEOUT = int(os.getenv("IB_REQUEST_TIMEOUT", "30"))
    IB_MAX_RETRIES = int(os.getenv("IB_MAX_RETRIES", "3"))

# Host service specific configuration
HOST_SERVICE_HOST = os.getenv("HOST_SERVICE_HOST", "127.0.0.1")
HOST_SERVICE_PORT = int(os.getenv("HOST_SERVICE_PORT", "5001"))

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

class IbConfig:
    """IB connection configuration."""
    
    host: str = IB_HOST
    port: int = IB_PORT
    client_id_base: int = IB_CLIENT_ID_BASE
    connection_timeout: int = IB_CONNECTION_TIMEOUT
    request_timeout: int = IB_REQUEST_TIMEOUT
    max_retries: int = IB_MAX_RETRIES

class HostServiceConfig:
    """Host service configuration."""
    
    host: str = HOST_SERVICE_HOST
    port: int = HOST_SERVICE_PORT
    log_level: str = LOG_LEVEL