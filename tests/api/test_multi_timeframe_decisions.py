"""
Tests for multi-timeframe decision API endpoints.
"""

import pytest
import json
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
import pandas as pd

from ktrdr.api.main import app
from ktrdr.decision.base import Signal, Position, TradingDecision
from ktrdr.decision.multi_timeframe_orchestrator import (
    MultiTimeframeConsensus,
    TimeframeDecision,
)


class TestMultiTimeframeDecisionsAPI:
    """Test multi-timeframe decisions API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def sample_strategy_config(self):
        """Create sample strategy configuration."""
        return {
            "name": "test_multi_timeframe_strategy",
            "description": "Test strategy for multi-timeframe decisions",
            "timeframe_configs": {
                "1h": {"weight": 0.5, "primary": False},
                "4h": {"weight": 0.3, "primary": True},
                "1d": {"weight": 0.2, "primary": False},
            },
            "indicators": [
                {"name": "rsi", "period": 14},
                {"name": "macd", "fast": 12, "slow": 26, "signal": 9},
            ],
            "fuzzy_sets": {
                "rsi": {
                    "type": "triangular",
                    "sets": {
                        "oversold": {"low": 0, "mid": 30, "high": 50},
                        "neutral": {"low": 30, "mid": 50, "high": 70},
                        "overbought": {"low": 50, "mid": 70, "high": 100},
                    },
                }
            },
            "model": {
                "type": "mlp",
                "input_size": 10,
                "hidden_layers": [20, 10],
                "output_size": 3,
            },
            "multi_timeframe": {
                "consensus_method": "weighted_majority",
                "min_agreement_threshold": 0.6,
                "max_conflicting_timeframes": 1,
                "min_data_quality": 0.8,
            },
        }

    @pytest.fixture
    def temp_strategy_file(self, sample_strategy_config):
        """Create temporary strategy configuration file."""
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.dump(sample_strategy_config, temp_file)
        temp_file.close()
        yield temp_file.name
        Path(temp_file.name).unlink()

    @pytest.fixture
    def sample_timeframe_data(self):
        """Create sample timeframe data."""
        # Create sample data for multiple timeframes
        dates_1h = pd.date_range("2024-01-01", periods=100, freq="1h")
        data_1h = pd.DataFrame(
            {
                "open": [100.0] * 100,
                "high": [101.0] * 100,
                "low": [99.0] * 100,
                "close": [100.5] * 100,
                "volume": [1000] * 100,
            },
            index=dates_1h,
        )

        dates_4h = pd.date_range("2024-01-01", periods=25, freq="4h")
        data_4h = pd.DataFrame(
            {
                "open": [100.0] * 25,
                "high": [101.0] * 25,
                "low": [99.0] * 25,
                "close": [100.5] * 25,
                "volume": [4000] * 25,
            },
            index=dates_4h,
        )

        return {"1h": data_1h, "4h": data_4h}

    @pytest.fixture
    def mock_decision_orchestrator(self):
        """Create mock multi-timeframe decision orchestrator."""
        mock_orchestrator = Mock()

        # Mock decision
        mock_decision = TradingDecision(
            signal=Signal.BUY,
            confidence=0.8,
            timestamp=pd.Timestamp.now(tz="UTC"),
            reasoning={"test": "reasoning"},
            current_position=Position.FLAT,
        )
        mock_orchestrator.make_multi_timeframe_decision.return_value = mock_decision

        # Mock consensus
        mock_consensus = MultiTimeframeConsensus(
            final_signal=Signal.BUY,
            consensus_confidence=0.8,
            timeframe_decisions={
                "1h": TimeframeDecision(
                    timeframe="1h",
                    signal=Signal.BUY,
                    confidence=0.7,
                    weight=0.5,
                    reasoning={},
                    data_quality=0.9,
                ),
                "4h": TimeframeDecision(
                    timeframe="4h",
                    signal=Signal.BUY,
                    confidence=0.9,
                    weight=0.3,
                    reasoning={},
                    data_quality=0.8,
                ),
            },
            agreement_score=0.9,
            conflicting_timeframes=[],
            primary_timeframe_influence=0.8,
            consensus_method="weighted_majority",
            reasoning={"method": "weighted_majority"},
        )
        mock_orchestrator.get_consensus_history.return_value = [mock_consensus]

        # Mock analysis
        mock_analysis = {
            "symbol": "AAPL",
            "timeframes": ["1h", "4h"],
            "primary_timeframe": "4h",
            "timeframe_weights": {"1h": 0.5, "4h": 0.3},
            "recent_decisions_count": 5,
            "latest_consensus": {
                "final_signal": "BUY",
                "consensus_confidence": 0.8,
                "agreement_score": 0.9,
                "conflicting_timeframes": [],
                "consensus_method": "weighted_majority",
            },
        }
        mock_orchestrator.get_timeframe_analysis.return_value = mock_analysis

        return mock_orchestrator

    def test_make_multi_timeframe_decision_success(
        self,
        client,
        temp_strategy_file,
        mock_decision_orchestrator,
        sample_timeframe_data,
    ):
        """Test successful multi-timeframe decision generation."""

        with (
            patch(
                "ktrdr.api.endpoints.multi_timeframe_decisions.create_multi_timeframe_decision_orchestrator"
            ) as mock_create,
            patch(
                "ktrdr.api.endpoints.multi_timeframe_decisions.DataManager"
            ) as mock_dm,
        ):

            mock_create.return_value = mock_decision_orchestrator

            # Mock data manager
            mock_dm_instance = Mock()
            mock_dm_instance.get_data.side_effect = (
                lambda symbol, timeframe, rows: sample_timeframe_data.get(timeframe)
            )
            mock_dm.return_value = mock_dm_instance

            request_data = {
                "symbol": "AAPL",
                "strategy_config_path": temp_strategy_file,
                "timeframes": ["1h", "4h"],
                "mode": "backtest",
                "portfolio_state": {"total_value": 100000, "available_capital": 50000},
            }

            response = client.post(
                "/api/v1/multi-timeframe-decisions/decide", json=request_data
            )

            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            assert data["symbol"] == "AAPL"
            assert "timestamp" in data
            assert "decision" in data
            assert "consensus" in data
            assert "metadata" in data

            # Check decision structure
            decision = data["decision"]
            assert decision["signal"] == "BUY"
            assert decision["confidence"] == 0.8
            assert decision["current_position"] == "FLAT"

            # Check consensus structure
            consensus = data["consensus"]
            assert consensus["final_signal"] == "BUY"
            assert consensus["consensus_confidence"] == 0.8
            assert consensus["consensus_method"] == "weighted_majority"
            assert "timeframe_decisions" in consensus

    def test_make_multi_timeframe_decision_invalid_timeframe(
        self, client, temp_strategy_file
    ):
        """Test multi-timeframe decision with invalid timeframe."""

        request_data = {
            "symbol": "AAPL",
            "strategy_config_path": temp_strategy_file,
            "timeframes": ["1h", "invalid_tf"],
            "mode": "backtest",
        }

        response = client.post(
            "/api/v1/multi-timeframe-decisions/decide", json=request_data
        )

        assert response.status_code == 422  # Validation error

    def test_make_multi_timeframe_decision_invalid_mode(
        self, client, temp_strategy_file
    ):
        """Test multi-timeframe decision with invalid mode."""

        request_data = {
            "symbol": "AAPL",
            "strategy_config_path": temp_strategy_file,
            "timeframes": ["1h", "4h"],
            "mode": "invalid_mode",
        }

        response = client.post(
            "/api/v1/multi-timeframe-decisions/decide", json=request_data
        )

        assert response.status_code == 422  # Validation error

    def test_make_multi_timeframe_decision_missing_config(self, client):
        """Test multi-timeframe decision with missing configuration file."""

        request_data = {
            "symbol": "AAPL",
            "strategy_config_path": "/nonexistent/config.yaml",
            "timeframes": ["1h", "4h"],
            "mode": "backtest",
        }

        response = client.post(
            "/api/v1/multi-timeframe-decisions/decide", json=request_data
        )

        assert response.status_code == 404  # Config not found

    def test_make_multi_timeframe_decision_no_data(
        self, client, temp_strategy_file, mock_decision_orchestrator
    ):
        """Test multi-timeframe decision with no available data."""

        with (
            patch(
                "ktrdr.api.endpoints.multi_timeframe_decisions.create_multi_timeframe_decision_orchestrator"
            ) as mock_create,
            patch(
                "ktrdr.api.endpoints.multi_timeframe_decisions.DataManager"
            ) as mock_dm,
        ):

            mock_create.return_value = mock_decision_orchestrator

            # Mock data manager to return None/empty data
            mock_dm_instance = Mock()
            mock_dm_instance.get_data.return_value = None
            mock_dm.return_value = mock_dm_instance

            request_data = {
                "symbol": "UNKNOWN",
                "strategy_config_path": temp_strategy_file,
                "timeframes": ["1h", "4h"],
                "mode": "backtest",
            }

            response = client.post(
                "/api/v1/multi-timeframe-decisions/decide", json=request_data
            )

            assert response.status_code == 404  # No data available

    def test_analyze_timeframe_performance(
        self, client, temp_strategy_file, mock_decision_orchestrator
    ):
        """Test timeframe performance analysis endpoint."""

        with patch(
            "ktrdr.api.endpoints.multi_timeframe_decisions.create_multi_timeframe_decision_orchestrator"
        ) as mock_create:
            mock_create.return_value = mock_decision_orchestrator

            response = client.get(
                f"/api/v1/multi-timeframe-decisions/analyze/AAPL",
                params={
                    "strategy_config_path": temp_strategy_file,
                    "timeframes": ["1h", "4h"],
                    "mode": "backtest",
                },
            )

            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            assert data["symbol"] == "AAPL"
            assert data["timeframes"] == ["1h", "4h"]
            assert data["primary_timeframe"] == "4h"
            assert "timeframe_weights" in data
            assert "recent_decisions_count" in data
            assert "analysis_timestamp" in data

    def test_check_multi_timeframe_data_status(self, client, sample_timeframe_data):
        """Test multi-timeframe data status check."""

        with patch(
            "ktrdr.api.endpoints.multi_timeframe_decisions.DataManager"
        ) as mock_dm:
            # Mock data manager
            mock_dm_instance = Mock()
            mock_dm_instance.get_data.side_effect = (
                lambda symbol, timeframe, rows: sample_timeframe_data.get(timeframe)
            )
            mock_dm.return_value = mock_dm_instance

            response = client.get(
                "/api/v1/multi-timeframe-decisions/data-status/AAPL",
                params={"timeframes": ["1h", "4h"]},
            )

            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            assert data["symbol"] == "AAPL"
            assert len(data["timeframe_status"]) == 2
            assert "overall_data_quality" in data
            assert "ready_for_analysis" in data

            # Check timeframe status structure
            for tf_status in data["timeframe_status"]:
                assert "timeframe" in tf_status
                assert "available" in tf_status
                assert "record_count" in tf_status
                assert "data_quality_score" in tf_status
                assert "freshness_score" in tf_status

    def test_list_multi_timeframe_strategies(self, client, temp_strategy_file):
        """Test listing multi-timeframe strategies."""

        # Mock the strategies directory to include our temp file
        with patch("ktrdr.api.endpoints.multi_timeframe_decisions.Path") as mock_path:
            mock_strategies_dir = Mock()
            mock_strategies_dir.exists.return_value = True
            mock_strategies_dir.glob.return_value = [Path(temp_strategy_file)]
            mock_path.return_value = mock_strategies_dir

            response = client.get("/api/v1/multi-timeframe-decisions/strategies")

            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            assert len(data["strategies"]) >= 1

            # Check strategy structure
            strategy = data["strategies"][0]
            assert "name" in strategy
            assert "supports_multi_timeframe" in strategy
            assert strategy["supports_multi_timeframe"] is True
            assert "timeframes" in strategy
            assert "consensus_method" in strategy

    def test_batch_multi_timeframe_decisions(
        self,
        client,
        temp_strategy_file,
        mock_decision_orchestrator,
        sample_timeframe_data,
    ):
        """Test batch multi-timeframe decisions."""

        with (
            patch(
                "ktrdr.api.endpoints.multi_timeframe_decisions.create_multi_timeframe_decision_orchestrator"
            ) as mock_create,
            patch(
                "ktrdr.api.endpoints.multi_timeframe_decisions.DataManager"
            ) as mock_dm,
        ):

            mock_create.return_value = mock_decision_orchestrator

            # Mock data manager
            mock_dm_instance = Mock()
            mock_dm_instance.get_data.side_effect = (
                lambda symbol, timeframe, rows: sample_timeframe_data.get(timeframe)
            )
            mock_dm.return_value = mock_dm_instance

            batch_requests = [
                {
                    "symbol": "AAPL",
                    "strategy_config_path": temp_strategy_file,
                    "timeframes": ["1h", "4h"],
                    "mode": "backtest",
                },
                {
                    "symbol": "GOOGL",
                    "strategy_config_path": temp_strategy_file,
                    "timeframes": ["1h", "4h"],
                    "mode": "backtest",
                },
            ]

            response = client.post(
                "/api/v1/multi-timeframe-decisions/batch-decisions", json=batch_requests
            )

            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            assert data["processed"] == 2
            assert data["failed"] == 0
            assert len(data["results"]) == 2
            assert len(data["errors"]) == 0

    def test_batch_multi_timeframe_decisions_size_limit(
        self, client, temp_strategy_file
    ):
        """Test batch multi-timeframe decisions with size limit."""

        # Create batch larger than limit (10)
        batch_requests = [
            {
                "symbol": f"SYMBOL{i}",
                "strategy_config_path": temp_strategy_file,
                "timeframes": ["1h", "4h"],
                "mode": "backtest",
            }
            for i in range(11)  # 11 requests (over limit)
        ]

        response = client.post(
            "/api/v1/multi-timeframe-decisions/batch-decisions", json=batch_requests
        )

        assert response.status_code == 400  # Batch size limit exceeded

    def test_legacy_multi_timeframe_decision(
        self,
        client,
        temp_strategy_file,
        mock_decision_orchestrator,
        sample_timeframe_data,
    ):
        """Test legacy multi-timeframe decision endpoint."""

        with (
            patch(
                "ktrdr.api.endpoints.multi_timeframe_decisions.create_multi_timeframe_decision_orchestrator"
            ) as mock_create,
            patch(
                "ktrdr.api.endpoints.multi_timeframe_decisions.DataManager"
            ) as mock_dm,
        ):

            mock_create.return_value = mock_decision_orchestrator

            # Mock data manager
            mock_dm_instance = Mock()
            mock_dm_instance.get_data.side_effect = (
                lambda symbol, timeframe, rows: sample_timeframe_data.get(timeframe)
            )
            mock_dm.return_value = mock_dm_instance

            request_data = {
                "symbol": "AAPL",
                "strategy_config_path": temp_strategy_file,
                "timeframes": "1h,4h,1d",  # Comma-separated string
                "mode": "backtest",
            }

            response = client.post(
                "/api/v1/multi-timeframe-decisions/legacy/decide", json=request_data
            )

            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            assert data["symbol"] == "AAPL"

    def test_data_status_no_data_available(self, client):
        """Test data status check with no data available."""

        with patch(
            "ktrdr.api.endpoints.multi_timeframe_decisions.DataManager"
        ) as mock_dm:
            # Mock data manager to return None
            mock_dm_instance = Mock()
            mock_dm_instance.get_data.return_value = None
            mock_dm.return_value = mock_dm_instance

            response = client.get(
                "/api/v1/multi-timeframe-decisions/data-status/UNKNOWN",
                params={"timeframes": ["1h", "4h"]},
            )

            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            assert data["symbol"] == "UNKNOWN"
            assert data["overall_data_quality"] == 0.0
            assert data["ready_for_analysis"] is False

            # All timeframes should show as unavailable
            for tf_status in data["timeframe_status"]:
                assert tf_status["available"] is False
                assert tf_status["record_count"] == 0

    def test_strategies_list_empty_directory(self, client):
        """Test listing strategies when strategies directory doesn't exist."""

        with patch("ktrdr.api.endpoints.multi_timeframe_decisions.Path") as mock_path:
            mock_strategies_dir = Mock()
            mock_strategies_dir.exists.return_value = False
            mock_path.return_value = mock_strategies_dir

            response = client.get("/api/v1/multi-timeframe-decisions/strategies")

            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            assert data["strategies"] == []

    def test_analyze_timeframe_performance_missing_config(self, client):
        """Test timeframe analysis with missing configuration."""

        response = client.get(
            "/api/v1/multi-timeframe-decisions/analyze/AAPL",
            params={
                "strategy_config_path": "/nonexistent/config.yaml",
                "timeframes": ["1h", "4h"],
            },
        )

        assert response.status_code == 404
