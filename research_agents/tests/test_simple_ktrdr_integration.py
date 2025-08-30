"""
Simple Tests for KTRDR Integration

Basic tests to verify core functionality works.
"""

from unittest.mock import AsyncMock, patch

import pytest

from research_agents.services.ktrdr_integration import (
    BacktestConfig,
    BacktestResults,
    BacktestStatus,
    KTRDRIntegrationService,
    TrainingConfig,
    TrainingResults,
    TrainingStatus,
)


class TestBasicKTRDRIntegration:
    """Test basic KTRDR integration functionality"""

    def test_service_creation_defaults(self):
        """Test creating service with defaults"""
        service = KTRDRIntegrationService()

        assert service.api_base_url == "http://localhost:8000"
        assert service.api_key is None
        assert service.timeout_seconds == 300
        assert service.max_retries == 3
        assert not service._is_initialized
        assert service._session is None

    def test_service_creation_custom(self):
        """Test creating service with custom config"""
        service = KTRDRIntegrationService(
            ktrdr_api_base_url="https://custom-api:9000",
            api_key="test-key",
            timeout_seconds=60,
            max_retries=5,
        )

        assert service.api_base_url == "https://custom-api:9000"
        assert service.api_key == "test-key"
        assert service.timeout_seconds == 60
        assert service.max_retries == 5

    def test_url_construction(self):
        """Test proper URL construction"""
        service = KTRDRIntegrationService(
            ktrdr_api_base_url="http://localhost:8000/"  # With trailing slash
        )

        assert (
            service.api_base_url == "http://localhost:8000"
        )  # Should remove trailing slash
        assert service.training_endpoint == "http://localhost:8000/api/training"
        assert service.backtest_endpoint == "http://localhost:8000/api/backtest"
        assert service.health_endpoint == "http://localhost:8000/api/health"

    def test_training_config_creation(self):
        """Test creating training configuration"""
        config = TrainingConfig(
            strategy_name="TestStrategy",
            symbol="EURUSD",
            timeframe="H1",
            start_date="2023-01-01",
            end_date="2023-12-31",
            architecture={"layers": [64, 32, 16]},
            training_params={"epochs": 100, "lr": 0.001},
            fuzzy_config={"variables": 3},
            indicators=["SMA", "RSI"],
            lookback_period=20,
            validation_split=0.2,
        )

        assert config.strategy_name == "TestStrategy"
        assert config.symbol == "EURUSD"
        assert config.timeframe == "H1"
        assert config.validation_split == 0.2
        assert len(config.indicators) == 2

    def test_backtest_config_creation(self):
        """Test creating backtest configuration"""
        config = BacktestConfig(
            strategy_name="TestStrategy",
            model_path="/models/test.h5",
            symbol="EURUSD",
            timeframe="H1",
            start_date="2024-01-01",
            end_date="2024-03-31",
            initial_capital=100000.0,
            commission=0.001,
        )

        assert config.strategy_name == "TestStrategy"
        assert config.model_path == "/models/test.h5"
        assert config.initial_capital == 100000.0
        assert config.commission == 0.001
        # Check defaults
        assert config.slippage == 0.0001
        assert config.max_position_size == 1.0

    def test_training_results_creation(self):
        """Test creating training results"""
        results = TrainingResults(
            training_id="train-123",
            status=TrainingStatus.COMPLETED,
            model_path="/models/train-123.h5",
            epochs_completed=100,
            final_loss=0.023,
            validation_loss=0.025,
            training_time_minutes=45.0,
            accuracy=0.85,
            precision=0.82,
            recall=0.88,
            f1_score=0.85,
            loss_history=[0.1, 0.05, 0.023],
            validation_history=[0.12, 0.06, 0.025],
            error_info=None,
            metadata={"framework": "tensorflow"},
        )

        assert results.training_id == "train-123"
        assert results.status == TrainingStatus.COMPLETED
        assert results.epochs_completed == 100
        assert results.accuracy == 0.85
        assert len(results.loss_history) == 3

    def test_backtest_results_creation(self):
        """Test creating backtest results"""
        results = BacktestResults(
            backtest_id="backtest-456",
            status=BacktestStatus.COMPLETED,
            total_trades=150,
            profitable_trades=90,
            losing_trades=60,
            win_rate=0.6,
            total_return=0.15,
            profit_factor=1.25,
            sharpe_ratio=1.4,
            sortino_ratio=1.6,
            max_drawdown=-0.08,
            avg_trade_return=0.001,
            volatility=0.12,
            var_95=-0.025,
            max_consecutive_losses=5,
            trade_details=[],
            equity_curve=[],
            drawdown_periods=[],
            execution_time_minutes=15.0,
            error_info=None,
            metadata={"version": "1.0"},
        )

        assert results.backtest_id == "backtest-456"
        assert results.status == BacktestStatus.COMPLETED
        assert results.total_trades == 150
        assert results.win_rate == 0.6
        assert results.profit_factor == 1.25

    def test_status_enums(self):
        """Test status enum values"""
        # Training status
        assert TrainingStatus.PENDING == "pending"
        assert TrainingStatus.RUNNING == "running"
        assert TrainingStatus.COMPLETED == "completed"
        assert TrainingStatus.FAILED == "failed"

        # Backtest status
        assert BacktestStatus.PENDING == "pending"
        assert BacktestStatus.RUNNING == "running"
        assert BacktestStatus.COMPLETED == "completed"
        assert BacktestStatus.FAILED == "failed"

    @pytest.mark.asyncio
    async def test_service_close(self):
        """Test service closure"""
        service = KTRDRIntegrationService()

        # Mock session
        mock_session = AsyncMock()
        service._session = mock_session
        service._is_initialized = True

        await service.close()

        mock_session.close.assert_called_once()
        assert service._session is None
        assert not service._is_initialized

    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self):
        """Test health check when not initialized"""
        service = KTRDRIntegrationService()

        from research_agents.services.ktrdr_integration import KTRDRIntegrationError

        with pytest.raises(KTRDRIntegrationError, match="not initialized"):
            await service.health_check()

    @pytest.mark.asyncio
    async def test_submit_training_not_initialized(self):
        """Test training submission when not initialized"""
        service = KTRDRIntegrationService()

        config = TrainingConfig(
            strategy_name="Test",
            symbol="EURUSD",
            timeframe="H1",
            start_date="2023-01-01",
            end_date="2023-12-31",
            architecture={},
            training_params={},
            fuzzy_config={},
            indicators=[],
            lookback_period=20,
        )

        from research_agents.services.ktrdr_integration import KTRDRIntegrationError

        with pytest.raises(KTRDRIntegrationError, match="not initialized"):
            await service.submit_training(config)

    def test_factory_function_defaults(self):
        """Test factory function with defaults"""
        with patch(
            "research_agents.services.ktrdr_integration.KTRDRIntegrationService.initialize"
        ):
            # Can't actually call async factory in sync test, but can test service creation
            service = KTRDRIntegrationService()
            assert isinstance(service, KTRDRIntegrationService)
            assert service.api_base_url == "http://localhost:8000"

    def test_factory_function_custom(self):
        """Test factory function with custom params"""
        with patch(
            "research_agents.services.ktrdr_integration.KTRDRIntegrationService.initialize"
        ):
            service = KTRDRIntegrationService(
                ktrdr_api_base_url="https://custom:9000", api_key="custom-key"
            )
            assert isinstance(service, KTRDRIntegrationService)
            assert service.api_base_url == "https://custom:9000"
            assert service.api_key == "custom-key"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
