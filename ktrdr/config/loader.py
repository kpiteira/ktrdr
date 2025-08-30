"""
Configuration loader for YAML-based settings.

This module provides functionality to load and validate configuration from
YAML files using Pydantic models.
"""

import os
from pathlib import Path
from typing import Any, Optional, TypeVar, Union

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ValidationError

# Import the new logging system
from ktrdr import get_logger, log_entry_exit, log_error
from ktrdr.config.models import (
    KtrdrConfig,
    MultiTimeframeIndicatorConfig,
)
from ktrdr.config.validation import InputValidator, sanitize_parameter
from ktrdr.errors import (
    ConfigurationError,
    ConfigurationFileError,
    ErrorHandler,
    FallbackStrategy,
    InvalidConfigurationError,
    MissingConfigurationError,
    fallback,
    retry_with_backoff,
)

T = TypeVar("T", bound=BaseModel)

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
    def load(
        self, config_path: Union[str, Path], model_type: type[T] = KtrdrConfig
    ) -> T:
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
            path_str = (
                str(config_path) if isinstance(config_path, Path) else config_path
            )

            # Validate the path string
            path_str = InputValidator.validate_string(
                path_str, min_length=1, max_length=1024
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
                details={"path": str(config_path), "error": str(e)},
            ) from e

        # Check if file exists
        if not config_path.exists():
            raise ConfigurationFileError(
                message=f"Configuration file not found: {config_path}",
                error_code="CONF-FileNotFound",
                details={"path": str(config_path)},
            )

        # Load YAML file
        try:
            with open(config_path) as file:
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
                    details={"validation_errors": e.errors()},
                ) from e

        except yaml.YAMLError as e:
            raise InvalidConfigurationError(
                message=f"Invalid YAML format in {config_path}: {e}",
                error_code="CONF-InvalidYaml",
                details={"yaml_error": str(e)},
            ) from e

    @fallback(strategy=FallbackStrategy.DEFAULT_VALUE, logger=logger)
    @log_entry_exit(logger=logger, log_result=True)
    def load_from_env(
        self,
        env_var: str = "KTRDR_CONFIG",
        default_path: Optional[Union[str, Path]] = None,
        model_type: type[T] = KtrdrConfig,
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
                pattern=r"^[A-Za-z0-9_]+$",  # Allow only alphanumeric and underscore
            )
        except ValidationError as e:
            raise ConfigurationError(
                message=f"Invalid environment variable name: {e}",
                error_code="CONF-InvalidEnvVar",
                details={"env_var": env_var, "error": str(e)},
            ) from e

        config_path = os.environ.get(env_var)

        # If env var not set, use default path
        if not config_path and default_path is None:
            raise MissingConfigurationError(
                message=f"Environment variable {env_var} not set and no default path provided",
                error_code="CONF-MissingEnvVar",
                details={"env_var": env_var},
            )

        path_to_use = config_path if config_path else default_path
        logger.info(
            f"Loading configuration from {path_to_use} (from env var: {config_path is not None})"
        )
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

    @log_entry_exit(logger=logger)
    def load_fuzzy_defaults(self) -> dict[str, Any]:
        """
        Load fuzzy logic default configurations from config/fuzzy.yaml.

        Returns:
            Dictionary containing fuzzy logic configurations

        Raises:
            ConfigurationError: If the file cannot be loaded or is invalid
        """
        try:
            # Define the default path to fuzzy.yaml
            fuzzy_config_path = Path("config") / "fuzzy.yaml"

            if not fuzzy_config_path.exists():
                logger.warning(
                    f"Fuzzy configuration file not found at {fuzzy_config_path}"
                )
                return {}

            # Load YAML file without using a specific Pydantic model
            with open(fuzzy_config_path) as file:
                config_dict = yaml.safe_load(file)

            # Handle empty file case
            if config_dict is None:
                logger.warning(f"Empty fuzzy configuration file: {fuzzy_config_path}")
                return {}

            logger.info(
                f"Successfully loaded fuzzy configurations from {fuzzy_config_path}"
            )
            return config_dict

        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML format in {fuzzy_config_path}: {e}")
            raise InvalidConfigurationError(
                message=f"Invalid YAML format in fuzzy configuration: {e}",
                error_code="CONF-InvalidYaml",
                details={"yaml_error": str(e)},
            ) from e
        except Exception as e:
            logger.error(f"Failed to load fuzzy configuration: {e}")
            raise ConfigurationError(
                message=f"Failed to load fuzzy configuration: {e}",
                error_code="CONF-FuzzyLoadFailed",
                details={"error": str(e)},
            ) from e

    @log_entry_exit(logger=logger)
    def load_multi_timeframe_indicators(
        self, config_path: Union[str, Path]
    ) -> MultiTimeframeIndicatorConfig:
        """
        Load multi-timeframe indicator configuration from a YAML file.

        Args:
            config_path: Path to the multi-timeframe indicator configuration file

        Returns:
            Validated MultiTimeframeIndicatorConfig object

        Raises:
            ConfigurationError: If loading or validation fails
        """
        try:
            # Load the full configuration first
            full_config = self.load(config_path, model_type=KtrdrConfig)

            # Extract multi-timeframe indicators section
            if full_config.indicators and full_config.indicators.multi_timeframe:
                logger.info(
                    "Successfully loaded multi-timeframe indicator configuration"
                )
                return full_config.indicators.multi_timeframe
            else:
                logger.warning("No multi-timeframe indicator configuration found")
                return MultiTimeframeIndicatorConfig()

        except ConfigurationError:
            # Re-raise configuration errors
            raise
        except Exception as e:
            raise ConfigurationError(
                message=f"Failed to load multi-timeframe indicator configuration: {e}",
                error_code="CONF-MultiTimeframeLoadFailed",
                details={"error": str(e), "path": str(config_path)},
            ) from e

    @log_entry_exit(logger=logger)
    def validate_multi_timeframe_config(
        self, config: MultiTimeframeIndicatorConfig
    ) -> dict[str, Any]:
        """
        Validate a multi-timeframe indicator configuration.

        Args:
            config: MultiTimeframeIndicatorConfig to validate

        Returns:
            Dictionary with validation results
        """
        validation_results: dict[str, Any] = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "recommendations": [],
            "timeframe_summary": {},
        }

        try:
            # Check timeframe coverage
            timeframes = [tf.timeframe for tf in config.timeframes]
            validation_results["timeframe_summary"]["count"] = len(timeframes)
            validation_results["timeframe_summary"]["timeframes"] = timeframes

            if len(timeframes) == 0:
                validation_results["errors"].append("No timeframes configured")
                validation_results["valid"] = False
                return validation_results

            # Validate timeframe hierarchy
            common_hierarchy = [
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
            hierarchy_issues = []

            for tf in timeframes:
                if tf not in common_hierarchy:
                    hierarchy_issues.append(f"Non-standard timeframe: {tf}")

            if hierarchy_issues:
                validation_results["warnings"].extend(hierarchy_issues)

            # Check for balanced indicator distribution
            indicator_counts = {}
            total_indicators = 0

            for tf_config in config.timeframes:
                count = len(tf_config.indicators)
                indicator_counts[tf_config.timeframe] = count
                total_indicators += count

            validation_results["timeframe_summary"][
                "indicator_counts"
            ] = indicator_counts
            validation_results["timeframe_summary"][
                "total_indicators"
            ] = total_indicators

            # Performance warnings
            if total_indicators > 50:
                validation_results["warnings"].append(
                    f"High total indicator count ({total_indicators}) may impact performance"
                )

            # Check for common indicators across timeframes
            indicator_types_by_tf = {}
            for tf_config in config.timeframes:
                types = [ind.type for ind in tf_config.indicators]
                indicator_types_by_tf[tf_config.timeframe] = set(types)

            if len(indicator_types_by_tf) > 1:
                common_types = set.intersection(*indicator_types_by_tf.values())
                validation_results["timeframe_summary"]["common_indicator_types"] = (
                    list(common_types)
                )

                if len(common_types) == 0:
                    validation_results["warnings"].append(
                        "No common indicator types across timeframes"
                    )

            # Validate cross-timeframe features
            if config.cross_timeframe_features:
                for (
                    feature_name,
                    feature_config,
                ) in config.cross_timeframe_features.items():
                    # Check that referenced timeframes exist
                    primary_tf = feature_config.get("primary_timeframe")
                    secondary_tf = feature_config.get("secondary_timeframe")

                    if primary_tf and primary_tf not in timeframes:
                        validation_results["errors"].append(
                            f"Cross-feature '{feature_name}' references unknown primary timeframe: {primary_tf}"
                        )
                        validation_results["valid"] = False

                    if secondary_tf and secondary_tf not in timeframes:
                        validation_results["errors"].append(
                            f"Cross-feature '{feature_name}' references unknown secondary timeframe: {secondary_tf}"
                        )
                        validation_results["valid"] = False

            # Recommendations
            if len(timeframes) < 2:
                validation_results["recommendations"].append(
                    "Consider adding more timeframes for better multi-timeframe analysis"
                )

            if total_indicators < 5:
                validation_results["recommendations"].append(
                    "Consider adding more indicators for comprehensive analysis"
                )

            logger.info(
                f"Multi-timeframe configuration validation completed: {validation_results['valid']}"
            )
            return validation_results

        except Exception as e:
            validation_results["valid"] = False
            validation_results["errors"].append(f"Validation error: {str(e)}")
            logger.error(f"Error during multi-timeframe config validation: {e}")
            return validation_results

    @log_entry_exit(logger=logger)
    def create_sample_multi_timeframe_config(
        self, output_path: Union[str, Path]
    ) -> None:
        """
        Create a sample multi-timeframe indicator configuration file.

        Args:
            output_path: Path where to save the sample configuration
        """
        sample_config = {
            "indicators": {
                "multi_timeframe": {
                    "column_standardization": True,
                    "timeframes": [
                        {
                            "timeframe": "1h",
                            "enabled": True,
                            "weight": 1.0,
                            "indicators": [
                                {
                                    "type": "RSI",
                                    "name": "rsi_short",
                                    "params": {"period": 14},
                                },
                                {
                                    "type": "SimpleMovingAverage",
                                    "name": "sma_fast",
                                    "params": {"period": 10},
                                },
                            ],
                        },
                        {
                            "timeframe": "4h",
                            "enabled": True,
                            "weight": 1.5,
                            "indicators": [
                                {
                                    "type": "RSI",
                                    "name": "rsi_medium",
                                    "params": {"period": 14},
                                },
                                {
                                    "type": "SimpleMovingAverage",
                                    "name": "sma_trend",
                                    "params": {"period": 50},
                                },
                            ],
                        },
                        {
                            "timeframe": "1d",
                            "enabled": True,
                            "weight": 2.0,
                            "indicators": [
                                {
                                    "type": "SimpleMovingAverage",
                                    "name": "sma_long",
                                    "params": {"period": 200},
                                }
                            ],
                        },
                    ],
                    "cross_timeframe_features": {
                        "rsi_divergence": {
                            "primary_timeframe": "1h",
                            "secondary_timeframe": "4h",
                            "primary_column": "rsi_short_1h",
                            "secondary_column": "rsi_medium_4h",
                            "operation": "difference",
                        }
                    },
                }
            },
            "data": {"directory": "./data"},
            "logging": {"level": "INFO"},
        }

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            yaml.dump(sample_config, f, default_flow_style=False, indent=2)

        logger.info(f"Sample multi-timeframe configuration saved to {output_path}")
