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
            raise ValueError(
                f"Invalid logging level: {v}. Must be one of {valid_levels}"
            )
        return upper_v


class SecurityConfig(BaseModel):
    """Configuration settings for security features."""

    credential_providers: List[str] = Field(
        default_factory=list, description="List of credential providers to initialize"
    )
    validate_user_input: bool = Field(
        True, description="Whether to validate user-provided parameters"
    )
    sensitive_file_patterns: List[str] = Field(
        default_factory=lambda: ["*.key", "*.pem", "*.env", "*_credentials*"],
        description="Patterns for files that should be protected",
    )


class IndicatorConfig(BaseModel):
    """Configuration for a technical indicator."""

    type: str = Field(..., description="The type/class of indicator")
    name: Optional[str] = Field(None, description="Custom name for the indicator")
    params: Dict[str, Any] = Field(
        default_factory=dict, description="Parameters for indicator initialization"
    )

    @field_validator("type")
    @classmethod
    def validate_indicator_type(cls, v: str) -> str:
        """Validate that the indicator type is not empty."""
        v = v.strip()
        if not v:
            raise ValueError("Indicator type cannot be empty")
        return v


class TimeframeIndicatorConfig(BaseModel):
    """Configuration for indicators on a specific timeframe."""
    
    timeframe: str = Field(..., description="Timeframe identifier (e.g., '1h', '4h', '1d')")
    indicators: List[IndicatorConfig] = Field(
        default_factory=list, description="List of indicator configurations for this timeframe"
    )
    enabled: bool = Field(True, description="Whether this timeframe is enabled")
    weight: float = Field(1.0, description="Weight for this timeframe in decision making")
    
    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        """Validate timeframe format."""
        v = v.strip()
        if not v:
            raise ValueError("Timeframe cannot be empty")
        
        # Common timeframe patterns
        valid_patterns = [
            r'^\d+[smhDwM]$',  # 1m, 5m, 1h, 4h, 1D, 1w, 1M
            r'^\d+(min|hour|day|week|month)s?$',  # 1min, 5mins, 1hour, etc.
        ]
        
        import re
        if not any(re.match(pattern, v, re.IGNORECASE) for pattern in valid_patterns):
            # Allow common abbreviations
            common_timeframes = ['1m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '1w', '1M']
            if v not in common_timeframes:
                raise ValueError(f"Invalid timeframe format: {v}. Use formats like '1h', '4h', '1d'")
        
        return v
    
    @field_validator("weight")
    @classmethod
    def validate_weight(cls, v: float) -> float:
        """Validate weight is positive."""
        if v <= 0:
            raise ValueError("Weight must be positive")
        return v


class MultiTimeframeIndicatorConfig(BaseModel):
    """Configuration for multi-timeframe indicators."""
    
    timeframes: List[TimeframeIndicatorConfig] = Field(
        default_factory=list, description="List of timeframe-specific indicator configurations"
    )
    cross_timeframe_features: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Cross-timeframe feature specifications"
    )
    column_standardization: bool = Field(
        True, description="Whether to apply column name standardization"
    )
    
    @field_validator("timeframes")
    @classmethod
    def validate_unique_timeframes(cls, v: List[TimeframeIndicatorConfig]) -> List[TimeframeIndicatorConfig]:
        """Validate that timeframes are unique."""
        timeframes = [tf.timeframe for tf in v]
        if len(timeframes) != len(set(timeframes)):
            duplicates = [tf for tf in set(timeframes) if timeframes.count(tf) > 1]
            raise ValueError(f"Duplicate timeframes found: {duplicates}")
        return v


class IndicatorsConfig(BaseModel):
    """Configuration for all indicators."""

    indicators: List[IndicatorConfig] = Field(
        default_factory=list, description="List of indicator configurations"
    )
    multi_timeframe: Optional[MultiTimeframeIndicatorConfig] = Field(
        None, description="Multi-timeframe indicator configuration"
    )


class KtrdrConfig(BaseModel):
    """Root configuration model for KTRDR."""

    data: DataConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    debug: bool = Field(False, description="Global debug flag")
    indicators: Optional[IndicatorsConfig] = Field(
        None, description="Indicator configurations"
    )
