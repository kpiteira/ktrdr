"""
Tests for multi-timeframe decision orchestrator.
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from ktrdr.decision.multi_timeframe_orchestrator import (
    MultiTimeframeDecisionOrchestrator,
    MultiTimeframeDecisionContext,
    TimeframeDecisionContext,
    TimeframeDecision,
    MultiTimeframeConsensus,
    create_multi_timeframe_decision_orchestrator,
)
from ktrdr.decision.base import Signal, Position, TradingDecision


class TestMultiTimeframeDecisionOrchestrator:
    """Test multi-timeframe decision orchestrator."""

    @pytest.fixture
    def sample_strategy_config(self):
        """Create sample strategy configuration."""
        return {
            "name": "test_multi_timeframe_strategy",
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
                "modes": {
                    "backtest": {"confidence_threshold": 0.5},
                    "live": {"confidence_threshold": 0.8},
                },
            },
        }

    @pytest.fixture
    def temp_strategy_config_file(self, sample_strategy_config):
        """Create temporary strategy config file."""
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.dump(sample_strategy_config, temp_file)
        temp_file.close()
        yield temp_file.name
        Path(temp_file.name).unlink()

    @pytest.fixture
    def sample_timeframe_data(self):
        """Create sample timeframe data."""
        np.random.seed(42)

        # 1h data
        dates_1h = pd.date_range("2024-01-01", periods=100, freq="1h")
        data_1h = pd.DataFrame(
            {
                "open": np.random.uniform(95, 105, 100),
                "high": np.random.uniform(98, 108, 100),
                "low": np.random.uniform(92, 102, 100),
                "close": np.random.uniform(94, 106, 100),
                "volume": np.random.randint(1000, 10000, 100),
            },
            index=dates_1h,
        )

        # 4h data (aggregated)
        dates_4h = pd.date_range("2024-01-01", periods=25, freq="4h")
        data_4h = pd.DataFrame(
            {
                "open": np.random.uniform(95, 105, 25),
                "high": np.random.uniform(98, 108, 25),
                "low": np.random.uniform(92, 102, 25),
                "close": np.random.uniform(94, 106, 25),
                "volume": np.random.randint(4000, 40000, 25),
            },
            index=dates_4h,
        )

        # 1d data (aggregated)
        dates_1d = pd.date_range("2024-01-01", periods=5, freq="1d")
        data_1d = pd.DataFrame(
            {
                "open": np.random.uniform(95, 105, 5),
                "high": np.random.uniform(98, 108, 5),
                "low": np.random.uniform(92, 102, 5),
                "close": np.random.uniform(94, 106, 5),
                "volume": np.random.randint(20000, 200000, 5),
            },
            index=dates_1d,
        )

        return {"1h": data_1h, "4h": data_4h, "1d": data_1d}

    @pytest.fixture
    def sample_portfolio_state(self):
        """Create sample portfolio state."""
        return {"total_value": 100000.0, "available_capital": 50000.0, "positions": {}}

    @pytest.fixture
    def mock_orchestrator(self, temp_strategy_config_file):
        """Create orchestrator with mocked dependencies."""
        with patch(
            "ktrdr.decision.multi_timeframe_orchestrator.DecisionOrchestrator"
        ) as mock_single_tf:
            # Mock the single-timeframe orchestrators
            mock_instance = Mock()
            mock_instance.indicator_engine = Mock()
            mock_instance.fuzzy_engine = Mock()
            mock_instance.make_decision.return_value = TradingDecision(
                signal=Signal.BUY,
                confidence=0.8,
                timestamp=pd.Timestamp.now(tz="UTC"),
                reasoning={"test": "data"},
                current_position=Position.FLAT,
            )

            # Mock indicator engine
            mock_indicators_df = pd.DataFrame(
                {
                    "RSI_14": [30, 40, 50, 60, 70],
                    "MACD_12_26_9": [0.1, 0.2, 0.3, 0.4, 0.5],
                }
            )
            mock_instance.indicator_engine.apply.return_value = mock_indicators_df

            # Mock fuzzy engine
            mock_instance.fuzzy_engine.fuzzify.return_value = {
                "rsi_oversold": 0.3,
                "rsi_neutral": 0.5,
                "rsi_overbought": 0.2,
            }

            mock_single_tf.return_value = mock_instance

            orchestrator = MultiTimeframeDecisionOrchestrator(
                strategy_config_path=temp_strategy_config_file, mode="backtest"
            )

            yield orchestrator

    def test_orchestrator_initialization(self, temp_strategy_config_file):
        """Test orchestrator initialization."""
        with patch("ktrdr.decision.multi_timeframe_orchestrator.DecisionOrchestrator"):
            orchestrator = MultiTimeframeDecisionOrchestrator(
                strategy_config_path=temp_strategy_config_file,
                mode="backtest",
                timeframes=["1h", "4h"],
            )

            assert orchestrator.mode == "backtest"
            assert orchestrator.timeframes == ["1h", "4h"]
            assert orchestrator.primary_timeframe == "4h"  # From config
            assert len(orchestrator.timeframe_orchestrators) == 2
            assert "1h" in orchestrator.timeframe_orchestrators
            assert "4h" in orchestrator.timeframe_orchestrators

    def test_timeframe_extraction_from_config(self, temp_strategy_config_file):
        """Test extraction of timeframes from configuration."""
        with patch("ktrdr.decision.multi_timeframe_orchestrator.DecisionOrchestrator"):
            orchestrator = MultiTimeframeDecisionOrchestrator(
                strategy_config_path=temp_strategy_config_file, mode="backtest"
            )

            expected_timeframes = ["1h", "4h", "1d"]
            assert set(orchestrator.timeframes) == set(expected_timeframes)

    def test_primary_timeframe_determination(self, temp_strategy_config_file):
        """Test primary timeframe determination."""
        with patch("ktrdr.decision.multi_timeframe_orchestrator.DecisionOrchestrator"):
            orchestrator = MultiTimeframeDecisionOrchestrator(
                strategy_config_path=temp_strategy_config_file, mode="backtest"
            )

            assert orchestrator.primary_timeframe == "4h"  # Marked as primary in config

    def test_timeframe_weights_calculation(self, temp_strategy_config_file):
        """Test timeframe weights calculation."""
        with patch("ktrdr.decision.multi_timeframe_orchestrator.DecisionOrchestrator"):
            orchestrator = MultiTimeframeDecisionOrchestrator(
                strategy_config_path=temp_strategy_config_file, mode="backtest"
            )

            weights = orchestrator.timeframe_weights
            assert abs(weights["1h"] - 0.5) < 0.01
            assert abs(weights["4h"] - 0.3) < 0.01
            assert abs(weights["1d"] - 0.2) < 0.01
            assert abs(sum(weights.values()) - 1.0) < 0.001

    def test_data_quality_calculation(self, mock_orchestrator, sample_timeframe_data):
        """Test data quality calculation."""
        data = sample_timeframe_data["1h"]
        quality_score = mock_orchestrator._calculate_data_quality(data)

        assert 0.0 <= quality_score <= 1.0
        assert quality_score > 0.9  # Should be high for complete data

    def test_freshness_score_calculation(
        self, mock_orchestrator, sample_timeframe_data
    ):
        """Test data freshness score calculation."""
        data = sample_timeframe_data["1h"]
        freshness_score = mock_orchestrator._calculate_freshness_score(data, "1h")

        assert 0.0 <= freshness_score <= 1.0
        # Freshness will be low since sample data is from 2024-01-01

    def test_timeframe_context_preparation(
        self, mock_orchestrator, sample_timeframe_data
    ):
        """Test timeframe context preparation."""
        data = sample_timeframe_data["1h"]

        context = mock_orchestrator._prepare_timeframe_context("1h", data)

        assert isinstance(context, TimeframeDecisionContext)
        assert context.timeframe == "1h"
        assert not context.current_bar.empty
        assert len(context.recent_bars) > 0
        assert isinstance(context.indicators, dict)
        assert isinstance(context.fuzzy_memberships, dict)
        assert 0.0 <= context.data_quality_score <= 1.0
        assert 0.0 <= context.freshness_score <= 1.0

    def test_multi_timeframe_context_preparation(
        self, mock_orchestrator, sample_timeframe_data, sample_portfolio_state
    ):
        """Test multi-timeframe context preparation."""
        context = mock_orchestrator._prepare_multi_timeframe_context(
            symbol="AAPL",
            timeframe_data=sample_timeframe_data,
            portfolio_state=sample_portfolio_state,
        )

        assert isinstance(context, MultiTimeframeDecisionContext)
        assert context.symbol == "AAPL"
        assert len(context.timeframe_contexts) == 3
        assert "1h" in context.timeframe_contexts
        assert "4h" in context.timeframe_contexts
        assert "1d" in context.timeframe_contexts
        assert context.primary_timeframe == "4h"
        assert context.portfolio_value == 100000.0

    def test_weighted_majority_consensus(self, mock_orchestrator):
        """Test weighted majority consensus building."""
        # Create timeframe decisions
        timeframe_decisions = {
            "1h": TimeframeDecision(
                timeframe="1h",
                signal=Signal.BUY,
                confidence=0.8,
                weight=0.5,
                reasoning={},
                data_quality=0.9,
            ),
            "4h": TimeframeDecision(
                timeframe="4h",
                signal=Signal.BUY,
                confidence=0.7,
                weight=0.3,
                reasoning={},
                data_quality=0.8,
            ),
            "1d": TimeframeDecision(
                timeframe="1d",
                signal=Signal.HOLD,
                confidence=0.6,
                weight=0.2,
                reasoning={},
                data_quality=0.7,
            ),
        }

        context = MultiTimeframeDecisionContext(
            symbol="AAPL",
            timestamp=pd.Timestamp.now(),
            timeframe_contexts={},
            current_position=Position.FLAT,
            position_entry_price=None,
            position_holding_period=None,
            unrealized_pnl=None,
            portfolio_value=100000,
            available_capital=50000,
            recent_decisions=[],
            last_signal_time=None,
            primary_timeframe="4h",
            timeframe_weights={"1h": 0.5, "4h": 0.3, "1d": 0.2},
        )

        consensus = mock_orchestrator._weighted_majority_consensus(
            timeframe_decisions, context
        )

        assert isinstance(consensus, MultiTimeframeConsensus)
        assert (
            consensus.final_signal == Signal.BUY
        )  # Should win with higher weighted votes
        assert consensus.consensus_confidence > 0
        assert consensus.consensus_method == "weighted_majority"

    def test_hierarchical_consensus(self, mock_orchestrator):
        """Test hierarchical consensus building."""
        timeframe_decisions = {
            "1h": TimeframeDecision(
                timeframe="1h",
                signal=Signal.SELL,
                confidence=0.9,
                weight=0.5,
                reasoning={},
                data_quality=0.9,
            ),
            "4h": TimeframeDecision(  # Primary timeframe
                timeframe="4h",
                signal=Signal.BUY,
                confidence=0.8,  # High confidence
                weight=0.3,
                reasoning={},
                data_quality=0.8,
            ),
            "1d": TimeframeDecision(
                timeframe="1d",
                signal=Signal.HOLD,
                confidence=0.6,
                weight=0.2,
                reasoning={},
                data_quality=0.7,
            ),
        }

        context = MultiTimeframeDecisionContext(
            symbol="AAPL",
            timestamp=pd.Timestamp.now(),
            timeframe_contexts={},
            current_position=Position.FLAT,
            position_entry_price=None,
            position_holding_period=None,
            unrealized_pnl=None,
            portfolio_value=100000,
            available_capital=50000,
            recent_decisions=[],
            last_signal_time=None,
            primary_timeframe="4h",
            timeframe_weights={"1h": 0.5, "4h": 0.3, "1d": 0.2},
        )

        consensus = mock_orchestrator._hierarchical_consensus(
            timeframe_decisions, context
        )

        assert consensus.final_signal == Signal.BUY  # Primary timeframe wins
        assert consensus.consensus_method == "hierarchical"
        assert consensus.primary_timeframe_influence == 1.0

    def test_simple_consensus(self, mock_orchestrator):
        """Test simple consensus building."""
        timeframe_decisions = {
            "1h": TimeframeDecision(
                timeframe="1h",
                signal=Signal.BUY,
                confidence=0.8,
                weight=0.5,
                reasoning={},
                data_quality=0.9,
            ),
            "4h": TimeframeDecision(
                timeframe="4h",
                signal=Signal.BUY,
                confidence=0.7,
                weight=0.3,
                reasoning={},
                data_quality=0.8,
            ),
            "1d": TimeframeDecision(
                timeframe="1d",
                signal=Signal.SELL,
                confidence=0.6,
                weight=0.2,
                reasoning={},
                data_quality=0.7,
            ),
        }

        context = MultiTimeframeDecisionContext(
            symbol="AAPL",
            timestamp=pd.Timestamp.now(),
            timeframe_contexts={},
            current_position=Position.FLAT,
            position_entry_price=None,
            position_holding_period=None,
            unrealized_pnl=None,
            portfolio_value=100000,
            available_capital=50000,
            recent_decisions=[],
            last_signal_time=None,
            primary_timeframe="4h",
            timeframe_weights={"1h": 0.5, "4h": 0.3, "1d": 0.2},
        )

        consensus = mock_orchestrator._simple_consensus(timeframe_decisions, context)

        assert consensus.final_signal == Signal.BUY  # 2 vs 1 votes
        assert consensus.consensus_method == "simple_consensus"

    def test_multi_timeframe_decision_generation(
        self, mock_orchestrator, sample_timeframe_data, sample_portfolio_state
    ):
        """Test complete multi-timeframe decision generation."""
        decision = mock_orchestrator.make_multi_timeframe_decision(
            symbol="AAPL",
            timeframe_data=sample_timeframe_data,
            portfolio_state=sample_portfolio_state,
        )

        assert isinstance(decision, TradingDecision)
        assert decision.signal in [Signal.BUY, Signal.HOLD, Signal.SELL]
        assert 0.0 <= decision.confidence <= 1.0
        assert "consensus" in decision.reasoning
        assert "multi_timeframe_metadata" in decision.reasoning

    def test_orchestrator_logic_overrides(self, mock_orchestrator):
        """Test orchestrator logic overrides."""
        # Test low agreement override
        consensus = MultiTimeframeConsensus(
            final_signal=Signal.BUY,
            consensus_confidence=0.8,
            timeframe_decisions={},
            agreement_score=0.3,  # Low agreement
            conflicting_timeframes=["1h", "4h"],
            primary_timeframe_influence=0.5,
            consensus_method="weighted_majority",
            reasoning={},
        )

        context = MultiTimeframeDecisionContext(
            symbol="AAPL",
            timestamp=pd.Timestamp.now(),
            timeframe_contexts={},
            current_position=Position.FLAT,
            position_entry_price=None,
            position_holding_period=None,
            unrealized_pnl=None,
            portfolio_value=100000,
            available_capital=50000,
            recent_decisions=[],
            last_signal_time=None,
            primary_timeframe="4h",
            timeframe_weights={"1h": 0.5, "4h": 0.3, "1d": 0.2},
        )

        decision = mock_orchestrator._apply_multi_timeframe_logic(consensus, context)

        # Should be overridden to HOLD due to low agreement
        assert decision.signal == Signal.HOLD
        assert "orchestrator_overrides" in decision.reasoning

    def test_position_state_management(self, mock_orchestrator):
        """Test position state management."""
        symbol = "AAPL"

        # Test getting position state
        position_state = mock_orchestrator.get_position_state(symbol)
        assert position_state.symbol == symbol
        assert position_state.position == Position.FLAT

        # Test that state is persisted
        position_state2 = mock_orchestrator.get_position_state(symbol)
        assert position_state is position_state2

    def test_decision_history_tracking(self, mock_orchestrator):
        """Test decision history tracking."""
        initial_count = len(mock_orchestrator.get_decision_history())

        # Create a mock decision and update state
        decision = TradingDecision(
            signal=Signal.BUY,
            confidence=0.8,
            timestamp=pd.Timestamp.now(tz="UTC"),
            reasoning={"symbol": "AAPL"},
            current_position=Position.FLAT,
        )

        mock_orchestrator.decision_history.append(decision)

        history = mock_orchestrator.get_decision_history()
        assert len(history) == initial_count + 1

        # Test symbol filtering
        aapl_history = mock_orchestrator.get_decision_history(symbol="AAPL")
        assert len(aapl_history) >= 1
        assert all(d.reasoning.get("symbol") == "AAPL" for d in aapl_history)

    def test_timeframe_analysis(self, mock_orchestrator):
        """Test timeframe analysis generation."""
        symbol = "AAPL"

        analysis = mock_orchestrator.get_timeframe_analysis(symbol)

        assert analysis["symbol"] == symbol
        assert "timeframes" in analysis
        assert "primary_timeframe" in analysis
        assert "timeframe_weights" in analysis
        assert analysis["primary_timeframe"] == "4h"

    def test_state_reset(self, mock_orchestrator):
        """Test state reset functionality."""
        symbol = "AAPL"

        # Add some state
        mock_orchestrator.get_position_state(symbol)
        mock_orchestrator.decision_history.append(
            TradingDecision(
                signal=Signal.BUY,
                confidence=0.8,
                timestamp=pd.Timestamp.now(tz="UTC"),
                reasoning={"symbol": symbol},
                current_position=Position.FLAT,
            )
        )

        # Reset specific symbol
        mock_orchestrator.reset_state(symbol)

        # Position state should be reset
        position_state = mock_orchestrator.get_position_state(symbol)
        assert position_state.position == Position.FLAT

        # Reset all
        mock_orchestrator.reset_state()
        assert len(mock_orchestrator.decision_history) == 0

    def test_factory_function(self, temp_strategy_config_file):
        """Test factory function."""
        with patch("ktrdr.decision.multi_timeframe_orchestrator.DecisionOrchestrator"):
            orchestrator = create_multi_timeframe_decision_orchestrator(
                strategy_config_path=temp_strategy_config_file,
                mode="backtest",
                timeframes=["1h", "4h"],
            )

            assert isinstance(orchestrator, MultiTimeframeDecisionOrchestrator)
            assert orchestrator.mode == "backtest"
            assert orchestrator.timeframes == ["1h", "4h"]

    def test_empty_timeframe_data_handling(self, mock_orchestrator):
        """Test handling of empty timeframe data."""
        empty_data = pd.DataFrame()

        context = mock_orchestrator._prepare_timeframe_context("1h", empty_data)

        assert context.timeframe == "1h"
        assert context.current_bar.empty
        assert context.recent_bars.empty
        assert context.indicators == {}
        assert context.fuzzy_memberships == {}
        assert context.data_quality_score == 0.0
        assert context.freshness_score == 0.0

    def test_consensus_with_no_decisions(self, mock_orchestrator):
        """Test consensus building with no timeframe decisions."""
        context = MultiTimeframeDecisionContext(
            symbol="AAPL",
            timestamp=pd.Timestamp.now(),
            timeframe_contexts={},
            current_position=Position.FLAT,
            position_entry_price=None,
            position_holding_period=None,
            unrealized_pnl=None,
            portfolio_value=100000,
            available_capital=50000,
            recent_decisions=[],
            last_signal_time=None,
            primary_timeframe="4h",
            timeframe_weights={"1h": 0.5, "4h": 0.3, "1d": 0.2},
        )

        consensus = mock_orchestrator._build_multi_timeframe_consensus({}, context)

        assert consensus.final_signal == Signal.HOLD
        assert consensus.consensus_confidence == 0.0
        assert consensus.consensus_method == "none"

    def test_mode_specific_logic(self, temp_strategy_config_file):
        """Test mode-specific logic application."""
        with patch("ktrdr.decision.multi_timeframe_orchestrator.DecisionOrchestrator"):
            # Test live mode with higher confidence requirement
            orchestrator = MultiTimeframeDecisionOrchestrator(
                strategy_config_path=temp_strategy_config_file, mode="live"
            )

            consensus = MultiTimeframeConsensus(
                final_signal=Signal.BUY,
                consensus_confidence=0.6,  # Below live threshold (0.8)
                timeframe_decisions={},
                agreement_score=0.9,
                conflicting_timeframes=[],
                primary_timeframe_influence=0.5,
                consensus_method="weighted_majority",
                reasoning={},
            )

            context = MultiTimeframeDecisionContext(
                symbol="AAPL",
                timestamp=pd.Timestamp.now(),
                timeframe_contexts={},
                current_position=Position.FLAT,
                position_entry_price=None,
                position_holding_period=None,
                unrealized_pnl=None,
                portfolio_value=100000,
                available_capital=50000,
                recent_decisions=[],
                last_signal_time=None,
                primary_timeframe="4h",
                timeframe_weights={"1h": 0.5, "4h": 0.3, "1d": 0.2},
            )

            decision = orchestrator._apply_multi_timeframe_logic(consensus, context)

            # Should be overridden to HOLD due to low confidence in live mode
            assert decision.signal == Signal.HOLD
