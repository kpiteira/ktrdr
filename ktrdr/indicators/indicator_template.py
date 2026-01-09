"""
Template for creating new indicators.

This file serves as a template and guide for implementing new indicators that
will automatically integrate with the testing framework.

Steps to create a new indicator:
1. Copy this file to a new module file (e.g., my_indicator.py)
2. Implement the indicator class following this template
3. Update __init__.py to import and expose your indicator
4. Register your indicator in tests/indicators/indicator_registry.py
5. Add reference values in tests/indicators/reference_datasets.py

Your indicator will then automatically be tested by the testing framework.
"""

import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator

# Get a logger for this module
logger = get_logger(__name__)


class NewIndicator(BaseIndicator):
    """
    Template for a new indicator implementation.

    Replace this docstring with a description of your indicator, including:
    - What the indicator measures
    - Common use cases
    - Default parameters and their meanings

    Attributes:
        name (str): The name of the indicator
        params (dict): Parameters for indicator calculation including:
            - param1 (type): Description of parameter
            - param2 (type): Description of parameter
    """

    def __init__(self, param1: int = 14, param2: str = "close"):
        """
        Initialize the indicator.

        Args:
            param1 (int): Description of parameter (default: 14)
            param2 (str): Description of parameter (default: 'close')
        """
        # Call parent constructor with name and parameters
        super().__init__(name="MY_INDICATOR", param1=param1, param2=param2)
        logger.debug(f"Initialized {self.name} indicator with params: {self.params}")

    def _validate_params(self, params):
        """
        Validate parameters for the indicator.

        Args:
            params (dict): Parameters to validate

        Returns:
            dict: Validated parameters

        Raises:
            DataError: If parameters are invalid
        """
        # Example parameter validation
        if "param1" in params:
            param1 = params["param1"]
            if not isinstance(param1, int):
                raise DataError(
                    message="Parameter 'param1' must be an integer",
                    error_code="DATA-InvalidType",
                    details={
                        "parameter": "param1",
                        "expected": "int",
                        "received": type(param1).__name__,
                    },
                )
            if param1 < 2:
                raise DataError(
                    message="Parameter 'param1' must be at least 2",
                    error_code="DATA-InvalidValue",
                    details={"parameter": "param1", "minimum": 2, "received": param1},
                )

        # Example validation for string parameter
        if "param2" in params and not isinstance(params["param2"], str):
            raise DataError(
                message="Parameter 'param2' must be a string",
                error_code="DATA-InvalidType",
                details={
                    "parameter": "param2",
                    "expected": "str",
                    "received": type(params["param2"]).__name__,
                },
            )

        return params

    def compute(self, df: pd.DataFrame) -> pd.Series:
        """
        Compute the indicator for the given data.

        Args:
            df (pd.DataFrame): DataFrame containing price data

        Returns:
            pd.Series: Series containing indicator values

        Raises:
            DataError: If input data is invalid or insufficient
        """
        # Validate input data
        param1 = self.params["param1"]
        param2 = self.params["param2"]

        # Ensure required columns are present
        self.validate_input_data(df, [param2])

        # Ensure we have enough data points
        self.validate_sufficient_data(df, param1)

        logger.debug(
            f"Computing {self.name} with param1={param1} on DataFrame with {len(df)} rows"
        )

        try:
            # Implement your indicator calculation here
            # This is just a placeholder implementation
            result = df[param2].rolling(window=param1).mean()

            # Note: In v3, column naming is handled by IndicatorEngine
            # No need to set result.name here

            logger.debug(
                f"{self.name} calculation completed, non-NaN values: {result.count()}"
            )
            return result

        except Exception as e:
            error_msg = f"Error calculating {self.name}: {str(e)}"
            logger.error(error_msg)
            raise DataError(
                message=error_msg,
                error_code="DATA-CalculationError",
                details={"indicator": self.name, "error": str(e)},
            ) from e


# To register this indicator for testing, add the following to
# tests/indicators/indicator_registry.py:
"""
# In register_builtin_indicators() function:
from ktrdr.indicators import NewIndicator

# Register new indicator
register_indicator(
    indicator_class=NewIndicator,
    default_params={'param1': 14, 'param2': 'close'},
    reference_datasets=['reference_dataset_1'],
    reference_values={
        'reference_dataset_1': {
            9: 105.0,  # Expected value at index 9
            19: 110.0,  # Expected value at index 19
            # Add more reference points as needed
        }
    },
    tolerance=0.5  # Tolerance for validation
)
"""

# Also add reference values to tests/indicators/reference_datasets.py:
"""
# In reference_datasets.py:
NEW_INDICATOR_REFERENCE_DATASET_1 = {
    'PARAM1_14': {
        9: 105.0,
        19: 110.0,
        # Add more reference points
    }
}

# Update REFERENCE_VALUES dictionary:
REFERENCE_VALUES = {
    # Existing indicators...
    'NEW_INDICATOR': {
        'dataset_1': NEW_INDICATOR_REFERENCE_DATASET_1,
    }
}

# Update TOLERANCES dictionary:
TOLERANCES = {
    # Existing indicators...
    'NEW_INDICATOR': 0.5,
}
"""
