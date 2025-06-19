"""
Tests for fuzzy configuration migration utilities.
"""

import pytest
import tempfile
from pathlib import Path
import yaml

from ktrdr.fuzzy.migration import (
    FuzzyConfigMigrator,
    migrate_fuzzy_config,
    check_config_compatibility,
)
from ktrdr.errors import ConfigurationError


class TestFuzzyConfigMigrator:
    """Tests for FuzzyConfigMigrator."""

    @pytest.fixture
    def sample_single_config(self):
        """Sample single-timeframe fuzzy configuration."""
        return {
            "rsi": {
                "low": {"type": "triangular", "parameters": [0, 30, 45]},
                "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
                "high": {"type": "triangular", "parameters": [55, 70, 100]},
            },
            "macd": {
                "negative": {"type": "triangular", "parameters": [-1, -0.5, 0]},
                "positive": {"type": "triangular", "parameters": [0, 0.5, 1]},
            },
        }

    @pytest.fixture
    def sample_multi_config(self):
        """Sample multi-timeframe fuzzy configuration."""
        return {
            "timeframes": {
                "1h": {
                    "indicators": ["rsi"],
                    "fuzzy_sets": {
                        "rsi": {
                            "low": {"type": "triangular", "parameters": [0, 30, 45]}
                        }
                    },
                    "weight": 1.0,
                    "enabled": True,
                }
            },
            "indicators": ["rsi"],
        }

    def test_migrate_single_to_multi_timeframe_basic(self, sample_single_config):
        """Test basic single-to-multi-timeframe migration."""
        migrator = FuzzyConfigMigrator()
        result = migrator.migrate_single_to_multi_timeframe(sample_single_config)

        # Check structure
        assert "timeframes" in result
        assert "indicators" in result
        assert "1h" in result["timeframes"]

        # Check timeframe config
        tf_config = result["timeframes"]["1h"]
        assert tf_config["indicators"] == ["rsi", "macd"]
        assert tf_config["fuzzy_sets"] == sample_single_config
        assert tf_config["weight"] == 1.0
        assert tf_config["enabled"] is True

        # Check indicators list
        assert set(result["indicators"]) == {"rsi", "macd"}

    def test_migrate_single_to_multi_timeframe_custom(self, sample_single_config):
        """Test migration with custom timeframe and weight."""
        migrator = FuzzyConfigMigrator()
        result = migrator.migrate_single_to_multi_timeframe(
            sample_single_config, target_timeframe="4h", timeframe_weight=0.7
        )

        assert "4h" in result["timeframes"]
        assert result["timeframes"]["4h"]["weight"] == 0.7

    def test_migrate_to_multiple_timeframes(self, sample_single_config):
        """Test migration to multiple timeframes."""
        migrator = FuzzyConfigMigrator()
        timeframes = ["1h", "4h", "1d"]
        weights = {"1h": 0.5, "4h": 0.3, "1d": 0.2}

        result = migrator.migrate_to_multiple_timeframes(
            sample_single_config, timeframes, weights
        )

        # Check all timeframes are present
        assert len(result["timeframes"]) == 3
        for tf in timeframes:
            assert tf in result["timeframes"]
            assert result["timeframes"][tf]["weight"] == weights[tf]
            assert result["timeframes"][tf]["fuzzy_sets"] == sample_single_config

    def test_migrate_to_multiple_timeframes_default_weights(self, sample_single_config):
        """Test migration with default weights."""
        migrator = FuzzyConfigMigrator()
        timeframes = ["1h", "4h"]

        result = migrator.migrate_to_multiple_timeframes(
            sample_single_config, timeframes
        )

        # Check default equal weights
        expected_weight = 1.0 / len(timeframes)
        for tf in timeframes:
            assert result["timeframes"][tf]["weight"] == expected_weight

    def test_migrate_empty_timeframes_error(self, sample_single_config):
        """Test that empty timeframes list raises error."""
        migrator = FuzzyConfigMigrator()

        with pytest.raises(ConfigurationError) as exc_info:
            migrator.migrate_to_multiple_timeframes(sample_single_config, [])
        assert "At least one timeframe must be specified" in str(exc_info.value)

    def test_migrate_invalid_config_error(self):
        """Test that invalid config raises error."""
        migrator = FuzzyConfigMigrator()
        invalid_config = {"invalid": "config"}

        with pytest.raises(ConfigurationError) as exc_info:
            migrator.migrate_single_to_multi_timeframe(invalid_config)
        assert "Failed to migrate fuzzy configuration" in str(exc_info.value)

    def test_check_migration_needed(self, sample_single_config, sample_multi_config):
        """Test migration need detection."""
        migrator = FuzzyConfigMigrator()

        # Single config needs migration
        assert migrator.check_migration_needed(sample_single_config) is True

        # Multi config doesn't need migration
        assert migrator.check_migration_needed(sample_multi_config) is False

        # Empty config
        assert migrator.check_migration_needed({}) is False

    def test_get_migration_recommendations(self, sample_single_config):
        """Test migration recommendations."""
        migrator = FuzzyConfigMigrator()
        recommendations = migrator.get_migration_recommendations(sample_single_config)

        assert recommendations["migration_needed"] is True
        assert set(recommendations["indicators_found"]) == {"rsi", "macd"}
        assert "1h" in recommendations["recommended_timeframes"]
        assert "4h" in recommendations["recommended_timeframes"]
        assert "1d" in recommendations["recommended_timeframes"]
        assert isinstance(recommendations["suggested_weights"], dict)
        assert isinstance(recommendations["notes"], list)

    def test_migrate_yaml_file(self, sample_single_config):
        """Test YAML file migration."""
        migrator = FuzzyConfigMigrator()

        with tempfile.TemporaryDirectory() as temp_dir:
            input_file = Path(temp_dir) / "input.yaml"
            output_file = Path(temp_dir) / "output.yaml"

            # Write input file
            with open(input_file, "w") as f:
                yaml.dump(sample_single_config, f)

            # Migrate
            migrator.migrate_yaml_file(input_file, output_file)

            # Check output file exists and has correct content
            assert output_file.exists()

            with open(output_file, "r") as f:
                migrated_config = yaml.safe_load(f)

            assert "timeframes" in migrated_config
            assert "1h" in migrated_config["timeframes"]


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_migrate_fuzzy_config(self):
        """Test convenience migration function."""
        single_config = {
            "rsi": {"low": {"type": "triangular", "parameters": [0, 30, 45]}}
        }

        result = migrate_fuzzy_config(single_config, "4h")

        assert "timeframes" in result
        assert "4h" in result["timeframes"]
        assert result["timeframes"]["4h"]["fuzzy_sets"] == single_config

    def test_check_config_compatibility(self):
        """Test compatibility check function."""
        single_config = {
            "rsi": {"low": {"type": "triangular", "parameters": [0, 30, 45]}}
        }

        report = check_config_compatibility(single_config)

        assert "migration_needed" in report
        assert "indicators_found" in report
        assert "recommended_timeframes" in report
        assert "suggested_weights" in report
