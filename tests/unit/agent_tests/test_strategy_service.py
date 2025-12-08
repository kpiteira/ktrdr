"""
Unit tests for strategy service (Task 1.3).

Tests cover:
- save_strategy_config: Validate and save strategy to disk
- Valid strategies saved successfully
- Invalid strategies rejected with clear errors
- Duplicate names rejected

These tests follow TDD - written BEFORE implementation.
"""

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def valid_strategy_config():
    """A valid v2 strategy configuration."""
    return {
        "name": "test_agent_strategy",
        "description": "Test strategy for unit testing",
        "version": "1.0",
        "scope": "universal",
        "hypothesis": "Test hypothesis for agent-generated strategy",
        "training_data": {
            "symbols": {"mode": "single", "symbol": "EURUSD"},
            "timeframes": {"mode": "single", "timeframe": "1h"},
        },
        "deployment": {
            "target_symbols": {"mode": "universal"},
            "target_timeframes": {"mode": "single", "timeframe": "1h"},
        },
        "indicators": [
            {"name": "rsi", "feature_id": "rsi_14", "period": 14, "source": "close"},
        ],
        "fuzzy_sets": {
            "rsi_14": {
                "oversold": {"type": "triangular", "parameters": [0, 20, 35]},
                "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
                "overbought": {"type": "triangular", "parameters": [65, 80, 100]},
            }
        },
        "model": {
            "type": "mlp",
            "architecture": {
                "hidden_layers": [32, 16],
                "activation": "relu",
                "output_activation": "softmax",
                "dropout": 0.2,
            },
            "training": {
                "learning_rate": 0.001,
                "batch_size": 32,
                "epochs": 50,
                "optimizer": "adam",
            },
            "features": {
                "include_price_context": False,
                "lookback_periods": 2,
                "scale_features": True,
            },
        },
        "decisions": {
            "output_format": "classification",
            "confidence_threshold": 0.6,
            "position_awareness": True,
        },
        "training": {
            "method": "supervised",
            "labels": {
                "source": "zigzag",
                "zigzag_threshold": 0.03,
                "label_lookahead": 20,
            },
            "data_split": {"train": 0.7, "validation": 0.15, "test": 0.15},
        },
    }


@pytest.fixture
def invalid_strategy_config():
    """An invalid strategy with unknown indicator."""
    return {
        "name": "test_invalid_strategy",
        "version": "1.0",
        "scope": "universal",
        "training_data": {
            "symbols": {"mode": "single", "symbol": "EURUSD"},
            "timeframes": {"mode": "single", "timeframe": "1h"},
        },
        "deployment": {
            "target_symbols": {"mode": "universal"},
            "target_timeframes": {"mode": "single", "timeframe": "1h"},
        },
        "indicators": [
            {
                "name": "fake_indicator_xyz",
                "feature_id": "fake_1",
                "period": 14,
            },
        ],
        "fuzzy_sets": {
            "fake_1": {
                "low": {"type": "triangular", "parameters": [0, 20, 40]},
            }
        },
        "model": {
            "type": "mlp",
            "architecture": {
                "hidden_layers": [20, 10],
                "activation": "relu",
                "output_activation": "softmax",
                "dropout": 0.2,
            },
            "training": {
                "learning_rate": 0.001,
                "batch_size": 32,
                "epochs": 100,
                "optimizer": "adam",
            },
            "features": {
                "include_price_context": False,
                "lookback_periods": 2,
                "scale_features": True,
            },
        },
        "decisions": {
            "output_format": "classification",
            "confidence_threshold": 0.6,
            "position_awareness": True,
        },
        "training": {
            "method": "supervised",
            "labels": {
                "source": "zigzag",
                "zigzag_threshold": 0.03,
                "label_lookahead": 20,
            },
            "data_split": {"train": 0.7, "validation": 0.15, "test": 0.15},
        },
    }


class TestSaveStrategyConfig:
    """Tests for save_strategy_config service function."""

    @pytest.mark.asyncio
    async def test_save_valid_strategy_success(self, tmp_path, valid_strategy_config):
        """Valid strategy should be saved to disk."""
        from research_agents.services.strategy_service import save_strategy_config

        result = await save_strategy_config(
            name="test_agent_strategy",
            config=valid_strategy_config,
            description="Test strategy",
            strategies_dir=str(tmp_path),
        )

        assert result["success"] is True
        assert "path" in result
        assert result["path"].endswith(".yaml")

        # Verify file was created
        saved_path = Path(result["path"])
        assert saved_path.exists()

        # Verify content is valid YAML
        with open(saved_path) as f:
            saved_config = yaml.safe_load(f)

        assert saved_config["name"] == "test_agent_strategy"
        assert "indicators" in saved_config
        assert "fuzzy_sets" in saved_config

    @pytest.mark.asyncio
    async def test_save_invalid_strategy_rejected(
        self, tmp_path, invalid_strategy_config
    ):
        """Invalid strategy should be rejected with errors."""
        from research_agents.services.strategy_service import save_strategy_config

        result = await save_strategy_config(
            name="test_invalid_strategy",
            config=invalid_strategy_config,
            description="Invalid strategy",
            strategies_dir=str(tmp_path),
        )

        assert result["success"] is False
        assert "errors" in result
        assert len(result["errors"]) > 0

        # Error should mention the invalid indicator
        errors_str = " ".join(result["errors"])
        assert "fake_indicator_xyz" in errors_str.lower()

        # File should NOT be created
        yaml_path = tmp_path / "test_invalid_strategy.yaml"
        assert not yaml_path.exists()

    @pytest.mark.asyncio
    async def test_save_duplicate_name_rejected(self, tmp_path, valid_strategy_config):
        """Duplicate strategy name should be rejected."""
        from research_agents.services.strategy_service import save_strategy_config

        # Create a file with the same name
        existing_file = tmp_path / "test_duplicate.yaml"
        existing_file.write_text("name: test_duplicate\n")

        # Try to save with same name
        config = valid_strategy_config.copy()
        config["name"] = "test_duplicate"

        result = await save_strategy_config(
            name="test_duplicate",
            config=config,
            description="Duplicate strategy",
            strategies_dir=str(tmp_path),
        )

        assert result["success"] is False
        assert "errors" in result
        assert any("already exists" in err.lower() for err in result["errors"])

    @pytest.mark.asyncio
    async def test_save_with_description_in_yaml(self, tmp_path, valid_strategy_config):
        """Description should be included in saved YAML."""
        from research_agents.services.strategy_service import save_strategy_config

        result = await save_strategy_config(
            name="test_with_description",
            config=valid_strategy_config,
            description="Agent-designed momentum strategy",
            strategies_dir=str(tmp_path),
        )

        assert result["success"] is True

        # Read saved file
        with open(result["path"]) as f:
            saved_config = yaml.safe_load(f)

        # Description should be in the config
        assert saved_config.get("description") == "Agent-designed momentum strategy"

    @pytest.mark.asyncio
    async def test_save_creates_directory_if_missing(
        self, tmp_path, valid_strategy_config
    ):
        """Should create strategies directory if it doesn't exist."""
        from research_agents.services.strategy_service import save_strategy_config

        # Use a non-existent subdirectory
        new_strategies_dir = tmp_path / "new_strategies_subdir"
        assert not new_strategies_dir.exists()

        result = await save_strategy_config(
            name="test_new_dir",
            config=valid_strategy_config,
            description="Test",
            strategies_dir=str(new_strategies_dir),
        )

        assert result["success"] is True
        assert new_strategies_dir.exists()
        assert (new_strategies_dir / "test_new_dir.yaml").exists()

    @pytest.mark.asyncio
    async def test_save_includes_suggestions_on_error(
        self, tmp_path, invalid_strategy_config
    ):
        """Error response should include suggestions for fixing."""
        from research_agents.services.strategy_service import save_strategy_config

        result = await save_strategy_config(
            name="test_suggestions",
            config=invalid_strategy_config,
            description="Test",
            strategies_dir=str(tmp_path),
        )

        assert result["success"] is False
        assert "suggestions" in result

    @pytest.mark.asyncio
    async def test_save_returns_correct_path(self, tmp_path, valid_strategy_config):
        """Returned path should be absolute and correct."""
        from research_agents.services.strategy_service import save_strategy_config

        result = await save_strategy_config(
            name="correct_path_test",
            config=valid_strategy_config,
            description="Test",
            strategies_dir=str(tmp_path),
        )

        assert result["success"] is True
        path = Path(result["path"])

        # Path should be absolute
        assert path.is_absolute()

        # Path should point to actual file
        assert path.exists()
        assert path.name == "correct_path_test.yaml"


class TestSaveStrategyConfigEdgeCases:
    """Edge case tests for save_strategy_config."""

    @pytest.mark.asyncio
    async def test_name_with_yaml_extension_handled(
        self, tmp_path, valid_strategy_config
    ):
        """Name with .yaml extension should work correctly."""
        from research_agents.services.strategy_service import save_strategy_config

        result = await save_strategy_config(
            name="test_with_ext.yaml",
            config=valid_strategy_config,
            description="Test",
            strategies_dir=str(tmp_path),
        )

        assert result["success"] is True
        # Should not create "test_with_ext.yaml.yaml"
        assert not (tmp_path / "test_with_ext.yaml.yaml").exists()
        # Should create "test_with_ext.yaml"
        assert (tmp_path / "test_with_ext.yaml").exists()

    @pytest.mark.asyncio
    async def test_empty_config_rejected(self, tmp_path):
        """Empty config should be rejected."""
        from research_agents.services.strategy_service import save_strategy_config

        result = await save_strategy_config(
            name="empty_config",
            config={},
            description="Empty",
            strategies_dir=str(tmp_path),
        )

        assert result["success"] is False
        assert "errors" in result

    @pytest.mark.asyncio
    async def test_name_overwrites_config_name(self, tmp_path, valid_strategy_config):
        """Name parameter should be used even if config has different name."""
        from research_agents.services.strategy_service import save_strategy_config

        config = valid_strategy_config.copy()
        config["name"] = "original_name"

        result = await save_strategy_config(
            name="override_name",
            config=config,
            description="Test",
            strategies_dir=str(tmp_path),
        )

        assert result["success"] is True
        # File should use the name parameter, not config name
        assert (tmp_path / "override_name.yaml").exists()
        assert not (tmp_path / "original_name.yaml").exists()

        # Config inside file should have the correct name
        with open(tmp_path / "override_name.yaml") as f:
            saved = yaml.safe_load(f)
        assert saved["name"] == "override_name"
