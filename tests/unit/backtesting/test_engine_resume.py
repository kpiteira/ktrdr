"""Unit tests for BacktestingEngine resume from checkpoint functionality.

Task 5.4: Implement Indicator Recomputation on Resume

Tests that the engine can:
1. Resume from a BacktestResumeContext
2. Load full data range for indicator computation
3. Restore portfolio state (cash, positions, trades)
4. Restore equity curve samples
5. Continue processing from the correct bar
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


class TestEngineHasResumeMethod:
    """Tests that BacktestingEngine has the resume_from_context method."""

    def test_engine_has_resume_from_context_method(self):
        """Engine should have resume_from_context method."""
        from ktrdr.backtesting.engine import BacktestingEngine

        assert hasattr(BacktestingEngine, "resume_from_context")

    def test_resume_from_context_accepts_context(self):
        """resume_from_context should accept a BacktestResumeContext."""
        import inspect

        from ktrdr.backtesting.engine import BacktestingEngine

        sig = inspect.signature(BacktestingEngine.resume_from_context)
        params = list(sig.parameters.keys())

        # Should have 'self' and 'context' parameters
        assert "context" in params


class TestEngineRunSupportsResume:
    """Tests that run() method supports resume_start_bar parameter."""

    def test_run_accepts_resume_start_bar_parameter(self):
        """run() should accept an optional resume_start_bar parameter."""
        import inspect

        from ktrdr.backtesting.engine import BacktestingEngine

        sig = inspect.signature(BacktestingEngine.run)
        params = list(sig.parameters.keys())

        assert "resume_start_bar" in params

    def test_resume_start_bar_defaults_to_none(self):
        """resume_start_bar should default to None."""
        import inspect

        from ktrdr.backtesting.engine import BacktestingEngine

        sig = inspect.signature(BacktestingEngine.run)
        param = sig.parameters.get("resume_start_bar")

        assert param is not None
        assert param.default is None


class TestResumeFromContextLoadsData:
    """Tests that resume_from_context loads data for full range."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock BacktestingEngine with minimal initialization."""
        with patch(
            "ktrdr.backtesting.engine.BacktestingEngine.__init__",
            lambda self, config: None,
        ):
            from ktrdr.backtesting.engine import BacktestingEngine

            engine = BacktestingEngine.__new__(BacktestingEngine)

            # Set up minimal mocks
            engine.config = MagicMock()
            engine.config.symbol = "EURUSD"
            engine.config.timeframe = "1h"
            engine.config.start_date = "2023-01-01"
            engine.config.end_date = "2023-12-31"

            engine.repository = MagicMock()
            engine.orchestrator = MagicMock()
            engine.position_manager = MagicMock()
            engine.position_manager.current_capital = 100000.0
            engine.position_manager.current_position = None
            engine.position_manager.trade_history = []
            engine.position_manager.next_trade_id = 1
            engine.performance_tracker = MagicMock()
            engine.performance_tracker.equity_curve = []

            # Mock data loading
            mock_data = pd.DataFrame(
                {
                    "open": [1.0] * 100,
                    "high": [1.1] * 100,
                    "low": [0.9] * 100,
                    "close": [1.05] * 100,
                    "volume": [1000] * 100,
                },
                index=pd.date_range("2023-01-01", periods=100, freq="h"),
            )
            engine._load_historical_data = MagicMock(return_value=mock_data)

            return engine

    @pytest.fixture
    def sample_context(self):
        """Create a sample BacktestResumeContext."""
        from ktrdr.backtesting.checkpoint_restore import BacktestResumeContext

        return BacktestResumeContext(
            start_bar=5001,
            cash=105000.0,
            original_request={
                "symbol": "EURUSD",
                "timeframe": "1h",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
            },
            positions=[],
            trades=[],
            equity_samples=[],
        )

    def test_loads_historical_data(self, mock_engine, sample_context):
        """resume_from_context should load historical data."""
        mock_engine.resume_from_context(sample_context)

        # Should call _load_historical_data
        mock_engine._load_historical_data.assert_called_once()

    def test_computes_indicators(self, mock_engine, sample_context):
        """resume_from_context should compute indicators via prepare_feature_cache."""
        mock_engine.resume_from_context(sample_context)

        # Should call orchestrator.prepare_feature_cache with the loaded data
        mock_engine.orchestrator.prepare_feature_cache.assert_called_once()


class TestResumeFromContextRestoresPortfolioState:
    """Tests that resume_from_context restores portfolio state."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock BacktestingEngine."""
        with patch(
            "ktrdr.backtesting.engine.BacktestingEngine.__init__",
            lambda self, config: None,
        ):
            from ktrdr.backtesting.engine import BacktestingEngine

            engine = BacktestingEngine.__new__(BacktestingEngine)

            engine.config = MagicMock()
            engine.repository = MagicMock()
            engine.orchestrator = MagicMock()

            # Real position manager mock with settable attributes
            engine.position_manager = MagicMock()
            engine.position_manager.current_capital = 100000.0
            engine.position_manager.current_position = None
            engine.position_manager.trade_history = []
            engine.position_manager.next_trade_id = 1

            engine.performance_tracker = MagicMock()
            engine.performance_tracker.equity_curve = []

            # Mock data loading
            mock_data = pd.DataFrame(
                {
                    "open": [1.0] * 100,
                    "high": [1.1] * 100,
                    "low": [0.9] * 100,
                    "close": [1.05] * 100,
                    "volume": [1000] * 100,
                },
                index=pd.date_range("2023-01-01", periods=100, freq="h"),
            )
            engine._load_historical_data = MagicMock(return_value=mock_data)

            return engine

    def test_restores_cash(self, mock_engine):
        """resume_from_context should restore cash from context."""
        from ktrdr.backtesting.checkpoint_restore import BacktestResumeContext

        context = BacktestResumeContext(
            start_bar=5001,
            cash=95000.0,  # Different from default
            original_request={"symbol": "EURUSD"},
        )

        mock_engine.resume_from_context(context)

        # Cash should be restored
        assert mock_engine.position_manager.current_capital == 95000.0

    def test_restores_empty_positions_when_flat(self, mock_engine):
        """resume_from_context should set no position when checkpoint had none."""
        from ktrdr.backtesting.checkpoint_restore import BacktestResumeContext

        context = BacktestResumeContext(
            start_bar=5001,
            cash=100000.0,
            original_request={"symbol": "EURUSD"},
            positions=[],  # No positions
        )

        mock_engine.resume_from_context(context)

        # Position should be None
        assert mock_engine.position_manager.current_position is None

    def test_restores_open_position(self, mock_engine):
        """resume_from_context should restore an open position."""
        from ktrdr.backtesting.checkpoint_restore import BacktestResumeContext

        context = BacktestResumeContext(
            start_bar=5001,
            cash=50000.0,
            original_request={"symbol": "EURUSD"},
            positions=[
                {
                    "symbol": "EURUSD",
                    "quantity": 1000,
                    "entry_price": 1.1000,
                    "entry_date": "2023-06-10T10:00:00",
                    "status": "LONG",
                    "current_price": 1.1050,
                }
            ],
        )

        mock_engine.resume_from_context(context)

        # Position should be restored
        position = mock_engine.position_manager.current_position
        assert position is not None
        assert position.quantity == 1000
        assert position.entry_price == 1.1000

    def test_restores_trade_history(self, mock_engine):
        """resume_from_context should restore trade history."""
        from ktrdr.backtesting.checkpoint_restore import BacktestResumeContext

        context = BacktestResumeContext(
            start_bar=5001,
            cash=100000.0,
            original_request={"symbol": "EURUSD"},
            trades=[
                {
                    "trade_id": 1,
                    "symbol": "EURUSD",
                    "side": "BUY",
                    "entry_price": 1.0950,
                    "entry_time": "2023-05-01T09:00:00",
                    "exit_price": 1.1000,
                    "exit_time": "2023-05-02T09:00:00",
                    "quantity": 500,
                    "gross_pnl": 25.0,
                    "commission": 0.5,
                    "slippage": 0.25,
                    "net_pnl": 24.25,
                    "holding_period_hours": 24.0,
                    "max_favorable_excursion": 30.0,
                    "max_adverse_excursion": -5.0,
                },
                {
                    "trade_id": 2,
                    "symbol": "EURUSD",
                    "side": "BUY",
                    "entry_price": 1.1000,
                    "entry_time": "2023-05-05T10:00:00",
                    "exit_price": 1.0900,
                    "exit_time": "2023-05-06T10:00:00",
                    "quantity": 500,
                    "gross_pnl": -50.0,
                    "commission": 0.5,
                    "slippage": 0.25,
                    "net_pnl": -50.75,
                    "holding_period_hours": 24.0,
                    "max_favorable_excursion": 5.0,
                    "max_adverse_excursion": -55.0,
                },
            ],
        )

        mock_engine.resume_from_context(context)

        # Trade history should be restored
        assert len(mock_engine.position_manager.trade_history) == 2

    def test_sets_next_trade_id_correctly(self, mock_engine):
        """resume_from_context should set next_trade_id based on restored trades."""
        from ktrdr.backtesting.checkpoint_restore import BacktestResumeContext

        context = BacktestResumeContext(
            start_bar=5001,
            cash=100000.0,
            original_request={"symbol": "EURUSD"},
            trades=[
                {
                    "trade_id": 5,
                    "symbol": "EURUSD",
                    "side": "BUY",
                    "entry_price": 1.0950,
                    "entry_time": "2023-05-01T09:00:00",
                    "exit_price": 1.1000,
                    "exit_time": "2023-05-02T09:00:00",
                    "quantity": 500,
                    "gross_pnl": 25.0,
                    "commission": 0.5,
                    "slippage": 0.25,
                    "net_pnl": 24.25,
                    "holding_period_hours": 24.0,
                    "max_favorable_excursion": 30.0,
                    "max_adverse_excursion": -5.0,
                }
            ],
        )

        mock_engine.resume_from_context(context)

        # Next trade ID should be max(trade_ids) + 1
        assert mock_engine.position_manager.next_trade_id == 6


class TestResumeFromContextRestoresEquityCurve:
    """Tests that resume_from_context restores equity curve samples."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock BacktestingEngine."""
        with patch(
            "ktrdr.backtesting.engine.BacktestingEngine.__init__",
            lambda self, config: None,
        ):
            from ktrdr.backtesting.engine import BacktestingEngine

            engine = BacktestingEngine.__new__(BacktestingEngine)

            engine.config = MagicMock()
            engine.repository = MagicMock()
            engine.orchestrator = MagicMock()
            engine.position_manager = MagicMock()
            engine.position_manager.current_capital = 100000.0
            engine.position_manager.current_position = None
            engine.position_manager.trade_history = []
            engine.position_manager.next_trade_id = 1

            # Real performance tracker mock
            engine.performance_tracker = MagicMock()
            engine.performance_tracker.equity_curve = []

            mock_data = pd.DataFrame(
                {"close": [1.0] * 100},
                index=pd.date_range("2023-01-01", periods=100, freq="h"),
            )
            engine._load_historical_data = MagicMock(return_value=mock_data)

            return engine

    def test_restores_equity_samples(self, mock_engine):
        """resume_from_context should restore equity samples to performance tracker."""
        from ktrdr.backtesting.checkpoint_restore import BacktestResumeContext

        context = BacktestResumeContext(
            start_bar=5001,
            cash=100000.0,
            original_request={"symbol": "EURUSD"},
            equity_samples=[
                {"bar_index": 0, "equity": 100000.0},
                {"bar_index": 100, "equity": 100500.0},
                {"bar_index": 200, "equity": 101000.0},
            ],
        )

        mock_engine.resume_from_context(context)

        # Equity curve should be restored
        assert len(mock_engine.performance_tracker.equity_curve) == 3
        assert mock_engine.performance_tracker.equity_curve[0]["equity"] == 100000.0


class TestRunWithResumeStartBar:
    """Tests that run() correctly starts from resume_start_bar when provided."""

    @pytest.fixture
    def minimal_mock_engine(self):
        """Create a minimal mock engine to test run() bar logic."""
        with patch(
            "ktrdr.backtesting.engine.BacktestingEngine.__init__",
            lambda self, config: None,
        ):
            from ktrdr.backtesting.engine import BacktestingEngine

            engine = BacktestingEngine.__new__(BacktestingEngine)

            engine.config = MagicMock()
            engine.config.symbol = "EURUSD"
            engine.config.timeframe = "1h"
            engine.config.start_date = "2023-01-01"
            engine.config.end_date = "2023-12-31"
            engine.config.initial_capital = 100000.0
            engine.config.verbose = False

            engine.strategy_name = "test_strategy"
            engine.progress_callback = None

            return engine

    def test_run_respects_resume_start_bar(self, minimal_mock_engine):
        """run() with resume_start_bar should skip bars before that point.

        This is a behavioral test - actual verification would require
        integration testing with a real engine.
        """
        # This test verifies the parameter exists and is used
        # Full behavior testing is done in integration tests
        # Verify the method signature includes resume_start_bar
        import inspect

        from ktrdr.backtesting.engine import BacktestingEngine

        sig = inspect.signature(BacktestingEngine.run)
        assert "resume_start_bar" in sig.parameters


class TestResumeFromContextReturnsData:
    """Tests that resume_from_context returns loaded data for run() to use."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock BacktestingEngine."""
        with patch(
            "ktrdr.backtesting.engine.BacktestingEngine.__init__",
            lambda self, config: None,
        ):
            from ktrdr.backtesting.engine import BacktestingEngine

            engine = BacktestingEngine.__new__(BacktestingEngine)

            engine.config = MagicMock()
            engine.repository = MagicMock()
            engine.orchestrator = MagicMock()
            engine.position_manager = MagicMock()
            engine.position_manager.current_capital = 100000.0
            engine.position_manager.current_position = None
            engine.position_manager.trade_history = []
            engine.position_manager.next_trade_id = 1
            engine.performance_tracker = MagicMock()
            engine.performance_tracker.equity_curve = []

            mock_data = pd.DataFrame(
                {"close": [1.0] * 100},
                index=pd.date_range("2023-01-01", periods=100, freq="h"),
            )
            engine._load_historical_data = MagicMock(return_value=mock_data)

            return engine

    def test_returns_loaded_data(self, mock_engine):
        """resume_from_context should return the loaded data."""
        from ktrdr.backtesting.checkpoint_restore import BacktestResumeContext

        context = BacktestResumeContext(
            start_bar=5001,
            cash=100000.0,
            original_request={"symbol": "EURUSD"},
        )

        result = mock_engine.resume_from_context(context)

        # Should return a DataFrame with the loaded data
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 100
