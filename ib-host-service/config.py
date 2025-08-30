"""
Configuration for IB Connector Host Service

Uses YAML-based configuration consistent with KTRDR patterns.
Imports existing IB configuration and extends with host service settings.
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from ktrdr.config.ib_config import IbConfig as KtrdrIbConfig

# Import existing ktrdr config utilities
from ktrdr.config.loader import ConfigLoader


# Define host service specific configuration model
class HostServiceConfig(BaseModel):
    """Configuration for IB Connector Host Service."""

    host: str = Field(default="127.0.0.1", description="Host to bind service to")
    port: int = Field(default=5001, description="Port to bind service to")
    log_level: str = Field(default="INFO", description="Logging level")

    class Config:
        extra = "forbid"


class IbHostServiceConfig(BaseModel):
    """Complete configuration for IB Host Service."""

    host_service: HostServiceConfig = Field(default_factory=HostServiceConfig)

    class Config:
        extra = "forbid"


# Configuration loader instance
_config_loader = ConfigLoader()
_service_config: Optional[IbHostServiceConfig] = None


def get_host_service_config() -> IbHostServiceConfig:
    """
    Get host service configuration.

    Loads from YAML config if available, otherwise uses defaults.
    """
    global _service_config
    if _service_config is None:
        try:
            # Try to load from project config directory
            config_path = (
                Path(__file__).parent.parent / "config" / "ib_host_service.yaml"
            )
            if config_path.exists():
                _service_config = _config_loader.load(config_path, IbHostServiceConfig)
            else:
                # Use defaults if no config file
                _service_config = IbHostServiceConfig()
        except Exception:
            # Fallback to defaults on any error
            _service_config = IbHostServiceConfig()

    return _service_config


def get_ktrdr_ib_config() -> KtrdrIbConfig:
    """Get IB configuration using existing ktrdr config system."""
    from ktrdr.config.ib_config import get_ib_config

    return get_ib_config()
