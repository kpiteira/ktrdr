"""Tests for strategy validator regression support."""

import pytest
import yaml

from ktrdr.config.models import StrategyConfigurationV3
from ktrdr.config.strategy_loader import StrategyConfigurationLoader
from ktrdr.config.strategy_validator import (
    StrategyValidationError,
    validate_v3_strategy,
)

# Shared base config for constructing V3 models directly
_BASE = {
    "name": "test_strategy",
    "version": "3.0",
    "training_data": {
        "symbols": {"mode": "single", "symbol": "EURUSD"},
        "timeframes": {"mode": "single", "timeframe": "1h"},
    },
    "indicators": {
        "rsi_14": {"type": "rsi", "period": 14},
    },
    "fuzzy_sets": {
        "rsi_low": {"indicator": "rsi_14", "oversold": [20, 30, 40]},
    },
    "nn_inputs": [{"fuzzy_set": "rsi_low", "timeframes": "all"}],
    "model": {"type": "mlp", "architecture": {"hidden_layers": [64, 32]}},
}


def make_config(**overrides) -> StrategyConfigurationV3:
    """Create a V3 config model with overrides."""
    import copy

    config = copy.deepcopy(_BASE)
    config.update(overrides)
    return StrategyConfigurationV3(**config)


class TestV3RegressionValidation:
    """Test V3 regression strategy validation."""

    def test_valid_regression_config_passes(self):
        """Valid regression strategy config passes validation."""
        config = make_config(
            decisions={
                "output_format": "regression",
                "cost_model": {"round_trip_cost": 0.003, "min_edge_multiplier": 1.5},
            },
            training={
                "labels": {"source": "forward_return", "horizon": 20},
                "loss": "huber",
            },
        )
        warnings = validate_v3_strategy(config)
        assert isinstance(warnings, list)

    def test_missing_cost_model_rejected(self):
        """Missing cost_model in regression mode is rejected."""
        config = make_config(
            decisions={"output_format": "regression"},
            training={"labels": {"source": "forward_return", "horizon": 20}},
        )
        with pytest.raises(StrategyValidationError, match="cost_model"):
            validate_v3_strategy(config)

    def test_invalid_output_format_rejected(self):
        """Invalid output_format value is rejected."""
        config = make_config(
            decisions={"output_format": "bad_value"},
            training={"labels": {"source": "zigzag"}},
        )
        with pytest.raises(StrategyValidationError, match="output_format"):
            validate_v3_strategy(config)

    def test_missing_horizon_rejected(self):
        """Missing horizon for forward_return labels is rejected."""
        config = make_config(
            decisions={
                "output_format": "regression",
                "cost_model": {"round_trip_cost": 0.003, "min_edge_multiplier": 1.5},
            },
            training={"labels": {"source": "forward_return"}},
        )
        with pytest.raises(StrategyValidationError, match="horizon"):
            validate_v3_strategy(config)

    def test_invalid_loss_rejected(self):
        """Invalid loss type is rejected."""
        config = make_config(
            decisions={
                "output_format": "regression",
                "cost_model": {"round_trip_cost": 0.003, "min_edge_multiplier": 1.5},
            },
            training={
                "labels": {"source": "forward_return", "horizon": 20},
                "loss": "bad_loss",
            },
        )
        with pytest.raises(StrategyValidationError, match="loss"):
            validate_v3_strategy(config)

    def test_confidence_threshold_warning(self):
        """Warning when confidence_threshold present in regression mode."""
        config = make_config(
            decisions={
                "output_format": "regression",
                "cost_model": {"round_trip_cost": 0.003, "min_edge_multiplier": 1.5},
                "confidence_threshold": 0.6,
            },
            training={"labels": {"source": "forward_return", "horizon": 20}},
        )
        warnings = validate_v3_strategy(config)
        warning_messages = [w.message for w in warnings]
        assert any(
            "confidence_threshold" in msg and "ignored" in msg
            for msg in warning_messages
        )

    def test_classification_still_validates(self):
        """Classification config still validates correctly."""
        config = make_config(
            decisions={
                "output_format": "classification",
                "confidence_threshold": 0.6,
                "position_awareness": True,
            },
            training={"labels": {"source": "zigzag"}},
        )
        warnings = validate_v3_strategy(config)
        assert isinstance(warnings, list)

    def test_negative_round_trip_cost_rejected(self):
        """Negative round_trip_cost is rejected."""
        config = make_config(
            decisions={
                "output_format": "regression",
                "cost_model": {"round_trip_cost": -0.003, "min_edge_multiplier": 1.5},
            },
            training={"labels": {"source": "forward_return", "horizon": 20}},
        )
        with pytest.raises(StrategyValidationError, match="round_trip_cost"):
            validate_v3_strategy(config)

    def test_zero_min_edge_multiplier_rejected(self):
        """Zero min_edge_multiplier is rejected."""
        config = make_config(
            decisions={
                "output_format": "regression",
                "cost_model": {"round_trip_cost": 0.003, "min_edge_multiplier": 0},
            },
            training={"labels": {"source": "forward_return", "horizon": 20}},
        )
        with pytest.raises(StrategyValidationError, match="min_edge_multiplier"):
            validate_v3_strategy(config)

    def test_regression_strategy_loads_from_yaml(self, tmp_path):
        """Full round-trip: YAML -> load -> validate for regression strategy."""
        strategy = {
            "name": "regression_yaml_test",
            "version": "3.0",
            "training_data": {
                "symbols": {"mode": "single", "symbol": "EURUSD"},
                "timeframes": {"mode": "single", "timeframe": "1h"},
            },
            "indicators": {"rsi_14": {"type": "rsi", "period": 14}},
            "fuzzy_sets": {
                "rsi_low": {"indicator": "rsi_14", "oversold": [20, 30, 40]}
            },
            "nn_inputs": [{"fuzzy_set": "rsi_low", "timeframes": "all"}],
            "model": {"type": "mlp", "architecture": {"hidden_layers": [64, 32]}},
            "decisions": {
                "output_format": "regression",
                "cost_model": {"round_trip_cost": 0.003, "min_edge_multiplier": 1.5},
            },
            "training": {
                "labels": {"source": "forward_return", "horizon": 20},
                "loss": "huber",
            },
        }
        yaml_file = tmp_path / "regression.yaml"
        with open(yaml_file, "w") as f:
            yaml.dump(strategy, f)
        loader = StrategyConfigurationLoader()
        config = loader.load_v3_strategy(yaml_file)
        assert config.decisions["output_format"] == "regression"
