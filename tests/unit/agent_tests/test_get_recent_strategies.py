"""
Unit tests for get_recent_strategies service function (Task 1.4).

Tests cover:
- get_recent_strategies: Query recent strategies for agent context
- Returns strategy details from completed sessions
- Gracefully handles missing YAML files
- Respects the limit parameter

These tests follow TDD - written BEFORE implementation.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import yaml


@pytest.fixture
def sample_strategy_yaml():
    """A complete strategy configuration as saved to disk."""
    return {
        "name": "momentum_rsi_v1",
        "description": "RSI-based momentum strategy",
        "version": "1.0",
        "scope": "universal",
        "training_data": {
            "symbols": {"mode": "single", "symbol": "EURUSD"},
            "timeframes": {"mode": "single", "timeframe": "1h"},
        },
        "indicators": [
            {"name": "rsi", "feature_id": "rsi_14", "period": 14, "source": "close"},
            {"name": "macd", "feature_id": "macd_12_26_9", "fast_period": 12},
        ],
        "fuzzy_sets": {
            "rsi_14": {
                "oversold": {"type": "triangular", "parameters": [0, 20, 35]},
            }
        },
        "model": {"type": "mlp", "architecture": {"hidden_layers": [32, 16]}},
        "decisions": {"output_format": "classification"},
        "training": {"method": "supervised"},
    }


@pytest.fixture
def mock_db_sessions():
    """Mock database sessions for testing."""
    return [
        {
            "id": 3,
            "strategy_name": "momentum_rsi_v1",
            "outcome": "success",
            "created_at": datetime(2024, 1, 3, 12, 0, 0, tzinfo=timezone.utc),
        },
        {
            "id": 2,
            "strategy_name": "mean_reversion_v2",
            "outcome": "failed_backtest_gate",
            "created_at": datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
        },
        {
            "id": 1,
            "strategy_name": "trend_follow_v1",
            "outcome": "failed_training",
            "created_at": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        },
    ]


class TestGetRecentStrategies:
    """Tests for get_recent_strategies service function."""

    @pytest.mark.asyncio
    async def test_returns_strategies_with_details(
        self, tmp_path, sample_strategy_yaml, mock_db_sessions
    ):
        """Should return strategies with name, type, indicators, outcome, created_at."""
        from research_agents.services.strategy_service import get_recent_strategies

        # Setup: Create strategy YAML file
        yaml_file = tmp_path / "momentum_rsi_v1.yaml"
        with open(yaml_file, "w") as f:
            yaml.dump(sample_strategy_yaml, f)

        # Mock database to return sessions
        mock_db = AsyncMock()
        mock_db.get_recent_completed_sessions = AsyncMock(
            return_value=mock_db_sessions[:1]  # Just first session
        )

        with patch(
            "research_agents.services.strategy_service.get_agent_db",
            return_value=mock_db,
        ):
            result = await get_recent_strategies(n=5, strategies_dir=str(tmp_path))

        assert len(result) == 1
        strategy = result[0]

        # Check all required fields are present
        assert "name" in strategy
        assert "type" in strategy
        assert "indicators" in strategy
        assert "outcome" in strategy
        assert "created_at" in strategy

        # Check values
        assert strategy["name"] == "momentum_rsi_v1"
        assert strategy["type"] == "mlp"  # From model.type
        assert strategy["indicators"] == ["rsi", "macd"]  # Indicator names
        assert strategy["outcome"] == "success"
        assert strategy["created_at"] == "2024-01-03T12:00:00+00:00"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_sessions(self, tmp_path):
        """Should return empty list when no completed sessions exist."""
        from research_agents.services.strategy_service import get_recent_strategies

        mock_db = AsyncMock()
        mock_db.get_recent_completed_sessions = AsyncMock(return_value=[])

        with patch(
            "research_agents.services.strategy_service.get_agent_db",
            return_value=mock_db,
        ):
            result = await get_recent_strategies(n=5, strategies_dir=str(tmp_path))

        assert result == []

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(self, tmp_path, mock_db_sessions):
        """Should return only n strategies when more exist."""
        from research_agents.services.strategy_service import get_recent_strategies

        mock_db = AsyncMock()
        mock_db.get_recent_completed_sessions = AsyncMock(return_value=mock_db_sessions)

        with patch(
            "research_agents.services.strategy_service.get_agent_db",
            return_value=mock_db,
        ):
            await get_recent_strategies(n=2, strategies_dir=str(tmp_path))

        # Should call database with limit
        mock_db.get_recent_completed_sessions.assert_called_once_with(n=2)

    @pytest.mark.asyncio
    async def test_default_limit_is_five(self, tmp_path, mock_db_sessions):
        """Default limit should be 5."""
        from research_agents.services.strategy_service import get_recent_strategies

        mock_db = AsyncMock()
        mock_db.get_recent_completed_sessions = AsyncMock(return_value=[])

        with patch(
            "research_agents.services.strategy_service.get_agent_db",
            return_value=mock_db,
        ):
            await get_recent_strategies(strategies_dir=str(tmp_path))

        mock_db.get_recent_completed_sessions.assert_called_once_with(n=5)

    @pytest.mark.asyncio
    async def test_handles_missing_yaml_gracefully(self, tmp_path, mock_db_sessions):
        """Should return partial info when YAML file is missing."""
        from research_agents.services.strategy_service import get_recent_strategies

        # No YAML files created - they're "missing"
        mock_db = AsyncMock()
        mock_db.get_recent_completed_sessions = AsyncMock(
            return_value=mock_db_sessions[:1]
        )

        with patch(
            "research_agents.services.strategy_service.get_agent_db",
            return_value=mock_db,
        ):
            result = await get_recent_strategies(n=5, strategies_dir=str(tmp_path))

        assert len(result) == 1
        strategy = result[0]

        # Should still have basic info from database
        assert strategy["name"] == "momentum_rsi_v1"
        assert strategy["outcome"] == "success"
        assert strategy["created_at"] == "2024-01-03T12:00:00+00:00"

        # Type and indicators should be None when YAML missing
        assert strategy["type"] is None
        assert strategy["indicators"] is None

    @pytest.mark.asyncio
    async def test_handles_corrupt_yaml_gracefully(self, tmp_path, mock_db_sessions):
        """Should return partial info when YAML file is corrupt."""
        from research_agents.services.strategy_service import get_recent_strategies

        # Create corrupt YAML file
        corrupt_file = tmp_path / "momentum_rsi_v1.yaml"
        corrupt_file.write_text("not: valid: yaml: {{{}}}}")

        mock_db = AsyncMock()
        mock_db.get_recent_completed_sessions = AsyncMock(
            return_value=mock_db_sessions[:1]
        )

        with patch(
            "research_agents.services.strategy_service.get_agent_db",
            return_value=mock_db,
        ):
            result = await get_recent_strategies(n=5, strategies_dir=str(tmp_path))

        assert len(result) == 1
        strategy = result[0]

        # Should still have basic info
        assert strategy["name"] == "momentum_rsi_v1"
        # Type and indicators should be None when YAML is unreadable
        assert strategy["type"] is None
        assert strategy["indicators"] is None

    @pytest.mark.asyncio
    async def test_extracts_indicators_correctly(self, tmp_path, mock_db_sessions):
        """Should extract indicator names from config."""
        from research_agents.services.strategy_service import get_recent_strategies

        # Create YAML with multiple indicators
        config = {
            "name": "momentum_rsi_v1",
            "model": {"type": "lstm"},
            "indicators": [
                {"name": "rsi", "feature_id": "rsi_14"},
                {"name": "macd", "feature_id": "macd_12_26_9"},
                {"name": "bollinger_bands", "feature_id": "bb_20"},
            ],
        }
        yaml_file = tmp_path / "momentum_rsi_v1.yaml"
        with open(yaml_file, "w") as f:
            yaml.dump(config, f)

        mock_db = AsyncMock()
        mock_db.get_recent_completed_sessions = AsyncMock(
            return_value=mock_db_sessions[:1]
        )

        with patch(
            "research_agents.services.strategy_service.get_agent_db",
            return_value=mock_db,
        ):
            result = await get_recent_strategies(n=5, strategies_dir=str(tmp_path))

        assert result[0]["indicators"] == ["rsi", "macd", "bollinger_bands"]

    @pytest.mark.asyncio
    async def test_extracts_model_type_correctly(self, tmp_path, mock_db_sessions):
        """Should extract model type from config."""
        from research_agents.services.strategy_service import get_recent_strategies

        # Test different model types
        for model_type in ["mlp", "lstm", "transformer"]:
            config = {
                "name": "momentum_rsi_v1",
                "model": {"type": model_type},
                "indicators": [],
            }
            yaml_file = tmp_path / "momentum_rsi_v1.yaml"
            with open(yaml_file, "w") as f:
                yaml.dump(config, f)

            mock_db = AsyncMock()
            mock_db.get_recent_completed_sessions = AsyncMock(
                return_value=mock_db_sessions[:1]
            )

            with patch(
                "research_agents.services.strategy_service.get_agent_db",
                return_value=mock_db,
            ):
                result = await get_recent_strategies(n=5, strategies_dir=str(tmp_path))

            assert result[0]["type"] == model_type

    @pytest.mark.asyncio
    async def test_returns_strategies_in_order(self, tmp_path, mock_db_sessions):
        """Should return strategies in most-recent-first order."""
        from research_agents.services.strategy_service import get_recent_strategies

        # Create YAML files for each
        for session in mock_db_sessions:
            config = {
                "name": session["strategy_name"],
                "model": {"type": "mlp"},
                "indicators": [],
            }
            yaml_file = tmp_path / f"{session['strategy_name']}.yaml"
            with open(yaml_file, "w") as f:
                yaml.dump(config, f)

        mock_db = AsyncMock()
        mock_db.get_recent_completed_sessions = AsyncMock(return_value=mock_db_sessions)

        with patch(
            "research_agents.services.strategy_service.get_agent_db",
            return_value=mock_db,
        ):
            result = await get_recent_strategies(n=5, strategies_dir=str(tmp_path))

        # Verify order matches mock data (most recent first)
        assert result[0]["name"] == "momentum_rsi_v1"  # id=3, most recent
        assert result[1]["name"] == "mean_reversion_v2"  # id=2
        assert result[2]["name"] == "trend_follow_v1"  # id=1, oldest

    @pytest.mark.asyncio
    async def test_skips_sessions_without_strategy_name(self, tmp_path):
        """Should skip sessions that don't have a strategy name."""
        from research_agents.services.strategy_service import get_recent_strategies

        sessions_with_none = [
            {
                "id": 2,
                "strategy_name": "valid_strategy",
                "outcome": "success",
                "created_at": datetime(2024, 1, 2, tzinfo=timezone.utc),
            },
            {
                "id": 1,
                "strategy_name": None,  # No strategy name
                "outcome": "failed_design",
                "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            },
        ]

        mock_db = AsyncMock()
        mock_db.get_recent_completed_sessions = AsyncMock(
            return_value=sessions_with_none
        )

        # Create YAML for valid strategy
        config = {"name": "valid_strategy", "model": {"type": "mlp"}, "indicators": []}
        yaml_file = tmp_path / "valid_strategy.yaml"
        with open(yaml_file, "w") as f:
            yaml.dump(config, f)

        with patch(
            "research_agents.services.strategy_service.get_agent_db",
            return_value=mock_db,
        ):
            result = await get_recent_strategies(n=5, strategies_dir=str(tmp_path))

        # Should only return the valid one
        assert len(result) == 1
        assert result[0]["name"] == "valid_strategy"


class TestGetRecentStrategiesIntegration:
    """Integration-style tests with database layer."""

    @pytest.mark.asyncio
    async def test_database_method_exists(self):
        """AgentDatabase should have get_recent_completed_sessions method."""
        from research_agents.database.queries import AgentDatabase

        db = AgentDatabase()
        assert hasattr(db, "get_recent_completed_sessions")
        assert callable(db.get_recent_completed_sessions)
