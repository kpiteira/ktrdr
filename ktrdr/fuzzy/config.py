"""
Configuration models for fuzzy logic membership functions.

This module defines Pydantic models for validating fuzzy logic configurations,
particularly focusing on triangular membership functions in Phase 1.
"""

from pathlib import Path
from typing import Annotated, Literal, Optional, Union

import yaml
from pydantic import (
    BaseModel,
    Field,
    RootModel,
    field_validator,
    model_validator,
)

from ktrdr import get_logger
from ktrdr.errors import (
    ConfigurationError,
    ConfigurationFileError,
    InvalidConfigurationError,
)

# Set up module-level logger
logger = get_logger(__name__)


class TriangularMFConfig(BaseModel):
    """
    Configuration for a triangular membership function.

    A triangular membership function is defined by three parameters [a, b, c]:
    - a: start point (membership value = 0)
    - b: peak point (membership value = 1)
    - c: end point (membership value = 0)

    The parameters must satisfy: a ≤ b ≤ c
    """

    type: Literal["triangular"] = "triangular"
    parameters: list[float] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Three parameters [a, b, c] defining the triangular membership function",
    )

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, parameters: list[float]) -> list[float]:
        """
        Validate triangular membership function parameters.

        Parameters must satisfy: a ≤ b ≤ c

        Args:
            parameters: List of three parameters [a, b, c]

        Returns:
            Validated parameters list

        Raises:
            ConfigurationError: If parameters are invalid
        """
        if len(parameters) != 3:
            raise ConfigurationError(
                message="Triangular membership function requires exactly 3 parameters [a, b, c]",
                error_code="CONFIG-InvalidParameterCount",
                details={"expected": 3, "actual": len(parameters)},
            )

        a, b, c = parameters

        # Check parameter ordering
        if not (a <= b <= c):
            raise ConfigurationError(
                message="Triangular membership function parameters must satisfy: a ≤ b ≤ c",
                error_code="CONFIG-InvalidParameterOrder",
                details={"parameters": {"a": a, "b": b, "c": c}},
            )

        # Log successful validation
        logger.debug(f"Validated triangular MF parameters: {parameters}")
        return parameters


class TrapezoidalMFConfig(BaseModel):
    """
    Configuration for a trapezoidal membership function.

    A trapezoidal membership function is defined by four parameters [a, b, c, d]:
    - a: start point (membership value = 0)
    - b: start of plateau (membership value = 1)
    - c: end of plateau (membership value = 1)
    - d: end point (membership value = 0)

    The parameters must satisfy: a ≤ b ≤ c ≤ d
    """

    type: Literal["trapezoidal"] = "trapezoidal"
    parameters: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Four parameters [a, b, c, d] defining the trapezoidal membership function",
    )

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, parameters: list[float]) -> list[float]:
        """
        Validate trapezoidal membership function parameters.

        Parameters must satisfy: a ≤ b ≤ c ≤ d

        Args:
            parameters: List of four parameters [a, b, c, d]

        Returns:
            Validated parameters list

        Raises:
            ConfigurationError: If parameters are invalid
        """
        if len(parameters) != 4:
            raise ConfigurationError(
                message="Trapezoidal membership function requires exactly 4 parameters [a, b, c, d]",
                error_code="CONFIG-InvalidParameterCount",
                details={"expected": 4, "actual": len(parameters)},
            )

        a, b, c, d = parameters

        # Check parameter ordering
        if not (a <= b <= c <= d):
            raise ConfigurationError(
                message="Trapezoidal membership function parameters must satisfy: a ≤ b ≤ c ≤ d",
                error_code="CONFIG-InvalidParameterOrder",
                details={"parameters": {"a": a, "b": b, "c": c, "d": d}},
            )

        # Log successful validation
        logger.debug(f"Validated trapezoidal MF parameters: {parameters}")
        return parameters


class GaussianMFConfig(BaseModel):
    """
    Configuration for a Gaussian membership function.

    A Gaussian membership function is defined by two parameters [μ, σ]:
    - μ: center/mean of the Gaussian curve (peak point)
    - σ: standard deviation (controls the width of the curve, must be > 0)
    """

    type: Literal["gaussian"] = "gaussian"
    parameters: list[float] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Two parameters [μ, σ] defining the Gaussian membership function",
    )

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, parameters: list[float]) -> list[float]:
        """
        Validate Gaussian membership function parameters.

        Args:
            parameters: List of two parameters [μ, σ]

        Returns:
            Validated parameters list

        Raises:
            ConfigurationError: If parameters are invalid
        """
        if len(parameters) != 2:
            raise ConfigurationError(
                message="Gaussian membership function requires exactly 2 parameters [μ, σ]",
                error_code="CONFIG-InvalidParameterCount",
                details={"expected": 2, "actual": len(parameters)},
            )

        mu, sigma = parameters

        # Check sigma > 0
        if sigma <= 0:
            raise ConfigurationError(
                message="Gaussian membership function sigma must be greater than 0",
                error_code="CONFIG-InvalidSigma",
                details={"sigma": sigma},
            )

        # Log successful validation
        logger.debug(f"Validated Gaussian MF parameters: {parameters}")
        return parameters


# Union type for all membership function configurations with discriminator
MembershipFunctionConfig = Annotated[
    Union[TriangularMFConfig, TrapezoidalMFConfig, GaussianMFConfig],
    Field(discriminator="type"),
]


class PriceRatioTransformConfig(BaseModel):
    """
    Configuration for price ratio input transformation.

    Transforms indicator values to price ratios for fuzzification.
    Formula: reference_price / indicator_value

    Used for moving averages (SMA/EMA) to normalize unbounded price values
    for fuzzification as relative positions (e.g., 1.0 = at MA, 1.05 = 5% above).
    """

    type: Literal["price_ratio"] = "price_ratio"
    reference: str = Field(
        ..., description="Price column to use as reference (open, high, low, close)"
    )

    @field_validator("reference")
    @classmethod
    def validate_reference(cls, reference: str) -> str:
        """
        Validate reference column name.

        Args:
            reference: Reference column name

        Returns:
            Validated reference column name

        Raises:
            ConfigurationError: If reference is not a valid price column
        """
        valid_references = ["open", "high", "low", "close"]
        if reference.lower() not in valid_references:
            raise ConfigurationError(
                message=f"Invalid reference column '{reference}' for price_ratio transform",
                error_code="CONFIG-InvalidPriceRatioReference",
                details={"reference": reference, "valid_references": valid_references},
                suggestion=f"Use one of: {', '.join(valid_references)}",
            )

        logger.debug(f"Validated price ratio reference: {reference}")
        return reference.lower()


class IdentityTransformConfig(BaseModel):
    """
    Configuration for identity input transformation (no transformation).

    Returns indicator values unchanged. This is the default when no
    input_transform is specified.
    """

    type: Literal["identity"] = "identity"


# Union type for all input transform configurations with discriminator
InputTransformConfig = Annotated[
    Union[PriceRatioTransformConfig, IdentityTransformConfig],
    Field(discriminator="type"),
]


class FuzzySetConfigModel(BaseModel):
    """
    Configuration for a fuzzy set, which contains named membership functions
    and an optional input transformation.

    For example, an RSI indicator might have "low", "medium", and "high" fuzzy sets,
    each defined by a membership function.

    Optionally, an input_transform can be specified to transform indicator values
    before fuzzification (e.g., converting moving averages to price ratios).

    The structure allows arbitrary fuzzy set names as dynamic fields, while
    reserving 'input_transform' as a special optional field.
    """

    # Optional input transformation (applied before fuzzification)
    input_transform: Optional[InputTransformConfig] = Field(
        default=None,
        description="Optional transformation to apply to indicator values before fuzzification",
    )

    # Allow extra fields for fuzzy set names (oversold, neutral, overbought, etc.)
    model_config = {"extra": "allow"}

    @model_validator(mode="after")
    def validate_and_parse_membership_functions(self) -> "FuzzySetConfigModel":
        """
        Validate that at least one membership function is defined and parse them.

        Returns:
            Self reference for chaining

        Raises:
            ConfigurationError: If no membership functions defined or parsing fails
        """
        # Collect membership function fields from __pydantic_extra__
        # This is where Pydantic stores extra fields when extra="allow"
        extra_fields = getattr(self, "__pydantic_extra__", {}) or {}

        if not extra_fields:
            raise ConfigurationError(
                message="At least one fuzzy set (membership function) must be defined",
                error_code="CONFIG-EmptyFuzzySet",
                details={},
            )

        # Validate and parse each membership function
        for name, value in extra_fields.items():
            if isinstance(value, dict):
                try:
                    # Parse based on discriminator (type field)
                    mf_type = value.get("type")
                    if mf_type == "triangular":
                        extra_fields[name] = TriangularMFConfig(**value)
                    elif mf_type == "trapezoidal":
                        extra_fields[name] = TrapezoidalMFConfig(**value)
                    elif mf_type == "gaussian":
                        extra_fields[name] = GaussianMFConfig(**value)
                    else:
                        raise ConfigurationError(
                            message=f"Unknown membership function type '{mf_type}' for fuzzy set '{name}'",
                            error_code="CONFIG-UnknownMembershipType",
                            details={"fuzzy_set": name, "type": mf_type},
                        )
                except ConfigurationError:
                    raise
                except Exception as e:
                    raise ConfigurationError(
                        message=f"Failed to parse membership function '{name}'",
                        error_code="CONFIG-InvalidMembershipFunction",
                        details={"fuzzy_set": name, "error": str(e)},
                    ) from e

        # Log the fuzzy set names
        fuzzy_set_names = list(extra_fields.keys())
        logger.debug(f"Validated fuzzy sets: {fuzzy_set_names}")
        if self.input_transform:
            logger.debug(f"Input transform configured: {self.input_transform.type}")

        return self

    def get_membership_functions(self) -> dict[str, MembershipFunctionConfig]:
        """
        Get all membership function configurations, excluding input_transform.

        Returns:
            Dictionary mapping fuzzy set names to membership function configs
        """
        # Get membership functions from __pydantic_extra__
        extra_fields = getattr(self, "__pydantic_extra__", {}) or {}

        result = {}
        for key, value in extra_fields.items():
            if isinstance(
                value, (TriangularMFConfig, TrapezoidalMFConfig, GaussianMFConfig)
            ):
                result[key] = value

        return result

    @property
    def root(self) -> dict[str, MembershipFunctionConfig]:
        """
        Backward compatibility property for code expecting RootModel interface.

        Returns:
            Dictionary mapping fuzzy set names to membership function configs
        """
        return self.get_membership_functions()


class FuzzyConfigModel(RootModel[dict[str, FuzzySetConfigModel]]):
    """
    Overall configuration for fuzzy logic, including multiple indicators
    and their associated fuzzy sets.
    """

    # The key is the indicator name (e.g., "rsi", "macd")
    # The value is the configuration for that indicator's fuzzy sets

    @model_validator(mode="after")
    def validate_indicators(self) -> "FuzzyConfigModel":
        """
        Validate that indicator configurations are valid.

        Currently, just checks that there is at least one indicator defined.
        Future versions may have more specific requirements.

        Returns:
            Self reference for chaining

        Raises:
            ConfigurationError: If validation fails
        """
        if not self.root:
            raise ConfigurationError(
                message="At least one indicator must be defined",
                error_code="CONFIG-EmptyFuzzyConfig",
                details={},
            )

        # Log the indicator names
        logger.debug(f"Validated fuzzy indicators: {list(self.root.keys())}")
        return self


# Define more friendly type aliases
FuzzySetConfig = FuzzySetConfigModel
FuzzyConfig = FuzzyConfigModel


class FuzzyConfigLoader:
    """
    Loads and validates fuzzy configuration from YAML files.
    """

    def __init__(self, config_dir: Optional[Union[str, Path]] = None):
        """
        Initialize the FuzzyConfigLoader with an optional config directory.

        Args:
            config_dir: Optional directory where configuration files are located.
                       If not provided, the current working directory is used.
        """
        self.config_dir = Path(config_dir) if config_dir else Path.cwd()
        logger.debug(
            f"Initialized FuzzyConfigLoader with config directory: {self.config_dir}"
        )

    @staticmethod
    def load_from_dict(config_dict: dict) -> FuzzyConfig:
        """
        Load and validate fuzzy configuration from a dictionary.

        Args:
            config_dict: Dictionary representation of the fuzzy configuration

        Returns:
            Validated FuzzyConfig object

        Raises:
            ConfigurationError: If configuration is invalid
        """
        try:
            logger.debug("Loading fuzzy configuration from dictionary")
            return FuzzyConfig.model_validate(config_dict)
        except Exception as e:
            logger.error(f"Failed to load fuzzy configuration: {e}")
            raise ConfigurationError(
                message="Failed to load fuzzy configuration",
                error_code="CONFIG-InvalidFuzzyConfig",
                details={"original_error": str(e)},
            ) from e

    def load_from_yaml(self, file_path: Union[str, Path]) -> FuzzyConfig:
        """
        Load and validate fuzzy configuration from a YAML file.

        Args:
            file_path: Path to the YAML configuration file.
                      If a relative path is provided, it is resolved relative to the config directory.

        Returns:
            Validated FuzzyConfig object

        Raises:
            ConfigurationFileError: If the file cannot be found or accessed
            InvalidConfigurationError: If the YAML format is invalid
            ConfigurationError: If validation fails or another error occurs
        """
        # Resolve the path if it's relative
        path = Path(file_path)
        if not path.is_absolute():
            path = self.config_dir / path

        logger.info(f"Loading fuzzy configuration from file: {path}")

        # Check if file exists
        if not path.exists():
            logger.error(f"Fuzzy configuration file not found: {path}")
            raise ConfigurationFileError(
                message=f"Fuzzy configuration file not found: {path}",
                error_code="CONFIG-FuzzyFileNotFound",
                details={"path": str(path)},
            )

        # Load YAML file
        try:
            with open(path) as file:
                config_dict = yaml.safe_load(file)

            # Handle empty file case
            if config_dict is None:
                logger.warning(f"Empty fuzzy configuration file: {path}")
                config_dict = {}

            # Validate with Pydantic model
            try:
                fuzzy_config = self.load_from_dict(config_dict)
                logger.info(f"Successfully loaded fuzzy configuration from {path}")
                return fuzzy_config
            except Exception as e:
                logger.error(f"Failed to validate fuzzy configuration: {e}")
                raise InvalidConfigurationError(
                    message="Fuzzy configuration validation failed",
                    error_code="CONFIG-FuzzyValidationFailed",
                    details={"validation_errors": str(e)},
                ) from e

        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML format in fuzzy configuration file: {e}")
            raise InvalidConfigurationError(
                message="Invalid YAML format in fuzzy configuration file",
                error_code="CONFIG-InvalidFuzzyYaml",
                details={"yaml_error": str(e)},
            ) from e
        except Exception as e:
            logger.error(f"Error loading fuzzy configuration file: {e}")
            raise ConfigurationError(
                message="Error loading fuzzy configuration file",
                error_code="CONFIG-FuzzyLoadError",
                details={"error": str(e)},
            ) from e

    def load_default(self) -> FuzzyConfig:
        """
        Load the default fuzzy configuration from 'fuzzy.yaml' in the config directory.

        Returns:
            Validated FuzzyConfig object

        Raises:
            ConfigurationFileError: If the default file cannot be found or accessed
            InvalidConfigurationError: If the YAML format is invalid
            ConfigurationError: If validation fails or another error occurs
        """
        default_path = self.config_dir / "fuzzy.yaml"
        logger.info(f"Loading default fuzzy configuration from: {default_path}")
        return self.load_from_yaml(default_path)

    def load_strategy_fuzzy_config(self, strategy_name: str) -> FuzzyConfig:
        """
        Load fuzzy configuration from a strategy-specific file.

        Args:
            strategy_name: Name of the strategy

        Returns:
            Validated FuzzyConfig object

        Raises:
            ConfigurationFileError: If the strategy file cannot be found or accessed
            InvalidConfigurationError: If the YAML format is invalid
            ConfigurationError: If validation fails or another error occurs
        """
        strategy_path = self.config_dir.parent / "strategies" / f"{strategy_name}.yaml"
        logger.info(
            f"Loading strategy-specific fuzzy configuration from: {strategy_path}"
        )

        if not strategy_path.exists():
            logger.error(f"Strategy file not found: {strategy_path}")
            raise ConfigurationFileError(
                message=f"Strategy configuration file not found: {strategy_path}",
                error_code="CONFIG-StrategyFileNotFound",
                details={"strategy_name": strategy_name, "path": str(strategy_path)},
            )

        # Load strategy YAML file
        try:
            with open(strategy_path) as file:
                strategy_dict = yaml.safe_load(file)

            # Extract fuzzy_sets section from strategy file
            if strategy_dict and "fuzzy_sets" in strategy_dict:
                logger.debug(f"Found fuzzy_sets section in strategy: {strategy_name}")
                fuzzy_sets = strategy_dict["fuzzy_sets"]
                return self.load_from_dict(fuzzy_sets)
            else:
                logger.warning(
                    f"No fuzzy_sets section found in strategy: {strategy_name}"
                )
                # Return empty config or use default config?
                return FuzzyConfig({})

        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML format in strategy file: {e}")
            raise InvalidConfigurationError(
                message="Invalid YAML format in strategy file",
                error_code="CONFIG-InvalidStrategyYaml",
                details={"yaml_error": str(e)},
            ) from e
        except Exception as e:
            logger.error(f"Error loading strategy file: {e}")
            raise ConfigurationError(
                message="Error loading strategy file",
                error_code="CONFIG-StrategyLoadError",
                details={"error": str(e)},
            ) from e

    def merge_configs(
        self, base_config: FuzzyConfig, override_config: FuzzyConfig
    ) -> FuzzyConfig:
        """
        Merge two fuzzy configurations, with override_config taking precedence.

        Args:
            base_config: Base configuration
            override_config: Configuration that overrides base_config

        Returns:
            Merged FuzzyConfig object
        """
        logger.debug("Merging fuzzy configurations")

        # Start with a copy of the base config
        merged_dict = {
            ind: dict(fuzzy_sets.root.items())
            for ind, fuzzy_sets in base_config.root.items()
        }

        # Override with values from override_config
        for indicator, fuzzy_sets in override_config.root.items():
            if indicator not in merged_dict:
                merged_dict[indicator] = {}

            for set_name, mf_config in fuzzy_sets.root.items():
                merged_dict[indicator][set_name] = mf_config

        return self.load_from_dict(merged_dict)

    def load_with_strategy_override(
        self, strategy_name: Optional[str] = None
    ) -> FuzzyConfig:
        """
        Load fuzzy configuration with optional strategy-specific overrides.

        First loads the default fuzzy configuration from 'fuzzy.yaml',
        then overrides it with settings from the specified strategy file if provided.

        Args:
            strategy_name: Optional name of the strategy for configuration overrides

        Returns:
            Validated FuzzyConfig object with merged settings
        """
        # Load default configuration
        default_config = self.load_default()

        # If no strategy specified, return default config
        if not strategy_name:
            logger.info("No strategy specified, using default fuzzy configuration")
            return default_config

        try:
            # Load strategy-specific configuration
            logger.info(
                f"Loading strategy-specific fuzzy configuration for: {strategy_name}"
            )
            strategy_config = self.load_strategy_fuzzy_config(strategy_name)

            # Merge configurations
            logger.info("Merging default and strategy-specific fuzzy configurations")
            return self.merge_configs(default_config, strategy_config)

        except ConfigurationFileError:
            # Strategy file not found, just use default config
            logger.warning(
                f"Strategy file not found for {strategy_name}, using default fuzzy configuration"
            )
            return default_config
