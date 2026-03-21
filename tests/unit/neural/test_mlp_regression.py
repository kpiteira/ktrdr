"""Tests for MLPTradingModel build_model regression vs classification output."""

import pytest

torch = pytest.importorskip("torch")
import torch.nn as nn  # noqa: E402

from ktrdr.neural.models.mlp import MLPTradingModel  # noqa: E402


def make_config(output_format: str = "classification") -> dict:
    """Create a model config dict."""
    return {
        "architecture": {
            "hidden_layers": [32, 16],
            "dropout": 0.1,
            "activation": "relu",
        },
        "output_format": output_format,
    }


class TestMLPBuildModel:
    """Test build_model regression vs classification output."""

    def test_regression_model_has_1_output(self):
        """Regression model has 1 output neuron."""
        model = MLPTradingModel(make_config("regression"))
        net = model.build_model(input_size=4)
        last_linear = [m for m in net.modules() if isinstance(m, nn.Linear)][-1]
        assert last_linear.out_features == 1

    def test_classification_model_has_3_outputs(self):
        """Classification model has 3 output neurons."""
        model = MLPTradingModel(make_config("classification"))
        net = model.build_model(input_size=4)
        last_linear = [m for m in net.modules() if isinstance(m, nn.Linear)][-1]
        assert last_linear.out_features == 3

    def test_default_is_classification(self):
        """No output_format defaults to classification (3 outputs)."""
        config = make_config("classification")
        del config["output_format"]
        model = MLPTradingModel(config)
        net = model.build_model(input_size=4)
        last_linear = [m for m in net.modules() if isinstance(m, nn.Linear)][-1]
        assert last_linear.out_features == 3

    def test_invalid_output_format_raises(self):
        """Invalid output_format raises ValueError."""
        config = make_config("classification")
        config["output_format"] = "invalid"
        model = MLPTradingModel(config)
        with pytest.raises(ValueError, match="Unsupported output_format"):
            model.build_model(input_size=4)

    def test_configurable_num_classes(self):
        """Classification with custom num_classes."""
        config = make_config("classification")
        config["num_classes"] = 4
        model = MLPTradingModel(config)
        net = model.build_model(input_size=8)
        last_linear = [m for m in net.modules() if isinstance(m, nn.Linear)][-1]
        assert last_linear.out_features == 4

    def test_hidden_layers_architecture(self):
        """Hidden layers match config."""
        config = make_config("classification")
        config["architecture"]["hidden_layers"] = [64, 32, 16]
        model = MLPTradingModel(config)
        net = model.build_model(input_size=10)
        linears = [m for m in net.modules() if isinstance(m, nn.Linear)]
        # 3 hidden + 1 output = 4 linear layers
        assert len(linears) == 4
        assert linears[0].in_features == 10
        assert linears[0].out_features == 64
        assert linears[1].out_features == 32
        assert linears[2].out_features == 16
        assert linears[3].out_features == 3  # classification output
