"""
Configuration loader for YAML-based settings.

This module provides functionality to load and validate configuration from
YAML files using Pydantic models.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar, Union, cast

import yaml
from pydantic import BaseModel, ValidationError

from ktrdr.config.models import KtrdrConfig

T = TypeVar('T', bound=BaseModel)


class ConfigurationError(Exception):
    """Exception raised for configuration-related errors."""
    pass


class ConfigLoader:
    """Loads and validates configuration from YAML files."""
    
    def __init__(self) -> None:
        """Initialize the ConfigLoader."""
        pass
    
    def load(self, config_path: Union[str, Path], model_type: Type[T] = KtrdrConfig) -> T:
        """
        Load a YAML configuration file and validate it against a Pydantic model.
        
        Args:
            config_path: Path to the YAML configuration file
            model_type: Pydantic model class to validate against (default: KtrdrConfig)
            
        Returns:
            A validated configuration object of type model_type
            
        Raises:
            ConfigurationError: If the file cannot be loaded or validation fails
        """
        try:
            # Convert to Path object if string
            if isinstance(config_path, str):
                config_path = Path(config_path)
                
            # Check if file exists
            if not config_path.exists():
                raise ConfigurationError(f"Configuration file not found: {config_path}")
                
            # Load YAML file
            with open(config_path, 'r') as file:
                config_dict = yaml.safe_load(file)
                
            # Handle empty file case
            if config_dict is None:
                config_dict = {}
                
            # Validate with Pydantic model
            config_obj = model_type(**config_dict)
            return config_obj
            
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML format: {e}")
        except ValidationError as e:
            raise ConfigurationError(f"Configuration validation failed: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")
    
    def load_from_env(
        self, 
        env_var: str = "KTRDR_CONFIG", 
        default_path: Optional[Union[str, Path]] = None,
        model_type: Type[T] = KtrdrConfig
    ) -> T:
        """
        Load configuration from a path specified in an environment variable.
        
        Args:
            env_var: Name of environment variable containing config path
            default_path: Default path to use if environment variable is not set
            model_type: Pydantic model class to validate against
            
        Returns:
            A validated configuration object of type model_type
            
        Raises:
            ConfigurationError: If no valid configuration path is available or loading fails
        """
        config_path = os.environ.get(env_var)
        
        # If env var not set, use default path
        if not config_path and default_path is None:
            raise ConfigurationError(
                f"Environment variable {env_var} not set and no default path provided"
            )
        
        path_to_use = config_path if config_path else default_path
        return self.load(path_to_use, model_type)
