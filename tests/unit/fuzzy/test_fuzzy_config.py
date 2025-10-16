"""
Tests for the fuzzy logic configuration module.
"""

import pytest
from pydantic import ValidationError

from ktrdr.errors import ConfigurationError
from ktrdr.fuzzy.config import (
    FuzzyConfig,
    FuzzyConfigLoader,
    FuzzySetConfig,
    TriangularMFConfig,
)


class TestTriangularMFConfig:
    """Tests for triangular membership function configuration."""

    def test_valid_triangular_mf_config(self):
        """Test valid triangular membership function configuration."""
        # Valid configuration with a < b < c
        config = TriangularMFConfig(type="triangular", parameters=[0, 30, 60])
        assert config.type == "triangular"
        assert config.parameters == [0, 30, 60]

    def test_invalid_parameter_count(self):
        """Test that an error is raised for invalid parameter count."""
        # Too few parameters
        with pytest.raises(ValidationError):
            TriangularMFConfig(type="triangular", parameters=[0, 30])

        # Too many parameters
        with pytest.raises(ValidationError):
            TriangularMFConfig(type="triangular", parameters=[0, 30, 60, 100])

    def test_invalid_parameter_order(self):
        """Test that an error is raised for invalid parameter order."""
        # b < a (should be a <= b)
        with pytest.raises(ConfigurationError) as exc_info:
            TriangularMFConfig(type="triangular", parameters=[30, 10, 60])
        assert "parameters must satisfy: a ≤ b ≤ c" in str(exc_info.value)

        # c < b (should be b <= c)
        with pytest.raises(ConfigurationError) as exc_info:
            TriangularMFConfig(type="triangular", parameters=[10, 60, 40])
        assert "parameters must satisfy: a ≤ b ≤ c" in str(exc_info.value)

    def test_equal_parameters_allowed(self):
        """Test that equal parameters are allowed (a = b or b = c)."""
        # a = b < c
        config1 = TriangularMFConfig(type="triangular", parameters=[30, 30, 60])
        assert config1.parameters == [30, 30, 60]

        # a < b = c
        config2 = TriangularMFConfig(type="triangular", parameters=[10, 60, 60])
        assert config2.parameters == [10, 60, 60]

        # a = b = c
        config3 = TriangularMFConfig(type="triangular", parameters=[50, 50, 50])
        assert config3.parameters == [50, 50, 50]


class TestFuzzySetConfig:
    """Tests for fuzzy set configuration."""

    def test_valid_fuzzy_set_config(self):
        """Test valid fuzzy set configuration."""
        config_dict = {
            "low": {"type": "triangular", "parameters": [0, 30, 45]},
            "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
            "high": {"type": "triangular", "parameters": [55, 70, 100]},
        }

        config = FuzzySetConfig.model_validate(config_dict)
        assert "low" in config.root
        assert "neutral" in config.root
        assert "high" in config.root
        assert config.root["low"].parameters == [0, 30, 45]

    def test_empty_fuzzy_set(self):
        """Test that an error is raised for empty fuzzy set."""
        with pytest.raises(ConfigurationError) as exc_info:
            FuzzySetConfig.model_validate({})
        assert "At least one fuzzy set" in str(exc_info.value)


class TestFuzzyConfig:
    """Tests for overall fuzzy configuration."""

    def test_valid_fuzzy_config(self):
        """Test valid fuzzy configuration."""
        config_dict = {
            "rsi": {
                "low": {"type": "triangular", "parameters": [0, 30, 45]},
                "high": {"type": "triangular", "parameters": [55, 70, 100]},
            },
            "macd": {
                "negative": {"type": "triangular", "parameters": [-10, -2, 0]},
                "positive": {"type": "triangular", "parameters": [0, 2, 10]},
            },
        }

        config = FuzzyConfig.model_validate(config_dict)
        assert "rsi" in config.root
        assert "macd" in config.root
        assert "low" in config.root["rsi"].root
        assert "high" in config.root["rsi"].root
        assert config.root["rsi"].root["low"].parameters == [0, 30, 45]

    def test_empty_fuzzy_config(self):
        """Test that an error is raised for empty fuzzy configuration."""
        with pytest.raises(ConfigurationError) as exc_info:
            FuzzyConfig.model_validate({})
        assert "At least one indicator must be defined" in str(exc_info.value)


class TestFuzzyConfigLoader:
    """Tests for fuzzy configuration loader."""

    def test_load_valid_config(self):
        """Test loading a valid configuration."""
        config_dict = {
            "rsi": {
                "low": {"type": "triangular", "parameters": [0, 30, 45]},
                "high": {"type": "triangular", "parameters": [55, 70, 100]},
            }
        }

        config = FuzzyConfigLoader.load_from_dict(config_dict)
        assert "rsi" in config.root
        assert "low" in config.root["rsi"].root
        assert "high" in config.root["rsi"].root
        assert config.root["rsi"].root["low"].parameters == [0, 30, 45]

    def test_load_invalid_config(self):
        """Test that an error is raised for invalid configuration."""
        # Empty configuration
        with pytest.raises(ConfigurationError) as exc_info:
            FuzzyConfigLoader.load_from_dict({})
        assert "Failed to load fuzzy configuration" in str(exc_info.value)

        # Invalid parameters
        with pytest.raises(ConfigurationError):
            FuzzyConfigLoader.load_from_dict(
                {
                    "rsi": {
                        "low": {
                            "type": "triangular",
                            "parameters": [45, 30, 60],  # Invalid order
                        }
                    }
                }
            )
