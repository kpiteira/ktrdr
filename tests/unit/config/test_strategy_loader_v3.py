"""Unit tests for v3 strategy loader."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from ktrdr.config.models import StrategyConfigurationV3
from ktrdr.config.strategy_loader import StrategyConfigurationLoader
from ktrdr.config.strategy_validator import (
    StrategyValidationError,
    StrategyValidationWarning,
)


@pytest.fixture
def valid_v3_strategy_yaml(tmp_path: Path) -> Path:
    """Create a valid v3 strategy YAML file."""
    strategy = {
        "name": "test_v3_strategy",
        "version": "3.0",
        "description": "Test v3 strategy",
        "training_data": {
            "symbols": {"mode": "single", "symbol": "EURUSD"},
            "timeframes": {
                "mode": "multi_timeframe",
                "list": ["5m", "1h"],
                "base_timeframe": "1h",
            },
            "history_required": 100,
        },
        "indicators": {
            "rsi_14": {"type": "rsi", "period": 14},
            "bbands_20_2": {"type": "bbands", "period": 20, "multiplier": 2.0},
        },
        "fuzzy_sets": {
            "rsi_fast": {
                "indicator": "rsi_14",
                "oversold": [0, 25, 40],
                "overbought": [60, 75, 100],
            },
            "bbands_squeeze": {
                "indicator": "bbands_20_2.middle",
                "tight": [0, 0.5, 1.0],
            },
        },
        "nn_inputs": [
            {"fuzzy_set": "rsi_fast", "timeframes": ["5m"]},
            {"fuzzy_set": "bbands_squeeze", "timeframes": "all"},
        ],
        "model": {"type": "mlp", "architecture": {"hidden_layers": [64, 32]}},
        "decisions": {"output_format": "classification", "confidence_threshold": 0.6},
        "training": {"method": "supervised", "labels": {"source": "zigzag"}},
    }

    yaml_file = tmp_path / "valid_v3.yaml"
    with open(yaml_file, "w") as f:
        yaml.dump(strategy, f)

    return yaml_file


@pytest.fixture
def v2_strategy_yaml(tmp_path: Path) -> Path:
    """Create a v2 strategy YAML file (list indicators)."""
    strategy = {
        "name": "v2_strategy",
        "version": "2.0",
        "scope": "symbol_specific",
        "training_data": {
            "symbols": {"mode": "single", "symbol": "TEST"},
            "timeframes": {"mode": "single", "timeframe": "1h"},
        },
        "deployment": {
            "target_symbols": {"mode": "training_only"},
            "target_timeframes": {"mode": "single", "timeframe": "1h"},
        },
        "indicators": [  # V2 uses list
            {"name": "rsi", "feature_id": "rsi_14", "period": 14}
        ],
        "fuzzy_sets": {
            "rsi_14": {"oversold": {"type": "triangular", "parameters": [0, 20, 35]}}
        },
        "model": {"type": "mlp", "architecture": {"hidden_layers": [32]}},
        "decisions": {"output_format": "classification"},
        "training": {"method": "supervised", "labels": {"source": "zigzag"}},
    }

    yaml_file = tmp_path / "v2_strategy.yaml"
    with open(yaml_file, "w") as f:
        yaml.dump(strategy, f)

    return yaml_file


@pytest.fixture
def v2_no_nn_inputs_yaml(tmp_path: Path) -> Path:
    """Create a v2-style strategy without nn_inputs."""
    strategy = {
        "name": "v2_no_inputs",
        "version": "2.0",
        "training_data": {
            "symbols": {"mode": "single", "symbol": "TEST"},
            "timeframes": {"mode": "single", "timeframe": "1h"},
        },
        "indicators": {
            "rsi_14": {"type": "rsi", "period": 14}
        },  # Dict but no nn_inputs
        "fuzzy_sets": {"rsi_14": {"indicator": "rsi_14", "low": [0, 20, 35]}},
        "model": {"type": "mlp"},
        "decisions": {"output_format": "classification"},
        "training": {"method": "supervised", "labels": {"source": "zigzag"}},
    }

    yaml_file = tmp_path / "v2_no_inputs.yaml"
    with open(yaml_file, "w") as f:
        yaml.dump(strategy, f)

    return yaml_file


@pytest.fixture
def invalid_yaml_file(tmp_path: Path) -> Path:
    """Create an invalid YAML file."""
    yaml_file = tmp_path / "invalid.yaml"
    with open(yaml_file, "w") as f:
        f.write("invalid: yaml: content: [\n")
    return yaml_file


@pytest.fixture
def invalid_indicator_ref_yaml(tmp_path: Path) -> Path:
    """Create a v3 strategy with invalid indicator reference."""
    strategy = {
        "name": "invalid_ref",
        "version": "3.0",
        "training_data": {
            "symbols": {"mode": "single", "symbol": "TEST"},
            "timeframes": {"mode": "single", "timeframe": "1h"},
            "history_required": 100,
        },
        "indicators": {"rsi_14": {"type": "rsi", "period": 14}},
        "fuzzy_sets": {
            "bad_ref": {
                "indicator": "nonexistent_indicator",  # Invalid reference
                "low": [0, 25, 50],
            }
        },
        "nn_inputs": [{"fuzzy_set": "bad_ref", "timeframes": "all"}],
        "model": {"type": "mlp", "architecture": {"hidden_layers": [32]}},
        "decisions": {"output_format": "classification"},
        "training": {"method": "supervised", "labels": {"source": "zigzag"}},
    }

    yaml_file = tmp_path / "invalid_ref.yaml"
    with open(yaml_file, "w") as f:
        yaml.dump(strategy, f)

    return yaml_file


class TestV3StrategyLoader:
    """Tests for v3 strategy loading."""

    def test_loads_valid_v3_strategy(self, valid_v3_strategy_yaml: Path):
        """Test that valid v3 strategy loads successfully."""
        loader = StrategyConfigurationLoader()
        config = loader.load_v3_strategy(valid_v3_strategy_yaml)

        assert isinstance(config, StrategyConfigurationV3)
        assert config.name == "test_v3_strategy"
        assert config.version == "3.0"
        assert "rsi_14" in config.indicators
        assert "rsi_fast" in config.fuzzy_sets
        assert len(config.nn_inputs) == 2

    def test_rejects_v2_strategy_with_list_indicators(self, v2_strategy_yaml: Path):
        """Test that v2 strategy (list indicators) is rejected with clear message."""
        loader = StrategyConfigurationLoader()

        with pytest.raises(ValueError) as exc_info:
            loader.load_v3_strategy(v2_strategy_yaml)

        error_message = str(exc_info.value)
        assert "not v3 format" in error_message.lower()
        assert "migrate" in error_message.lower()

    def test_rejects_v2_strategy_without_nn_inputs(self, v2_no_nn_inputs_yaml: Path):
        """Test that v2 strategy (no nn_inputs) is rejected."""
        loader = StrategyConfigurationLoader()

        with pytest.raises(ValueError) as exc_info:
            loader.load_v3_strategy(v2_no_nn_inputs_yaml)

        error_message = str(exc_info.value)
        assert "not v3 format" in error_message.lower()

    def test_invalid_yaml_produces_sensible_error(self, invalid_yaml_file: Path):
        """Test that invalid YAML produces a sensible error."""
        loader = StrategyConfigurationLoader()

        with pytest.raises(ValueError) as exc_info:
            loader.load_v3_strategy(invalid_yaml_file)

        error_message = str(exc_info.value)
        assert "yaml" in error_message.lower() or "invalid" in error_message.lower()

    def test_validation_runs_automatically(self, invalid_indicator_ref_yaml: Path):
        """Test that validation runs automatically on load."""
        loader = StrategyConfigurationLoader()

        with pytest.raises(StrategyValidationError) as exc_info:
            loader.load_v3_strategy(invalid_indicator_ref_yaml)

        error_message = str(exc_info.value)
        assert "nonexistent" in error_message

    @patch("ktrdr.config.strategy_validator.validate_v3_strategy")
    def test_warnings_are_logged(
        self, mock_validate: MagicMock, valid_v3_strategy_yaml: Path, caplog
    ):
        """Test that validation warnings are logged."""
        # Mock validation to return a warning
        mock_validate.return_value = [
            StrategyValidationWarning(
                message="Unused indicator detected",
                location="indicators.unused_indicator",
            )
        ]

        loader = StrategyConfigurationLoader()
        loader.load_v3_strategy(valid_v3_strategy_yaml)

        # Check that warning was logged
        assert "unused indicator" in caplog.text.lower()
        assert "indicators.unused_indicator" in caplog.text

    def test_file_not_found_error(self):
        """Test that loading non-existent file raises FileNotFoundError."""
        loader = StrategyConfigurationLoader()

        with pytest.raises(FileNotFoundError):
            loader.load_v3_strategy(Path("/nonexistent/file.yaml"))

    def test_is_v3_format_detection(self):
        """Test v3 format detection logic."""
        loader = StrategyConfigurationLoader()

        # V3: dict indicators + nn_inputs
        v3_config = {
            "indicators": {"rsi_14": {"type": "rsi"}},
            "nn_inputs": [{"fuzzy_set": "test"}],
        }
        assert loader._is_v3_format(v3_config) is True

        # Not v3: list indicators
        v2_list = {
            "indicators": [{"name": "rsi"}],
            "nn_inputs": [{"fuzzy_set": "test"}],
        }
        assert loader._is_v3_format(v2_list) is False

        # Not v3: no nn_inputs
        v2_no_inputs = {"indicators": {"rsi_14": {"type": "rsi"}}}
        assert loader._is_v3_format(v2_no_inputs) is False

        # Not v3: neither
        v1_format = {"indicators": [{"name": "rsi"}]}
        assert loader._is_v3_format(v1_format) is False
