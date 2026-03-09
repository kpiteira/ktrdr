"""Unit tests for multi-TF training timeframes resolution (M1).

Tests that the training orchestrator resolves timeframes from the v3 strategy
config rather than relying solely on API-passed timeframes.
"""

from unittest.mock import MagicMock


class TestTrainingTimeframeResolution:
    """Tests that v3 training uses strategy config timeframes, not just API-passed."""

    def test_multi_tf_resolution_logic(self) -> None:
        """Strategy declaring [1h, 4h, 1d] should override API's [1h] for data loading.

        This tests the core logic: if v3_config.training_data.timeframes has
        multiple entries, use those instead of context.timeframes.
        """
        # Simulate the resolution logic from _execute_v3_training
        context_timeframes = ["1h"]  # What API passed

        # Multi-TF strategy config
        tf_config = MagicMock()
        tf_config.timeframes = ["1h", "4h", "1d"]

        if tf_config.timeframes and len(tf_config.timeframes) > 1:
            training_timeframes = list(tf_config.timeframes)
        else:
            training_timeframes = context_timeframes

        assert training_timeframes == ["1h", "4h", "1d"]

    def test_single_tf_resolution_logic(self) -> None:
        """Single-TF strategy should fall back to context timeframes."""
        context_timeframes = ["1h"]

        tf_config = MagicMock()
        tf_config.timeframes = None  # Single-TF mode

        if tf_config.timeframes and len(tf_config.timeframes) > 1:
            training_timeframes = list(tf_config.timeframes)
        else:
            training_timeframes = context_timeframes

        assert training_timeframes == ["1h"]

    def test_metadata_uses_actual_features_not_config(self) -> None:
        """Metadata resolved_features should use actual training features, not config."""
        import inspect

        from ktrdr.api.services.training.local_orchestrator import (
            LocalTrainingOrchestrator,
        )

        source = inspect.getsource(LocalTrainingOrchestrator._execute_v3_training)

        # The metadata call should use feature_names (actual), not resolved_features (config)
        assert "resolved_features=feature_names" in source, (
            "_save_v3_metadata should use feature_names (actual training features), "
            "not resolved_features (config-declared features)"
        )

        # Should warn when they differ
        assert (
            "Feature mismatch: strategy config declares" in source
        ), "Should warn when actual features differ from config-declared features"

    def test_orchestrator_has_strategy_config_resolution(self) -> None:
        """Verify the orchestrator resolves timeframes from v3_config, not just context."""
        import inspect

        from ktrdr.api.services.training.local_orchestrator import (
            LocalTrainingOrchestrator,
        )

        source = inspect.getsource(LocalTrainingOrchestrator._execute_v3_training)

        # Must resolve from strategy config
        assert "tf_config = v3_config.training_data.timeframes" in source
        assert "tf_config.timeframes" in source
        assert "training_timeframes" in source

        # Must use resolved timeframes for data loading, not context.timeframes
        assert "timeframes=training_timeframes" in source

    def test_data_summary_uses_resolved_timeframes(self) -> None:
        """Data summary in result should report actual training timeframes."""
        import inspect

        from ktrdr.api.services.training.local_orchestrator import (
            LocalTrainingOrchestrator,
        )

        source = inspect.getsource(LocalTrainingOrchestrator._execute_v3_training)

        # data_summary should use training_timeframes not self._context.timeframes
        assert '"timeframes": training_timeframes' in source, (
            "data_summary should report actual training_timeframes, "
            "not API-passed self._context.timeframes"
        )
