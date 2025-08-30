"""
Tests for the fuzzy configuration loader functionality.

These tests verify that the FuzzyConfigLoader can correctly load and merge
fuzzy configurations from different sources.
"""

import os
from pathlib import Path

import pytest
import yaml

from ktrdr.errors import (
    ConfigurationError,
    ConfigurationFileError,
)
from ktrdr.fuzzy.config import (
    FuzzyConfig,
    FuzzyConfigLoader,
)


class TestFuzzyConfigLoader:
    """Test suite for FuzzyConfigLoader class."""

    def test_load_from_dict(self):
        """Test loading fuzzy configuration from a dictionary."""
        config_dict = {
            "rsi": {
                "low": {"type": "triangular", "parameters": [0, 30, 45]},
                "high": {"type": "triangular", "parameters": [55, 70, 100]},
            }
        }

        loader = FuzzyConfigLoader()
        config = loader.load_from_dict(config_dict)

        assert isinstance(config, FuzzyConfig)
        assert "rsi" in config.root
        assert "low" in config.root["rsi"].root
        assert "high" in config.root["rsi"].root
        assert config.root["rsi"].root["low"].parameters == [0, 30, 45]
        assert config.root["rsi"].root["high"].parameters == [55, 70, 100]

    def test_load_from_yaml(self, tmp_path):
        """Test loading fuzzy configuration from a YAML file."""
        # Create a temporary YAML file
        config_dict = {
            "macd": {
                "negative": {"type": "triangular", "parameters": [-10, -2, 0]},
                "positive": {"type": "triangular", "parameters": [0, 2, 10]},
            }
        }

        yaml_path = tmp_path / "test_fuzzy.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(config_dict, f)

        loader = FuzzyConfigLoader(config_dir=tmp_path)
        config = loader.load_from_yaml(yaml_path)

        assert isinstance(config, FuzzyConfig)
        assert "macd" in config.root
        assert "negative" in config.root["macd"].root
        assert "positive" in config.root["macd"].root
        assert config.root["macd"].root["negative"].parameters == [-10, -2, 0]
        assert config.root["macd"].root["positive"].parameters == [0, 2, 10]

    def test_load_default(self, monkeypatch, tmp_path):
        """Test loading the default fuzzy configuration."""
        # Create a temporary default config
        config_dict = {
            "rsi": {"low": {"type": "triangular", "parameters": [0, 30, 45]}}
        }

        config_dir = tmp_path / "config"
        os.makedirs(config_dir, exist_ok=True)

        with open(config_dir / "fuzzy.yaml", "w") as f:
            yaml.dump(config_dict, f)

        loader = FuzzyConfigLoader(config_dir=config_dir)
        config = loader.load_default()

        assert isinstance(config, FuzzyConfig)
        assert "rsi" in config.root
        assert "low" in config.root["rsi"].root
        assert config.root["rsi"].root["low"].parameters == [0, 30, 45]

    def test_load_strategy_fuzzy_config(self, tmp_path):
        """Test loading fuzzy configuration from a strategy file."""
        # Create temporary directories
        os.makedirs(tmp_path / "config", exist_ok=True)
        os.makedirs(tmp_path / "strategies", exist_ok=True)

        # Create a strategy file with fuzzy_sets section
        strategy_dict = {
            "name": "test_strategy",
            "fuzzy_sets": {
                "stoch": {
                    "low": {"type": "triangular", "parameters": [0, 20, 40]},
                    "high": {"type": "triangular", "parameters": [60, 80, 100]},
                }
            },
        }

        with open(tmp_path / "strategies" / "test_strategy.yaml", "w") as f:
            yaml.dump(strategy_dict, f)

        loader = FuzzyConfigLoader(config_dir=tmp_path / "config")
        config = loader.load_strategy_fuzzy_config("test_strategy")

        assert isinstance(config, FuzzyConfig)
        assert "stoch" in config.root
        assert "low" in config.root["stoch"].root
        assert "high" in config.root["stoch"].root
        assert config.root["stoch"].root["low"].parameters == [0, 20, 40]
        assert config.root["stoch"].root["high"].parameters == [60, 80, 100]

    def test_merge_configs(self):
        """Test merging two fuzzy configurations."""
        # Base config
        base_config_dict = {
            "rsi": {
                "low": {"type": "triangular", "parameters": [0, 30, 45]},
                "high": {"type": "triangular", "parameters": [55, 70, 100]},
            }
        }

        # Override config
        override_config_dict = {
            "rsi": {
                "low": {
                    "type": "triangular",
                    "parameters": [0, 20, 35],  # Override existing
                },
                "neutral": {
                    "type": "triangular",
                    "parameters": [30, 50, 70],  # Add new
                },
            },
            "macd": {  # Add new indicator
                "negative": {"type": "triangular", "parameters": [-10, -2, 0]},
                "positive": {"type": "triangular", "parameters": [0, 2, 10]},
            },
        }

        loader = FuzzyConfigLoader()
        base_config = loader.load_from_dict(base_config_dict)
        override_config = loader.load_from_dict(override_config_dict)

        merged_config = loader.merge_configs(base_config, override_config)

        # Check that original values were overridden
        assert merged_config.root["rsi"].root["low"].parameters == [0, 20, 35]

        # Check that new values were added
        assert "neutral" in merged_config.root["rsi"].root
        assert merged_config.root["rsi"].root["neutral"].parameters == [30, 50, 70]

        # Check that original values not mentioned in override remain
        assert "high" in merged_config.root["rsi"].root
        assert merged_config.root["rsi"].root["high"].parameters == [55, 70, 100]

        # Check that new indicators were added
        assert "macd" in merged_config.root
        assert "negative" in merged_config.root["macd"].root
        assert "positive" in merged_config.root["macd"].root

    def test_load_with_strategy_override(self, tmp_path):
        """Test loading default config with strategy overrides."""
        # Create temporary directories
        config_dir = tmp_path / "config"
        strategy_dir = tmp_path / "strategies"
        os.makedirs(config_dir, exist_ok=True)
        os.makedirs(strategy_dir, exist_ok=True)

        # Create default config
        default_config = {
            "rsi": {
                "low": {"type": "triangular", "parameters": [0, 30, 45]},
                "high": {"type": "triangular", "parameters": [55, 70, 100]},
            }
        }

        with open(config_dir / "fuzzy.yaml", "w") as f:
            yaml.dump(default_config, f)

        # Create strategy config
        strategy_config = {
            "name": "test_strategy",
            "fuzzy_sets": {
                "rsi": {
                    "low": {
                        "type": "triangular",
                        "parameters": [0, 20, 35],  # Override existing
                    }
                },
                "stoch": {  # Add new indicator
                    "low": {"type": "triangular", "parameters": [0, 20, 40]},
                    "high": {"type": "triangular", "parameters": [60, 80, 100]},
                },
            },
        }

        with open(strategy_dir / "test_strategy.yaml", "w") as f:
            yaml.dump(strategy_config, f)

        loader = FuzzyConfigLoader(config_dir=config_dir)
        config = loader.load_with_strategy_override("test_strategy")

        # Check that original values were overridden
        assert config.root["rsi"].root["low"].parameters == [0, 20, 35]

        # Check that original values not mentioned in override remain
        assert "high" in config.root["rsi"].root
        assert config.root["rsi"].root["high"].parameters == [55, 70, 100]

        # Check that new indicators were added
        assert "stoch" in config.root
        assert "low" in config.root["stoch"].root
        assert "high" in config.root["stoch"].root

    def test_validation_errors(self):
        """Test that validation errors are raised for invalid configurations."""
        loader = FuzzyConfigLoader()

        # Test invalid parameter order
        with pytest.raises(ConfigurationError):
            loader.load_from_dict(
                {
                    "rsi": {
                        "low": {
                            "type": "triangular",
                            "parameters": [50, 30, 70],  # a > b, which is invalid
                        }
                    }
                }
            )

        # Test missing parameters
        with pytest.raises(ConfigurationError):
            loader.load_from_dict(
                {
                    "rsi": {
                        "low": {
                            "type": "triangular",
                            "parameters": [30, 50],  # Only 2 parameters instead of 3
                        }
                    }
                }
            )

    def test_file_not_found(self):
        """Test that appropriate error is raised when file is not found."""
        loader = FuzzyConfigLoader()

        with pytest.raises(ConfigurationFileError):
            loader.load_from_yaml("nonexistent_file.yaml")

    def test_integration_with_real_configs(self):
        """Test with the actual project configuration files."""
        # This test uses the actual project files
        # It will pass if the default fuzzy.yaml and any strategy files are valid
        loader = FuzzyConfigLoader(
            config_dir=Path(__file__).parent.parent.parent / "config"
        )

        # Load default config
        default_config = loader.load_default()
        assert isinstance(default_config, FuzzyConfig)

        # Try loading with trend_momentum_strategy
        try:
            strategy_config = loader.load_with_strategy_override(
                "trend_momentum_strategy"
            )
            assert isinstance(strategy_config, FuzzyConfig)
            # If we loaded a strategy, check that it has some expected fuzzy sets
            if "rsi" in strategy_config.root:
                assert len(strategy_config.root["rsi"].root) > 0
        except ConfigurationFileError:
            # It's okay if the strategy file doesn't exist
            pass
