"""Tests for create_model() dispatch to LSTM/GRU."""

import pytest

torch = pytest.importorskip("torch")
import torch.nn as nn  # noqa: E402

from ktrdr.training.training_pipeline import TrainingPipeline  # noqa: E402


class TestCreateModelDispatch:
    """Test that create_model dispatches to correct model type."""

    def test_mlp_still_works(self):
        """MLP path unchanged — regression test."""
        config = {
            "type": "mlp",
            "architecture": {"hidden_layers": [32, 16], "dropout": 0.2},
        }
        model = TrainingPipeline.create_model(
            input_dim=6, output_dim=3, model_config=config
        )
        assert isinstance(model, nn.Module)
        # MLP: (batch, features) -> (batch, classes)
        out = model(torch.randn(2, 6))
        assert out.shape == (2, 3)

    def test_lstm_dispatch(self):
        """create_model(type='lstm') returns LSTM architecture."""
        config = {
            "type": "lstm",
            "architecture": {
                "hidden_size": 32,
                "num_layers": 1,
                "dropout": 0.1,
                "sequence_length": 10,
            },
        }
        model = TrainingPipeline.create_model(
            input_dim=6, output_dim=3, model_config=config
        )
        assert isinstance(model, nn.Module)
        # LSTM: (batch, seq_len, features) -> (batch, classes)
        out = model(torch.randn(2, 10, 6))
        assert out.shape == (2, 3)

    def test_gru_dispatch(self):
        """create_model(type='gru') returns GRU architecture."""
        config = {
            "type": "gru",
            "architecture": {
                "hidden_size": 32,
                "num_layers": 1,
                "dropout": 0.1,
                "sequence_length": 10,
            },
        }
        model = TrainingPipeline.create_model(
            input_dim=6, output_dim=3, model_config=config
        )
        assert isinstance(model, nn.Module)
        out = model(torch.randn(2, 10, 6))
        assert out.shape == (2, 3)

    def test_unknown_type_raises(self):
        """Unknown model type raises ValueError."""
        config = {"type": "transformer", "architecture": {}}
        with pytest.raises(ValueError, match="Unknown model type"):
            TrainingPipeline.create_model(
                input_dim=6, output_dim=3, model_config=config
            )

    def test_default_type_is_mlp(self):
        """No type specified defaults to MLP."""
        config = {"architecture": {"hidden_layers": [16], "dropout": 0.1}}
        model = TrainingPipeline.create_model(
            input_dim=4, output_dim=3, model_config=config
        )
        out = model(torch.randn(1, 4))
        assert out.shape == (1, 3)
