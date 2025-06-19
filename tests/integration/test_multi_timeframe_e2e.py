"""
End-to-end integration tests for multi-timeframe system.

This module tests the complete pipeline from data loading to decision making,
ensuring all components work together seamlessly.
"""

import pytest
import asyncio
import tempfile
import yaml
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from ktrdr.decision.multi_timeframe_orchestrator import (
    MultiTimeframeDecisionOrchestrator,
    create_multi_timeframe_decision_orchestrator,
)
from ktrdr.data.data_manager import DataManager
from ktrdr.decision.base import Signal, Position, TradingDecision

# from ktrdr.config.strategy_config import StrategyConfig
# from ktrdr.neural.multi_timeframe_model import MultiTimeframeNeuroFuzzyModel


class TestMultiTimeframeEndToEnd:
    """End-to-end integration tests for multi-timeframe system."""

    @pytest.fixture
    def sample_data(self):
        """Create sample market data for testing."""
        dates = pd.date_range(
            start=datetime.now() - timedelta(days=100), end=datetime.now(), freq="1h"
        )

        # Create realistic OHLCV data
        data = {
            "1h": pd.DataFrame(
                {
                    "timestamp": dates,
                    "open": 150 + (pd.Series(range(len(dates))) * 0.1),
                    "high": 152 + (pd.Series(range(len(dates))) * 0.1),
                    "low": 148 + (pd.Series(range(len(dates))) * 0.1),
                    "close": 151 + (pd.Series(range(len(dates))) * 0.1),
                    "volume": 1000000 + (pd.Series(range(len(dates))) * 1000),
                }
            ),
            "4h": pd.DataFrame(
                {
                    "timestamp": dates[::4],  # Every 4 hours
                    "open": 150 + (pd.Series(range(len(dates[::4]))) * 0.4),
                    "high": 153 + (pd.Series(range(len(dates[::4]))) * 0.4),
                    "low": 147 + (pd.Series(range(len(dates[::4]))) * 0.4),
                    "close": 151.5 + (pd.Series(range(len(dates[::4]))) * 0.4),
                    "volume": 4000000 + (pd.Series(range(len(dates[::4]))) * 4000),
                }
            ),
            "1d": pd.DataFrame(
                {
                    "timestamp": dates[::24],  # Every 24 hours
                    "open": 150 + (pd.Series(range(len(dates[::24]))) * 2.0),
                    "high": 155 + (pd.Series(range(len(dates[::24]))) * 2.0),
                    "low": 145 + (pd.Series(range(len(dates[::24]))) * 2.0),
                    "close": 152 + (pd.Series(range(len(dates[::24]))) * 2.0),
                    "volume": 24000000 + (pd.Series(range(len(dates[::24]))) * 24000),
                }
            ),
        }

        # Set timestamp as index
        for tf in data:
            data[tf] = data[tf].set_index("timestamp")

        return data

    @pytest.fixture
    def comprehensive_strategy_config(self):
        """Create comprehensive strategy configuration."""
        return {
            "name": "comprehensive_multi_timeframe_strategy",
            "version": "2.0",
            "description": "Comprehensive multi-timeframe neuro-fuzzy strategy",
            "timeframe_configs": {
                "1h": {
                    "weight": 0.5,
                    "primary": False,
                    "lookback_periods": 50,
                    "min_data_quality": 0.8,
                },
                "4h": {
                    "weight": 0.3,
                    "primary": True,
                    "lookback_periods": 30,
                    "min_data_quality": 0.9,
                },
                "1d": {
                    "weight": 0.2,
                    "primary": False,
                    "lookback_periods": 20,
                    "min_data_quality": 0.85,
                },
            },
            "indicators": [
                {"name": "rsi", "period": 14, "timeframes": ["1h", "4h", "1d"]},
                {"name": "sma", "period": 20, "timeframes": ["1h", "4h", "1d"]},
                {"name": "ema", "period": 12, "timeframes": ["4h", "1d"]},
            ],
            "fuzzy_sets": {
                "rsi": {
                    "oversold": {"type": "triangular", "parameters": [0, 30, 50]},
                    "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
                    "overbought": {"type": "triangular", "parameters": [50, 70, 100]},
                },
                "sma_position": {
                    "below": {"type": "triangular", "parameters": [0.9, 0.95, 1.0]},
                    "near": {"type": "triangular", "parameters": [0.95, 1.0, 1.05]},
                    "above": {"type": "triangular", "parameters": [1.0, 1.05, 1.1]},
                },
            },
            "fuzzy_rules": [
                {
                    "name": "oversold_buy",
                    "conditions": [
                        {"indicator": "rsi", "set": "oversold", "timeframe": "4h"},
                        {
                            "indicator": "sma_position",
                            "set": "below",
                            "timeframe": "1d",
                        },
                    ],
                    "action": {"signal": "BUY", "confidence": 0.8},
                },
                {
                    "name": "overbought_sell",
                    "conditions": [
                        {"indicator": "rsi", "set": "overbought", "timeframe": "4h"},
                        {
                            "indicator": "sma_position",
                            "set": "above",
                            "timeframe": "1d",
                        },
                    ],
                    "action": {"signal": "SELL", "confidence": 0.75},
                },
            ],
            "model": {
                "type": "mlp",
                "input_features": ["rsi", "sma_position"],
                "hidden_layers": [64, 32],
                "activation": "tanh",
                "learning_rate": 0.001,
                "epochs": 100,
            },
            "multi_timeframe": {
                "consensus_method": "weighted_majority",
                "min_agreement_score": 0.6,
                "conflicting_signal_resolution": "favor_primary",
                "data_quality_threshold": 0.8,
                "max_timeframe_lag": 300,  # 5 minutes
            },
            "neural_config": {
                "model_type": "multi_timeframe_lstm",
                "hidden_layers": [128, 64, 32],
                "dropout_rate": 0.2,
                "learning_rate": 0.001,
                "batch_size": 32,
                "epochs": 100,
                "early_stopping_patience": 10,
                "use_fuzzy_features": True,
                "timeframe_fusion_method": "attention",
            },
            "risk_management": {
                "max_position_size": 0.1,
                "stop_loss_pct": 0.02,
                "take_profit_pct": 0.04,
                "max_correlation": 0.7,
            },
        }

    @pytest.fixture
    def temp_strategy_file(self, comprehensive_strategy_config):
        """Create temporary strategy configuration file."""
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.dump(comprehensive_strategy_config, temp_file)
        temp_file.close()
        yield temp_file.name
        Path(temp_file.name).unlink()

    @pytest.mark.asyncio
    async def test_complete_pipeline_data_to_decision(
        self, sample_data, temp_strategy_file
    ):
        """Test complete pipeline from data loading to decision generation."""

        # Mock data manager to return our sample data
        with patch(
            "ktrdr.decision.multi_timeframe_orchestrator.DataManager"
        ) as mock_dm:
            mock_dm_instance = Mock()

            def mock_get_data(symbol, timeframe, rows=100):
                if timeframe in sample_data:
                    return sample_data[timeframe].tail(rows)
                return None

            mock_dm_instance.get_data.side_effect = mock_get_data
            mock_dm.return_value = mock_dm_instance

            # Create orchestrator
            orchestrator = create_multi_timeframe_decision_orchestrator(
                strategy_config_path=temp_strategy_file,
                timeframes=["1h", "4h", "1d"],
                mode="backtest",
            )

            # Portfolio state
            portfolio_state = {
                "total_value": 100000.0,
                "available_capital": 50000.0,
                "positions": {},
                "risk_exposure": 0.0,
            }

            # Generate decision
            decision = orchestrator.make_multi_timeframe_decision(
                symbol="AAPL",
                timeframe_data=sample_data,
                portfolio_state=portfolio_state,
            )

            # Validate decision structure
            assert isinstance(decision, TradingDecision)
            assert decision.signal in [Signal.BUY, Signal.SELL, Signal.HOLD]
            assert 0.0 <= decision.confidence <= 1.0
            assert decision.current_position in [
                Position.FLAT,
                Position.LONG,
                Position.SHORT,
            ]
            assert isinstance(decision.reasoning, dict)
            assert decision.timestamp is not None

            # Validate reasoning contains multi-timeframe information
            assert "multi_timeframe" in decision.reasoning
            assert "consensus_method" in decision.reasoning
            assert "multi_timeframe_metadata" in decision.reasoning

    @pytest.mark.asyncio
    async def test_pipeline_with_missing_data(self, temp_strategy_file):
        """Test pipeline resilience with missing timeframe data."""

        # Create partial data (missing 1d timeframe)
        base_time = pd.Timestamp.now(tz="UTC")
        partial_data = {
            "1h": pd.DataFrame(
                {
                    "timestamp": [base_time],
                    "open": [150],
                    "high": [152],
                    "low": [148],
                    "close": [151],
                    "volume": [1000000],
                }
            ).set_index("timestamp"),
            "4h": pd.DataFrame(
                {
                    "timestamp": [base_time],
                    "open": [150],
                    "high": [153],
                    "low": [147],
                    "close": [151.5],
                    "volume": [4000000],
                }
            ).set_index("timestamp"),
            # '1d' missing
        }

        with patch(
            "ktrdr.decision.multi_timeframe_orchestrator.DataManager"
        ) as mock_dm:
            mock_dm_instance = Mock()

            def mock_get_data(symbol, timeframe, rows=100):
                return partial_data.get(timeframe)

            mock_dm_instance.get_data.side_effect = mock_get_data
            mock_dm.return_value = mock_dm_instance

            orchestrator = create_multi_timeframe_decision_orchestrator(
                strategy_config_path=temp_strategy_file,
                timeframes=["1h", "4h", "1d"],
                mode="backtest",
            )

            portfolio_state = {"total_value": 100000.0, "available_capital": 50000.0}

            # Should handle missing data gracefully
            decision = orchestrator.make_multi_timeframe_decision(
                symbol="AAPL",
                timeframe_data=partial_data,
                portfolio_state=portfolio_state,
            )

            assert isinstance(decision, TradingDecision)
            assert "data_quality_issues" in decision.reasoning

    @pytest.mark.asyncio
    async def test_consensus_building_with_conflicting_signals(
        self, sample_data, temp_strategy_file
    ):
        """Test consensus building when timeframes give conflicting signals."""

        with patch(
            "ktrdr.decision.multi_timeframe_orchestrator.DataManager"
        ) as mock_dm:
            # Mock the base orchestrator to return conflicting signals
            with patch(
                "ktrdr.decision.multi_timeframe_orchestrator.DecisionOrchestrator"
            ) as mock_base:
                mock_dm_instance = Mock()
                mock_dm_instance.get_data.return_value = sample_data["1h"]
                mock_dm.return_value = mock_dm_instance

                # Create mock base orchestrator instances with conflicting decisions
                mock_orchestrator_1h = Mock()
                mock_orchestrator_4h = Mock()
                mock_orchestrator_1d = Mock()

                # 1h says BUY
                mock_decision_1h = TradingDecision(
                    signal=Signal.BUY,
                    confidence=0.8,
                    timestamp=pd.Timestamp.now(tz="UTC"),
                    reasoning={"timeframe": "1h", "signal": "BUY"},
                    current_position=Position.FLAT,
                )

                # 4h says SELL
                mock_decision_4h = TradingDecision(
                    signal=Signal.SELL,
                    confidence=0.7,
                    timestamp=pd.Timestamp.now(tz="UTC"),
                    reasoning={"timeframe": "4h", "signal": "SELL"},
                    current_position=Position.FLAT,
                )

                # 1d says HOLD
                mock_decision_1d = TradingDecision(
                    signal=Signal.HOLD,
                    confidence=0.6,
                    timestamp=pd.Timestamp.now(tz="UTC"),
                    reasoning={"timeframe": "1d", "signal": "HOLD"},
                    current_position=Position.FLAT,
                )

                mock_orchestrator_1h.make_decision.return_value = mock_decision_1h
                mock_orchestrator_4h.make_decision.return_value = mock_decision_4h
                mock_orchestrator_1d.make_decision.return_value = mock_decision_1d

                # Mock the factory function to return our mock orchestrators
                def mock_factory(*args, **kwargs):
                    if "1h" in str(kwargs.get("timeframes", [])):
                        return mock_orchestrator_1h
                    elif "4h" in str(kwargs.get("timeframes", [])):
                        return mock_orchestrator_4h
                    else:
                        return mock_orchestrator_1d

                mock_base.side_effect = mock_factory

                orchestrator = create_multi_timeframe_decision_orchestrator(
                    strategy_config_path=temp_strategy_file,
                    timeframes=["1h", "4h", "1d"],
                    mode="backtest",
                )

                portfolio_state = {
                    "total_value": 100000.0,
                    "available_capital": 50000.0,
                }

                decision = orchestrator.make_multi_timeframe_decision(
                    symbol="AAPL",
                    timeframe_data=sample_data,
                    portfolio_state=portfolio_state,
                )

                # Should have consensus information
                assert isinstance(decision, TradingDecision)
                assert "consensus_method" in decision.reasoning
                assert "conflicting_timeframes" in decision.reasoning

    @pytest.mark.asyncio
    async def test_model_integration_pipeline(self, sample_data, temp_strategy_file):
        """Test pipeline with neural model integration."""

        with patch(
            "ktrdr.decision.multi_timeframe_orchestrator.DataManager"
        ) as mock_dm:
            mock_dm_instance = Mock()
            mock_dm_instance.get_data.return_value = sample_data["1h"]
            mock_dm.return_value = mock_dm_instance

            # Create temp model file
            temp_model = tempfile.NamedTemporaryFile(suffix=".pt", delete=False)
            temp_model.close()

            try:
                orchestrator = create_multi_timeframe_decision_orchestrator(
                    strategy_config_path=temp_strategy_file,
                    timeframes=["1h", "4h", "1d"],
                    mode="backtest",
                    model_path=temp_model.name,
                )

                portfolio_state = {
                    "total_value": 100000.0,
                    "available_capital": 50000.0,
                }

                decision = orchestrator.make_multi_timeframe_decision(
                    symbol="AAPL",
                    timeframe_data=sample_data,
                    portfolio_state=portfolio_state,
                )

                assert isinstance(decision, TradingDecision)
                # Note: neural prediction testing depends on actual model implementation

            finally:
                Path(temp_model.name).unlink()

    @pytest.mark.asyncio
    async def test_error_recovery_and_fallbacks(self, sample_data, temp_strategy_file):
        """Test error recovery and fallback mechanisms."""

        with patch(
            "ktrdr.decision.multi_timeframe_orchestrator.DataManager"
        ) as mock_dm:
            # Simulate data manager throwing an exception for one timeframe
            mock_dm_instance = Mock()

            def mock_get_data_with_error(symbol, timeframe, rows=100):
                if timeframe == "4h":
                    raise Exception("Data fetch failed for 4h")
                return sample_data.get(timeframe)

            mock_dm_instance.get_data.side_effect = mock_get_data_with_error
            mock_dm.return_value = mock_dm_instance

            orchestrator = create_multi_timeframe_decision_orchestrator(
                strategy_config_path=temp_strategy_file,
                timeframes=["1h", "4h", "1d"],
                mode="backtest",
            )

            portfolio_state = {"total_value": 100000.0, "available_capital": 50000.0}

            # Should handle the error and continue with available data
            decision = orchestrator.make_multi_timeframe_decision(
                symbol="AAPL",
                timeframe_data={k: v for k, v in sample_data.items() if k != "4h"},
                portfolio_state=portfolio_state,
            )

            assert isinstance(decision, TradingDecision)
            assert "error_recovery" in decision.reasoning
            assert "failed_timeframes" in decision.reasoning

    @pytest.mark.asyncio
    async def test_performance_metrics_collection(
        self, sample_data, temp_strategy_file
    ):
        """Test that performance metrics are properly collected."""

        with patch(
            "ktrdr.decision.multi_timeframe_orchestrator.DataManager"
        ) as mock_dm:
            mock_dm_instance = Mock()
            mock_dm_instance.get_data.return_value = sample_data["1h"]
            mock_dm.return_value = mock_dm_instance

            orchestrator = create_multi_timeframe_decision_orchestrator(
                strategy_config_path=temp_strategy_file,
                timeframes=["1h", "4h", "1d"],
                mode="backtest",
            )

            portfolio_state = {"total_value": 100000.0, "available_capital": 50000.0}

            # Generate multiple decisions to test metrics
            for i in range(3):
                decision = orchestrator.make_multi_timeframe_decision(
                    symbol="AAPL",
                    timeframe_data=sample_data,
                    portfolio_state=portfolio_state,
                )

                assert isinstance(decision, TradingDecision)

            # Check that metrics are being collected
            metrics = orchestrator.get_performance_metrics()
            assert "total_decisions" in metrics
            assert "average_confidence" in metrics
            assert "consensus_distribution" in metrics
            assert metrics["total_decisions"] == 3

    @pytest.mark.asyncio
    async def test_state_persistence_and_history(self, sample_data, temp_strategy_file):
        """Test state persistence and decision history."""

        with patch(
            "ktrdr.decision.multi_timeframe_orchestrator.DataManager"
        ) as mock_dm:
            mock_dm_instance = Mock()
            mock_dm_instance.get_data.return_value = sample_data["1h"]
            mock_dm.return_value = mock_dm_instance

            orchestrator = create_multi_timeframe_decision_orchestrator(
                strategy_config_path=temp_strategy_file,
                timeframes=["1h", "4h", "1d"],
                mode="backtest",
            )

            portfolio_state = {"total_value": 100000.0, "available_capital": 50000.0}

            # Generate decision
            decision1 = orchestrator.make_multi_timeframe_decision(
                symbol="AAPL",
                timeframe_data=sample_data,
                portfolio_state=portfolio_state,
            )

            # Check decision history
            history = orchestrator.get_decision_history(symbol="AAPL", limit=10)
            assert len(history) == 1
            assert history[0]["decision"]["signal"] == decision1.signal.value

            # Generate another decision
            decision2 = orchestrator.make_multi_timeframe_decision(
                symbol="AAPL",
                timeframe_data=sample_data,
                portfolio_state=portfolio_state,
            )

            # Check updated history
            history = orchestrator.get_decision_history(symbol="AAPL", limit=10)
            assert len(history) == 2

    def test_configuration_validation_and_loading(self, temp_strategy_file):
        """Test configuration validation and loading."""

        # Test valid configuration
        orchestrator = create_multi_timeframe_decision_orchestrator(
            strategy_config_path=temp_strategy_file,
            timeframes=["1h", "4h", "1d"],
            mode="backtest",
        )

        assert isinstance(orchestrator, MultiTimeframeDecisionOrchestrator)

        # Test invalid configuration path
        with pytest.raises(Exception):
            create_multi_timeframe_decision_orchestrator(
                strategy_config_path="/nonexistent/path.yaml",
                timeframes=["1h", "4h", "1d"],
                mode="backtest",
            )

        # Test invalid timeframes
        with pytest.raises(Exception):
            create_multi_timeframe_decision_orchestrator(
                strategy_config_path=temp_strategy_file,
                timeframes=["invalid_tf"],
                mode="backtest",
            )

    @pytest.mark.asyncio
    async def test_concurrent_decision_generation(
        self, sample_data, temp_strategy_file
    ):
        """Test concurrent decision generation for multiple symbols."""

        with patch(
            "ktrdr.decision.multi_timeframe_orchestrator.DataManager"
        ) as mock_dm:
            mock_dm_instance = Mock()
            mock_dm_instance.get_data.return_value = sample_data["1h"]
            mock_dm.return_value = mock_dm_instance

            orchestrator = create_multi_timeframe_decision_orchestrator(
                strategy_config_path=temp_strategy_file,
                timeframes=["1h", "4h", "1d"],
                mode="backtest",
            )

            portfolio_state = {"total_value": 100000.0, "available_capital": 50000.0}
            symbols = ["AAPL", "MSFT", "GOOGL"]

            # Generate decisions concurrently
            tasks = []
            for symbol in symbols:
                task = asyncio.create_task(
                    asyncio.to_thread(
                        orchestrator.make_multi_timeframe_decision,
                        symbol=symbol,
                        timeframe_data=sample_data,
                        portfolio_state=portfolio_state,
                    )
                )
                tasks.append(task)

            decisions = await asyncio.gather(*tasks, return_exceptions=True)

            # All decisions should succeed
            assert len(decisions) == 3
            for decision in decisions:
                assert isinstance(decision, TradingDecision)
                assert decision.signal in [Signal.BUY, Signal.SELL, Signal.HOLD]
