"""
Tests for the On-Balance Volume (OBV) indicator.

This module tests the OBV indicator implementation including:
- Basic functionality with Series output
- Parameter validation using schema system
- Edge cases and error handling
- Reference value validation
"""

import pandas as pd
import pytest

from ktrdr.errors import DataError
from ktrdr.indicators.obv_indicator import OBVIndicator
from ktrdr.indicators.schemas import OBV_SCHEMA


class TestOBVIndicator:
    """Test the OBV indicator implementation."""

    def test_obv_initialization(self):
        """Test OBV indicator initialization."""
        # OBV has no parameters
        obv = OBVIndicator()
        assert obv.name == "OBV"
        assert not obv.display_as_overlay  # Should be in separate panel

    def test_obv_parameter_validation(self):
        """Test parameter validation using schema system."""
        # OBV should accept empty parameters
        params = {}
        validated = OBV_SCHEMA.validate(params)
        assert validated == {}

        # Test that unknown parameters are rejected
        with pytest.raises(DataError):
            OBV_SCHEMA.validate({"unknown_param": 123})

    def test_obv_basic_computation(self):
        """Test basic OBV computation with simple data."""
        # Create data with rising prices and volume
        data = pd.DataFrame(
            {
                "close": [100, 102, 101, 105, 104, 107, 106, 110],
                "volume": [1000, 1500, 800, 2000, 1200, 1800, 900, 2500],
            }
        )

        obv = OBVIndicator()
        result = obv.compute(data)

        # Check that result is a Series
        assert isinstance(result, pd.Series)
        assert result.name == "OBV"

        # Check that we have the right number of rows
        assert len(result) == len(data)

        # Manual calculation verification:
        # Index 0: OBV = 0 (starting point)
        # Index 1: Price 100->102 (up), OBV = 0 + 1500 = 1500
        # Index 2: Price 102->101 (down), OBV = 1500 - 800 = 700
        # Index 3: Price 101->105 (up), OBV = 700 + 2000 = 2700
        # Index 4: Price 105->104 (down), OBV = 2700 - 1200 = 1500
        # Index 5: Price 104->107 (up), OBV = 1500 + 1800 = 3300
        # Index 6: Price 107->106 (down), OBV = 3300 - 900 = 2400
        # Index 7: Price 106->110 (up), OBV = 2400 + 2500 = 4900

        expected_values = [0, 1500, 700, 2700, 1500, 3300, 2400, 4900]

        for i, expected in enumerate(expected_values):
            assert result.iloc[i] == expected, (
                f"Mismatch at index {i}: got {result.iloc[i]}, expected {expected}"
            )

    def test_obv_with_flat_prices(self):
        """Test OBV with flat prices (no price movement)."""
        # Create data with constant prices
        data = pd.DataFrame(
            {
                "close": [100, 100, 100, 100, 100],
                "volume": [1000, 1500, 800, 2000, 1200],
            }
        )

        obv = OBVIndicator()
        result = obv.compute(data)

        # With no price movement, OBV should remain at 0
        expected_values = [0, 0, 0, 0, 0]
        for i, expected in enumerate(expected_values):
            assert result.iloc[i] == expected

    def test_obv_with_declining_prices(self):
        """Test OBV with consistently declining prices."""
        # Create data with falling prices
        data = pd.DataFrame(
            {
                "close": [110, 108, 105, 102, 100],
                "volume": [1000, 1500, 800, 2000, 1200],
            }
        )

        obv = OBVIndicator()
        result = obv.compute(data)

        # Manual calculation:
        # Index 0: OBV = 0
        # Index 1: Price 110->108 (down), OBV = 0 - 1500 = -1500
        # Index 2: Price 108->105 (down), OBV = -1500 - 800 = -2300
        # Index 3: Price 105->102 (down), OBV = -2300 - 2000 = -4300
        # Index 4: Price 102->100 (down), OBV = -4300 - 1200 = -5500

        expected_values = [0, -1500, -2300, -4300, -5500]

        for i, expected in enumerate(expected_values):
            assert result.iloc[i] == expected

    def test_obv_with_mixed_volume_patterns(self):
        """Test OBV with various volume patterns."""
        # Create data with varied volume and price patterns
        data = pd.DataFrame(
            {
                "close": [100, 102, 102, 104, 103],  # up, flat, up, down
                "volume": [1000, 2000, 1500, 3000, 2500],
            }
        )

        obv = OBVIndicator()
        result = obv.compute(data)

        # Manual calculation:
        # Index 0: OBV = 0
        # Index 1: Price 100->102 (up), OBV = 0 + 2000 = 2000
        # Index 2: Price 102->102 (flat), OBV = 2000 + 0 = 2000
        # Index 3: Price 102->104 (up), OBV = 2000 + 3000 = 5000
        # Index 4: Price 104->103 (down), OBV = 5000 - 2500 = 2500

        expected_values = [0, 2000, 2000, 5000, 2500]

        for i, expected in enumerate(expected_values):
            assert result.iloc[i] == expected

    def test_obv_missing_columns(self):
        """Test error handling for missing required columns."""
        # Missing 'volume' column
        data = pd.DataFrame(
            {
                "close": [100, 101, 102],
            }
        )

        obv = OBVIndicator()
        with pytest.raises(DataError, match="OBV requires columns: volume"):
            obv.compute(data)

        # Missing 'close' column
        data = pd.DataFrame(
            {
                "volume": [1000, 1500, 800],
            }
        )

        with pytest.raises(DataError, match="OBV requires columns: close"):
            obv.compute(data)

        # Missing both columns
        data = pd.DataFrame(
            {
                "open": [100, 101, 102],
            }
        )

        with pytest.raises(DataError, match="OBV requires columns"):
            obv.compute(data)

    def test_obv_insufficient_data(self):
        """Test error handling for insufficient data."""
        # Create single data point (insufficient)
        data = pd.DataFrame(
            {
                "close": [100],
                "volume": [1000],
            }
        )

        obv = OBVIndicator()
        with pytest.raises(DataError, match="OBV requires at least 2 data points"):
            obv.compute(data)

    def test_obv_with_zero_volume(self):
        """Test OBV with zero volume periods."""
        # Create data with some zero volume periods
        data = pd.DataFrame(
            {
                "close": [100, 102, 101, 105, 104],
                "volume": [1000, 0, 800, 0, 1200],
            }
        )

        obv = OBVIndicator()
        result = obv.compute(data)

        # Manual calculation:
        # Index 0: OBV = 0
        # Index 1: Price 100->102 (up), Volume = 0, OBV = 0 + 0 = 0
        # Index 2: Price 102->101 (down), Volume = 800, OBV = 0 - 800 = -800
        # Index 3: Price 101->105 (up), Volume = 0, OBV = -800 + 0 = -800
        # Index 4: Price 105->104 (down), Volume = 1200, OBV = -800 - 1200 = -2000

        expected_values = [0, 0, -800, -800, -2000]

        for i, expected in enumerate(expected_values):
            assert result.iloc[i] == expected

    def test_obv_with_large_numbers(self):
        """Test OBV with large volume numbers."""
        # Create data with large volume values
        data = pd.DataFrame(
            {
                "close": [1000, 1100, 900, 1200],
                "volume": [1000000, 2000000, 1500000, 3000000],
            }
        )

        obv = OBVIndicator()
        result = obv.compute(data)

        # Manual calculation:
        # Index 0: OBV = 0
        # Index 1: Price 1000->1100 (up), OBV = 0 + 2000000 = 2000000
        # Index 2: Price 1100->900 (down), OBV = 2000000 - 1500000 = 500000
        # Index 3: Price 900->1200 (up), OBV = 500000 + 3000000 = 3500000

        expected_values = [0, 2000000, 500000, 3500000]

        for i, expected in enumerate(expected_values):
            assert result.iloc[i] == expected

    def test_obv_edge_cases(self):
        """Test OBV with various edge cases."""
        # Test with minimum required data
        data = pd.DataFrame(
            {
                "close": [100, 105],
                "volume": [1000, 1500],
            }
        )

        obv = OBVIndicator()
        result = obv.compute(data)

        assert isinstance(result, pd.Series)
        assert len(result) == 2
        assert result.name == "OBV"

        # Manual calculation:
        # Index 0: OBV = 0
        # Index 1: Price 100->105 (up), OBV = 0 + 1500 = 1500
        assert result.iloc[0] == 0
        assert result.iloc[1] == 1500

    def test_obv_with_decimal_prices(self):
        """Test OBV with decimal price values."""
        # Create data with decimal prices
        data = pd.DataFrame(
            {
                "close": [100.50, 100.75, 100.25, 101.00],
                "volume": [1000, 1500, 800, 2000],
            }
        )

        obv = OBVIndicator()
        result = obv.compute(data)

        # Manual calculation:
        # Index 0: OBV = 0
        # Index 1: Price 100.50->100.75 (up), OBV = 0 + 1500 = 1500
        # Index 2: Price 100.75->100.25 (down), OBV = 1500 - 800 = 700
        # Index 3: Price 100.25->101.00 (up), OBV = 700 + 2000 = 2700

        expected_values = [0, 1500, 700, 2700]

        for i, expected in enumerate(expected_values):
            assert result.iloc[i] == expected

    def test_obv_standard_reference_data(self):
        """Test OBV with standard reference dataset."""
        # Create a simple dataset for testing
        # OBV needs volume data, which the standard reference doesn't have
        # So we'll create our own reference data with volume
        data = pd.DataFrame(
            {
                "close": [100, 101, 102, 103, 104, 103, 102, 101, 100, 101],
                "volume": [1000, 1500, 1200, 1800, 1000, 2000, 1500, 1200, 1800, 1600],
            }
        )

        obv = OBVIndicator()
        result = obv.compute(data)

        # Verify structure
        assert isinstance(result, pd.Series)
        assert len(result) == len(data)
        assert result.name == "OBV"

        # Check some basic properties
        # OBV should start at 0
        assert result.iloc[0] == 0

        # OBV should be cumulative (each value depends on previous)
        # With rising then falling prices, OBV should show the pattern
        # First half (rising): should accumulate positive
        # Second half (falling): should reduce from the peak

        mid_point = len(result) // 2
        peak_obv = result.iloc[mid_point]
        final_obv = result.iloc[-1]

        # Peak should be higher than start and end (given the price pattern)
        assert peak_obv > 0
        assert abs(final_obv) < abs(peak_obv)  # Final should be closer to 0

    def test_obv_mathematical_accuracy(self):
        """Test OBV mathematical accuracy with known values."""
        # Create specific data for precise calculation verification
        data = pd.DataFrame(
            {
                "close": [50, 52, 51, 54, 53],
                "volume": [100, 200, 150, 300, 250],
            }
        )

        obv = OBVIndicator()
        result = obv.compute(data)

        # Detailed manual calculation:
        # Index 0: OBV = 0 (starting point)
        # Index 1: Price 50->52 (+2), Volume 200, OBV = 0 + 200 = 200
        # Index 2: Price 52->51 (-1), Volume 150, OBV = 200 - 150 = 50
        # Index 3: Price 51->54 (+3), Volume 300, OBV = 50 + 300 = 350
        # Index 4: Price 54->53 (-1), Volume 250, OBV = 350 - 250 = 100

        expected_values = [0, 200, 50, 350, 100]

        for i, expected in enumerate(expected_values):
            assert result.iloc[i] == expected

    def test_obv_negative_volume_handling(self):
        """Test OBV behavior with negative volume (edge case)."""
        # Some data sources might have negative volume for corrections
        data = pd.DataFrame(
            {
                "close": [100, 102, 101, 105],
                "volume": [1000, -500, 800, 1200],  # Negative volume
            }
        )

        obv = OBVIndicator()
        result = obv.compute(data)

        # Manual calculation (negative volume should be handled normally):
        # Index 0: OBV = 0
        # Index 1: Price 100->102 (up), Volume -500, OBV = 0 + (-500) = -500
        # Index 2: Price 102->101 (down), Volume 800, OBV = -500 - 800 = -1300
        # Index 3: Price 101->105 (up), Volume 1200, OBV = -1300 + 1200 = -100

        expected_values = [0, -500, -1300, -100]

        for i, expected in enumerate(expected_values):
            assert result.iloc[i] == expected


class TestOBVSchemaValidation:
    """Test schema-based parameter validation for OBV."""

    def test_schema_comprehensive_validation(self):
        """Test comprehensive schema validation."""
        # Test empty parameters (OBV has no parameters)
        validated = OBV_SCHEMA.validate({})
        assert validated == {}

        # Test that unknown parameters are rejected
        with pytest.raises(DataError):
            OBV_SCHEMA.validate({"unknown_param": 123})

    def test_schema_error_details(self):
        """Test detailed error information from schema validation."""
        try:
            OBV_SCHEMA.validate({"invalid_param": "value"})
            raise AssertionError("Should have raised DataError")
        except DataError as e:
            assert e.error_code == "PARAM-Unknown"
            assert "invalid_param" in str(e.message)
