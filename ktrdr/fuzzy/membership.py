"""
Membership function definitions for fuzzy logic.

This module defines the abstract base class for membership functions
and implements the triangular membership function for Phase 1.
"""

from abc import ABC, abstractmethod
from typing import List, Union

import numpy as np
import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import ConfigurationError

# Set up module-level logger
logger = get_logger(__name__)


class MembershipFunction(ABC):
    """
    Abstract base class for fuzzy membership functions.

    All membership functions must implement the evaluate method
    that converts input values to membership degrees.
    """

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

    def __init__(self, parameters: list[float]):
        """
        Initialize a triangular membership function with parameters [a, b, c].

        Args:
            parameters: List of three parameters [a, b, c] where:
                        a: start point (membership = 0)
                        b: peak point (membership = 1)
                        c: end point (membership = 0)

        Raises:
            ConfigurationError: If parameters are invalid
        """
        if len(parameters) != 3:
            logger.error(
                f"Invalid triangular MF parameters: expected 3, got {len(parameters)}"
            )
            raise ConfigurationError(
                message="Triangular membership function requires exactly 3 parameters [a, b, c]",
                error_code="MF-InvalidParameterCount",
                details={"expected": 3, "actual": len(parameters)},
            )

        self.a, self.b, self.c = parameters

        # Validate parameter ordering
        if not (self.a <= self.b <= self.c):
            logger.error(
                f"Invalid triangular MF parameter order: a={self.a}, b={self.b}, c={self.c}"
            )
            raise ConfigurationError(
                message="Triangular membership function parameters must satisfy: a ≤ b ≤ c",
                error_code="MF-InvalidParameterOrder",
                details={"parameters": {"a": self.a, "b": self.b, "c": self.c}},
            )

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

    def __init__(self, parameters: list[float]):
        """
        Initialize a trapezoidal membership function with parameters [a, b, c, d].

        Args:
            parameters: List of four parameters [a, b, c, d] where:
                        a: start point (membership = 0)
                        b: start of plateau (membership = 1)
                        c: end of plateau (membership = 1)
                        d: end point (membership = 0)

        Raises:
            ConfigurationError: If parameters are invalid
        """
        if len(parameters) != 4:
            logger.error(
                f"Invalid trapezoidal MF parameters: expected 4, got {len(parameters)}"
            )
            raise ConfigurationError(
                message="Trapezoidal membership function requires exactly 4 parameters [a, b, c, d]",
                error_code="MF-InvalidParameterCount",
                details={"expected": 4, "actual": len(parameters)},
            )

        self.a, self.b, self.c, self.d = parameters

        # Validate parameter ordering
        if not (self.a <= self.b <= self.c <= self.d):
            logger.error(
                f"Invalid trapezoidal MF parameter order: a={self.a}, b={self.b}, c={self.c}, d={self.d}"
            )
            raise ConfigurationError(
                message="Trapezoidal membership function parameters must satisfy: a ≤ b ≤ c ≤ d",
                error_code="MF-InvalidParameterOrder",
                details={
                    "parameters": {"a": self.a, "b": self.b, "c": self.c, "d": self.d}
                },
            )

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

    def __init__(self, parameters: list[float]):
        """
        Initialize a Gaussian membership function with parameters [μ, σ].

        Args:
            parameters: List of two parameters [μ, σ] where:
                        μ: center/mean of the Gaussian curve
                        σ: standard deviation (must be > 0)

        Raises:
            ConfigurationError: If parameters are invalid
        """
        if len(parameters) != 2:
            logger.error(
                f"Invalid Gaussian MF parameters: expected 2, got {len(parameters)}"
            )
            raise ConfigurationError(
                message="Gaussian membership function requires exactly 2 parameters [μ, σ]",
                error_code="MF-InvalidParameterCount",
                details={"expected": 2, "actual": len(parameters)},
            )

        self.mu, self.sigma = parameters

        # Validate sigma > 0
        if self.sigma <= 0:
            logger.error(f"Invalid Gaussian MF sigma: {self.sigma} (must be > 0)")
            raise ConfigurationError(
                message="Gaussian membership function sigma must be greater than 0",
                error_code="MF-InvalidSigma",
                details={"sigma": self.sigma},
            )

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
