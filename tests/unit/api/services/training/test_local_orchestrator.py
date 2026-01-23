"""Unit tests for LocalTrainingOrchestrator.

These tests verify the LocalTrainingOrchestrator class with mocked
TrainingPipeline and other dependencies. They are unit tests because
they mock nearly all external dependencies.
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from ktrdr.api.services.training.context import TrainingOperationContext
from ktrdr.api.services.training.local_orchestrator import LocalTrainingOrchestrator
from ktrdr.api.services.training.progress_bridge import TrainingProgressBridge
from ktrdr.async_infrastructure.cancellation import CancellationError
from ktrdr.training.model_storage import ModelStorage


@pytest.fixture
def training_context():
    """Create a training operation context for testing."""
    from ktrdr.api.services.training.context import OperationMetadata

    return TrainingOperationContext(
        operation_id="test-op-123",
        strategy_name="test_strategy",
        strategy_path=Path("config/strategies/test.yaml"),
        strategy_config={},
        symbols=["AAPL"],
        timeframes=["1d"],
        start_date="2024-01-01",
        end_date="2024-12-31",
        training_config={
            "validation_split": 0.2,
            "data_mode": "local",
        },
        analytics_enabled=False,
        use_host_service=False,
        training_mode="local",
        total_epochs=100,
        total_batches=None,
        metadata=OperationMetadata(
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            progress_updates=[],
        ),
        session_id=None,
    )


@pytest.fixture
def progress_bridge():
    """Create a mock progress bridge."""
    bridge = Mock(spec=TrainingProgressBridge)
    return bridge


@pytest.fixture
def cancellation_token():
    """Create a cancellation token."""
    from ktrdr.async_infrastructure.cancellation import AsyncCancellationToken

    return AsyncCancellationToken(operation_id="test-op-123")


@pytest.fixture
def model_storage(tmp_path):
    """Create a model storage instance."""
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    return ModelStorage(base_path=str(models_dir))


class TestLocalTrainingOrchestratorInitialization:
    """Test LocalTrainingOrchestrator initialization."""

    def test_init_accepts_required_parameters(
        self, training_context, progress_bridge, cancellation_token, model_storage
    ):
        """Test that orchestrator accepts correct initialization parameters."""
        orchestrator = LocalTrainingOrchestrator(
            context=training_context,
            progress_bridge=progress_bridge,
            cancellation_token=cancellation_token,
            model_storage=model_storage,
        )

        assert orchestrator is not None
        assert orchestrator._context == training_context
        assert orchestrator._bridge == progress_bridge
        assert orchestrator._token == cancellation_token
        assert orchestrator._model_storage == model_storage

    def test_init_without_cancellation_token(
        self, training_context, progress_bridge, model_storage
    ):
        """Test that orchestrator works without cancellation token."""
        orchestrator = LocalTrainingOrchestrator(
            context=training_context,
            progress_bridge=progress_bridge,
            cancellation_token=None,
            model_storage=model_storage,
        )

        assert orchestrator._token is None


class TestLocalTrainingOrchestratorConfigLoading:
    """Test strategy config loading."""

    @patch("ktrdr.api.services.training.local_orchestrator.yaml")
    def test_load_strategy_config_reads_yaml(
        self, mock_yaml, training_context, progress_bridge, model_storage
    ):
        """Test that orchestrator loads YAML config from filesystem."""
        orchestrator = LocalTrainingOrchestrator(
            context=training_context,
            progress_bridge=progress_bridge,
            cancellation_token=None,
            model_storage=model_storage,
        )

        # Mock yaml.safe_load to return a config
        mock_config = {
            "indicators": [],
            "fuzzy_sets": {},
            "model": {},
            "training": {},
        }
        mock_yaml.safe_load.return_value = mock_config

        # Mock open
        with patch("builtins.open", MagicMock()):
            config = orchestrator._load_strategy_config(training_context.strategy_path)

        assert config == mock_config
        assert "indicators" in config
        assert "fuzzy_sets" in config

    def test_load_strategy_config_validates_required_sections(
        self, training_context, progress_bridge, model_storage
    ):
        """Test that orchestrator validates required config sections."""
        orchestrator = LocalTrainingOrchestrator(
            context=training_context,
            progress_bridge=progress_bridge,
            cancellation_token=None,
            model_storage=model_storage,
        )

        # Test with missing required sections
        with patch("builtins.open", MagicMock()):
            with patch(
                "ktrdr.api.services.training.local_orchestrator.yaml.safe_load",
                return_value={},
            ):
                with pytest.raises(ValueError, match="Missing required sections"):
                    orchestrator._load_strategy_config(training_context.strategy_path)


class TestLocalTrainingOrchestratorProgressAdapter:
    """Test progress callback adapter."""

    def test_progress_adapter_translates_batch_progress(
        self, training_context, progress_bridge, model_storage
    ):
        """Test that progress adapter translates batch-level progress to bridge."""
        orchestrator = LocalTrainingOrchestrator(
            context=training_context,
            progress_bridge=progress_bridge,
            cancellation_token=None,
            model_storage=model_storage,
        )

        callback = orchestrator._create_progress_callback()

        # Simulate batch progress from TrainingPipeline
        callback(
            epoch=5,
            total_epochs=100,
            metrics={
                "progress_type": "batch",
                "batch": 10,
                "total_batches_per_epoch": 78,
                "loss": 0.5,
            },
        )

        # Verify bridge.on_batch was called correctly
        progress_bridge.on_batch.assert_called_once()
        call_kwargs = progress_bridge.on_batch.call_args[1]
        assert call_kwargs["epoch"] == 5
        assert call_kwargs["batch"] == 10
        assert call_kwargs["total_batches"] == 78

    def test_progress_adapter_translates_epoch_progress(
        self, training_context, progress_bridge, model_storage
    ):
        """Test that progress adapter translates epoch-level progress to bridge."""
        orchestrator = LocalTrainingOrchestrator(
            context=training_context,
            progress_bridge=progress_bridge,
            cancellation_token=None,
            model_storage=model_storage,
        )

        callback = orchestrator._create_progress_callback()

        # Simulate epoch progress from TrainingPipeline
        callback(
            epoch=5,
            total_epochs=100,
            metrics={
                "progress_type": "epoch",
                "train_loss": 0.5,
                "val_loss": 0.6,
                "train_accuracy": 0.85,
                "val_accuracy": 0.82,
            },
        )

        # Verify bridge.on_epoch was called correctly
        progress_bridge.on_epoch.assert_called_once()
        call_kwargs = progress_bridge.on_epoch.call_args[1]
        assert call_kwargs["epoch"] == 5
        assert call_kwargs["total_epochs"] == 100

    def test_progress_adapter_translates_phase_changes(
        self, training_context, progress_bridge, model_storage
    ):
        """Test that progress adapter translates phase changes to bridge."""
        orchestrator = LocalTrainingOrchestrator(
            context=training_context,
            progress_bridge=progress_bridge,
            cancellation_token=None,
            model_storage=model_storage,
        )

        callback = orchestrator._create_progress_callback()

        # Simulate phase change from TrainingPipeline
        callback(
            epoch=0,
            total_epochs=100,
            metrics={
                "progress_type": "data_loading",
                "message": "Loading market data",
            },
        )

        # Verify bridge.on_phase was called correctly
        progress_bridge.on_phase.assert_called_once_with(
            "data_loading", message="Loading market data"
        )


class TestLocalTrainingOrchestratorCancellation:
    """Test cancellation token handling."""

    @pytest.mark.asyncio
    async def test_cancellation_token_passed_through(
        self, training_context, progress_bridge, cancellation_token, model_storage
    ):
        """Test that in-memory cancellation token is passed to pipeline."""
        orchestrator = LocalTrainingOrchestrator(
            context=training_context,
            progress_bridge=progress_bridge,
            cancellation_token=cancellation_token,
            model_storage=model_storage,
        )

        # Mock TrainingPipeline.train_strategy to verify token is passed
        with patch(
            "ktrdr.api.services.training.local_orchestrator.TrainingPipeline.train_strategy"
        ) as mock_train:
            mock_train.return_value = {
                "model_path": "models/test.pth",
                "training_metrics": {},
                "test_metrics": {},
            }

            with patch.object(orchestrator, "_load_strategy_config", return_value={}):
                await orchestrator.run()

            # Verify cancellation_token was passed to train_strategy
            call_kwargs = mock_train.call_args[1]
            assert call_kwargs["cancellation_token"] == cancellation_token

    @pytest.mark.asyncio
    async def test_training_stops_when_token_cancelled(
        self, training_context, progress_bridge, cancellation_token, model_storage
    ):
        """Test that training stops when token is cancelled."""
        orchestrator = LocalTrainingOrchestrator(
            context=training_context,
            progress_bridge=progress_bridge,
            cancellation_token=cancellation_token,
            model_storage=model_storage,
        )

        # Mock TrainingPipeline to raise CancellationError
        with patch(
            "ktrdr.api.services.training.local_orchestrator.TrainingPipeline.train_strategy"
        ) as mock_train:
            mock_train.side_effect = CancellationError("Training cancelled")

            with patch.object(orchestrator, "_load_strategy_config", return_value={}):
                with pytest.raises(CancellationError):
                    await orchestrator.run()


class TestLocalTrainingOrchestratorResultMetadata:
    """Test result includes session metadata."""

    @pytest.mark.asyncio
    async def test_result_includes_session_metadata(
        self, training_context, progress_bridge, model_storage
    ):
        """Test that result includes operation_id, strategy_name, symbols, timeframes."""
        orchestrator = LocalTrainingOrchestrator(
            context=training_context,
            progress_bridge=progress_bridge,
            cancellation_token=None,
            model_storage=model_storage,
        )

        # Mock TrainingPipeline.train_strategy
        with patch(
            "ktrdr.api.services.training.local_orchestrator.TrainingPipeline.train_strategy"
        ) as mock_train:
            mock_train.return_value = {
                "model_path": "models/test.pth",
                "training_metrics": {"final_train_loss": 0.5},
                "test_metrics": {"test_accuracy": 0.85},
            }

            with patch.object(
                orchestrator,
                "_load_strategy_config",
                return_value={
                    "indicators": [],
                    "fuzzy_sets": {},
                    "model": {},
                    "training": {},
                },
            ):
                result = await orchestrator.run()

        # Verify session metadata is present
        assert "session_info" in result
        session_info = result["session_info"]
        assert session_info["operation_id"] == "test-op-123"
        assert session_info["strategy_name"] == "test_strategy"
        assert session_info["symbols"] == ["AAPL"]
        assert session_info["timeframes"] == ["1d"]
        assert session_info["use_host_service"] is False

    @pytest.mark.asyncio
    async def test_result_includes_training_mode_local(
        self, training_context, progress_bridge, model_storage
    ):
        """Test that resource_usage includes training_mode = 'local'."""
        orchestrator = LocalTrainingOrchestrator(
            context=training_context,
            progress_bridge=progress_bridge,
            cancellation_token=None,
            model_storage=model_storage,
        )

        # Mock TrainingPipeline.train_strategy
        with patch(
            "ktrdr.api.services.training.local_orchestrator.TrainingPipeline.train_strategy"
        ) as mock_train:
            mock_train.return_value = {
                "model_path": "models/test.pth",
                "training_metrics": {},
                "test_metrics": {},
            }

            with patch.object(
                orchestrator,
                "_load_strategy_config",
                return_value={
                    "indicators": [],
                    "fuzzy_sets": {},
                    "model": {},
                    "training": {},
                },
            ):
                result = await orchestrator.run()

        # Verify training_mode is "local"
        assert "resource_usage" in result
        assert result["resource_usage"]["training_mode"] == "local"


class TestLocalTrainingOrchestratorAsyncPattern:
    """Test async execution pattern."""

    @pytest.mark.asyncio
    async def test_run_uses_asyncio_to_thread(
        self, training_context, progress_bridge, model_storage
    ):
        """Test that run() wraps execution in asyncio.to_thread()."""
        orchestrator = LocalTrainingOrchestrator(
            context=training_context,
            progress_bridge=progress_bridge,
            cancellation_token=None,
            model_storage=model_storage,
        )

        # Mock asyncio.to_thread to verify it's called
        with patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = asyncio.Future()
            mock_to_thread.return_value.set_result(
                {
                    "model_path": "models/test.pth",
                    "training_metrics": {},
                    "test_metrics": {},
                }
            )

            with patch.object(
                orchestrator,
                "_load_strategy_config",
                return_value={
                    "indicators": [],
                    "fuzzy_sets": {},
                    "model": {},
                    "training": {},
                },
            ):
                await orchestrator.run()

            # Verify asyncio.to_thread was called
            mock_to_thread.assert_called_once()


class TestLocalTrainingOrchestratorFullFlow:
    """Test full training flow integration."""

    @pytest.mark.asyncio
    async def test_full_orchestration_flow(
        self, training_context, progress_bridge, model_storage
    ):
        """Test complete flow: load config → create callback → call pipeline → add metadata."""
        orchestrator = LocalTrainingOrchestrator(
            context=training_context,
            progress_bridge=progress_bridge,
            cancellation_token=None,
            model_storage=model_storage,
        )

        mock_config = {
            "indicators": [{"name": "SMA", "period": 20}],
            "fuzzy_sets": {},
            "model": {"hidden_layers": [64, 32]},
            "training": {"epochs": 100},
        }

        # Mock TrainingPipeline.train_strategy
        with patch(
            "ktrdr.api.services.training.local_orchestrator.TrainingPipeline.train_strategy"
        ) as mock_train:
            mock_train.return_value = {
                "model_path": "models/test_strategy/AAPL_1d_v1/model.pth",
                "training_metrics": {
                    "final_train_loss": 0.5,
                    "final_val_loss": 0.6,
                    "epochs_completed": 100,
                },
                "test_metrics": {"test_accuracy": 0.85, "test_loss": 0.55},
                "artifacts": {"feature_importance": {}},
                "model_info": {"input_dim": 50, "output_dim": 3},
            }

            with patch.object(
                orchestrator, "_load_strategy_config", return_value=mock_config
            ):
                result = await orchestrator.run()

        # Verify result structure
        assert "model_path" in result
        assert "training_metrics" in result
        assert "test_metrics" in result
        assert "session_info" in result
        assert "resource_usage" in result

        # Verify session metadata was added
        assert result["session_info"]["operation_id"] == "test-op-123"
        assert result["session_info"]["use_host_service"] is False

        # Verify progress bridge was used
        assert progress_bridge.on_complete.called
