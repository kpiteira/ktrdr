"""
API configuration module.

This module defines the configuration for the KTRDR API, with support for
environment variables and different deployment environments.
"""

import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class APIConfig(BaseModel):
    """
    API configuration model with environment variable support.
    
    This model loads configuration from environment variables with sensible
    defaults for local development.
    """
    # API metadata
    title: str = Field(
        default="KTRDR API",
        description="API title displayed in documentation"
    )
    description: str = Field(
        default="REST API for KTRDR trading system",
        description="API description displayed in documentation"
    )
    version: str = Field(
        default="1.0.5.2",
        description="API version"
    )
    
    # Server configuration
    host: str = Field(
        default="127.0.0.1",
        description="Host to bind the API server"
    )
    port: int = Field(
        default=8000,
        description="Port to bind the API server"
    )
    reload: bool = Field(
        default=True,
        description="Enable/disable auto-reload for development"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level for the API server"
    )
    
    # Environment
    environment: str = Field(
        default="development",
        description="Deployment environment (development, staging, production)"
    )
    
    # API routing
    api_prefix: str = Field(
        default="/api/v1",
        description="API version prefix for all endpoints"
    )
    
    # CORS configuration
    cors_origins: List[str] = Field(
        default=["*"],
        description="List of allowed origins for CORS"
    )
    cors_allow_credentials: bool = Field(
        default=True,
        description="Allow credentials for CORS requests"
    )
    cors_allow_methods: List[str] = Field(
        default=["*"],
        description="List of allowed HTTP methods for CORS"
    )
    cors_allow_headers: List[str] = Field(
        default=["*"],
        description="List of allowed HTTP headers for CORS"
    )
    cors_max_age: int = Field(
        default=600,
        description="Maximum age (in seconds) of CORS preflight responses to cache"
    )
    
    # Use ConfigDict instead of Config class
    model_config = ConfigDict(
        env_prefix="KTRDR_API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
        json_schema_extra={
            "example": {
                "title": "KTRDR API",
                "version": "1.0.5",
                "host": "127.0.0.1",
                "port": 8000
            }
        }
    )
    
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        """Parse CORS origins from string to list if provided as a string."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
    
    @field_validator("cors_allow_methods", mode="before")
    @classmethod
    def parse_cors_methods(cls, v: Any) -> List[str]:
        """Parse CORS methods from string to list if provided as a string."""
        if isinstance(v, str):
            return [method.strip() for method in v.split(",") if method.strip()]
        return v
    
    @field_validator("cors_allow_headers", mode="before")
    @classmethod
    def parse_cors_headers(cls, v: Any) -> List[str]:
        """Parse CORS headers from string to list if provided as a string."""
        if isinstance(v, str):
            return [header.strip() for header in v.split(",") if header.strip()]
        return v
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate that the environment is one of the allowed values."""
        allowed_environments = ["development", "staging", "production"]
        if v.lower() not in allowed_environments:
            raise ValueError(f"Environment must be one of {allowed_environments}")
        return v.lower()
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate that the log level is one of the allowed values."""
        allowed_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_log_levels:
            raise ValueError(f"Log level must be one of {allowed_log_levels}")
        return v.upper()
        
    # For testing purposes, add a method to create a manually configured instance
    @classmethod
    def from_env(cls, env_vars: Dict[str, str]) -> "APIConfig":
        """
        Create a config instance with specific environment variables.
        
        This method manually creates and configures an instance for testing
        without relying on actual environment variables.
        
        Args:
            env_vars: A dictionary of environment variables to use for configuration
        
        Returns:
            An APIConfig instance with the specified configuration
        """
        # Create a fresh instance with default values
        instance = cls()
        
        # Map environment variables to their respective attributes
        attribute_map = {
            "KTRDR_API_TITLE": "title",
            "KTRDR_API_DESCRIPTION": "description",
            "KTRDR_API_VERSION": "version",
            "KTRDR_API_HOST": "host",
            "KTRDR_API_PORT": "port",
            "KTRDR_API_RELOAD": "reload",
            "KTRDR_API_LOG_LEVEL": "log_level",
            "KTRDR_API_ENVIRONMENT": "environment",
            "KTRDR_API_API_PREFIX": "api_prefix",
            "KTRDR_API_CORS_ORIGINS": "cors_origins",
            "KTRDR_API_CORS_ALLOW_CREDENTIALS": "cors_allow_credentials",
            "KTRDR_API_CORS_ALLOW_METHODS": "cors_allow_methods",
            "KTRDR_API_CORS_ALLOW_HEADERS": "cors_allow_headers",
            "KTRDR_API_CORS_MAX_AGE": "cors_max_age",
        }
        
        # Process each environment variable and set the corresponding attribute
        for env_name, value in env_vars.items():
            if env_name in attribute_map:
                attr_name = attribute_map[env_name]
                
                # Convert values to appropriate types
                if attr_name == "port" or attr_name == "cors_max_age":
                    setattr(instance, attr_name, int(value))
                elif attr_name == "reload" or attr_name == "cors_allow_credentials":
                    # Convert string to boolean
                    if value.lower() in ("true", "1", "yes"):
                        setattr(instance, attr_name, True)
                    elif value.lower() in ("false", "0", "no"):
                        setattr(instance, attr_name, False)
                elif attr_name == "cors_origins":
                    # Apply the validator directly
                    setattr(instance, attr_name, instance.parse_cors_origins(value))
                elif attr_name == "cors_allow_methods":
                    # Apply the validator directly
                    setattr(instance, attr_name, instance.parse_cors_methods(value))
                elif attr_name == "cors_allow_headers":
                    # Apply the validator directly
                    setattr(instance, attr_name, instance.parse_cors_headers(value))
                elif attr_name == "environment":
                    # Validate and set environment
                    if value.lower() not in ["development", "staging", "production"]:
                        raise ValueError(f"Environment must be one of ['development', 'staging', 'production']")
                    setattr(instance, attr_name, value.lower())
                elif attr_name == "log_level":
                    # Validate and set log level
                    if value.upper() not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
                        raise ValueError(f"Log level must be one of ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']")
                    setattr(instance, attr_name, value.upper())
                else:
                    setattr(instance, attr_name, value)
        
        return instance