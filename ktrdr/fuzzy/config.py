"""
Configuration models for fuzzy logic membership functions.

This module defines Pydantic models for validating fuzzy logic configurations,
particularly focusing on triangular membership functions in Phase 1.
"""

from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator, RootModel

from ktrdr.errors import ConfigurationError
from ktrdr import get_logger

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
    parameters: List[float] = Field(..., min_length=3, max_length=3, 
                                description="Three parameters [a, b, c] defining the triangular membership function")
    
    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, parameters: List[float]) -> List[float]:
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
                details={"expected": 3, "actual": len(parameters)}
            )
            
        a, b, c = parameters
        
        # Check parameter ordering
        if not (a <= b <= c):
            raise ConfigurationError(
                message="Triangular membership function parameters must satisfy: a ≤ b ≤ c",
                error_code="CONFIG-InvalidParameterOrder",
                details={"parameters": {"a": a, "b": b, "c": c}}
            )
            
        # Log successful validation
        logger.debug(f"Validated triangular MF parameters: {parameters}")
        return parameters


# In Phase 1, we only implement triangular membership functions
# This type alias will make it easier to extend with more types in the future
MembershipFunctionConfig = TriangularMFConfig


class FuzzySetConfigModel(RootModel[Dict[str, MembershipFunctionConfig]]):
    """
    Configuration for a fuzzy set, which contains named membership functions.
    
    For example, an RSI indicator might have "low", "medium", and "high" fuzzy sets,
    each defined by a membership function.
    """
    
    # The key is the fuzzy set name (e.g., "low", "neutral", "high")
    # The value is the membership function configuration
    
    @model_validator(mode='after')
    def validate_set_names(self) -> 'FuzzySetConfigModel':
        """
        Validate that fuzzy set names are valid.
        
        Currently, just checks that there is at least one set defined.
        Future versions may have more specific naming requirements.
        
        Returns:
            Self reference for chaining
            
        Raises:
            ConfigurationError: If validation fails
        """
        if not self.root:
            raise ConfigurationError(
                message="At least one fuzzy set must be defined",
                error_code="CONFIG-EmptyFuzzySet",
                details={}
            )
            
        # Log the fuzzy set names
        logger.debug(f"Validated fuzzy sets: {list(self.root.keys())}")
        return self


class FuzzyConfigModel(RootModel[Dict[str, FuzzySetConfigModel]]):
    """
    Overall configuration for fuzzy logic, including multiple indicators
    and their associated fuzzy sets.
    """
    
    # The key is the indicator name (e.g., "rsi", "macd")
    # The value is the configuration for that indicator's fuzzy sets
    
    @model_validator(mode='after')
    def validate_indicators(self) -> 'FuzzyConfigModel':
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
                details={}
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
    
    @staticmethod
    def load(config_dict: dict) -> FuzzyConfig:
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
            logger.debug("Loading fuzzy configuration")
            return FuzzyConfig.model_validate(config_dict)
        except Exception as e:
            logger.error(f"Failed to load fuzzy configuration: {e}")
            raise ConfigurationError(
                message="Failed to load fuzzy configuration",
                error_code="CONFIG-InvalidFuzzyConfig",
                details={"original_error": str(e)}
            ) from e