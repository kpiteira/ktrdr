"""Unit tests for threading timeframes through API/service/remote (M1, Task 1.2).

Tests that the full timeframes list flows from:
  API endpoint → BacktestingService → worker request payload
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestBacktestingServiceTimeframes:
    """Tests for timeframes flowing through BacktestingService to worker."""

    @pytest.fixture
    def mock_worker_registry(self):
        worker = MagicMock()
        worker.worker_id = "test-worker-1"
        worker.endpoint_url = "http://localhost:5003"

        registry = MagicMock()
        registry.select_worker.return_value = worker
        registry.list_workers.return_value = [worker]
        return registry

    @pytest.fixture
    def service(self, mock_worker_registry):
        from ktrdr.backtesting.backtesting_service import BacktestingService

        svc = BacktestingService(worker_registry=mock_worker_registry)
        return svc

    @pytest.mark.asyncio
    async def test_run_backtest_includes_timeframes_in_payload(self, service) -> None:
        """Service includes timeframes in worker request payload."""
        captured_payload = {}

        async def mock_post(url, json, timeout):
            captured_payload.update(json)
            resp = MagicMock()
            resp.json.return_value = {"operation_id": "op-123"}
            resp.raise_for_status = MagicMock()
            return resp

        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch.object(
                service.operations_service,
                "generate_operation_id",
                return_value="op-backend-1",
            ):
                with patch.object(service.operations_service, "register_remote_proxy"):
                    await service.run_backtest(
                        symbol="EURUSD",
                        timeframe="1h",
                        strategy_config_path="strategies/test.yaml",
                        model_path="/tmp/model",
                        start_date=datetime(2024, 1, 1),
                        end_date=datetime(2024, 2, 1),
                        timeframes=["1h", "1d"],
                    )

        assert "timeframes" in captured_payload
        assert captured_payload["timeframes"] == ["1h", "1d"]

    @pytest.mark.asyncio
    async def test_run_backtest_default_empty_timeframes(self, service) -> None:
        """Service sends empty timeframes list when none provided."""
        captured_payload = {}

        async def mock_post(url, json, timeout):
            captured_payload.update(json)
            resp = MagicMock()
            resp.json.return_value = {"operation_id": "op-123"}
            resp.raise_for_status = MagicMock()
            return resp

        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch.object(
                service.operations_service,
                "generate_operation_id",
                return_value="op-backend-1",
            ):
                with patch.object(service.operations_service, "register_remote_proxy"):
                    await service.run_backtest(
                        symbol="EURUSD",
                        timeframe="1h",
                        strategy_config_path="strategies/test.yaml",
                        model_path="/tmp/model",
                        start_date=datetime(2024, 1, 1),
                        end_date=datetime(2024, 2, 1),
                    )

        assert captured_payload.get("timeframes") == []


class TestAPIEndpointTimeframes:
    """Tests for API endpoint extracting and forwarding timeframes."""

    @pytest.mark.asyncio
    async def test_endpoint_passes_timeframes_from_strategy(self) -> None:
        """API endpoint extracts timeframes from strategy and passes to service."""
        from ktrdr.api.endpoints.backtesting import start_backtest
        from ktrdr.api.models.backtesting import BacktestStartRequest

        request = BacktestStartRequest(
            strategy_name="multi_tf_test",
            symbol="EURUSD",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-02-01",
            model_path="/tmp/model",
        )

        mock_service = AsyncMock()
        mock_service.run_backtest.return_value = {
            "success": True,
            "operation_id": "op-1",
            "status": "started",
            "message": "ok",
            "symbol": "EURUSD",
            "timeframe": "1h",
            "mode": "distributed",
        }

        with patch(
            "ktrdr.api.endpoints.backtesting.extract_symbols_timeframes_from_strategy",
            return_value=(["EURUSD"], ["1h", "1d"]),
        ):
            await start_backtest(request=request, service=mock_service)

        call_kwargs = mock_service.run_backtest.call_args.kwargs
        assert "timeframes" in call_kwargs
        assert call_kwargs["timeframes"] == ["1h", "1d"]

    @pytest.mark.asyncio
    async def test_endpoint_single_tf_strategy(self) -> None:
        """API endpoint passes single-element timeframes list for single-TF strategy."""
        from ktrdr.api.endpoints.backtesting import start_backtest
        from ktrdr.api.models.backtesting import BacktestStartRequest

        request = BacktestStartRequest(
            strategy_name="single_tf_test",
            symbol="EURUSD",
            timeframe="1h",
            start_date="2024-01-01",
            end_date="2024-02-01",
            model_path="/tmp/model",
        )

        mock_service = AsyncMock()
        mock_service.run_backtest.return_value = {
            "success": True,
            "operation_id": "op-1",
            "status": "started",
            "message": "ok",
            "symbol": "EURUSD",
            "timeframe": "1h",
            "mode": "distributed",
        }

        with patch(
            "ktrdr.api.endpoints.backtesting.extract_symbols_timeframes_from_strategy",
            return_value=(["EURUSD"], ["1h"]),
        ):
            await start_backtest(request=request, service=mock_service)

        call_kwargs = mock_service.run_backtest.call_args.kwargs
        assert call_kwargs["timeframes"] == ["1h"]
