"""
Tests for the BaseIndicator abstract class.
"""

import pandas as pd
import pytest

from ktrdr.errors import DataError
from ktrdr.errors.exceptions import ValidationError
from ktrdr.indicators import BaseIndicator


class DummyIndicator(BaseIndicator):
    """A concrete implementation of BaseIndicator for testing purposes."""

    def __init__(self, name="Dummy", period=14, source="close", **kwargs):
        """Initialize the dummy indicator."""
        all_params = {"period": period, "source": source}
        all_params.update(kwargs)
        super().__init__(name=name, **all_params)

    def _validate_params(self, params):
        """Validate parameters for the dummy indicator."""
        if "period" in params and (params["period"] < 1 or params["period"] > 100):
            raise DataError(
                message="Period must be between 1 and 100",
                error_code="DATA-InvalidPeriod",
                details={"period": params["period"]},
            )
        return params

    def compute(self, df: pd.DataFrame) -> pd.Series:
        """Compute a dummy indicator - just returns the source column."""
        self.validate_input_data(df, [self.params["source"]])
        self.validate_sufficient_data(df, self.params["period"])

        # Simply return the source column for testing
        return df[self.params["source"]]


class DummyMultiOutputIndicator(BaseIndicator):
    """A multi-output indicator for testing the new interface."""

    def __init__(self, name="DummyMulti", period=14, **kwargs):
        """Initialize the dummy multi-output indicator."""
        all_params = {"period": period}
        all_params.update(kwargs)
        super().__init__(name=name, **all_params)

    @classmethod
    def is_multi_output(cls) -> bool:
        """This indicator returns a DataFrame."""
        return True

    @classmethod
    def get_output_names(cls) -> list[str]:
        """Return semantic output names."""
        return ["upper", "middle", "lower"]

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute dummy multi-output values."""
        return pd.DataFrame(
            {
                "upper": df["close"] * 1.1,
                "middle": df["close"],
                "lower": df["close"] * 0.9,
            }
        )


class TestBaseIndicator:
    """Test cases for the BaseIndicator abstract class."""

    def test_initialization(self):
        """Test that indicators can be initialized with parameters."""
        indicator = DummyIndicator(name="TestIndicator", period=10, source="close")
        assert indicator.name == "TestIndicator"
        assert indicator.params["period"] == 10
        assert indicator.params["source"] == "close"

    def test_parameter_validation(self):
        """Test that parameter validation works."""
        # Valid parameter
        indicator = DummyIndicator(period=50)
        assert indicator.params["period"] == 50

        # Invalid parameter
        with pytest.raises(DataError) as excinfo:
            DummyIndicator(period=101)
        assert "Period must be between 1 and 100" in str(excinfo.value)
        assert excinfo.value.error_code == "DATA-InvalidPeriod"

    def test_input_data_validation(self):
        """Test validation of input data."""
        indicator = DummyIndicator(source="close")

        # Valid DataFrame
        valid_df = pd.DataFrame({"close": [1, 2, 3]})
        indicator.validate_input_data(valid_df, ["close"])

        # Empty DataFrame
        with pytest.raises(DataError) as excinfo:
            indicator.validate_input_data(pd.DataFrame(), ["close"])
        assert "Input DataFrame is empty" in str(excinfo.value)

        # Missing columns
        with pytest.raises(DataError) as excinfo:
            indicator.validate_input_data(pd.DataFrame({"open": [1, 2, 3]}), ["close"])
        assert "Missing required columns" in str(excinfo.value)

    def test_sufficient_data_validation(self):
        """Test validation of sufficient data points."""
        indicator = DummyIndicator(period=5)

        # Sufficient data
        valid_df = pd.DataFrame({"close": range(10)})
        indicator.validate_sufficient_data(valid_df, 5)

        # Insufficient data
        with pytest.raises(DataError) as excinfo:
            indicator.validate_sufficient_data(pd.DataFrame({"close": range(3)}), 5)
        assert "Insufficient data" in str(excinfo.value)
        assert "3 points available, 5 required" in str(excinfo.value)

    def test_compute_method(self):
        """Test the compute method implementation."""
        indicator = DummyIndicator()
        df = pd.DataFrame({"close": range(20)})
        result = indicator.compute(df)

        # For our dummy indicator, result should be the same as the input column
        pd.testing.assert_series_equal(result, df["close"])

    def test_name_validation(self):
        """Test validation of indicator names."""
        # Valid name
        indicator = DummyIndicator(name="ValidName123")
        assert indicator.name == "ValidName123"

        # Invalid name (special characters)
        with pytest.raises(ValidationError) as excinfo:
            DummyIndicator(name="Invalid-Name!")
        assert "String does not match required pattern" in str(excinfo.value)

    def test_get_output_names_default(self):
        """Test that default get_output_names() returns empty list."""
        # Single-output indicator should return empty list
        assert DummyIndicator.get_output_names() == []

    def test_get_primary_output_default(self):
        """Test that default get_primary_output() returns None."""
        # Single-output indicator should return None
        assert DummyIndicator.get_primary_output() is None

    def test_multi_output_get_output_names(self):
        """Test that multi-output indicators return correct output names."""
        # Multi-output indicator should return list of semantic names
        assert DummyMultiOutputIndicator.get_output_names() == [
            "upper",
            "middle",
            "lower",
        ]

    def test_multi_output_get_primary_output(self):
        """Test that multi-output indicators return first output as primary."""
        # Primary output should be first in the list
        assert DummyMultiOutputIndicator.get_primary_output() == "upper"
