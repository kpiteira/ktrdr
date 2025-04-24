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

# Import the new logging system
from ktrdr import get_logger, log_entry_exit, log_error

from ktrdr.config.models import KtrdrConfig
from ktrdr.config.validation import InputValidator, sanitize_parameter
from ktrdr.errors import (
    ConfigurationError, 
    MissingConfigurationError, 
    InvalidConfigurationError, 
    ConfigurationFileError,
    ErrorHandler,
    retry_with_backoff,
    fallback,
    FallbackStrategy
)

T = TypeVar('T', bound=BaseModel)

# Get module logger
logger = get_logger(__name__)


class ConfigLoader:
    """Loads and validates configuration from YAML files."""
    
    def __init__(self) -> None:
        """Initialize the ConfigLoader."""
        pass
    
    @retry_with_backoff(retryable_exceptions=[IOError, OSError], logger=logger)
    @ErrorHandler.with_error_handling(logger=logger)
    @log_entry_exit(logger=logger)
    def load(self, config_path: Union[str, Path], model_type: Type[T] = KtrdrConfig) -> T:
        """
        Load a YAML configuration file and validate it against a Pydantic model.
        
        Args:
            config_path: Path to the YAML configuration file
            model_type: Pydantic model class to validate against (default: KtrdrConfig)
            
        Returns:
            A validated configuration object of type model_type
            
        Raises:
            ConfigurationFileError: If the file cannot be found or accessed
            InvalidConfigurationError: If the YAML format is invalid
            ConfigurationError: If validation fails or another error occurs
        """
        # Validate and sanitize the config path to prevent path traversal attacks
        try:
            # Convert to string if it's a Path object
            path_str = str(config_path) if isinstance(config_path, Path) else config_path
            
            # Validate the path string
            path_str = InputValidator.validate_string(
                path_str,
                min_length=1,
                max_length=1024
            )
            
            # Sanitize the path
            path_str = sanitize_parameter("config_path", path_str)
            
            # Convert back to Path object
            config_path = Path(path_str)
            
            # Check if path is absolute
            if not config_path.is_absolute():
                # Convert to absolute path relative to current working directory
                config_path = Path.cwd() / config_path
                
        except ValidationError as e:
            raise ConfigurationError(
                message=f"Invalid configuration path: {e}",
                error_code="CONF-InvalidPath",
                details={"path": str(config_path), "error": str(e)}
            )
        
        # Check if file exists
        if not config_path.exists():
            raise ConfigurationFileError(
                message=f"Configuration file not found: {config_path}",
                error_code="CONF-FileNotFound",
                details={"path": str(config_path)}
            )
            
        # Load YAML file
        try:
            with open(config_path, 'r') as file:
                config_dict = yaml.safe_load(file)
                
            # Handle empty file case
            if config_dict is None:
                logger.warning(f"Empty configuration file: {config_path}")
                config_dict = {}
                
            # Validate with Pydantic model
            try:
                config_obj = model_type(**config_dict)
                logger.info(f"Successfully loaded configuration from {config_path}")
                return config_obj
            except ValidationError as e:
                raise InvalidConfigurationError(
                    message=f"Configuration validation failed: {e}",
                    error_code="CONF-ValidationFailed",
                    details={"validation_errors": e.errors()}
                )
                
        except yaml.YAMLError as e:
            raise InvalidConfigurationError(
                message=f"Invalid YAML format in {config_path}: {e}",
                error_code="CONF-InvalidYaml",
                details={"yaml_error": str(e)}
            )
    
    @fallback(strategy=FallbackStrategy.DEFAULT_VALUE, logger=logger)
    @log_entry_exit(logger=logger, log_result=True)
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
            MissingConfigurationError: If no valid configuration path is available
            ConfigurationError: If loading fails for other reasons
        """
        # Validate env_var against injection attempts
        try:
            env_var = InputValidator.validate_string(
                env_var,
                min_length=1,
                max_length=100,
                pattern=r'^[A-Za-z0-9_]+$'  # Allow only alphanumeric and underscore
            )
        except ValidationError as e:
            raise ConfigurationError(
                message=f"Invalid environment variable name: {e}",
                error_code="CONF-InvalidEnvVar",
                details={"env_var": env_var, "error": str(e)}
            )
            
        config_path = os.environ.get(env_var)
        
        # If env var not set, use default path
        if not config_path and default_path is None:
            raise MissingConfigurationError(
                message=f"Environment variable {env_var} not set and no default path provided",
                error_code="CONF-MissingEnvVar",
                details={"env_var": env_var}
            )
        
        path_to_use = config_path if config_path else default_path
        logger.info(f"Loading configuration from {path_to_use} (from env var: {config_path is not None})")
        try:
            return self.load(path_to_use, model_type)
        except ConfigurationError as e:
            # Use log_error from our new logging system
            log_error(e, logger=logger, extra={"path": str(path_to_use)})
            
            if config_path and default_path:
                # Try loading from default path as fallback if we were using env var
                logger.warning(f"Attempting to load from default path: {default_path}")
                return self.load(default_path, model_type)
            raise
