"""
Fuzzy logic models for the KTRDR API.

This module defines the models related to fuzzy logic, including membership
functions, rules, and fuzzy set configurations.
"""

from enum import Enum
from typing import Dict, List, Any, Optional, Union, Literal
from pydantic import BaseModel, Field, field_validator, model_validator

from ktrdr.api.models.base import ApiResponse


class MembershipFunctionType(str, Enum):
    """Types of membership functions."""

    TRIANGULAR = "triangular"
    TRAPEZOIDAL = "trapezoidal"
    GAUSSIAN = "gaussian"
    SIGMOID = "sigmoid"
    BELL = "bell"
    SINGLETON = "singleton"
    CUSTOM = "custom"


class MembershipFunction(BaseModel):
    """
    Definition of a membership function.

    Attributes:
        type (MembershipFunctionType): Type of membership function
        name (str): Name of the membership function
        parameters (Dict[str, Union[float, List[float]]]): Parameters for the function
    """

    type: MembershipFunctionType = Field(..., description="Type of membership function")
    name: str = Field(..., description="Name of the membership function")
    parameters: Dict[str, Union[float, List[float]]] = Field(
        ..., description="Parameters for the function"
    )

    @model_validator(mode="after")
    def validate_parameters(self) -> "MembershipFunction":
        """Validate that the parameters are appropriate for the membership function type."""
        if self.type == MembershipFunctionType.TRIANGULAR:
            if (
                "points" not in self.parameters
                or not isinstance(self.parameters["points"], list)
                or len(self.parameters["points"]) != 3
            ):
                raise ValueError(
                    "Triangular membership function must have 'points' parameter with 3 values [a, b, c]"
                )

            a, b, c = self.parameters["points"]
            if not (a <= b <= c):
                raise ValueError(
                    "Triangular membership function points must satisfy a <= b <= c"
                )

        elif self.type == MembershipFunctionType.TRAPEZOIDAL:
            if (
                "points" not in self.parameters
                or not isinstance(self.parameters["points"], list)
                or len(self.parameters["points"]) != 4
            ):
                raise ValueError(
                    "Trapezoidal membership function must have 'points' parameter with 4 values [a, b, c, d]"
                )

            a, b, c, d = self.parameters["points"]
            if not (a <= b <= c <= d):
                raise ValueError(
                    "Trapezoidal membership function points must satisfy a <= b <= c <= d"
                )

        elif self.type == MembershipFunctionType.GAUSSIAN:
            if "mean" not in self.parameters or not isinstance(
                self.parameters["mean"], (int, float)
            ):
                raise ValueError(
                    "Gaussian membership function must have 'mean' parameter"
                )
            if (
                "sigma" not in self.parameters
                or not isinstance(self.parameters["sigma"], (int, float))
                or self.parameters["sigma"] <= 0
            ):
                raise ValueError(
                    "Gaussian membership function must have positive 'sigma' parameter"
                )

        elif self.type == MembershipFunctionType.SIGMOID:
            if "a" not in self.parameters or not isinstance(
                self.parameters["a"], (int, float)
            ):
                raise ValueError("Sigmoid membership function must have 'a' parameter")
            if "c" not in self.parameters or not isinstance(
                self.parameters["c"], (int, float)
            ):
                raise ValueError("Sigmoid membership function must have 'c' parameter")

        elif self.type == MembershipFunctionType.BELL:
            if (
                "a" not in self.parameters
                or not isinstance(self.parameters["a"], (int, float))
                or self.parameters["a"] <= 0
            ):
                raise ValueError(
                    "Bell membership function must have positive 'a' parameter"
                )
            if (
                "b" not in self.parameters
                or not isinstance(self.parameters["b"], (int, float))
                or self.parameters["b"] <= 0
            ):
                raise ValueError(
                    "Bell membership function must have positive 'b' parameter"
                )
            if "c" not in self.parameters or not isinstance(
                self.parameters["c"], (int, float)
            ):
                raise ValueError("Bell membership function must have 'c' parameter")

        elif self.type == MembershipFunctionType.SINGLETON:
            if "value" not in self.parameters or not isinstance(
                self.parameters["value"], (int, float)
            ):
                raise ValueError(
                    "Singleton membership function must have 'value' parameter"
                )

        return self


class FuzzyVariable(BaseModel):
    """
    Definition of a fuzzy variable.

    Attributes:
        name (str): Name of the fuzzy variable
        description (Optional[str]): Description of the variable
        range (List[float]): Range of possible values [min, max]
        membership_functions (List[MembershipFunction]): Membership functions for this variable
    """

    name: str = Field(..., description="Name of the fuzzy variable")
    description: Optional[str] = Field(None, description="Description of the variable")
    range: List[float] = Field(..., description="Range of possible values [min, max]")
    membership_functions: List[MembershipFunction] = Field(
        ..., description="Membership functions for this variable"
    )

    @field_validator("range")
    @classmethod
    def validate_range(cls, v: List[float]) -> List[float]:
        """Validate the range definition."""
        if len(v) != 2:
            raise ValueError("Range must be a list with 2 values [min, max]")
        if v[0] >= v[1]:
            raise ValueError("Range minimum must be less than maximum")
        return v

    @model_validator(mode="after")
    def validate_membership_functions(self) -> "FuzzyVariable":
        """Validate that membership function names are unique."""
        names = set()
        for mf in self.membership_functions:
            if mf.name in names:
                raise ValueError(f"Duplicate membership function name: {mf.name}")
            names.add(mf.name)
        return self


class FuzzyRule(BaseModel):
    """
    Definition of a fuzzy rule.

    Attributes:
        id (str): Unique identifier for the rule
        description (Optional[str]): Human-readable description
        antecedent (str): Rule antecedent (IF part)
        consequent (str): Rule consequent (THEN part)
        weight (float): Rule weight (0.0 to 1.0)
    """

    id: str = Field(..., description="Unique identifier for the rule")
    description: Optional[str] = Field(None, description="Human-readable description")
    antecedent: str = Field(..., description="Rule antecedent (IF part)")
    consequent: str = Field(..., description="Rule consequent (THEN part)")
    weight: float = Field(1.0, description="Rule weight (0.0 to 1.0)")

    @field_validator("weight")
    @classmethod
    def validate_weight(cls, v: float) -> float:
        """Validate that weight is between 0 and 1."""
        if v < 0.0 or v > 1.0:
            raise ValueError("Rule weight must be between 0.0 and 1.0")
        return v


class FuzzySystem(BaseModel):
    """
    Definition of a complete fuzzy system.

    Attributes:
        name (str): Name of the fuzzy system
        description (Optional[str]): Description of the system
        input_variables (List[FuzzyVariable]): Input fuzzy variables
        output_variables (List[FuzzyVariable]): Output fuzzy variables
        rules (List[FuzzyRule]): Fuzzy rules
        defuzzification_method (str): Method used for defuzzification
    """

    name: str = Field(..., description="Name of the fuzzy system")
    description: Optional[str] = Field(None, description="Description of the system")
    input_variables: List[FuzzyVariable] = Field(
        ..., description="Input fuzzy variables"
    )
    output_variables: List[FuzzyVariable] = Field(
        ..., description="Output fuzzy variables"
    )
    rules: List[FuzzyRule] = Field(..., description="Fuzzy rules")
    defuzzification_method: str = Field(
        "centroid", description="Method used for defuzzification"
    )

    @field_validator("defuzzification_method")
    @classmethod
    def validate_defuzzification_method(cls, v: str) -> str:
        """Validate the defuzzification method."""
        valid_methods = [
            "centroid",
            "bisector",
            "mean_of_maximum",
            "smallest_of_maximum",
            "largest_of_maximum",
        ]
        if v not in valid_methods:
            raise ValueError(f"Defuzzification method must be one of {valid_methods}")
        return v

    @model_validator(mode="after")
    def validate_variable_references(self) -> "FuzzySystem":
        """Validate that variable names are unique across the system."""
        input_names = {var.name for var in self.input_variables}
        output_names = {var.name for var in self.output_variables}

        # Check for duplicate names between input and output variables
        duplicates = input_names.intersection(output_names)
        if duplicates:
            raise ValueError(
                f"Variable names must be unique across inputs and outputs. Duplicates: {duplicates}"
            )

        # Check for duplicate names within input variables
        if len(input_names) != len(self.input_variables):
            raise ValueError("Input variable names must be unique")

        # Check for duplicate names within output variables
        if len(output_names) != len(self.output_variables):
            raise ValueError("Output variable names must be unique")

        return self


class FuzzyConfig(BaseModel):
    """
    Configuration for a fuzzy logic setup.

    Attributes:
        id (str): Unique identifier for this configuration
        name (str): Display name
        description (Optional[str]): Description of this fuzzy configuration
        system (FuzzySystem): The fuzzy system definition
    """

    id: str = Field(..., description="Unique identifier for this configuration")
    name: str = Field(..., description="Display name")
    description: Optional[str] = Field(
        None, description="Description of this fuzzy configuration"
    )
    system: FuzzySystem = Field(..., description="The fuzzy system definition")


class FuzzyInput(BaseModel):
    """
    Input data for fuzzy system evaluation.

    Attributes:
        variable_name (str): Name of the input variable
        value (float): Input value
    """

    variable_name: str = Field(..., description="Name of the input variable")
    value: float = Field(..., description="Input value")


class FuzzyOutput(BaseModel):
    """
    Output data from fuzzy system evaluation.

    Attributes:
        variable_name (str): Name of the output variable
        value (float): Crisp output value
        membership_degrees (Optional[Dict[str, float]]): Membership degrees for each fuzzy set
    """

    variable_name: str = Field(..., description="Name of the output variable")
    value: float = Field(..., description="Crisp output value")
    membership_degrees: Optional[Dict[str, float]] = Field(
        None, description="Membership degrees for each fuzzy set"
    )


class FuzzyEvaluateRequest(BaseModel):
    """
    Request model for evaluating a fuzzy system.

    Attributes:
        config_id (str): ID of the fuzzy configuration to use
        inputs (List[FuzzyInput]): Input values for evaluation
        return_membership_degrees (bool): Whether to return membership degrees
    """

    config_id: str = Field(..., description="ID of the fuzzy configuration to use")
    inputs: List[FuzzyInput] = Field(..., description="Input values for evaluation")
    return_membership_degrees: bool = Field(
        False, description="Whether to return membership degrees"
    )


class FuzzyEvaluateResponse(ApiResponse[List[FuzzyOutput]]):
    """Response model for fuzzy system evaluation."""

    pass


class FuzzyConfigResponse(ApiResponse[FuzzyConfig]):
    """Response model for retrieving a fuzzy configuration."""

    pass


class FuzzyConfigsResponse(ApiResponse[List[FuzzyConfig]]):
    """Response model for listing available fuzzy configurations."""

    pass


# Models for the new fuzzy overlay API (slice 4)

class FuzzyMembershipPoint(BaseModel):
    """
    A single point in a fuzzy membership time series.
    
    Attributes:
        timestamp (str): ISO format timestamp
        value (Optional[float]): Membership value (0.0-1.0) or None for missing data
    """
    
    timestamp: str = Field(..., description="ISO format timestamp")
    value: Optional[float] = Field(None, description="Membership value (0.0-1.0) or None for missing data")
    
    @field_validator("value")
    @classmethod
    def validate_membership_value(cls, v: Optional[float]) -> Optional[float]:
        """Validate that membership value is in [0, 1] range."""
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError("Membership value must be between 0.0 and 1.0")
        return v


class FuzzySetMembership(BaseModel):
    """
    Membership data for a single fuzzy set over time.
    
    Attributes:
        set (str): Name of the fuzzy set (e.g., "low", "neutral", "high")
        membership (List[FuzzyMembershipPoint]): Time series of membership values
    """
    
    set: str = Field(..., description="Name of the fuzzy set")
    membership: List[FuzzyMembershipPoint] = Field(..., description="Time series of membership values")
    
    @field_validator("set")
    @classmethod
    def validate_set_name(cls, v: str) -> str:
        """Validate that set name is not empty."""
        if not v.strip():
            raise ValueError("Fuzzy set name cannot be empty")
        return v.strip()


# Note: FuzzyOverlayData is just a Dict[str, List[FuzzySetMembership]]
# We'll use this type directly in FuzzyOverlayResponse for simplicity


class FuzzyOverlayResponse(BaseModel):
    """
    Response model for the GET /fuzzy/data endpoint.
    
    Attributes:
        symbol (str): Trading symbol
        timeframe (str): Data timeframe
        data (Dict[str, List[FuzzySetMembership]]): Fuzzy overlay data by indicator
        warnings (Optional[List[str]]): Warning messages for invalid indicators
    """
    
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Data timeframe")
    data: Dict[str, List[FuzzySetMembership]] = Field(..., description="Fuzzy overlay data by indicator")
    warnings: Optional[List[str]] = Field(None, description="Warning messages for invalid indicators")
    
    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate that symbol is not empty."""
        if not v.strip():
            raise ValueError("Symbol cannot be empty")
        return v.strip().upper()
    
    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        """Validate that timeframe is not empty."""
        if not v.strip():
            raise ValueError("Timeframe cannot be empty")
        return v.strip()
    
    @model_validator(mode="after")
    def validate_data_consistency(self) -> "FuzzyOverlayResponse":
        """Validate that data is consistent."""
        if not self.data:
            # Empty data is allowed (e.g., no valid indicators)
            return self
        
        # Check that all indicators have at least one fuzzy set
        for indicator_name, fuzzy_sets in self.data.items():
            if not fuzzy_sets:
                raise ValueError(f"Indicator '{indicator_name}' must have at least one fuzzy set")
            
            # Check that fuzzy set names are unique within each indicator
            set_names = [fs.set for fs in fuzzy_sets]
            if len(set_names) != len(set(set_names)):
                raise ValueError(f"Fuzzy set names must be unique for indicator '{indicator_name}'")
        
        return self
