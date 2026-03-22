"""Tests for LSTM trading model."""

import pytest

torch = pytest.importorskip("torch")
from ktrdr.neural.models.lstm import LSTMNetwork, LSTMTradingModel  # noqa: E402


class TestLSTMNetwork:
    """Test the raw PyTorch LSTM network module."""

    def test_forward_classification(self):
        """LSTM forward pass produces correct output shape for classification."""
        batch, seq_len, features, hidden, classes = 8, 20, 6, 64, 3
        net = LSTMNetwork(
            features, hidden, num_layers=2, num_classes=classes, dropout=0.2
        )
        x = torch.randn(batch, seq_len, features)
        out = net(x)
        assert out.shape == (batch, classes)

    def test_forward_regression(self):
        """LSTM forward pass produces correct output shape for regression."""
        batch, seq_len, features, hidden = 8, 20, 6, 64
        net = LSTMNetwork(features, hidden, num_layers=2, num_classes=1, dropout=0.2)
        x = torch.randn(batch, seq_len, features)
        out = net(x)
        assert out.shape == (batch, 1)

    def test_single_layer_no_dropout(self):
        """Single-layer LSTM works (dropout only applied between layers)."""
        net = LSTMNetwork(4, 32, num_layers=1, num_classes=3, dropout=0.5)
        x = torch.randn(2, 10, 4)
        out = net(x)
        assert out.shape == (2, 3)

    def test_single_sample_inference(self):
        """Batch size 1 works for inference."""
        net = LSTMNetwork(6, 64, num_layers=2, num_classes=3, dropout=0.0)
        net.eval()
        x = torch.randn(1, 20, 6)
        with torch.no_grad():
            out = net(x)
        assert out.shape == (1, 3)

    def test_output_not_nan(self):
        """Output contains no NaN values with normal input."""
        net = LSTMNetwork(6, 64, num_layers=2, num_classes=3, dropout=0.0)
        net.eval()
        x = torch.randn(4, 20, 6)
        with torch.no_grad():
            out = net(x)
        assert not torch.isnan(out).any()


class TestLSTMTradingModel:
    """Test the LSTMTradingModel wrapper."""

    def _make_config(self, **overrides):
        config = {
            "type": "lstm",
            "architecture": {
                "hidden_size": 32,
                "num_layers": 1,
                "dropout": 0.1,
                "sequence_length": 10,
            },
            "output_format": "classification",
            "num_classes": 3,
        }
        config.update(overrides)
        return config

    def test_build_model_returns_lstm_network(self):
        """build_model creates an LSTMNetwork."""
        model = LSTMTradingModel(self._make_config())
        net = model.build_model(input_size=6)
        assert isinstance(net, LSTMNetwork)

    def test_build_model_sets_input_size(self):
        """build_model stores input_size on the model object."""
        model = LSTMTradingModel(self._make_config())
        model.build_model(input_size=6)
        assert model.input_size == 6

    def test_build_model_classification(self):
        """Classification model has correct output dimension."""
        model = LSTMTradingModel(self._make_config(num_classes=3))
        net = model.build_model(input_size=6)
        x = torch.randn(2, 10, 6)
        out = net(x)
        assert out.shape == (2, 3)

    def test_build_model_regression(self):
        """Regression model has 1 output neuron."""
        config = self._make_config(output_format="regression")
        model = LSTMTradingModel(config)
        net = model.build_model(input_size=6)
        x = torch.randn(2, 10, 6)
        out = net(x)
        assert out.shape == (2, 1)

    def test_missing_sequence_length_raises(self):
        """Missing sequence_length in architecture raises ValueError."""
        config = self._make_config()
        del config["architecture"]["sequence_length"]
        model = LSTMTradingModel(config)
        with pytest.raises(ValueError, match="sequence_length"):
            model.build_model(input_size=6)

    def test_sequence_length_property(self):
        """sequence_length is accessible from config."""
        model = LSTMTradingModel(self._make_config())
        assert model.sequence_length == 10
