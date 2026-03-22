"""Tests for ModelMetadata temporal model fields."""

from ktrdr.models.model_metadata import ModelMetadata


class TestModelMetadataTemporal:
    """Test model_type and sequence_length fields."""

    def test_default_model_type_is_mlp(self):
        """Default model_type is 'mlp' for backward compatibility."""
        meta = ModelMetadata(model_name="test", strategy_name="test")
        assert meta.model_type == "mlp"

    def test_default_sequence_length_is_none(self):
        """Default sequence_length is None."""
        meta = ModelMetadata(model_name="test", strategy_name="test")
        assert meta.sequence_length is None

    def test_serialize_temporal_fields(self):
        """model_type and sequence_length round-trip through to_dict/from_dict."""
        meta = ModelMetadata(
            model_name="lstm_test",
            strategy_name="trend_lstm",
            model_type="lstm",
            sequence_length=20,
        )
        d = meta.to_dict()
        assert d["model_type"] == "lstm"
        assert d["sequence_length"] == 20

        restored = ModelMetadata.from_dict(d)
        assert restored.model_type == "lstm"
        assert restored.sequence_length == 20

    def test_backward_compat_missing_fields(self):
        """Old metadata without model_type/sequence_length loads with defaults."""
        old_data = {
            "model_name": "old_model",
            "strategy_name": "old_strategy",
            "resolved_features": ["rsi_oversold"],
        }
        meta = ModelMetadata.from_dict(old_data)
        assert meta.model_type == "mlp"
        assert meta.sequence_length is None
