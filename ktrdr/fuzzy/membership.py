"""
Membership function definitions for fuzzy logic.

This module defines the abstract base class for membership functions
and implements the triangular membership function for Phase 1.
"""

from abc import ABC, abstractmethod
from typing import List, Union

import numpy as np
import pandas as pd

from ktrdr.errors import ConfigurationError
from ktrdr import get_logger

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

    def __init__(self, parameters: List[float]):
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
