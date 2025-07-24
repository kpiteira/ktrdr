"""
Configuration for Training Host Service

Uses YAML-based configuration consistent with KTRDR patterns.
Imports existing training configuration and extends with host service settings.
"""

from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

# Import existing ktrdr config utilities
from ktrdr.config.loader import ConfigLoader

# Define host service specific configuration model
class HostServiceConfig(BaseModel):
    """Configuration for Training Host Service."""
    
    host: str = Field(default="127.0.0.1", description="Host to bind service to")
    port: int = Field(default=5002, description="Port to bind service to")
    log_level: str = Field(default="INFO", description="Logging level")
    max_concurrent_sessions: int = Field(default=3, description="Maximum concurrent training sessions")
    session_timeout_minutes: int = Field(default=60, description="Training session timeout in minutes")
    
    class Config:
        extra = "forbid"

class TrainingHostServiceConfig(BaseModel):
    """Complete configuration for Training Host Service."""
    
    host_service: HostServiceConfig = Field(default_factory=HostServiceConfig)
    
    class Config:
        extra = "allow"  # Allow extra fields for flexibility

# Configuration loader instance
_config_loader = ConfigLoader()
_service_config: Optional[TrainingHostServiceConfig] = None

def get_host_service_config() -> TrainingHostServiceConfig:
    """
    Get host service configuration.
    
    Loads from YAML config if available, otherwise uses defaults.
    """
    global _service_config
    if _service_config is None:
        try:
            # Try to load from project config directory
            config_path = Path(__file__).parent.parent / "config" / "training_host_service.yaml"
            if config_path.exists():
                _service_config = _config_loader.load(config_path, TrainingHostServiceConfig)
            else:
                # Use defaults if no config file
                _service_config = TrainingHostServiceConfig()
        except Exception:
            # Fallback to defaults on any error
            _service_config = TrainingHostServiceConfig()
    
    return _service_config

def get_ktrdr_training_config():
    """Get training configuration using existing ktrdr config system."""
    # TODO: Import from ktrdr.config.training_config when available
    # For now, return basic configuration
    return {
        "gpu_enabled": True,
        "mixed_precision": True,
        "max_epochs": 100,
        "early_stopping": True
    }