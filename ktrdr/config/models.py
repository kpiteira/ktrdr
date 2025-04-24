"""
Pydantic models for configuration validation.

This module defines the structure and validation rules for KTRDR configuration.
"""

from pathlib import Path
from typing import Optional, List, Any, Dict, Union
from pydantic import BaseModel, Field, field_validator


class DataConfig(BaseModel):
    """Configuration settings for data handling."""
    
    directory: str = Field(..., description="Directory path for data files")
    default_format: str = Field("csv", description="Default file format for data")
    
    @field_validator("directory")
    @classmethod
    def directory_must_exist(cls, v: str) -> str:
        """Validate that the directory exists or can be created."""
        path = Path(v)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        elif not path.is_dir():
            raise ValueError(f"Path exists but is not a directory: {v}")
        return str(path.absolute())


class LoggingConfig(BaseModel):
    """Configuration settings for logging."""
    
    level: str = Field("INFO", description="Default logging level")
    file_path: Optional[str] = Field(None, description="Path to log file")
    console_output: bool = Field(True, description="Whether to output logs to console")
    
    @field_validator("level")
    @classmethod
    def valid_log_level(cls, v: str) -> str:
        """Validate that the logging level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(f"Invalid logging level: {v}. Must be one of {valid_levels}")
        return upper_v


class SecurityConfig(BaseModel):
    """Configuration settings for security features."""
    
    credential_providers: List[str] = Field(
        default_factory=list,
        description="List of credential providers to initialize"
    )
    validate_user_input: bool = Field(
        True, 
        description="Whether to validate user-provided parameters"
    )
    sensitive_file_patterns: List[str] = Field(
        default_factory=lambda: ["*.key", "*.pem", "*.env", "*_credentials*"],
        description="Patterns for files that should be protected"
    )


class IndicatorConfig(BaseModel):
    """Configuration for a technical indicator."""
    
    type: str = Field(..., description="The type/class of indicator")
    name: Optional[str] = Field(None, description="Custom name for the indicator")
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for indicator initialization"
    )
    
    @field_validator("type")
    @classmethod
    def validate_indicator_type(cls, v: str) -> str:
        """Validate that the indicator type is not empty."""
        v = v.strip()
        if not v:
            raise ValueError("Indicator type cannot be empty")
        return v


class IndicatorsConfig(BaseModel):
    """Configuration for all indicators."""
    
    indicators: List[IndicatorConfig] = Field(
        default_factory=list,
        description="List of indicator configurations"
    )


class KtrdrConfig(BaseModel):
    """Root configuration model for KTRDR."""
    
    data: DataConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    debug: bool = Field(False, description="Global debug flag")
    indicators: Optional[IndicatorsConfig] = Field(None, description="Indicator configurations")
