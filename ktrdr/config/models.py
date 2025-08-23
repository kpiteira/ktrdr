"""
Pydantic models for configuration validation.

This module defines the structure and validation rules for KTRDR configuration.
"""

import builtins
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

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


class IbHostServiceConfig(BaseModel):
    """Configuration settings for IB Host Service."""

    enabled: bool = Field(
        False, description="Whether to use host service instead of direct IB connection"
    )
    url: str = Field("http://localhost:5001", description="URL of the IB host service")


class IndicatorConfig(BaseModel):
    """Configuration for a technical indicator."""

    type: str = Field(..., description="The type/class of indicator")
    name: Optional[str] = Field(None, description="Custom name for the indicator")
    params: dict[str, Any] = Field(
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

    timeframe: str = Field(
        ..., description="Timeframe identifier (e.g., '1h', '4h', '1d')"
    )
    indicators: list[IndicatorConfig] = Field(
        default_factory=list,
        description="List of indicator configurations for this timeframe",
    )
    enabled: bool = Field(True, description="Whether this timeframe is enabled")
    weight: float = Field(
        1.0, description="Weight for this timeframe in decision making"
    )

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        """Validate timeframe format."""
        v = v.strip()
        if not v:
            raise ValueError("Timeframe cannot be empty")

        # Common timeframe patterns
        valid_patterns = [
            r"^\d+[smhDwM]$",  # 1m, 5m, 1h, 4h, 1D, 1w, 1M
            r"^\d+(min|hour|day|week|month)s?$",  # 1min, 5mins, 1hour, etc.
        ]

        import re

        if not any(re.match(pattern, v, re.IGNORECASE) for pattern in valid_patterns):
            # Allow common abbreviations
            common_timeframes = [
                "1m",
                "5m",
                "15m",
                "30m",
                "1h",
                "2h",
                "4h",
                "6h",
                "8h",
                "12h",
                "1d",
                "1w",
                "1M",
            ]
            if v not in common_timeframes:
                raise ValueError(
                    f"Invalid timeframe format: {v}. Use formats like '1h', '4h', '1d'"
                )

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

    timeframes: list[TimeframeIndicatorConfig] = Field(
        default_factory=list,
        description="List of timeframe-specific indicator configurations",
    )
    cross_timeframe_features: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="Cross-timeframe feature specifications"
    )
    column_standardization: bool = Field(
        True, description="Whether to apply column name standardization"
    )

    @field_validator("timeframes")
    @classmethod
    def validate_unique_timeframes(
        cls, v: list[TimeframeIndicatorConfig]
    ) -> list[TimeframeIndicatorConfig]:
        """Validate that timeframes are unique."""
        timeframes = [tf.timeframe for tf in v]
        if len(timeframes) != len(set(timeframes)):
            duplicates = [tf for tf in set(timeframes) if timeframes.count(tf) > 1]
            raise ValueError(f"Duplicate timeframes found: {duplicates}")
        return v


class IndicatorsConfig(BaseModel):
    """Configuration for all indicators."""

    indicators: list[IndicatorConfig] = Field(
        default_factory=list, description="List of indicator configurations"
    )
    multi_timeframe: Optional[MultiTimeframeIndicatorConfig] = Field(
        None, description="Multi-timeframe indicator configuration"
    )


# Strategy Configuration Models (New Schema)
class StrategyScope(str, Enum):
    """Defines the scope/applicability of a strategy."""

    UNIVERSAL = "universal"  # Can trade any compatible symbol
    SYMBOL_GROUP = "symbol_group"  # Restricted to specific symbol groups
    SYMBOL_SPECIFIC = "symbol_specific"  # Legacy: trained for specific symbols only


class SymbolMode(str, Enum):
    """Defines how symbols are specified in strategy."""

    SINGLE = "single"  # Legacy single symbol
    MULTI_SYMBOL = "multi_symbol"  # Multiple symbols for training


class TimeframeMode(str, Enum):
    """Defines how timeframes are specified in strategy."""

    SINGLE = "single"  # Legacy single timeframe
    MULTI_TIMEFRAME = "multi_timeframe"  # Multiple timeframes for features


class TargetSymbolMode(str, Enum):
    """Defines deployment symbol restrictions."""

    UNIVERSAL = "universal"  # No symbol restrictions
    GROUP_RESTRICTED = "group_restricted"  # Restricted to specific groups
    TRAINING_ONLY = "training_only"  # Legacy: only symbols used in training


class SymbolSelectionCriteria(BaseModel):
    """Criteria for automatic symbol selection."""

    asset_class: Optional[str] = Field(
        None, description="Asset class filter (forex, stocks, crypto)"
    )
    volatility_range: Optional[list[float]] = Field(
        None, description="[min, max] volatility range"
    )
    liquidity_tier: Optional[str] = Field(
        None, description="Liquidity tier requirement"
    )
    market_cap_range: Optional[list[float]] = Field(
        None, description="Market cap range for stocks"
    )

    @field_validator("volatility_range")
    @classmethod
    def validate_volatility_range(
        cls, v: Optional[list[float]]
    ) -> Optional[list[float]]:
        if v is not None:
            if len(v) != 2 or v[0] >= v[1]:
                raise ValueError("Volatility range must be [min, max] with min < max")
        return v


class SymbolConfiguration(BaseModel):
    """Configuration for symbols in strategy."""

    mode: SymbolMode = Field(..., description="Symbol specification mode")

    # For single symbol mode (legacy)
    symbol: Optional[str] = Field(None, description="Single symbol for legacy mode")

    # For multi-symbol mode
    list: Optional[List[str]] = Field(None, description="Explicit list of symbols")
    selection_criteria: Optional[SymbolSelectionCriteria] = Field(
        None, description="Automatic symbol selection criteria"
    )

    @field_validator("symbol")
    @classmethod
    def validate_single_mode_symbol(cls, v: Optional[str], info) -> Optional[str]:
        if hasattr(info, "data") and info.data.get("mode") == SymbolMode.SINGLE:
            if not v:
                raise ValueError("Symbol must be specified for single mode")
        return v

    @field_validator("list")
    @classmethod
    def validate_multi_mode_symbols(
        cls, v: Optional[List[str]], info
    ) -> Optional[List[str]]:
        if hasattr(info, "data") and info.data.get("mode") == SymbolMode.MULTI_SYMBOL:
            if not v and not info.data.get("selection_criteria"):
                raise ValueError(
                    "Either symbol list or selection criteria must be specified for multi_symbol mode"
                )
            if v and len(v) < 1:
                raise ValueError("Multi-symbol mode requires at least 1 symbol")
        return v


class TimeframeConfiguration(BaseModel):
    """Configuration for timeframes in strategy."""

    mode: TimeframeMode = Field(..., description="Timeframe specification mode")

    # For single timeframe mode (legacy)
    timeframe: Optional[str] = Field(
        None, description="Single timeframe for legacy mode"
    )

    # For multi-timeframe mode
    list: Optional[List[str]] = Field(
        None, description="List of timeframes for features"
    )
    base_timeframe: Optional[str] = Field(
        None, description="Reference timeframe for alignment"
    )

    @field_validator("timeframe")
    @classmethod
    def validate_single_mode_timeframe(cls, v: Optional[str], info) -> Optional[str]:
        if hasattr(info, "data") and info.data.get("mode") == TimeframeMode.SINGLE:
            if not v:
                raise ValueError("Timeframe must be specified for single mode")
        return v

    @field_validator("list")
    @classmethod
    def validate_multi_mode_timeframes(
        cls, v: Optional[List[str]], info
    ) -> Optional[List[str]]:
        if (
            hasattr(info, "data")
            and info.data.get("mode") == TimeframeMode.MULTI_TIMEFRAME
        ):
            if not v:
                raise ValueError(
                    "Timeframe list must be specified for multi_timeframe mode"
                )
            if len(v) < 2:
                raise ValueError("Multi-timeframe mode requires at least 2 timeframes")
        return v

    @field_validator("base_timeframe")
    @classmethod
    def validate_base_timeframe_in_list(cls, v: Optional[str], info) -> Optional[str]:
        if (
            hasattr(info, "data")
            and info.data.get("mode") == TimeframeMode.MULTI_TIMEFRAME
            and v
            and info.data.get("list")
        ):
            if v not in info.data["list"]:
                raise ValueError("Base timeframe must be in the timeframes list")
        return v


class TrainingDataConfiguration(BaseModel):
    """Configuration for training data."""

    symbols: SymbolConfiguration = Field(..., description="Symbol configuration")
    timeframes: TimeframeConfiguration = Field(
        ..., description="Timeframe configuration"
    )

    # Data requirements
    history_required: int = Field(
        200, description="Minimum bars required per timeframe"
    )
    start_date: Optional[str] = Field(
        None, description="Explicit start date for training data"
    )
    end_date: Optional[str] = Field(
        None, description="Explicit end date for training data"
    )

    @field_validator("history_required")
    @classmethod
    def validate_history_required(cls, v: int) -> int:
        if v < 50:
            raise ValueError("History required must be at least 50 bars")
        return v


class TargetSymbolRestrictions(BaseModel):
    """Restrictions for target symbol deployment."""

    asset_classes: Optional[List[str]] = Field(
        None, description="Allowed asset classes"
    )
    excluded_symbols: Optional[List[str]] = Field(
        None, description="Explicitly excluded symbols"
    )
    min_liquidity_tier: Optional[str] = Field(
        None, description="Minimum liquidity tier"
    )


class TargetSymbolConfiguration(BaseModel):
    """Configuration for deployment target symbols."""

    mode: TargetSymbolMode = Field(..., description="Target symbol mode")
    restrictions: Optional[TargetSymbolRestrictions] = Field(
        None, description="Symbol restrictions (only for group_restricted mode)"
    )


class TargetTimeframeConfiguration(BaseModel):
    """Configuration for deployment target timeframes."""

    mode: TimeframeMode = Field(..., description="Target timeframe mode")
    supported: Optional[List[str]] = Field(
        None, description="Supported timeframes (subset of training)"
    )
    timeframe: Optional[str] = Field(None, description="Single timeframe for legacy")

    @field_validator("supported")
    @classmethod
    def validate_supported_timeframes(
        cls, v: Optional[List[str]], info
    ) -> Optional[List[str]]:
        if (
            hasattr(info, "data")
            and info.data.get("mode") == TimeframeMode.MULTI_TIMEFRAME
        ):
            if not v:
                raise ValueError(
                    "Supported timeframes must be specified for multi_timeframe mode"
                )
        return v


class DeploymentConfiguration(BaseModel):
    """Configuration for model deployment."""

    target_symbols: TargetSymbolConfiguration = Field(
        ..., description="Target symbol configuration"
    )
    target_timeframes: TargetTimeframeConfiguration = Field(
        ..., description="Target timeframe configuration"
    )


class StrategyConfigurationV2(BaseModel):
    """New strategy configuration schema (v2) supporting multi-scope training and deployment."""

    # Meta information
    name: str = Field(..., description="Strategy name")
    description: Optional[str] = Field(None, description="Strategy description")
    version: str = Field(..., description="Strategy version")
    scope: StrategyScope = Field(..., description="Strategy scope/applicability")

    # Training and deployment configuration
    training_data: TrainingDataConfiguration = Field(
        ..., description="Training data configuration"
    )
    deployment: DeploymentConfiguration = Field(
        ..., description="Deployment configuration"
    )

    # Existing sections (unchanged)
    indicators: list[dict[str, Any]] = Field(
        ..., description="Technical indicators configuration"
    )
    fuzzy_sets: dict[str, Any] = Field(
        ..., description="Fuzzy logic sets configuration"
    )
    model: dict[str, Any] = Field(..., description="Neural network configuration")
    decisions: dict[str, Any] = Field(..., description="Decision logic configuration")
    training: dict[str, Any] = Field(..., description="Training configuration")

    # Optional sections
    orchestrator: Optional[dict[str, Any]] = Field(
        None, description="Decision orchestrator settings"
    )
    risk_management: Optional[dict[str, Any]] = Field(
        None, description="Risk management configuration"
    )
    backtesting: Optional[dict[str, Any]] = Field(
        None, description="Backtesting configuration"
    )

    @field_validator("scope")
    @classmethod
    def validate_scope_consistency(cls, v: StrategyScope, info) -> StrategyScope:
        """Validate scope consistency with training/deployment configuration."""
        # Additional validation can be added here
        return v


class LegacyStrategyConfiguration(BaseModel):
    """Legacy strategy configuration for backward compatibility."""

    # Meta information
    name: str = Field(..., description="Strategy name")
    description: Optional[str] = Field(None, description="Strategy description")
    version: Optional[str] = Field(None, description="Strategy version")

    # Legacy data section (optional)
    data: Optional[dict[str, Any]] = Field(
        None, description="Legacy data configuration"
    )

    # Required sections
    indicators: list[dict[str, Any]] = Field(
        ..., description="Technical indicators configuration"
    )
    fuzzy_sets: dict[str, Any] = Field(
        ..., description="Fuzzy logic sets configuration"
    )
    model: dict[str, Any] = Field(..., description="Neural network configuration")
    decisions: dict[str, Any] = Field(..., description="Decision logic configuration")
    training: dict[str, Any] = Field(..., description="Training configuration")

    # Optional sections
    orchestrator: Optional[dict[str, Any]] = Field(
        None, description="Decision orchestrator settings"
    )
    risk_management: Optional[dict[str, Any]] = Field(
        None, description="Risk management configuration"
    )
    backtesting: Optional[dict[str, Any]] = Field(
        None, description="Backtesting configuration"
    )


class KtrdrConfig(BaseModel):
    """Root configuration model for KTRDR."""

    data: DataConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    ib_host_service: IbHostServiceConfig = Field(default_factory=IbHostServiceConfig)
    debug: bool = Field(False, description="Global debug flag")
    indicators: Optional[IndicatorsConfig] = Field(
        None, description="Indicator configurations"
    )
