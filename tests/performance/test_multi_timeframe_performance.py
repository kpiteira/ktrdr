"""
Performance and scalability tests for multi-timeframe system.

This module tests the performance characteristics and scalability limits
of the multi-timeframe decision system.
"""

import pytest
import asyncio
import time
import tempfile
import yaml
import pandas as pd
import psutil
import threading
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor, as_completed

from ktrdr.decision.multi_timeframe_orchestrator import (
    MultiTimeframeDecisionOrchestrator,
    create_multi_timeframe_decision_orchestrator,
)
from ktrdr.decision.base import Signal, Position, TradingDecision


class TestMultiTimeframePerformance:
    """Performance and scalability tests for multi-timeframe system."""

    @pytest.fixture
    def large_dataset(self):
        """Create large dataset for performance testing."""
        # Create 1 year of hourly data
        dates = pd.date_range(
            start=datetime.now() - timedelta(days=365), end=datetime.now(), freq="1h"
        )

        base_price = 150
        data = {}

        # Generate realistic price movements
        for tf, freq_hours in [("1h", 1), ("4h", 4), ("1d", 24)]:
            tf_dates = dates[::freq_hours]
            n_points = len(tf_dates)

            # Generate random walk with trend
            price_changes = pd.Series(range(n_points)).apply(
                lambda x: 0.1 * (0.5 - hash(x) % 100 / 100) + 0.001 * x
            )
            prices = base_price + price_changes.cumsum()

            data[tf] = pd.DataFrame(
                {
                    "timestamp": tf_dates,
                    "open": prices,
                    "high": prices * 1.02,
                    "low": prices * 0.98,
                    "close": prices * 1.001,
                    "volume": 1000000 * (1 + freq_hours),
                }
            ).set_index("timestamp")

        return data

    @pytest.fixture
    def performance_strategy_config(self):
        """Strategy config optimized for performance testing."""
        return {
            "name": "performance_test_strategy",
            "version": "2.0",
            "timeframe_configs": {
                "1h": {"weight": 0.5, "primary": False, "lookback_periods": 20},
                "4h": {"weight": 0.3, "primary": True, "lookback_periods": 15},
                "1d": {"weight": 0.2, "primary": False, "lookback_periods": 10},
            },
            "indicators": [
                {"name": "rsi", "period": 14, "timeframes": ["1h", "4h", "1d"]},
                {"name": "sma", "period": 20, "timeframes": ["1h", "4h"]},
            ],
            "fuzzy_sets": {
                "rsi": {
                    "oversold": {"type": "triangular", "parameters": [0, 30, 50]},
                    "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
                    "overbought": {"type": "triangular", "parameters": [50, 70, 100]},
                }
            },
            "fuzzy_rules": [
                {
                    "name": "buy_rule",
                    "conditions": [
                        {"indicator": "rsi", "set": "oversold", "timeframe": "4h"}
                    ],
                    "action": {"signal": "BUY", "confidence": 0.8},
                }
            ],
            "model": {
                "type": "mlp",
                "input_features": ["rsi"],
                "hidden_layers": [32, 16],
                "activation": "tanh",
                "learning_rate": 0.001,
                "epochs": 50,
            },
            "multi_timeframe": {
                "consensus_method": "weighted_majority",
                "min_agreement_score": 0.6,
            },
        }

    @pytest.fixture
    def temp_perf_strategy_file(self, performance_strategy_config):
        """Create temporary performance strategy file."""
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yaml.dump(performance_strategy_config, temp_file)
        temp_file.close()
        yield temp_file.name
        Path(temp_file.name).unlink()

    def test_single_decision_latency(self, large_dataset, temp_perf_strategy_file):
        """Test latency of single decision generation."""

        with patch(
            "ktrdr.decision.multi_timeframe_orchestrator.DataManager"
        ) as mock_dm:
            mock_dm_instance = Mock()
            mock_dm_instance.get_data.return_value = large_dataset["1h"]
            mock_dm.return_value = mock_dm_instance

            orchestrator = create_multi_timeframe_decision_orchestrator(
                strategy_config_path=temp_perf_strategy_file,
                timeframes=["1h", "4h", "1d"],
                mode="backtest",
            )

            portfolio_state = {"total_value": 100000.0, "available_capital": 50000.0}

            # Warm up
            orchestrator.make_multi_timeframe_decision(
                symbol="AAPL",
                timeframe_data=large_dataset,
                portfolio_state=portfolio_state,
            )

            # Measure decision latency
            start_time = time.perf_counter()
            decision = orchestrator.make_multi_timeframe_decision(
                symbol="AAPL",
                timeframe_data=large_dataset,
                portfolio_state=portfolio_state,
            )
            end_time = time.perf_counter()

            latency = end_time - start_time

            assert isinstance(decision, TradingDecision)
            assert latency < 1.0  # Should complete within 1 second
            print(f"Single decision latency: {latency:.3f} seconds")

    def test_throughput_multiple_symbols(self, large_dataset, temp_perf_strategy_file):
        """Test throughput with multiple symbols."""

        with patch(
            "ktrdr.decision.multi_timeframe_orchestrator.DataManager"
        ) as mock_dm:
            mock_dm_instance = Mock()
            mock_dm_instance.get_data.return_value = large_dataset["1h"]
            mock_dm.return_value = mock_dm_instance

            orchestrator = create_multi_timeframe_decision_orchestrator(
                strategy_config_path=temp_perf_strategy_file,
                timeframes=["1h", "4h", "1d"],
                mode="backtest",
            )

            portfolio_state = {"total_value": 100000.0, "available_capital": 50000.0}
            symbols = [f"SYM{i:03d}" for i in range(50)]  # 50 symbols

            # Measure throughput
            start_time = time.perf_counter()
            decisions = []

            for symbol in symbols:
                decision = orchestrator.make_multi_timeframe_decision(
                    symbol=symbol,
                    timeframe_data=large_dataset,
                    portfolio_state=portfolio_state,
                )
                decisions.append(decision)

            end_time = time.perf_counter()
            total_time = end_time - start_time
            throughput = len(symbols) / total_time

            assert len(decisions) == 50
            assert all(isinstance(d, TradingDecision) for d in decisions)
            assert (
                throughput > 3
            )  # Should process at least 3 symbols per second (CI-friendly threshold for complex multi-timeframe decisions)
            print(f"Throughput: {throughput:.2f} decisions/second")

    def test_concurrent_decision_performance(
        self, large_dataset, temp_perf_strategy_file
    ):
        """Test performance with concurrent decision generation."""

        with patch(
            "ktrdr.decision.multi_timeframe_orchestrator.DataManager"
        ) as mock_dm:
            mock_dm_instance = Mock()
            mock_dm_instance.get_data.return_value = large_dataset["1h"]
            mock_dm.return_value = mock_dm_instance

            orchestrator = create_multi_timeframe_decision_orchestrator(
                strategy_config_path=temp_perf_strategy_file,
                timeframes=["1h", "4h", "1d"],
                mode="backtest",
            )

            portfolio_state = {"total_value": 100000.0, "available_capital": 50000.0}
            symbols = [f"SYM{i:03d}" for i in range(20)]

            def make_decision(symbol):
                return orchestrator.make_multi_timeframe_decision(
                    symbol=symbol,
                    timeframe_data=large_dataset,
                    portfolio_state=portfolio_state,
                )

            # Test concurrent execution
            start_time = time.perf_counter()

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(make_decision, symbol) for symbol in symbols]
                decisions = [future.result() for future in as_completed(futures)]

            end_time = time.perf_counter()
            total_time = end_time - start_time
            throughput = len(symbols) / total_time

            assert len(decisions) == 20
            assert all(isinstance(d, TradingDecision) for d in decisions)
            print(f"Concurrent throughput: {throughput:.2f} decisions/second")

    def test_memory_usage_scaling(self, large_dataset, temp_perf_strategy_file):
        """Test memory usage as dataset size increases."""

        with patch(
            "ktrdr.decision.multi_timeframe_orchestrator.DataManager"
        ) as mock_dm:
            mock_dm_instance = Mock()
            mock_dm_instance.get_data.return_value = large_dataset["1h"]
            mock_dm.return_value = mock_dm_instance

            orchestrator = create_multi_timeframe_decision_orchestrator(
                strategy_config_path=temp_perf_strategy_file,
                timeframes=["1h", "4h", "1d"],
                mode="backtest",
            )

            portfolio_state = {"total_value": 100000.0, "available_capital": 50000.0}

            # Measure memory usage before
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Generate many decisions to test memory scaling
            for i in range(100):
                decision = orchestrator.make_multi_timeframe_decision(
                    symbol=f"SYM{i:03d}",
                    timeframe_data=large_dataset,
                    portfolio_state=portfolio_state,
                )
                assert isinstance(decision, TradingDecision)

            # Measure memory usage after
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory

            # Memory increase should be reasonable (less than 100MB for 100 decisions)
            assert memory_increase < 100
            print(f"Memory increase: {memory_increase:.2f} MB for 100 decisions")

    def test_timeframe_scaling_performance(
        self, large_dataset, temp_perf_strategy_file
    ):
        """Test performance scaling with different numbers of timeframes."""

        with patch(
            "ktrdr.decision.multi_timeframe_orchestrator.DataManager"
        ) as mock_dm:
            mock_dm_instance = Mock()
            mock_dm_instance.get_data.return_value = large_dataset["1h"]
            mock_dm.return_value = mock_dm_instance

            portfolio_state = {"total_value": 100000.0, "available_capital": 50000.0}
            timeframe_sets = [["1h"], ["1h", "4h"], ["1h", "4h", "1d"]]

            results = {}

            for timeframes in timeframe_sets:
                orchestrator = create_multi_timeframe_decision_orchestrator(
                    strategy_config_path=temp_perf_strategy_file,
                    timeframes=timeframes,
                    mode="backtest",
                )

                # Warm up
                orchestrator.make_multi_timeframe_decision(
                    symbol="AAPL",
                    timeframe_data=large_dataset,
                    portfolio_state=portfolio_state,
                )

                # Measure performance
                start_time = time.perf_counter()
                for i in range(10):
                    decision = orchestrator.make_multi_timeframe_decision(
                        symbol=f"SYM{i}",
                        timeframe_data=large_dataset,
                        portfolio_state=portfolio_state,
                    )
                    assert isinstance(decision, TradingDecision)

                end_time = time.perf_counter()
                avg_time = (end_time - start_time) / 10
                results[len(timeframes)] = avg_time

            # Performance should scale reasonably with timeframes
            assert results[1] < results[3]  # More timeframes should take more time
            assert results[3] < results[1] * 5  # But not exponentially more

            for tf_count, avg_time in results.items():
                print(f"{tf_count} timeframes: {avg_time:.3f}s average")

    def test_large_data_volume_performance(self, temp_perf_strategy_file):
        """Test performance with very large data volumes."""

        # Create extra large dataset (2 years of minute data for 1h timeframe)
        dates = pd.date_range(
            start=datetime.now() - timedelta(days=730), end=datetime.now(), freq="1min"
        )

        large_data = {
            "1h": pd.DataFrame(
                {
                    "timestamp": dates[::60],  # Every hour
                    "open": 150 + pd.Series(range(len(dates[::60]))) * 0.001,
                    "high": 152 + pd.Series(range(len(dates[::60]))) * 0.001,
                    "low": 148 + pd.Series(range(len(dates[::60]))) * 0.001,
                    "close": 151 + pd.Series(range(len(dates[::60]))) * 0.001,
                    "volume": 1000000,
                }
            ).set_index("timestamp")
        }

        with patch(
            "ktrdr.decision.multi_timeframe_orchestrator.DataManager"
        ) as mock_dm:
            mock_dm_instance = Mock()
            mock_dm_instance.get_data.return_value = large_data["1h"]
            mock_dm.return_value = mock_dm_instance

            orchestrator = create_multi_timeframe_decision_orchestrator(
                strategy_config_path=temp_perf_strategy_file,
                timeframes=["1h"],
                mode="backtest",
            )

            portfolio_state = {"total_value": 100000.0, "available_capital": 50000.0}

            # Test with large data volume
            start_time = time.perf_counter()
            decision = orchestrator.make_multi_timeframe_decision(
                symbol="AAPL",
                timeframe_data=large_data,
                portfolio_state=portfolio_state,
            )
            end_time = time.perf_counter()

            processing_time = end_time - start_time
            data_points = len(large_data["1h"])

            assert isinstance(decision, TradingDecision)
            assert processing_time < 5.0  # Should handle large data within 5 seconds
            print(
                f"Large data processing: {data_points} points in {processing_time:.3f}s"
            )

    @pytest.mark.asyncio
    async def test_async_performance_characteristics(
        self, large_dataset, temp_perf_strategy_file
    ):
        """Test performance characteristics in async environments."""

        with patch(
            "ktrdr.decision.multi_timeframe_orchestrator.DataManager"
        ) as mock_dm:
            mock_dm_instance = Mock()
            mock_dm_instance.get_data.return_value = large_dataset["1h"]
            mock_dm.return_value = mock_dm_instance

            orchestrator = create_multi_timeframe_decision_orchestrator(
                strategy_config_path=temp_perf_strategy_file,
                timeframes=["1h", "4h", "1d"],
                mode="backtest",
            )

            portfolio_state = {"total_value": 100000.0, "available_capital": 50000.0}

            async def async_decision(symbol):
                # Simulate async decision making
                return await asyncio.to_thread(
                    orchestrator.make_multi_timeframe_decision,
                    symbol=symbol,
                    timeframe_data=large_dataset,
                    portfolio_state=portfolio_state,
                )

            # Test async throughput
            start_time = time.perf_counter()
            symbols = [f"SYM{i:03d}" for i in range(10)]

            tasks = [async_decision(symbol) for symbol in symbols]
            decisions = await asyncio.gather(*tasks)

            end_time = time.perf_counter()
            total_time = end_time - start_time

            assert len(decisions) == 10
            assert all(isinstance(d, TradingDecision) for d in decisions)

            throughput = len(symbols) / total_time
            print(f"Async throughput: {throughput:.2f} decisions/second")
