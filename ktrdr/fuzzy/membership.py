"""
Membership function definitions for fuzzy logic.

This module defines the abstract base class for membership functions
and provides auto-registration via __init_subclass__ to MEMBERSHIP_REGISTRY.
"""

import inspect
from abc import ABC, abstractmethod
from typing import Any, Union

import numpy as np
import pandas as pd
from pydantic import BaseModel, ValidationError, field_validator

from ktrdr import get_logger
from ktrdr.core.type_registry import TypeRegistry
from ktrdr.errors import ConfigurationError

# Set up module-level logger
logger = get_logger(__name__)

# Global registry for all membership function types
MEMBERSHIP_REGISTRY: TypeRegistry["MembershipFunction"] = TypeRegistry(
    "membership function"
)


class MembershipFunction(ABC):
    """
    Abstract base class for fuzzy membership functions.

    All membership functions must implement the evaluate method
    that converts input values to membership degrees.

    Subclasses are automatically registered to MEMBERSHIP_REGISTRY via
    __init_subclass__. The canonical name is derived from the class name
    with "MF" suffix stripped (e.g., TriangularMF -> "triangular").

    Subclasses can define a Params nested class for Pydantic validation
    and an _aliases list for alternative lookup names.
    """

    class Params(BaseModel):
        """Base parameter schema. Subclasses can override with validators."""

        parameters: list[float]

    # Optional aliases for registry lookup (e.g., ["tri", "triangle"])
    _aliases: list[str] = []

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Auto-register concrete membership function subclasses."""
        super().__init_subclass__(**kwargs)

        # Skip abstract classes
        if inspect.isabstract(cls):
            return

        # Skip test classes (various module naming patterns from pytest)
        module = cls.__module__
        if (
            module.startswith("tests.")
            or ".tests." in module
            or module.startswith("test_")
            or "_test" in module
        ):
            return

        # Derive canonical name from class name
        name = cls.__name__
        if name.endswith("MF"):
            name = name[:-2]  # Strip "MF" suffix
        canonical = name.lower()

        # Build aliases list (always include full class name lowercase)
        aliases = [cls.__name__.lower()]
        if cls._aliases:
            aliases.extend(cls._aliases)

        MEMBERSHIP_REGISTRY.register(cls, canonical, aliases)

    def __init__(self, parameters: list[float]) -> None:
        """
        Initialize a membership function with validated parameters.

        Args:
            parameters: List of parameters for this membership function type

        Raises:
            ConfigurationError: If parameters are invalid
        """
        try:
            validated = self.__class__.Params(parameters=parameters)
        except ValidationError as e:
            raise ConfigurationError(
                f"Invalid parameters for {self.__class__.__name__}",
                error_code="MF-InvalidParameters",
                details={"validation_errors": e.errors()},
            ) from e
        self._init_from_params(validated.parameters)

    @abstractmethod
    def _init_from_params(self, parameters: list[float]) -> None:
        """
        Initialize instance attributes from validated parameters.

        Subclasses implement this to set their specific attributes.

        Args:
            parameters: Validated list of parameters
        """
        pass

    @abstractmethod
    def evaluate(
        self, x: Union[float, pd.Series, np.ndarray]
    ) -> Union[float, pd.Series, np.ndarray]:
        """
        Evaluate the membership function for a given input.

        Args:
            x: Input value(s) to evaluate

        Returns:
            Membership degree(s) in the range [0, 1]
        """
        pass


class TriangularMF(MembershipFunction):
    """
    Triangular membership function implementation.

    A triangular membership function is defined by three parameters [a, b, c]:
    - a: start point (membership degree = 0)
    - b: peak point (membership degree = 1)
    - c: end point (membership degree = 0)

    The membership degree μ(x) is calculated as:
    - μ(x) = 0,                 if x <= a or x >= c
    - μ(x) = (x - a) / (b - a), if a < x < b
    - μ(x) = (c - x) / (c - b), if b <= x < c

    Special cases:
    - If a = b, then μ(x) = 1 at x = a and decreases linearly to 0 at x = c
    - If b = c, then μ(x) increases linearly from 0 at x = a to 1 at x = c
    - If a = b = c, then μ(x) = 1 only at x = a = b = c, and 0 elsewhere
    """

    class Params(MembershipFunction.Params):
        """Parameter validation for triangular MF."""

        @field_validator("parameters")
        @classmethod
        def validate_parameters(cls, v: list[float]) -> list[float]:
            """Validate triangular MF parameters [a, b, c]."""
            if len(v) != 3:
                raise ValueError(
                    f"Triangular requires exactly 3 parameters [a, b, c], got {len(v)}"
                )
            a, b, c = v
            if not (a <= b <= c):
                raise ValueError(
                    f"Parameters must satisfy a <= b <= c, got a={a}, b={b}, c={c}"
                )
            return v

    def _init_from_params(self, parameters: list[float]) -> None:
        """Initialize triangular MF from validated parameters."""
        self.a, self.b, self.c = parameters

        # Handle degenerate cases for division operations
        self._ab_diff = max(
            self.b - self.a, np.finfo(float).eps
        )  # Avoid division by zero
        self._bc_diff = max(
            self.c - self.b, np.finfo(float).eps
        )  # Avoid division by zero

        logger.debug(
            f"Initialized triangular MF with parameters: a={self.a}, b={self.b}, c={self.c}"
        )

    def evaluate(
        self, x: Union[float, pd.Series, np.ndarray]
    ) -> Union[float, pd.Series, np.ndarray]:
        """
        Evaluate the triangular membership function for given input value(s).

        This method supports both scalar values and vectorized inputs (pandas Series or numpy arrays).

        Args:
            x: Input value(s) to evaluate

        Returns:
            Membership degree(s) in the range [0, 1]
        """
        # For scalar inputs
        if isinstance(x, (int, float)):
            return self._evaluate_scalar(x)

        # For pandas Series
        elif isinstance(x, pd.Series):
            logger.debug(
                f"Evaluating triangular MF for pandas Series of length {len(x)}"
            )
            return x.apply(self._evaluate_scalar)

        # For numpy arrays
        elif isinstance(x, np.ndarray):
            logger.debug(f"Evaluating triangular MF for numpy array of shape {x.shape}")
            # Vectorized implementation for numpy arrays
            result = np.zeros_like(x, dtype=float)

            # Calculate membership degrees for different regions
            # Region 1: a < x < b
            mask1 = (x > self.a) & (x < self.b)
            result[mask1] = (x[mask1] - self.a) / self._ab_diff

            # Region 2: b <= x < c
            mask2 = (x >= self.b) & (x < self.c)
            result[mask2] = (self.c - x[mask2]) / self._bc_diff

            # Region 3: x = b (peak point)
            # This is handled implicitly by the above conditions

            # Handle NaN values
            if np.isnan(x).any():
                logger.warning("NaN values encountered in input to triangular MF")
                result[np.isnan(x)] = np.nan

            return result

        else:
            logger.error(f"Unsupported input type for triangular MF: {type(x)}")
            raise TypeError(
                f"Unsupported input type: {type(x)}. Expected float, pd.Series, or np.ndarray."
            )

    def _evaluate_scalar(self, x: float) -> float:
        """
        Evaluate the triangular membership function for a single scalar value.

        Args:
            x: Input value to evaluate

        Returns:
            Membership degree in the range [0, 1]
        """
        # Handle NaN values
        if pd.isna(x):
            logger.debug("NaN value encountered in triangular MF evaluation")
            return np.nan

        # Special handling for the peak point (x = b)
        if x == self.b:
            return 1.0

        # Calculate membership degree based on input region
        if x <= self.a or x >= self.c:
            return 0.0
        elif x > self.a and x < self.b:
            return (x - self.a) / self._ab_diff
        elif x > self.b and x < self.c:
            return (self.c - x) / self._bc_diff
        else:
            # This should never happen due to the conditions above
            # but is included for completeness
            return 0.0

    def __repr__(self) -> str:
        """String representation of the triangular membership function."""
        return f"TriangularMF(a={self.a}, b={self.b}, c={self.c})"


class TrapezoidalMF(MembershipFunction):
    """
    Trapezoidal membership function implementation.

    A trapezoidal membership function is defined by four parameters [a, b, c, d]:
    - a: start point (membership degree = 0)
    - b: start of plateau (membership degree = 1)
    - c: end of plateau (membership degree = 1)
    - d: end point (membership degree = 0)

    The membership degree μ(x) is calculated as:
    - μ(x) = 0,                 if x <= a or x >= d
    - μ(x) = (x - a) / (b - a), if a < x < b
    - μ(x) = 1,                 if b <= x <= c
    - μ(x) = (d - x) / (d - c), if c < x < d
    """

    class Params(MembershipFunction.Params):
        """Parameter validation for trapezoidal MF."""

        @field_validator("parameters")
        @classmethod
        def validate_parameters(cls, v: list[float]) -> list[float]:
            """Validate trapezoidal MF parameters [a, b, c, d]."""
            if len(v) != 4:
                raise ValueError(
                    f"Trapezoidal requires exactly 4 parameters [a, b, c, d], got {len(v)}"
                )
            a, b, c, d = v
            if not (a <= b <= c <= d):
                raise ValueError(
                    f"Parameters must satisfy a <= b <= c <= d, got a={a}, b={b}, c={c}, d={d}"
                )
            return v

    def _init_from_params(self, parameters: list[float]) -> None:
        """Initialize trapezoidal MF from validated parameters."""
        self.a, self.b, self.c, self.d = parameters

        # Handle degenerate cases for division operations
        self._ab_diff = max(self.b - self.a, np.finfo(float).eps)
        self._dc_diff = max(self.d - self.c, np.finfo(float).eps)

        logger.debug(
            f"Initialized trapezoidal MF with parameters: a={self.a}, b={self.b}, c={self.c}, d={self.d}"
        )

    def evaluate(
        self, x: Union[float, pd.Series, np.ndarray]
    ) -> Union[float, pd.Series, np.ndarray]:
        """
        Evaluate the trapezoidal membership function for given input value(s).

        Args:
            x: Input value(s) to evaluate

        Returns:
            Membership degree(s) in the range [0, 1]
        """
        # For scalar inputs
        if isinstance(x, (int, float)):
            return self._evaluate_scalar(x)

        # For pandas Series
        elif isinstance(x, pd.Series):
            logger.debug(
                f"Evaluating trapezoidal MF for pandas Series of length {len(x)}"
            )
            return x.apply(self._evaluate_scalar)

        # For numpy arrays
        elif isinstance(x, np.ndarray):
            logger.debug(
                f"Evaluating trapezoidal MF for numpy array of shape {x.shape}"
            )
            result = np.zeros_like(x, dtype=float)

            # Region 1: a < x < b (rising edge)
            mask1 = (x > self.a) & (x < self.b)
            result[mask1] = (x[mask1] - self.a) / self._ab_diff

            # Region 2: b <= x <= c (plateau)
            mask2 = (x >= self.b) & (x <= self.c)
            result[mask2] = 1.0

            # Region 3: c < x < d (falling edge)
            mask3 = (x > self.c) & (x < self.d)
            result[mask3] = (self.d - x[mask3]) / self._dc_diff

            # Handle NaN values
            if np.isnan(x).any():
                logger.warning("NaN values encountered in input to trapezoidal MF")
                result[np.isnan(x)] = np.nan

            return result

        else:
            logger.error(f"Unsupported input type for trapezoidal MF: {type(x)}")
            raise TypeError(
                f"Unsupported input type: {type(x)}. Expected float, pd.Series, or np.ndarray."
            )

    def _evaluate_scalar(self, x: float) -> float:
        """
        Evaluate the trapezoidal membership function for a single scalar value.

        Args:
            x: Input value to evaluate

        Returns:
            Membership degree in the range [0, 1]
        """
        # Handle NaN values
        if pd.isna(x):
            logger.debug("NaN value encountered in trapezoidal MF evaluation")
            return np.nan

        # Calculate membership degree based on input region
        if x <= self.a or x >= self.d:
            return 0.0
        elif x > self.a and x < self.b:
            return (x - self.a) / self._ab_diff
        elif x >= self.b and x <= self.c:
            return 1.0
        elif x > self.c and x < self.d:
            return (self.d - x) / self._dc_diff
        else:
            return 0.0

    def __repr__(self) -> str:
        """String representation of the trapezoidal membership function."""
        return f"TrapezoidalMF(a={self.a}, b={self.b}, c={self.c}, d={self.d})"


class GaussianMF(MembershipFunction):
    """
    Gaussian membership function implementation.

    A Gaussian membership function is defined by two parameters [μ, σ]:
    - μ: center/mean of the Gaussian curve (peak point)
    - σ: standard deviation (controls the width of the curve)

    The membership degree μ(x) is calculated as:
    μ(x) = exp(-0.5 * ((x - μ) / σ)²)
    """

    class Params(MembershipFunction.Params):
        """Parameter validation for Gaussian MF."""

        @field_validator("parameters")
        @classmethod
        def validate_parameters(cls, v: list[float]) -> list[float]:
            """Validate Gaussian MF parameters [μ, σ]."""
            if len(v) != 2:
                raise ValueError(
                    f"Gaussian requires exactly 2 parameters [μ, σ], got {len(v)}"
                )
            mu, sigma = v
            if sigma <= 0:
                raise ValueError(f"Sigma must be > 0, got {sigma}")
            return v

    def _init_from_params(self, parameters: list[float]) -> None:
        """Initialize Gaussian MF from validated parameters."""
        self.mu, self.sigma = parameters

        logger.debug(
            f"Initialized Gaussian MF with parameters: μ={self.mu}, σ={self.sigma}"
        )

    def evaluate(
        self, x: Union[float, pd.Series, np.ndarray]
    ) -> Union[float, pd.Series, np.ndarray]:
        """
        Evaluate the Gaussian membership function for given input value(s).

        Args:
            x: Input value(s) to evaluate

        Returns:
            Membership degree(s) in the range [0, 1]
        """
        # For scalar inputs
        if isinstance(x, (int, float)):
            return self._evaluate_scalar(x)

        # For pandas Series
        elif isinstance(x, pd.Series):
            logger.debug(f"Evaluating Gaussian MF for pandas Series of length {len(x)}")
            return x.apply(self._evaluate_scalar)

        # For numpy arrays (vectorized implementation)
        elif isinstance(x, np.ndarray):
            logger.debug(f"Evaluating Gaussian MF for numpy array of shape {x.shape}")

            # Vectorized Gaussian calculation
            z = (x - self.mu) / self.sigma
            result = np.exp(-0.5 * z * z)

            # Handle NaN values
            if np.isnan(x).any():
                logger.warning("NaN values encountered in input to Gaussian MF")
                result[np.isnan(x)] = np.nan

            return result

        else:
            logger.error(f"Unsupported input type for Gaussian MF: {type(x)}")
            raise TypeError(
                f"Unsupported input type: {type(x)}. Expected float, pd.Series, or np.ndarray."
            )

    def _evaluate_scalar(self, x: float) -> float:
        """
        Evaluate the Gaussian membership function for a single scalar value.

        Args:
            x: Input value to evaluate

        Returns:
            Membership degree in the range [0, 1]
        """
        # Handle NaN values
        if pd.isna(x):
            logger.debug("NaN value encountered in Gaussian MF evaluation")
            return np.nan

        # Calculate Gaussian membership
        z = (x - self.mu) / self.sigma
        return np.exp(-0.5 * z * z)

    def __repr__(self) -> str:
        """String representation of the Gaussian membership function."""
        return f"GaussianMF(μ={self.mu}, σ={self.sigma})"


class MembershipFunctionFactory:
    """
    Factory class for creating membership function instances.

    This factory provides a centralized way to create membership functions
    based on configuration parameters and supports extensibility for new
    membership function types.
    """

    @staticmethod
    def create(mf_type: str, parameters: list[float]) -> MembershipFunction:
        """
        Create a membership function instance based on type and parameters.

        Args:
            mf_type: Type of membership function ("triangular", "trapezoidal", "gaussian")
            parameters: Parameters for the membership function

        Returns:
            MembershipFunction instance

        Raises:
            ConfigurationError: If the membership function type is unknown
        """
        mf_type_lower = mf_type.lower()

        if mf_type_lower == "triangular":
            return TriangularMF(parameters)
        elif mf_type_lower == "trapezoidal":
            return TrapezoidalMF(parameters)
        elif mf_type_lower == "gaussian":
            return GaussianMF(parameters)
        else:
            logger.error(f"Unknown membership function type: {mf_type}")
            raise ConfigurationError(
                message=f"Unknown membership function type: {mf_type}",
                error_code="MF-UnknownType",
                details={
                    "type": mf_type,
                    "supported_types": ["triangular", "trapezoidal", "gaussian"],
                },
            )

    @staticmethod
    def get_supported_types() -> list[str]:
        """
        Get list of supported membership function types.

        Returns:
            List of supported membership function type names
        """
        return ["triangular", "trapezoidal", "gaussian"]
