"""
Base configuration classes and utilities.

Provides the foundation for the configuration system with validation,
environment variable support, and configuration inheritance.
"""

import os
from typing import Any, Dict, Optional, Type, TypeVar, Union, cast
from dataclasses import dataclass, field, fields
from pathlib import Path

from ktrdr import get_logger

logger = get_logger(__name__)

T = TypeVar('T', bound='BaseConfig')


@dataclass
class BaseConfig:
    """Base configuration class with validation and environment support"""
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization"""
        self._validate()
    
    def _validate(self) -> None:
        """Validate configuration values - override in subclasses"""
        pass
    
    @classmethod
    def from_dict(cls: Type[T], config_dict: Dict[str, Any]) -> T:
        """Create configuration from dictionary"""
        # Filter dict to only include fields that exist in the dataclass
        field_names = {f.name for f in fields(cls)}
        filtered_dict = {k: v for k, v in config_dict.items() if k in field_names}
        return cls(**filtered_dict)
    
    @classmethod
    def from_env(cls: Type[T], prefix: str = "") -> T:
        """Create configuration from environment variables"""
        config_dict = {}
        
        for field_info in fields(cls):
            env_name = f"{prefix}{field_info.name.upper()}"
            env_value = os.getenv(env_name)
            
            if env_value is not None:
                # Convert string env value to appropriate type
                field_type = field_info.type
                
                try:
                    converted_value: Any
                    if field_type == bool:
                        converted_value = env_value.lower() in ('true', '1', 'yes', 'on')
                    elif field_type == int:
                        converted_value = int(env_value)
                    elif field_type == float:
                        converted_value = float(env_value)
                    else:
                        converted_value = env_value
                    
                    config_dict[field_info.name] = converted_value
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to convert environment variable {env_name}={env_value} to type {field_type}: {e}")
        
        return cls.from_dict(config_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        result = {}
        for field_info in fields(self):
            value = getattr(self, field_info.name)
            if isinstance(value, BaseConfig):
                result[field_info.name] = value.to_dict()
            else:
                result[field_info.name] = value
        return result
    
    def update(self: T, **kwargs: Any) -> T:
        """Create new configuration with updated values"""
        current_dict = self.to_dict()
        current_dict.update(kwargs)
        return self.__class__.from_dict(current_dict)


class ConfigurationManager:
    """
    Configuration manager for the research agents system.
    
    Provides centralized configuration management with support for:
    - Environment variables
    - Configuration files
    - Runtime overrides
    - Configuration validation
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path(__file__).parent
        self._configs: Dict[str, BaseConfig] = {}
        self._environment = os.getenv("RESEARCH_AGENTS_ENV", "development")
        
        logger.info(f"Configuration manager initialized for environment: {self._environment}")
    
    def register_config(self, name: str, config: BaseConfig) -> None:
        """Register a configuration object"""
        self._configs[name] = config
        logger.debug(f"Registered configuration: {name}")
    
    def get_config(self, name: str) -> Optional[BaseConfig]:
        """Get a registered configuration"""
        return self._configs.get(name)
    
    def load_from_file(self, name: str, config_class: Type[T], filename: str) -> T:
        """Load configuration from file"""
        config_path = self.config_dir / filename
        
        if config_path.exists():
            try:
                import json
                with open(config_path, 'r') as f:
                    config_dict = json.load(f)
                
                config = config_class.from_dict(config_dict)
                self.register_config(name, config)
                
                logger.info(f"Loaded configuration '{name}' from {config_path}")
                return config
                
            except Exception as e:
                logger.error(f"Failed to load configuration from {config_path}: {e}")
                raise
        else:
            logger.warning(f"Configuration file not found: {config_path}")
            # Return default configuration
            config = config_class()
            self.register_config(name, config)
            return config
    
    def save_to_file(self, name: str, filename: str) -> None:
        """Save configuration to file"""
        config = self.get_config(name)
        if not config:
            raise ValueError(f"Configuration '{name}' not found")
        
        config_path = self.config_dir / filename
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            import json
            with open(config_path, 'w') as f:
                json.dump(config.to_dict(), f, indent=2)
            
            logger.info(f"Saved configuration '{name}' to {config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration to {config_path}: {e}")
            raise
    
    def get_environment_config(self, config_class: Type[T], prefix: str = "RESEARCH_") -> T:
        """Get configuration from environment variables"""
        return config_class.from_env(prefix)
    
    def merge_configs(self, base_config: T, override_config: Optional[Dict[str, Any]] = None) -> T:
        """Merge base configuration with overrides"""
        if not override_config:
            return base_config
        
        return base_config.update(**override_config)


# Global configuration manager instance
config_manager = ConfigurationManager()