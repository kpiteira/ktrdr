"""Tests for pipeline exception types.

These exceptions are for infrastructure errors (bugs to fix),
not experiments to learn from. They should fail operations visibly.
"""

import pytest


class TestPipelineExceptionHierarchy:
    """Test exception class hierarchy and basic functionality."""

    def test_pipeline_error_is_importable(self):
        """PipelineError should be importable from training.exceptions."""
        from ktrdr.training.exceptions import PipelineError

        assert PipelineError is not None

    def test_training_data_error_is_importable(self):
        """TrainingDataError should be importable from training.exceptions."""
        from ktrdr.training.exceptions import TrainingDataError

        assert TrainingDataError is not None

    def test_backtest_data_error_is_importable(self):
        """BacktestDataError should be importable from training.exceptions."""
        from ktrdr.training.exceptions import BacktestDataError

        assert BacktestDataError is not None

    def test_model_load_error_is_importable(self):
        """ModelLoadError should be importable from training.exceptions."""
        from ktrdr.training.exceptions import ModelLoadError

        assert ModelLoadError is not None

    def test_pipeline_error_inherits_from_exception(self):
        """PipelineError should inherit from Exception."""
        from ktrdr.training.exceptions import PipelineError

        assert issubclass(PipelineError, Exception)

    def test_training_data_error_inherits_from_pipeline_error(self):
        """TrainingDataError should inherit from PipelineError."""
        from ktrdr.training.exceptions import PipelineError, TrainingDataError

        assert issubclass(TrainingDataError, PipelineError)

    def test_backtest_data_error_inherits_from_pipeline_error(self):
        """BacktestDataError should inherit from PipelineError."""
        from ktrdr.training.exceptions import BacktestDataError, PipelineError

        assert issubclass(BacktestDataError, PipelineError)

    def test_model_load_error_inherits_from_pipeline_error(self):
        """ModelLoadError should inherit from PipelineError."""
        from ktrdr.training.exceptions import ModelLoadError, PipelineError

        assert issubclass(ModelLoadError, PipelineError)


class TestExceptionMessages:
    """Test that exception messages are preserved correctly."""

    def test_pipeline_error_preserves_message(self):
        """PipelineError should preserve the error message."""
        from ktrdr.training.exceptions import PipelineError

        msg = "Something went wrong in the pipeline"
        exc = PipelineError(msg)
        assert str(exc) == msg

    def test_training_data_error_preserves_message(self):
        """TrainingDataError should preserve the error message."""
        from ktrdr.training.exceptions import TrainingDataError

        msg = "No test data provided - data pipeline failed"
        exc = TrainingDataError(msg)
        assert str(exc) == msg

    def test_backtest_data_error_preserves_message(self):
        """BacktestDataError should preserve the error message."""
        from ktrdr.training.exceptions import BacktestDataError

        msg = "No price data available for EURUSD"
        exc = BacktestDataError(msg)
        assert str(exc) == msg

    def test_model_load_error_preserves_message(self):
        """ModelLoadError should preserve the error message."""
        from ktrdr.training.exceptions import ModelLoadError

        msg = "Model file not found: /path/to/model.pt"
        exc = ModelLoadError(msg)
        assert str(exc) == msg


class TestExceptionRaising:
    """Test that exceptions can be raised and caught correctly."""

    def test_can_raise_and_catch_pipeline_error(self):
        """Should be able to raise and catch PipelineError."""
        from ktrdr.training.exceptions import PipelineError

        with pytest.raises(PipelineError) as exc_info:
            raise PipelineError("Test error")

        assert "Test error" in str(exc_info.value)

    def test_can_catch_training_data_error_as_pipeline_error(self):
        """TrainingDataError should be catchable as PipelineError."""
        from ktrdr.training.exceptions import PipelineError, TrainingDataError

        with pytest.raises(PipelineError):
            raise TrainingDataError("No test data")

    def test_can_catch_backtest_data_error_as_pipeline_error(self):
        """BacktestDataError should be catchable as PipelineError."""
        from ktrdr.training.exceptions import BacktestDataError, PipelineError

        with pytest.raises(PipelineError):
            raise BacktestDataError("No price data")

    def test_can_catch_model_load_error_as_pipeline_error(self):
        """ModelLoadError should be catchable as PipelineError."""
        from ktrdr.training.exceptions import ModelLoadError, PipelineError

        with pytest.raises(PipelineError):
            raise ModelLoadError("Model not found")
