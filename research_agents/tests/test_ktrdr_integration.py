"""
Unit Tests for KTRDR API Integration Service

Tests the KTRDR API integration layer following the implementation plan's
quality-first approach with comprehensive error handling and API communication.
"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from research_agents.services.ktrdr_integration import (
    BacktestConfig,
    BacktestError,
    BacktestResults,
    BacktestStatus,
    KTRDRIntegrationError,
    KTRDRIntegrationService,
    TrainingConfig,
    TrainingError,
    TrainingResults,
    TrainingStatus,
)
from research_agents.services.ktrdr_integration import (
    ConnectionError as KTRDRConnectionError,
)


@pytest.fixture
def integration_service():
    """Create KTRDR integration service instance"""
    return KTRDRIntegrationService(
        ktrdr_api_base_url="http://test-api:8000",
        api_key="test-api-key",
        timeout_seconds=30,
        max_retries=2,
    )


@pytest.fixture
def sample_training_config():
    """Create sample training configuration"""
    return TrainingConfig(
        strategy_name="TestStrategy",
        symbol="EURUSD",
        timeframe="H1",
        start_date="2023-01-01",
        end_date="2023-12-31",
        architecture={"layers": [64, 32, 16], "activation": "relu"},
        training_params={"epochs": 100, "batch_size": 32, "learning_rate": 0.001},
        fuzzy_config={"input_vars": 3, "rules": 27},
        indicators=["SMA", "RSI", "MACD"],
        lookback_period=20,
        validation_split=0.2,
    )


@pytest.fixture
def sample_backtest_config():
    """Create sample backtest configuration"""
    return BacktestConfig(
        strategy_name="TestStrategy",
        model_path="/models/test_model.h5",
        symbol="EURUSD",
        timeframe="H1",
        start_date="2024-01-01",
        end_date="2024-03-31",
        initial_capital=100000.0,
        commission=0.001,
        slippage=0.0001,
        max_position_size=1.0,
        stop_loss=0.02,
        take_profit=0.04,
    )


@pytest.fixture
def mock_session():
    """Create mock aiohttp ClientSession"""
    session = AsyncMock(spec=aiohttp.ClientSession)
    session.close = AsyncMock()
    return session


def create_mock_response(
    status_code: int, json_data: dict = None, text_data: str = None
):
    """Helper function to create proper async response mocks"""
    mock_response = AsyncMock()
    mock_response.status = status_code
    if json_data is not None:
        mock_response.json = AsyncMock(return_value=json_data)
    if text_data is not None:
        mock_response.text = AsyncMock(return_value=text_data)
    return mock_response


class MockAsyncContextManager:
    """Mock async context manager for aiohttp responses"""

    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


def create_mock_context_manager(response):
    """Helper function to create proper async context manager for aiohttp responses"""
    return MockAsyncContextManager(response)


def setup_mock_session_with_response(
    mock_session,
    method: str,
    status_code: int,
    json_data: dict = None,
    text_data: str = None,
):
    """Helper to set up mock session with proper async context manager for HTTP methods"""
    mock_response = create_mock_response(status_code, json_data, text_data)
    mock_context_manager = create_mock_context_manager(mock_response)

    # Set up the HTTP method mock (get, post, put, delete)
    method_mock = MagicMock(return_value=mock_context_manager)
    setattr(mock_session, method, method_mock)
    return mock_response


class TestServiceInitialization:
    """Test service initialization and configuration"""

    def test_initialization_with_defaults(self):
        """Test service initialization with default parameters"""
        service = KTRDRIntegrationService()

        assert service.api_base_url == "http://localhost:8000"
        assert service.api_key is None
        assert service.timeout_seconds == 300
        assert service.max_retries == 3
        assert service.training_endpoint == "http://localhost:8000/api/training"
        assert service.backtest_endpoint == "http://localhost:8000/api/backtest"
        assert service.health_endpoint == "http://localhost:8000/api/health"
        assert not service._is_initialized
        assert service._session is None

    def test_initialization_with_custom_params(self):
        """Test service initialization with custom parameters"""
        service = KTRDRIntegrationService(
            ktrdr_api_base_url="https://custom-api:9000/",  # With trailing slash
            api_key="custom-key",
            timeout_seconds=60,
            max_retries=5,
        )

        assert (
            service.api_base_url == "https://custom-api:9000"
        )  # Trailing slash removed
        assert service.api_key == "custom-key"
        assert service.timeout_seconds == 60
        assert service.max_retries == 5
        assert service.training_endpoint == "https://custom-api:9000/api/training"

    @pytest.mark.asyncio
    async def test_initialize_success(self, integration_service):
        """Test successful service initialization"""
        # Mock the session directly
        mock_session = AsyncMock()

        # Set up mock session with health check response
        setup_mock_session_with_response(
            mock_session, "get", 200, {"status": "healthy"}
        )

        # Patch the ClientSession creation
        with patch("aiohttp.ClientSession", return_value=mock_session):
            await integration_service.initialize()

            # Verify initialization
            assert integration_service._is_initialized
            assert integration_service._session is not None

            # Verify health check was called
            mock_session.get.assert_called_once_with(
                integration_service.health_endpoint
            )

    @pytest.mark.asyncio
    async def test_initialize_health_check_failure(self, integration_service):
        """Test initialization failure due to health check"""
        # Mock the session directly
        mock_session = AsyncMock()

        # Set up mock session with failed health check response
        setup_mock_session_with_response(mock_session, "get", 500)

        # Patch the ClientSession creation
        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(KTRDRConnectionError):
                await integration_service.initialize()

            assert not integration_service._is_initialized

    @pytest.mark.asyncio
    async def test_initialize_network_error(self, integration_service):
        """Test initialization failure due to network error"""
        # Mock the session directly
        mock_session = AsyncMock()

        # Mock network error on get method
        mock_session.get = MagicMock(side_effect=aiohttp.ClientError("Network error"))

        # Patch the ClientSession creation
        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(KTRDRConnectionError) as exc_info:
                await integration_service.initialize()

            assert "Failed to connect to KTRDR API" in str(exc_info.value)
            assert not integration_service._is_initialized

    @pytest.mark.asyncio
    async def test_double_initialization(self, integration_service):
        """Test that double initialization is handled gracefully"""
        mock_session = AsyncMock()

        # Set up mock session with health check response
        setup_mock_session_with_response(
            mock_session, "get", 200, {"status": "healthy"}
        )

        with patch(
            "aiohttp.ClientSession", return_value=mock_session
        ) as mock_session_class:
            # Initialize twice
            await integration_service.initialize()
            await integration_service.initialize()  # Should not create new session

            # Session should only be created once
            assert mock_session_class.call_count == 1
            assert integration_service._is_initialized

    @pytest.mark.asyncio
    async def test_close_service(self, integration_service):
        """Test service closure"""
        # Mock session
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        await integration_service.close()

        # Verify closure
        mock_session.close.assert_called_once()
        assert integration_service._session is None
        assert not integration_service._is_initialized


class TestHealthCheck:
    """Test health check functionality"""

    @pytest.mark.asyncio
    async def test_health_check_success(self, integration_service):
        """Test successful health check"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        # Set up mock session with successful response using helper
        setup_mock_session_with_response(
            mock_session, "get", 200, {"status": "healthy", "version": "1.0"}
        )

        health = await integration_service.health_check()

        # Verify response
        assert health["status"] == "healthy"
        assert health["ktrdr_api"]["status"] == "healthy"
        assert health["integration_service"] == "operational"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_response(self, integration_service):
        """Test health check with unhealthy API response"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        # Set up mock session with error response
        setup_mock_session_with_response(mock_session, "get", 503)

        health = await integration_service.health_check()

        # Verify response
        assert health["status"] == "unhealthy"
        assert "API returned status 503" in health["error"]
        assert health["integration_service"] == "degraded"

    @pytest.mark.asyncio
    async def test_health_check_network_error(self, integration_service):
        """Test health check with network error"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        # Mock network error
        mock_session.get = MagicMock(
            side_effect=aiohttp.ClientError("Connection failed")
        )

        health = await integration_service.health_check()

        # Verify response
        assert health["status"] == "unhealthy"
        assert "Connection failed" in health["error"]
        assert health["integration_service"] == "error"

    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self, integration_service):
        """Test health check when service not initialized"""
        with pytest.raises(KTRDRIntegrationError) as exc_info:
            await integration_service.health_check()

        assert "not initialized" in str(exc_info.value)


class TestTrainingOperations:
    """Test training-related operations"""

    @pytest.mark.asyncio
    async def test_submit_training_success(
        self, integration_service, sample_training_config
    ):
        """Test successful training submission"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.json = AsyncMock(return_value={"training_id": "train-123"})
        mock_session.post = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        training_id = await integration_service.submit_training(sample_training_config)

        # Verify result
        assert training_id == "train-123"

        # Verify API call
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args[0][0] == "http://test-api:8000/api/training/submit"

        # Verify payload
        payload = call_args[1]["json"]
        assert payload["strategy_name"] == sample_training_config.strategy_name
        assert payload["symbol"] == sample_training_config.symbol
        assert payload["timeframe"] == sample_training_config.timeframe
        assert payload["architecture"] == sample_training_config.architecture

    @pytest.mark.asyncio
    async def test_submit_training_validation_error(
        self, integration_service, sample_training_config
    ):
        """Test training submission with validation error"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        # Mock validation error response
        mock_response = AsyncMock()
        mock_response.status = 422
        mock_response.json = AsyncMock(return_value={"detail": "Invalid configuration"})
        mock_session.post = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        with pytest.raises(TrainingError) as exc_info:
            await integration_service.submit_training(sample_training_config)

        assert "Validation error" in str(exc_info.value)
        assert "Invalid configuration" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_training_bad_request(
        self, integration_service, sample_training_config
    ):
        """Test training submission with bad request"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        # Mock bad request response
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.json = AsyncMock(
            return_value={"detail": "Missing required field"}
        )
        mock_session.post = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        with pytest.raises(TrainingError) as exc_info:
            await integration_service.submit_training(sample_training_config)

        assert "Invalid training configuration" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_training_server_error(
        self, integration_service, sample_training_config
    ):
        """Test training submission with server error"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        # Mock server error response
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal server error")
        mock_session.post = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        with pytest.raises(TrainingError) as exc_info:
            await integration_service.submit_training(sample_training_config)

        assert "Training submission failed with status 500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_training_network_error(
        self, integration_service, sample_training_config
    ):
        """Test training submission with network error"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        # Mock network error
        mock_session.post = MagicMock(
            side_effect=aiohttp.ClientError("Connection timeout")
        )

        with pytest.raises(KTRDRConnectionError) as exc_info:
            await integration_service.submit_training(sample_training_config)

        assert "Failed to connect to KTRDR API" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_submit_training_not_initialized(
        self, integration_service, sample_training_config
    ):
        """Test training submission when service not initialized"""
        with pytest.raises(KTRDRIntegrationError) as exc_info:
            await integration_service.submit_training(sample_training_config)

        assert "not initialized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_training_status_success(self, integration_service):
        """Test successful training status retrieval"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        training_id = "train-123"

        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "status": "completed",
                "model_path": "/models/train-123.h5",
                "epochs_completed": 100,
                "final_loss": 0.023,
                "validation_loss": 0.025,
                "training_time_minutes": 45.5,
                "accuracy": 0.85,
                "precision": 0.82,
                "recall": 0.88,
                "f1_score": 0.85,
                "loss_history": [0.1, 0.05, 0.023],
                "validation_history": [0.12, 0.06, 0.025],
                "metadata": {"framework": "tensorflow"},
            }
        )
        mock_session.get = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        result = await integration_service.get_training_status(training_id)

        # Verify result
        assert isinstance(result, TrainingResults)
        assert result.training_id == training_id
        assert result.status == TrainingStatus.COMPLETED
        assert result.model_path == "/models/train-123.h5"
        assert result.epochs_completed == 100
        assert result.final_loss == 0.023
        assert result.accuracy == 0.85
        assert len(result.loss_history) == 3

        # Verify API call
        mock_session.get.assert_called_once_with(
            f"http://test-api:8000/api/training/{training_id}/status"
        )

    @pytest.mark.asyncio
    async def test_get_training_status_not_found(self, integration_service):
        """Test training status retrieval for non-existent training"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        training_id = "nonexistent-123"

        # Mock not found response
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_session.get = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        with pytest.raises(TrainingError) as exc_info:
            await integration_service.get_training_status(training_id)

        assert f"Training job {training_id} not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wait_for_training_completion_success(self, integration_service):
        """Test waiting for training completion"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        training_id = "train-123"

        # Mock responses: running, running, completed
        responses = [
            {"status": "running", "epochs_completed": 50, "final_loss": float("inf")},
            {"status": "running", "epochs_completed": 75, "final_loss": float("inf")},
            {"status": "completed", "epochs_completed": 100, "final_loss": 0.023},
        ]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_session.get = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        # Set up side effect for multiple calls
        mock_response.json.side_effect = responses

        # Mock sleep to speed up test
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await integration_service.wait_for_training_completion(
                training_id, poll_interval_seconds=1, max_wait_minutes=1
            )

        # Verify result
        assert result.status == TrainingStatus.COMPLETED
        assert result.epochs_completed == 100
        assert mock_session.get.call_count == 3  # Three status checks

    @pytest.mark.asyncio
    async def test_wait_for_training_completion_failure(self, integration_service):
        """Test waiting for training that fails"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        training_id = "train-failed"

        # Mock failed response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "status": "failed",
                "error_info": {"message": "Training diverged"},
            }
        )
        mock_session.get = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        with pytest.raises(TrainingError) as exc_info:
            await integration_service.wait_for_training_completion(training_id)

        assert f"Training {training_id} failed" in str(exc_info.value)
        assert "Training diverged" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wait_for_training_completion_timeout(self, integration_service):
        """Test waiting for training with timeout"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        training_id = "train-slow"

        # Mock always running response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"status": "running", "epochs_completed": 50}
        )
        mock_session.get = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        # Mock time to simulate timeout
        with patch(
            "research_agents.services.ktrdr_integration.datetime"
        ) as mock_datetime:
            # Set up time progression to exceed max_wait
            start_time = datetime.now(timezone.utc)
            times = [
                start_time,  # Initial time
                start_time,  # First check
                start_time.replace(
                    minute=start_time.minute + 2
                ),  # Exceed 1 minute limit
            ]
            mock_datetime.now.side_effect = times

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(TrainingError) as exc_info:
                    await integration_service.wait_for_training_completion(
                        training_id, poll_interval_seconds=1, max_wait_minutes=1
                    )

        assert "exceeded maximum wait time" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cancel_training_success(self, integration_service):
        """Test successful training cancellation"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        training_id = "train-123"

        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_session.post = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        await integration_service.cancel_training(training_id)

        # Verify API call
        mock_session.post.assert_called_once_with(
            f"http://test-api:8000/api/training/{training_id}/cancel"
        )

    @pytest.mark.asyncio
    async def test_cancel_training_not_found(self, integration_service):
        """Test cancelling non-existent training"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        training_id = "nonexistent-123"

        # Mock not found response
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_session.post = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        with pytest.raises(TrainingError) as exc_info:
            await integration_service.cancel_training(training_id)

        assert f"Training job {training_id} not found" in str(exc_info.value)


class TestBacktestingOperations:
    """Test backtesting-related operations"""

    @pytest.mark.asyncio
    async def test_submit_backtest_success(
        self, integration_service, sample_backtest_config
    ):
        """Test successful backtest submission"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.json = AsyncMock(return_value={"backtest_id": "backtest-456"})
        mock_session.post = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        backtest_id = await integration_service.submit_backtest(sample_backtest_config)

        # Verify result
        assert backtest_id == "backtest-456"

        # Verify API call
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args[0][0] == "http://test-api:8000/api/backtest/submit"

        # Verify payload
        payload = call_args[1]["json"]
        assert payload["strategy_name"] == sample_backtest_config.strategy_name
        assert payload["model_path"] == sample_backtest_config.model_path
        assert payload["symbol"] == sample_backtest_config.symbol
        assert payload["initial_capital"] == sample_backtest_config.initial_capital

    @pytest.mark.asyncio
    async def test_submit_backtest_bad_request(
        self, integration_service, sample_backtest_config
    ):
        """Test backtest submission with bad request"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        # Mock bad request response
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.json = AsyncMock(return_value={"detail": "Invalid model path"})
        mock_session.post = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        with pytest.raises(BacktestError) as exc_info:
            await integration_service.submit_backtest(sample_backtest_config)

        assert "Invalid backtest configuration" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_backtest_results_success(self, integration_service):
        """Test successful backtest results retrieval"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        backtest_id = "backtest-456"

        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "status": "completed",
                "total_trades": 150,
                "profitable_trades": 90,
                "losing_trades": 60,
                "win_rate": 0.6,
                "total_return": 0.15,
                "profit_factor": 1.25,
                "sharpe_ratio": 1.4,
                "sortino_ratio": 1.8,
                "max_drawdown": -0.08,
                "avg_trade_return": 0.001,
                "volatility": 0.12,
                "var_95": -0.02,
                "max_consecutive_losses": 5,
                "trade_details": [
                    {"entry": "2024-01-01", "exit": "2024-01-02", "pnl": 0.005}
                ],
                "equity_curve": [{"date": "2024-01-01", "equity": 100000}],
                "drawdown_periods": [
                    {"start": "2024-02-01", "end": "2024-02-05", "drawdown": -0.03}
                ],
                "execution_time_minutes": 15.5,
                "metadata": {"version": "1.0"},
            }
        )
        mock_session.get = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        result = await integration_service.get_backtest_results(backtest_id)

        # Verify result
        assert isinstance(result, BacktestResults)
        assert result.backtest_id == backtest_id
        assert result.status == BacktestStatus.COMPLETED
        assert result.total_trades == 150
        assert result.profitable_trades == 90
        assert result.win_rate == 0.6
        assert result.total_return == 0.15
        assert result.profit_factor == 1.25
        assert result.sharpe_ratio == 1.4
        assert len(result.trade_details) == 1

        # Verify API call
        mock_session.get.assert_called_once_with(
            f"http://test-api:8000/api/backtest/{backtest_id}/results"
        )

    @pytest.mark.asyncio
    async def test_get_backtest_results_not_found(self, integration_service):
        """Test backtest results retrieval for non-existent backtest"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        backtest_id = "nonexistent-456"

        # Mock not found response
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_session.get = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        with pytest.raises(BacktestError) as exc_info:
            await integration_service.get_backtest_results(backtest_id)

        assert f"Backtest job {backtest_id} not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wait_for_backtest_completion_success(self, integration_service):
        """Test waiting for backtest completion"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        backtest_id = "backtest-456"

        # Mock responses: running, completed
        responses = [
            {"status": "running", "total_trades": 0},
            {"status": "completed", "total_trades": 150, "total_return": 0.15},
        ]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_session.get = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        # Set up side effect for multiple calls
        mock_response.json.side_effect = responses

        # Mock sleep to speed up test
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await integration_service.wait_for_backtest_completion(
                backtest_id, poll_interval_seconds=1, max_wait_minutes=1
            )

        # Verify result
        assert result.status == BacktestStatus.COMPLETED
        assert result.total_trades == 150
        assert mock_session.get.call_count == 2  # Two status checks

    @pytest.mark.asyncio
    async def test_wait_for_backtest_completion_failure(self, integration_service):
        """Test waiting for backtest that fails"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        backtest_id = "backtest-failed"

        # Mock failed response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "status": "failed",
                "error_info": {"message": "Model file not found"},
            }
        )
        mock_session.get = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        with pytest.raises(BacktestError) as exc_info:
            await integration_service.wait_for_backtest_completion(backtest_id)

        assert f"Backtest {backtest_id} failed" in str(exc_info.value)
        assert "Model file not found" in str(exc_info.value)


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge case scenarios"""

    @pytest.mark.asyncio
    async def test_service_operations_not_initialized(
        self, integration_service, sample_training_config, sample_backtest_config
    ):
        """Test that all operations require initialization"""
        operations = [
            (integration_service.submit_training, sample_training_config),
            (integration_service.get_training_status, "train-123"),
            (integration_service.wait_for_training_completion, "train-123"),
            (integration_service.cancel_training, "train-123"),
            (integration_service.submit_backtest, sample_backtest_config),
            (integration_service.get_backtest_results, "backtest-456"),
            (integration_service.wait_for_backtest_completion, "backtest-456"),
        ]

        for operation, arg in operations:
            with pytest.raises(KTRDRIntegrationError) as exc_info:
                await operation(arg)
            assert "not initialized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_unexpected_api_errors(
        self, integration_service, sample_training_config
    ):
        """Test handling of unexpected API errors"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        # Mock unexpected error
        mock_session.post.side_effect = Exception("Unexpected error")

        with pytest.raises(TrainingError) as exc_info:
            await integration_service.submit_training(sample_training_config)

        assert "Training submission failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_malformed_api_responses(self, integration_service):
        """Test handling of malformed API responses"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        training_id = "train-123"

        # Mock response with missing fields
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "status": "completed"
                # Missing required fields like model_path, epochs_completed, etc.
            }
        )
        mock_session.get = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        result = await integration_service.get_training_status(training_id)

        # Should handle missing fields gracefully with defaults
        assert result.training_id == training_id
        assert result.status == TrainingStatus.COMPLETED
        assert result.model_path is None
        assert result.epochs_completed == 0
        assert result.final_loss == float("inf")

    @pytest.mark.asyncio
    async def test_json_decode_errors(self, integration_service):
        """Test handling of JSON decode errors"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        # Mock response with invalid JSON
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)
        mock_response.text = AsyncMock(return_value="Invalid response")
        mock_session.get = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        with pytest.raises(TrainingError):
            await integration_service.get_training_status("train-123")


class TestPerformanceAndConfiguration:
    """Test performance characteristics and configuration"""

    def test_endpoint_url_construction(self):
        """Test proper URL construction for different base URLs"""
        test_cases = [
            ("http://localhost:8000", "http://localhost:8000/api/training"),
            ("http://localhost:8000/", "http://localhost:8000/api/training"),
            ("https://api.example.com", "https://api.example.com/api/training"),
            (
                "https://api.example.com/ktrdr",
                "https://api.example.com/ktrdr/api/training",
            ),
        ]

        for base_url, expected_training_endpoint in test_cases:
            service = KTRDRIntegrationService(ktrdr_api_base_url=base_url)
            assert service.training_endpoint == expected_training_endpoint

    def test_configuration_validation(self):
        """Test configuration parameter validation"""
        # Test timeout validation
        service = KTRDRIntegrationService(timeout_seconds=0)
        assert service.timeout_seconds == 0  # Should accept 0

        # Test retry validation
        service = KTRDRIntegrationService(max_retries=0)
        assert service.max_retries == 0  # Should accept 0

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, integration_service):
        """Test handling of concurrent API requests"""
        mock_session = AsyncMock()
        integration_service._session = mock_session
        integration_service._is_initialized = True

        # Mock responses for concurrent requests
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "running"})
        mock_session.get = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        # Make concurrent requests
        tasks = [
            integration_service.get_training_status(f"train-{i}") for i in range(5)
        ]

        results = await asyncio.gather(*tasks)

        # Verify all requests completed
        assert len(results) == 5
        assert all(result.status == TrainingStatus.RUNNING for result in results)
        assert mock_session.get.call_count == 5


# Factory function tests


class TestFactoryFunction:
    """Test factory function for creating service instances"""

    @pytest.mark.asyncio
    async def test_create_ktrdr_integration_service_defaults(self):
        """Test factory function with default parameters"""
        with patch(
            "research_agents.services.ktrdr_integration.KTRDRIntegrationService.initialize"
        ) as mock_init:
            from research_agents.services.ktrdr_integration import (
                create_ktrdr_integration_service,
            )

            service = await create_ktrdr_integration_service()

            # Verify service creation and initialization
            assert isinstance(service, KTRDRIntegrationService)
            assert service.api_base_url == "http://localhost:8000"
            assert service.api_key is None
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_ktrdr_integration_service_custom(self):
        """Test factory function with custom parameters"""
        with patch(
            "research_agents.services.ktrdr_integration.KTRDRIntegrationService.initialize"
        ) as mock_init:
            from research_agents.services.ktrdr_integration import (
                create_ktrdr_integration_service,
            )

            service = await create_ktrdr_integration_service(
                ktrdr_api_base_url="https://custom-api:9000", api_key="custom-key"
            )

            # Verify service creation and initialization
            assert isinstance(service, KTRDRIntegrationService)
            assert service.api_base_url == "https://custom-api:9000"
            assert service.api_key == "custom-key"
            mock_init.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
