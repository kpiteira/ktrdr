"""Tests for training service context helpers."""

from pathlib import Path
from unittest.mock import patch

import pytest

from ktrdr.api.endpoints.strategies import ValidationIssue
from ktrdr.errors import ValidationError


@pytest.fixture
def strategy_yaml(tmp_path: Path) -> Path:
    """Create a minimal strategy YAML file for tests."""
    strategy_dir = tmp_path / "strategies"
    strategy_dir.mkdir()
    strategy_file = strategy_dir / "test_strategy.yaml"
    strategy_file.write_text(
        """
indicators: []
fuzzy_sets: []
model:
  type: mlp
  training:
    epochs: 25
    batch_size: 64
""".strip()
    )
    return strategy_file


def make_issue(message: str) -> ValidationIssue:
    """Helper to build an error-level validation issue."""
    return ValidationIssue(
        severity="error",
        category="structure",
        message=message,
        details=None,
    )


class TestBuildTrainingContext:
    """Behaviour tests for build_training_context factory."""

    def test_successful_context_build(self, strategy_yaml: Path):
        from ktrdr.api.services.training.context import build_training_context

        with patch(
            "ktrdr.api.services.training.context._validate_strategy_config",
            return_value=[],
        ):
            context = build_training_context(
                operation_id="op-123",
                strategy_name="test_strategy",
                symbols=["AAPL"],
                timeframes=["1h"],
                start_date="2024-01-01",
                end_date="2024-06-01",
                detailed_analytics=True,
                use_host_service=False,
                strategy_search_paths=[strategy_yaml.parent],
            )

        assert context.operation_id == "op-123"
        assert context.strategy_path == strategy_yaml
        assert context.training_mode == "local"
        assert context.analytics_enabled is True
        assert context.total_epochs == 25
        assert context.total_batches is None
        assert context.metadata.symbol == "AAPL"
        assert context.metadata.timeframe == "1h"
        assert context.metadata.mode == "training"
        assert context.metadata.parameters["strategy_name"] == "test_strategy"
        assert context.metadata.parameters["use_host_service"] is False
        assert context.training_config["epochs"] == 25

    def test_missing_strategy_file(self, tmp_path: Path):
        from ktrdr.api.services.training.context import build_training_context

        with pytest.raises(ValidationError, match="Strategy file not found"):
            build_training_context(
                operation_id="op-missing",
                strategy_name="missing_strategy",
                symbols=["AAPL"],
                timeframes=["1h"],
                start_date=None,
                end_date=None,
                detailed_analytics=False,
                use_host_service=False,
                strategy_search_paths=[tmp_path],
            )

    def test_validation_failure(self, strategy_yaml: Path):
        from ktrdr.api.services.training.context import build_training_context

        with patch(
            "ktrdr.api.services.training.context._validate_strategy_config",
            return_value=[make_issue("broken config")],
        ):
            with pytest.raises(ValidationError, match="Strategy validation failed"):
                build_training_context(
                    operation_id="op-invalid",
                    strategy_name="test_strategy",
                    symbols=["AAPL"],
                    timeframes=["1h"],
                    start_date=None,
                    end_date=None,
                    detailed_analytics=False,
                    use_host_service=False,
                    strategy_search_paths=[strategy_yaml.parent],
                )
