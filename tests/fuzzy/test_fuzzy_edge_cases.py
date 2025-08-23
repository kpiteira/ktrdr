"""
Tests for edge cases and performance of fuzzy logic implementation.

This module contains tests that verify the fuzzy logic system handles edge cases
correctly and performs efficiently with large datasets.
"""

import time

import numpy as np
import pandas as pd
import pytest

from ktrdr.fuzzy import FuzzyConfig, FuzzyEngine


class TestFuzzyEdgeCases:
    """Test suite for fuzzy logic edge cases."""

    @pytest.fixture
    def standard_fuzzy_config(self):
        """Fixture for a standard fuzzy configuration with known parameters."""
        config_dict = {
            "rsi": {
                "low": {"type": "triangular", "parameters": [0.0, 30.0, 50.0]},
                "medium": {"type": "triangular", "parameters": [30.0, 50.0, 70.0]},
                "high": {"type": "triangular", "parameters": [50.0, 70.0, 100.0]},
            }
        }
        return FuzzyConfig.model_validate(config_dict)

    @pytest.fixture
    def standard_fuzzy_engine(self, standard_fuzzy_config):
        """Fixture for a FuzzyEngine with standardized configuration."""
        return FuzzyEngine(standard_fuzzy_config)

    @pytest.fixture
    def edge_case_fuzzy_config(self):
        """Fixture for fuzzy configuration with edge case parameters."""
        config_dict = {
            "rsi": {
                # Singleton (a = b = c)
                "singleton": {"type": "triangular", "parameters": [50.0, 50.0, 50.0]},
                # Left shoulder (a = b)
                "left_shoulder": {"type": "triangular", "parameters": [0.0, 0.0, 50.0]},
                # Right shoulder (b = c)
                "right_shoulder": {
                    "type": "triangular",
                    "parameters": [50.0, 100.0, 100.0],
                },
                # Very narrow triangle
                "narrow": {"type": "triangular", "parameters": [49.9, 50.0, 50.1]},
            },
            "extreme_values": {
                # Extreme range
                "very_wide": {
                    "type": "triangular",
                    "parameters": [-1000.0, 0.0, 1000.0],
                }
            },
        }
        return FuzzyConfig.model_validate(config_dict)

    @pytest.fixture
    def edge_case_fuzzy_engine(self, edge_case_fuzzy_config):
        """Fixture for a FuzzyEngine with edge case configuration."""
        return FuzzyEngine(edge_case_fuzzy_config)

    def test_extreme_input_values(self, standard_fuzzy_engine):
        """Test fuzzification with extreme input values."""
        # Very large values
        result = standard_fuzzy_engine.fuzzify("rsi", 1000000.0)
        assert result["rsi_low"] == 0.0
        assert result["rsi_medium"] == 0.0
        assert result["rsi_high"] == 0.0  # Beyond the maximum triangle point

        # Very small values
        result = standard_fuzzy_engine.fuzzify("rsi", -1000000.0)
        assert result["rsi_low"] == 0.0  # Below the minimum triangle point
        assert result["rsi_medium"] == 0.0
        assert result["rsi_high"] == 0.0

    def test_nan_values(self, standard_fuzzy_engine):
        """Test fuzzification with NaN values."""
        # Single NaN value
        result = standard_fuzzy_engine.fuzzify("rsi", np.nan)
        assert np.isnan(result["rsi_low"])
        assert np.isnan(result["rsi_medium"])
        assert np.isnan(result["rsi_high"])

        # Series with some NaN values
        values = pd.Series([20.0, np.nan, 50.0, np.nan, 80.0])
        result = standard_fuzzy_engine.fuzzify("rsi", values)

        # Check NaN values are preserved
        assert not np.isnan(result.iloc[0]["rsi_low"])
        assert np.isnan(result.iloc[1]["rsi_low"])
        assert not np.isnan(result.iloc[2]["rsi_low"])
        assert np.isnan(result.iloc[3]["rsi_low"])
        assert not np.isnan(result.iloc[4]["rsi_low"])

    def test_exact_boundary_values(self, standard_fuzzy_engine):
        """Test fuzzification with values exactly at the boundaries."""
        # At triangle points - updated to match actual implementation behavior
        result_a = standard_fuzzy_engine.fuzzify("rsi", 0.0)  # Triangle start
        assert result_a["rsi_low"] == 0.0  # At boundary, membership is 0
        assert result_a["rsi_medium"] == 0.0
        assert result_a["rsi_high"] == 0.0

        result_b = standard_fuzzy_engine.fuzzify(
            "rsi", 30.0
        )  # Peak of low / start of medium
        assert result_b["rsi_low"] == 1.0  # At peak, membership is 1.0
        assert result_b["rsi_medium"] == 0.0  # At boundary, membership is 0
        assert result_b["rsi_high"] == 0.0

        result_c = standard_fuzzy_engine.fuzzify(
            "rsi", 50.0
        )  # End of low / peak of medium / start of high
        assert result_c["rsi_low"] == 0.0  # At boundary, membership is 0
        assert result_c["rsi_medium"] == 1.0  # At peak, membership is 1.0
        assert result_c["rsi_high"] == 0.0  # At boundary, membership is 0

        result_d = standard_fuzzy_engine.fuzzify(
            "rsi", 70.0
        )  # End of medium / peak of high
        assert result_d["rsi_low"] == 0.0
        assert result_d["rsi_medium"] == 0.0  # At boundary, membership is 0
        assert result_d["rsi_high"] == 1.0  # At peak, membership is 1.0

        result_e = standard_fuzzy_engine.fuzzify("rsi", 100.0)  # End of high
        assert result_e["rsi_low"] == 0.0
        assert result_e["rsi_medium"] == 0.0
        assert result_e["rsi_high"] == 0.0  # At boundary, membership is 0

    def test_special_triangles(self, edge_case_fuzzy_engine):
        """Test fuzzification with special triangle configurations."""
        # Singleton (a = b = c)
        result_singleton_below = edge_case_fuzzy_engine.fuzzify("rsi", 49.0)
        assert result_singleton_below["rsi_singleton"] == 0.0

        result_singleton_exact = edge_case_fuzzy_engine.fuzzify("rsi", 50.0)
        assert result_singleton_exact["rsi_singleton"] == 1.0

        result_singleton_above = edge_case_fuzzy_engine.fuzzify("rsi", 51.0)
        assert result_singleton_above["rsi_singleton"] == 0.0

        # Left shoulder (a = b)
        result_left_shoulder_start = edge_case_fuzzy_engine.fuzzify("rsi", 0.0)
        assert result_left_shoulder_start["rsi_left_shoulder"] == 1.0

        result_left_shoulder_mid = edge_case_fuzzy_engine.fuzzify("rsi", 25.0)
        assert result_left_shoulder_mid["rsi_left_shoulder"] == 0.5

        result_left_shoulder_end = edge_case_fuzzy_engine.fuzzify("rsi", 50.0)
        assert result_left_shoulder_end["rsi_left_shoulder"] == 0.0

        # Right shoulder (b = c)
        result_right_shoulder_start = edge_case_fuzzy_engine.fuzzify("rsi", 50.0)
        assert result_right_shoulder_start["rsi_right_shoulder"] == 0.0

        result_right_shoulder_mid = edge_case_fuzzy_engine.fuzzify("rsi", 75.0)
        assert result_right_shoulder_mid["rsi_right_shoulder"] == 0.5

        result_right_shoulder_end = edge_case_fuzzy_engine.fuzzify("rsi", 100.0)
        assert result_right_shoulder_end["rsi_right_shoulder"] == 1.0

        # Very narrow triangle
        result_narrow_below = edge_case_fuzzy_engine.fuzzify("rsi", 49.8)
        assert result_narrow_below["rsi_narrow"] < 1.0

        result_narrow_peak = edge_case_fuzzy_engine.fuzzify("rsi", 50.0)
        assert result_narrow_peak["rsi_narrow"] == 1.0

        result_narrow_above = edge_case_fuzzy_engine.fuzzify("rsi", 50.2)
        assert result_narrow_above["rsi_narrow"] < 1.0

    def test_extreme_range(self, edge_case_fuzzy_engine):
        """Test with very wide triangles covering extreme ranges."""
        result_min = edge_case_fuzzy_engine.fuzzify("extreme_values", -1000.0)
        assert result_min["extreme_values_very_wide"] == 0.0

        result_negative = edge_case_fuzzy_engine.fuzzify("extreme_values", -500.0)
        assert result_negative["extreme_values_very_wide"] == 0.5

        result_peak = edge_case_fuzzy_engine.fuzzify("extreme_values", 0.0)
        assert result_peak["extreme_values_very_wide"] == 1.0

        result_positive = edge_case_fuzzy_engine.fuzzify("extreme_values", 500.0)
        assert result_positive["extreme_values_very_wide"] == 0.5

        result_max = edge_case_fuzzy_engine.fuzzify("extreme_values", 1000.0)
        assert result_max["extreme_values_very_wide"] == 0.0


class TestFuzzyPerformance:
    """Test suite for fuzzy logic performance."""

    @pytest.fixture
    def standard_fuzzy_config(self):
        """Fixture for a standard fuzzy configuration with known parameters."""
        config_dict = {
            "rsi": {
                "low": {"type": "triangular", "parameters": [0.0, 30.0, 50.0]},
                "medium": {"type": "triangular", "parameters": [30.0, 50.0, 70.0]},
                "high": {"type": "triangular", "parameters": [50.0, 70.0, 100.0]},
            }
        }
        return FuzzyConfig.model_validate(config_dict)

    @pytest.fixture
    def standard_fuzzy_engine(self, standard_fuzzy_config):
        """Fixture for a FuzzyEngine with standardized configuration."""
        return FuzzyEngine(standard_fuzzy_config)

    def test_performance_large_series(self, standard_fuzzy_engine):
        """Test performance with a large Series of values."""
        # Create a large series (10,000 values)
        size = 10000
        values = pd.Series(np.random.uniform(0, 100, size))

        # Measure execution time
        start_time = time.time()
        result = standard_fuzzy_engine.fuzzify("rsi", values)
        end_time = time.time()

        # Verify result shape
        assert len(result) == size
        assert list(result.columns) == ["rsi_low", "rsi_medium", "rsi_high"]

        # Log performance
        execution_time = end_time - start_time
        print(f"\nFuzzification of {size} values took {execution_time:.6f} seconds")
        print(f"Average time per value: {(execution_time * 1000 / size):.6f} ms")

        # Set a very conservative threshold (adjust based on your hardware)
        # This is mainly to catch severe performance regressions
        assert execution_time < 1.0, "Fuzzification performance too slow"

    def test_performance_scalar_operations(self, standard_fuzzy_engine):
        """Test performance with multiple scalar operations."""
        # Number of scalar operations to perform
        num_operations = 1000

        # Fixed test values
        test_values = [0.0, 25.0, 50.0, 75.0, 100.0]

        start_time = time.time()
        for _ in range(num_operations):
            for value in test_values:
                standard_fuzzy_engine.fuzzify("rsi", value)
        end_time = time.time()

        # Log performance
        total_operations = num_operations * len(test_values)
        execution_time = end_time - start_time
        print(
            f"\nFuzzification of {total_operations} scalar values took {execution_time:.6f} seconds"
        )
        print(
            f"Average time per value: {(execution_time * 1000 / total_operations):.6f} ms"
        )

        # Set a very conservative threshold
        assert execution_time < 2.0, "Scalar fuzzification performance too slow"

    def test_performance_numpy_array(self, standard_fuzzy_engine):
        """Test performance with numpy array input."""
        # Create a large numpy array (10,000 values)
        size = 10000
        array_values = np.random.uniform(0, 100, size)

        # Measure execution time
        start_time = time.time()
        result = standard_fuzzy_engine.fuzzify("rsi", array_values)
        end_time = time.time()

        # Verify result shape
        assert len(result) == size
        assert list(result.columns) == ["rsi_low", "rsi_medium", "rsi_high"]

        # Log performance
        execution_time = end_time - start_time
        print(
            f"\nFuzzification of {size} numpy values took {execution_time:.6f} seconds"
        )
        print(f"Average time per value: {(execution_time * 1000 / size):.6f} ms")

        # Set a very conservative threshold
        assert execution_time < 1.0, "Numpy array fuzzification performance too slow"
