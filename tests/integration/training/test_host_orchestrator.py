"""Integration tests for HostTrainingOrchestrator."""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from unittest.mock import Mock, patch

import pytest

# Add training-host-service to path for imports
training_host_service_path = (
    Path(__file__).parent.parent.parent.parent / "training-host-service"
)
if str(training_host_service_path) not in sys.path:
    sys.path.insert(0, str(training_host_service_path))

from ktrdr.training.model_storage import ModelStorage  # noqa: E402


# Mock TrainingSession class for testing
class MockTrainingSession:
    """Mock TrainingSession for testing without host service dependencies."""

    def __init__(self, session_id: str, config: dict[str, Any]):
        self.session_id = session_id
        self.config = config
        self.status = "initializing"
        self.start_time = datetime.utcnow()
        self.last_updated = datetime.utcnow()

        # Progress tracking
        self.current_epoch = 0
        self.current_batch = 0
        self.total_epochs = config.get("training_config", {}).get("epochs", 100)
        self.total_batches = 0
        self.items_processed = 0
        self.message = "Initializing"
        self.current_item = ""

        # Metrics tracking
        self.metrics = {}
        self.best_metrics = {}

        # Cancellation flag
        self.stop_requested = False

        # Artifacts
        self.artifacts = {}

        # Resource managers (None for testing)
        self.gpu_manager: Optional[Any] = None
        self.memory_manager: Optional[Any] = None
        self.performance_optimizer: Optional[Any] = None
        self.data_optimizer: Optional[Any] = None

    def update_progress(
        self,
        epoch: int,
        batch: int,
        metrics: dict[str, Any],
    ) -> None:
        """Update progress tracking."""
        self.current_epoch = epoch
        self.current_batch = batch
        self.metrics = metrics
        self.last_updated = datetime.utcnow()

    def get_progress_dict(self) -> dict[str, Any]:
        """Get progress as dictionary."""
        return {
            "session_id": self.session_id,
            "status": self.status,
            "current_epoch": self.current_epoch,
            "current_batch": self.current_batch,
            "total_epochs": self.total_epochs,
            "total_batches": self.total_batches,
            "metrics": self.metrics,
            "message": self.message,
        }


@pytest.fixture
def training_session():
    """Create a mock training session for testing."""
    config = {
        "symbols": ["AAPL"],
        "timeframes": ["1d"],
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "strategy_config": {
            "name": "test_strategy",
            "model": {
                "hidden_layers": [64, 32],
                "dropout": 0.2,
                "learning_rate": 0.001,
            },
            "training": {
                "epochs": 10,
                "batch_size": 32,
                "validation_split": 0.2,
            },
            "indicators": [],
            "fuzzy": {"rules": []},
        },
        "training_config": {
            "epochs": 10,
            "batch_size": 32,
            "validation_split": 0.2,
            "data_mode": "local",
        },
    }
    return MockTrainingSession(session_id="test-session-123", config=config)


@pytest.fixture
def model_storage(tmp_path):
    """Create a model storage instance."""
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    return ModelStorage(base_path=str(models_dir))


class TestHostTrainingOrchestratorInitialization:
    """Test HostTrainingOrchestrator initialization."""

    def test_init_accepts_required_parameters(self, training_session, model_storage):
        """Test that orchestrator accepts correct initialization parameters."""
        # Import here to ensure class exists (will fail initially - TDD RED phase)
        from orchestrator import HostTrainingOrchestrator

        orchestrator = HostTrainingOrchestrator(
            session=training_session,
            model_storage=model_storage,
        )

        assert orchestrator is not None
        assert orchestrator._session == training_session
        assert orchestrator._model_storage == model_storage

    def test_init_extracts_config_correctly(self, training_session, model_storage):
        """Test that orchestrator extracts configuration from session."""
        from orchestrator import HostTrainingOrchestrator

        orchestrator = HostTrainingOrchestrator(
            session=training_session,
            model_storage=model_storage,
        )

        # Should extract symbols, timeframes, dates from session.config
        assert orchestrator._session.config["symbols"] == ["AAPL"]
        assert orchestrator._session.config["timeframes"] == ["1d"]
        assert orchestrator._session.config["start_date"] == "2024-01-01"
        assert orchestrator._session.config["end_date"] == "2024-12-31"


class TestSessionCancellationToken:
    """Test SessionCancellationToken implementation."""

    def test_token_implements_cancellation_token_interface(self, training_session):
        """Test that SessionCancellationToken implements CancellationToken interface."""
        from orchestrator import SessionCancellationToken

        token = SessionCancellationToken(training_session)

        # Should have is_cancelled method
        assert hasattr(token, "is_cancelled")
        assert callable(token.is_cancelled)

    def test_token_checks_session_stop_requested(self, training_session):
        """Test that token checks session.stop_requested flag."""
        from orchestrator import SessionCancellationToken

        token = SessionCancellationToken(training_session)

        # Initially not cancelled
        assert not token.is_cancelled()

        # After setting stop_requested
        training_session.stop_requested = True
        assert token.is_cancelled()

    def test_token_returns_false_when_not_cancelled(self, training_session):
        """Test that token returns False when training not cancelled."""
        from orchestrator import SessionCancellationToken

        training_session.stop_requested = False
        token = SessionCancellationToken(training_session)

        assert token.is_cancelled() is False


class TestThrottledProgressCallback:
    """Test throttled progress callback mechanism."""

    def test_progress_callback_updates_session(self, training_session, model_storage):
        """Test that progress callback updates session state."""
        from orchestrator import HostTrainingOrchestrator

        orchestrator = HostTrainingOrchestrator(
            session=training_session,
            model_storage=model_storage,
        )

        # Create callback
        callback = orchestrator._create_throttled_progress_callback()

        # Call callback with batch progress
        callback(
            epoch=1,
            total_epochs=10,
            metrics={
                "progress_type": "batch",
                "batch": 10,
                "loss": 0.5,
                "accuracy": 0.85,
            },
        )

        # Session should be updated
        assert training_session.current_epoch == 1
        assert training_session.current_batch == 10

    def test_progress_callback_throttles_updates(self, training_session, model_storage):
        """Test that callback only updates every N batches (throttling)."""
        from orchestrator import HostTrainingOrchestrator

        orchestrator = HostTrainingOrchestrator(
            session=training_session,
            model_storage=model_storage,
        )

        callback = orchestrator._create_throttled_progress_callback()

        # Call callback multiple times
        for batch in range(1, 20):
            callback(
                epoch=1,
                total_epochs=10,
                metrics={
                    "progress_type": "batch",
                    "batch": batch,
                    "loss": 0.5,
                },
            )

        # Should only update on batches that are multiples of PROGRESS_UPDATE_FREQUENCY (10)
        # Last update should be batch 10 (not 19)
        assert training_session.current_batch == 10

    def test_progress_callback_always_updates_on_epoch(
        self, training_session, model_storage
    ):
        """Test that callback always updates on epoch completion."""
        from orchestrator import HostTrainingOrchestrator

        orchestrator = HostTrainingOrchestrator(
            session=training_session,
            model_storage=model_storage,
        )

        callback = orchestrator._create_throttled_progress_callback()

        # Call with epoch progress
        callback(
            epoch=5,
            total_epochs=10,
            metrics={
                "progress_type": "epoch",
                "epoch_loss": 0.3,
                "epoch_accuracy": 0.9,
            },
        )

        # Should always update on epoch completion
        assert training_session.current_epoch == 5

    def test_progress_callback_has_no_sleep_operations(
        self, training_session, model_storage
    ):
        """Test that callback implementation contains NO sleep operations."""
        import inspect
        import re

        from orchestrator import HostTrainingOrchestrator

        orchestrator = HostTrainingOrchestrator(
            session=training_session,
            model_storage=model_storage,
        )

        # Get callback source code
        callback = orchestrator._create_throttled_progress_callback()
        source = inspect.getsource(callback)

        # Should NOT contain any actual sleep function calls
        # Use regex to find sleep() calls (not just the word "sleep" in comments)
        sleep_calls = re.findall(r"\b(asyncio\.sleep|time\.sleep)\s*\(", source)
        assert (
            len(sleep_calls) == 0
        ), f"Callback must NOT contain sleep operations! Found: {sleep_calls}"


class TestHostTrainingOrchestratorExecution:
    """Test HostTrainingOrchestrator execution flow."""

    @pytest.mark.asyncio
    async def test_run_uses_training_pipeline(self, training_session, model_storage):
        """Test that orchestrator uses TrainingPipeline.train_strategy()."""
        from orchestrator import HostTrainingOrchestrator

        orchestrator = HostTrainingOrchestrator(
            session=training_session,
            model_storage=model_storage,
        )

        # Mock TrainingPipeline.train_strategy
        with patch("orchestrator.TrainingPipeline.train_strategy") as mock_train:
            mock_train.return_value = {
                "success": True,
                "model_path": "/models/test_model.pt",
                "training_metrics": {"loss": 0.3, "accuracy": 0.9},
                "test_metrics": {"loss": 0.35, "accuracy": 0.88},
            }

            # Mock data manager
            with patch("orchestrator.DataManager") as mock_dm_class:
                mock_dm = Mock()
                mock_dm_class.return_value = mock_dm

                result = await orchestrator.run()

                # Should call TrainingPipeline.train_strategy
                assert mock_train.called
                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_run_is_direct_async(self, training_session, model_storage):
        """Test that run() is direct async (no asyncio.to_thread wrapper)."""
        import inspect

        from orchestrator import HostTrainingOrchestrator

        orchestrator = HostTrainingOrchestrator(
            session=training_session,
            model_storage=model_storage,
        )

        # Check that run() is an async method
        assert asyncio.iscoroutinefunction(orchestrator.run)

        # Get source code and verify NO to_thread usage
        source = inspect.getsource(orchestrator.run)
        assert (
            "to_thread" not in source
        ), "Host orchestrator should NOT use asyncio.to_thread"

    @pytest.mark.asyncio
    async def test_run_respects_cancellation(self, training_session, model_storage):
        """Test that training stops when session.stop_requested is set."""
        from orchestrator import HostTrainingOrchestrator

        from ktrdr.async_infrastructure.cancellation import CancellationError

        orchestrator = HostTrainingOrchestrator(
            session=training_session,
            model_storage=model_storage,
        )

        # Set stop_requested before training starts
        training_session.stop_requested = True

        # Mock TrainingPipeline to raise CancellationError
        with patch("orchestrator.TrainingPipeline.train_strategy") as mock_train:
            mock_train.side_effect = CancellationError("Training cancelled")

            with pytest.raises(CancellationError):
                await orchestrator.run()

    @pytest.mark.asyncio
    async def test_run_saves_model_via_model_storage(
        self, training_session, model_storage
    ):
        """Test that orchestrator saves model via shared ModelStorage."""
        from orchestrator import HostTrainingOrchestrator

        orchestrator = HostTrainingOrchestrator(
            session=training_session,
            model_storage=model_storage,
        )

        # Mock successful training
        with patch("orchestrator.TrainingPipeline.train_strategy") as mock_train:
            mock_model_path = str(model_storage.base_path / "test_model.pt")
            mock_train.return_value = {
                "success": True,
                "model_path": mock_model_path,
                "training_metrics": {"loss": 0.3},
                "test_metrics": {"loss": 0.35},
            }

            with patch("orchestrator.DataManager") as mock_dm_class:
                mock_dm = Mock()
                mock_dm_class.return_value = mock_dm

                result = await orchestrator.run()

                # Model path should be in result
                assert "model_path" in result
                assert result["model_path"] == mock_model_path

                # Session should have model_path in artifacts
                assert "model_path" in training_session.artifacts

    @pytest.mark.asyncio
    async def test_run_includes_host_metadata(self, training_session, model_storage):
        """Test that result includes host-specific metadata."""
        from orchestrator import HostTrainingOrchestrator

        orchestrator = HostTrainingOrchestrator(
            session=training_session,
            model_storage=model_storage,
        )

        with patch("orchestrator.TrainingPipeline.train_strategy") as mock_train:
            mock_train.return_value = {
                "success": True,
                "model_path": "/models/test.pt",
                "training_metrics": {},
                "test_metrics": {},
            }

            with patch("orchestrator.DataManager") as mock_dm_class:
                mock_dm = Mock()
                mock_dm_class.return_value = mock_dm

                # Mock device detection
                with patch(
                    "orchestrator.torch.cuda.is_available",
                    return_value=False,
                ):
                    with patch(
                        "orchestrator.torch.backends.mps.is_available",
                        return_value=True,
                    ):
                        result = await orchestrator.run()

                        # Should include resource_usage metadata
                        assert "resource_usage" in result
                        assert "gpu_used" in result["resource_usage"]
                        assert "session_id" in result


class TestPerformanceOptimizations:
    """Test critical performance optimizations."""

    def test_no_sleep_in_orchestrator_source(self, training_session, model_storage):
        """Test that HostTrainingOrchestrator source contains NO sleep operations."""
        import inspect

        from orchestrator import HostTrainingOrchestrator

        # Get entire class source
        source = inspect.getsource(HostTrainingOrchestrator)

        # Should NOT contain any sleep operations
        assert (
            "asyncio.sleep" not in source
        ), "Orchestrator must NOT contain asyncio.sleep!"
        assert "time.sleep" not in source, "Orchestrator must NOT contain time.sleep!"

    def test_throttling_constants_defined(self):
        """Test that throttling constants are properly defined."""
        from orchestrator import HostTrainingOrchestrator

        # Should have class-level constants
        assert hasattr(HostTrainingOrchestrator, "PROGRESS_UPDATE_FREQUENCY")
        assert hasattr(HostTrainingOrchestrator, "CANCELLATION_CHECK_FREQUENCY")

        # Should be reasonable values
        assert HostTrainingOrchestrator.PROGRESS_UPDATE_FREQUENCY == 10
        assert HostTrainingOrchestrator.CANCELLATION_CHECK_FREQUENCY == 5


class TestConfigExtraction:
    """Test configuration extraction from session."""

    def test_extracts_symbols_from_config(self, training_session, model_storage):
        """Test extraction of symbols from session config."""
        from orchestrator import HostTrainingOrchestrator

        orchestrator = HostTrainingOrchestrator(
            session=training_session,
            model_storage=model_storage,
        )

        # Extract symbols
        symbols = orchestrator._extract_symbols()
        assert symbols == ["AAPL"]

    def test_extracts_timeframes_from_config(self, training_session, model_storage):
        """Test extraction of timeframes from session config."""
        from orchestrator import HostTrainingOrchestrator

        orchestrator = HostTrainingOrchestrator(
            session=training_session,
            model_storage=model_storage,
        )

        timeframes = orchestrator._extract_timeframes()
        assert timeframes == ["1d"]

    def test_extracts_strategy_config(self, training_session, model_storage):
        """Test extraction of strategy configuration."""
        from orchestrator import HostTrainingOrchestrator

        orchestrator = HostTrainingOrchestrator(
            session=training_session,
            model_storage=model_storage,
        )

        strategy_config = orchestrator._extract_strategy_config()
        assert strategy_config is not None
        assert "name" in strategy_config
        assert strategy_config["name"] == "test_strategy"

    def test_handles_multi_symbol_config(self, training_session, model_storage):
        """Test handling of multi-symbol configuration."""
        # Update session to have multiple symbols
        training_session.config["symbols"] = ["AAPL", "MSFT", "GOOGL"]

        from orchestrator import HostTrainingOrchestrator

        orchestrator = HostTrainingOrchestrator(
            session=training_session,
            model_storage=model_storage,
        )

        symbols = orchestrator._extract_symbols()
        assert len(symbols) == 3
        assert symbols == ["AAPL", "MSFT", "GOOGL"]
