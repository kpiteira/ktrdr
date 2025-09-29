"""
Unit tests for the core training service.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestTrainingService:
    """Test suite for TrainingService class."""

    @pytest.mark.asyncio
    async def test_service_initialization(self, mock_gpu_available):
        """Test training service initializes correctly."""
        from services.training_service import TrainingService

        with patch.object(TrainingService, "_initialize_global_resources"):
            service = TrainingService(
                max_concurrent_sessions=2, session_timeout_minutes=30
            )

            assert service.max_concurrent_sessions == 2
            assert service.session_timeout_minutes == 30
            assert service.sessions == {}

    @pytest.mark.asyncio
    async def test_create_session_success(
        self, mock_gpu_available, sample_training_config
    ):
        """Test successful session creation."""
        from services.training_service import TrainingService

        with patch.object(TrainingService, "_initialize_global_resources"):
            with patch.object(
                TrainingService, "_initialize_session_resources", new_callable=AsyncMock
            ):
                with patch.object(
                    TrainingService, "_run_training_session", new_callable=AsyncMock
                ):
                    service = TrainingService()

                    session_id = await service.create_session(sample_training_config)

                    assert session_id in service.sessions
                    session = service.sessions[session_id]
                    assert session.config == sample_training_config
                    assert session.status in ["initializing", "running"]

    @pytest.mark.asyncio
    async def test_create_session_with_custom_id(
        self, mock_gpu_available, sample_training_config
    ):
        """Test session creation with custom session ID."""
        from services.training_service import TrainingService

        with patch.object(TrainingService, "_initialize_global_resources"):
            with patch.object(
                TrainingService, "_initialize_session_resources", new_callable=AsyncMock
            ):
                with patch.object(
                    TrainingService, "_run_training_session", new_callable=AsyncMock
                ):
                    service = TrainingService()

                    custom_id = "my-custom-session"
                    session_id = await service.create_session(
                        sample_training_config, custom_id
                    )

                    assert session_id == custom_id
                    assert custom_id in service.sessions

    @pytest.mark.asyncio
    async def test_create_session_exceeds_limit(
        self, mock_gpu_available, sample_training_config
    ):
        """Test session creation fails when limit exceeded."""
        from services.training_service import TrainingService

        with patch.object(TrainingService, "_initialize_global_resources"):
            with patch.object(
                TrainingService, "_initialize_session_resources", new_callable=AsyncMock
            ):
                with patch.object(
                    TrainingService, "_run_training_session", new_callable=AsyncMock
                ):
                    service = TrainingService(max_concurrent_sessions=1)

                    # Create first session
                    await service.create_session(sample_training_config)

                    # Try to create second session - should fail
                    with pytest.raises(Exception, match="Maximum concurrent sessions"):
                        await service.create_session(sample_training_config)

    @pytest.mark.asyncio
    async def test_create_duplicate_session_id(
        self, mock_gpu_available, sample_training_config
    ):
        """Test session creation fails with duplicate ID."""
        from services.training_service import TrainingService

        with patch.object(TrainingService, "_initialize_global_resources"):
            with patch.object(
                TrainingService, "_initialize_session_resources", new_callable=AsyncMock
            ):
                with patch.object(
                    TrainingService, "_run_training_session", new_callable=AsyncMock
                ):
                    service = TrainingService(
                        max_concurrent_sessions=2
                    )  # Allow multiple sessions

                    session_id = "duplicate-id"
                    await service.create_session(sample_training_config, session_id)

                    # Try to create with same ID - should fail
                    with pytest.raises(Exception, match="already exists"):
                        await service.create_session(sample_training_config, session_id)

    @pytest.mark.asyncio
    async def test_stop_session_success(
        self, mock_gpu_available, sample_training_config
    ):
        """Test successful session stop."""
        from services.training_service import TrainingService

        with patch.object(TrainingService, "_initialize_global_resources"):
            with patch.object(
                TrainingService, "_initialize_session_resources", new_callable=AsyncMock
            ):
                service = TrainingService()

                # Create a mock session
                session_id = "test-session"
                session_mock = Mock()
                session_mock.status = "running"
                session_mock.stop_requested = False

                # Create a proper async mock for training_task
                async def dummy_task():
                    return "completed"

                task_mock = asyncio.create_task(dummy_task())
                task_mock.cancel()  # Cancel it so it's done
                session_mock.training_task = task_mock

                service.sessions[session_id] = session_mock

                result = await service.stop_session(session_id)

                assert result is True
                assert session_mock.stop_requested is True

    @pytest.mark.asyncio
    async def test_stop_nonexistent_session(self, mock_gpu_available):
        """Test stopping non-existent session fails."""
        from services.training_service import TrainingService

        with patch.object(TrainingService, "_initialize_global_resources"):
            service = TrainingService()

            with pytest.raises(Exception, match="not found"):
                await service.stop_session("nonexistent-session")

    @pytest.mark.asyncio
    async def test_stop_non_running_session(self, mock_gpu_available):
        """Test stopping non-running session fails."""
        from services.training_service import TrainingService

        with patch.object(TrainingService, "_initialize_global_resources"):
            service = TrainingService()

            # Create a completed session
            session_mock = Mock()
            session_mock.status = "completed"
            service.sessions["completed-session"] = session_mock

            with pytest.raises(Exception, match="is not running"):
                await service.stop_session("completed-session")

    @pytest.mark.asyncio
    async def test_get_session_status_success(self, mock_training_session):
        """Test getting session status."""
        from services.training_service import TrainingService

        with patch.object(TrainingService, "_initialize_global_resources"):
            service = TrainingService()
            service.sessions["test-session"] = mock_training_session

            status = service.get_session_status("test-session")

            assert status["session_id"] == "test-session"
            assert status["status"] == "running"
            assert status["progress"]["message"].startswith("Epoch")
            assert status["progress"]["items_processed"] == 50
            assert status["progress"]["items_total"] == 100
            assert "metrics" in status
            assert "resource_usage" in status

    @pytest.mark.asyncio
    async def test_get_session_status_not_found(self, mock_gpu_available):
        """Test getting status of non-existent session."""
        from services.training_service import TrainingService

        with patch.object(TrainingService, "_initialize_global_resources"):
            service = TrainingService()

            with pytest.raises(Exception, match="not found"):
                service.get_session_status("nonexistent-session")

    @pytest.mark.asyncio
    async def test_list_sessions(self, mock_training_session):
        """Test listing all sessions."""
        from services.training_service import TrainingService

        with patch.object(TrainingService, "_initialize_global_resources"):
            service = TrainingService()
            # Use the mock's session_id as the key
            service.sessions[mock_training_session.session_id] = mock_training_session

            sessions = service.list_sessions()

            assert len(sessions) == 1
            assert sessions[0]["session_id"] == "test-session-123"
            assert "status" in sessions[0]
            assert "progress" in sessions[0]

    @pytest.mark.asyncio
    async def test_cleanup_session_success(self, mock_training_session):
        """Test successful session cleanup."""
        from services.training_service import TrainingService

        with patch.object(TrainingService, "_initialize_global_resources"):
            service = TrainingService()

            # Set session to completed status
            mock_training_session.status = "completed"
            mock_training_session.cleanup = AsyncMock()
            service.sessions["test-session"] = mock_training_session

            result = await service.cleanup_session("test-session")

            assert result is True
            assert "test-session" not in service.sessions
            mock_training_session.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_running_session_fails(self, mock_training_session):
        """Test cleanup fails for running session."""
        from services.training_service import TrainingService

        with patch.object(TrainingService, "_initialize_global_resources"):
            service = TrainingService()

            # Keep session in running status
            mock_training_session.status = "running"
            service.sessions["test-session"] = mock_training_session

            with pytest.raises(Exception, match="Cannot cleanup running session"):
                await service.cleanup_session("test-session")

    @pytest.mark.asyncio
    async def test_cleanup_nonexistent_session(self, mock_gpu_available):
        """Test cleanup of non-existent session fails."""
        from services.training_service import TrainingService

        with patch.object(TrainingService, "_initialize_global_resources"):
            service = TrainingService()

            with pytest.raises(Exception, match="not found"):
                await service.cleanup_session("nonexistent-session")


class TestTrainingSession:
    """Test suite for TrainingSession class."""

    def test_training_session_initialization(self, sample_training_config):
        """Test training session initializes correctly."""
        from services.training_service import TrainingSession

        session = TrainingSession("test-session", sample_training_config)

        assert session.session_id == "test-session"
        assert session.config == sample_training_config
        assert session.status == "initializing"
        assert session.current_epoch == 0
        assert session.current_batch == 0
        assert (
            session.total_epochs == sample_training_config["training_config"]["epochs"]
        )

    def test_update_progress(self, sample_training_config):
        """Test progress update functionality."""
        from services.training_service import TrainingSession

        session = TrainingSession("test-session", sample_training_config)

        metrics = {"train_loss": 0.5, "train_accuracy": 0.8}
        session.update_progress(5, 50, metrics)

        assert session.current_epoch == 6
        assert session.current_batch == 50
        assert session.metrics["train_loss"] == [0.5]
        assert session.metrics["train_accuracy"] == [0.8]
        assert session.best_metrics["train_loss"] == 0.5  # Loss - lower is better
        assert (
            session.best_metrics["train_accuracy"] == 0.8
        )  # Accuracy - higher is better

    def test_get_progress_dict(self, sample_training_config):
        """Test progress dictionary generation."""
        from services.training_service import TrainingSession

        session = TrainingSession("test-session", sample_training_config)
        session.current_epoch = 5
        session.total_epochs = 10
        session.current_batch = 50
        session.total_batches = 100
        session.items_processed = 50
        session.message = "Epoch 5/10 · Batch 50/100"
        session.current_item = "Batch 50/100"

        progress = session.get_progress_dict()

        assert progress["epoch"] == 5
        assert progress["total_epochs"] == 10
        assert progress["batch"] == 50
        assert progress["total_batches"] == 100
        assert progress["progress_percent"] == 50.0
        assert progress["items_processed"] == 50
        assert progress["items_total"] == 100
        assert progress["message"] == "Epoch 5/10 · Batch 50/100"

    @pytest.mark.asyncio
    async def test_session_cleanup(self, sample_training_config):
        """Test session cleanup functionality."""
        from services.training_service import TrainingSession

        session = TrainingSession("test-session", sample_training_config)

        # Mock managers
        session.gpu_manager = Mock()
        session.gpu_manager.cleanup_memory = Mock()
        session.memory_manager = Mock()
        session.memory_manager.cleanup_memory = Mock()

        # Mock training task properly
        async def dummy_task():
            return "completed"

        task_mock = asyncio.create_task(dummy_task())
        await task_mock  # Complete the task
        session.training_task = task_mock

        await session.cleanup()

        assert session.stop_requested is False
        session.gpu_manager.cleanup_memory.assert_called_once()
        session.memory_manager.cleanup_memory.assert_called_once()
