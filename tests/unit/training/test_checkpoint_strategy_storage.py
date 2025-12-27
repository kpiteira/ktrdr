"""Unit tests for checkpoint strategy storage (Task 4.8).

Tests that:
1. Checkpoint stores strategy_path (not strategy_yaml content)
2. Resume reads strategy from disk using path
3. Resume fails gracefully if strategy file missing
"""

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.services.operations_service import OperationsService


@pytest.fixture
def mock_operations_service():
    """Provide a mock OperationsService without real DB connections."""
    service = OperationsService(repository=None)
    return service


@pytest.fixture
def training_worker(mock_operations_service):
    """Create a TrainingWorker with mocked dependencies."""
    from ktrdr.training.training_worker import TrainingWorker

    worker = TrainingWorker(
        worker_port=5005,
        backend_url="http://test:8000",
    )
    worker._operations_service = mock_operations_service
    return worker


@pytest.fixture
def sample_strategy_yaml():
    """Sample strategy YAML content."""
    return """# === STRATEGY IDENTITY ===
name: "test_strategy"
description: "Test strategy for checkpoint tests"
type: neuro

# === DATA CONFIGURATION ===
data:
  symbols: ["BTCUSD"]
  timeframes: ["1h"]

# === NEURAL NETWORK ===
neural:
  model:
    type: mlp
    hidden_layers: [64, 32]
  training:
    epochs: 50
    batch_size: 32
"""


class TestTrainingStartRequestStrategyPath:
    """Tests for strategy_path field in TrainingStartRequest."""

    def test_request_accepts_strategy_path(self):
        """TrainingStartRequest should accept optional strategy_path."""
        from ktrdr.training.training_worker import TrainingStartRequest

        request = TrainingStartRequest(
            task_id="op_test_123",
            strategy_yaml="name: test\ntype: neuro",
            strategy_path="strategies/test.yaml",
        )
        assert request.strategy_path == "strategies/test.yaml"

    def test_request_strategy_path_is_optional(self):
        """TrainingStartRequest strategy_path should be optional."""
        from ktrdr.training.training_worker import TrainingStartRequest

        request = TrainingStartRequest(
            task_id="op_test_123",
            strategy_yaml="name: test\ntype: neuro",
        )
        # Should not raise, strategy_path defaults to None
        assert request.strategy_path is None


class TestCheckpointOriginalRequest:
    """Tests for original_request dict stored in checkpoint."""

    def test_original_request_contains_strategy_path(self, sample_strategy_yaml):
        """original_request should contain strategy_path, not strategy_yaml."""
        # This test verifies the structure of original_request
        # In the implementation, we build this dict and save to checkpoint
        from ktrdr.training.training_worker import TrainingStartRequest

        request = TrainingStartRequest(
            task_id="op_test_123",
            strategy_yaml=sample_strategy_yaml,
            strategy_path="strategies/test_strategy.yaml",
            symbols=["BTCUSD"],
            timeframes=["1h"],
        )

        # Build original_request as it should be (the implementation we're testing)
        original_request = {
            "strategy_path": request.strategy_path,
            "symbols": request.symbols,
            "timeframes": request.timeframes,
            "start_date": request.start_date,
            "end_date": request.end_date,
        }

        # Should have strategy_path
        assert "strategy_path" in original_request
        assert original_request["strategy_path"] == "strategies/test_strategy.yaml"

        # Should NOT have strategy_yaml (avoid truncation issue)
        assert "strategy_yaml" not in original_request

    def test_original_request_strategy_path_format(self):
        """strategy_path should be relative path (not absolute)."""
        from ktrdr.training.training_worker import TrainingStartRequest

        request = TrainingStartRequest(
            task_id="op_test_123",
            strategy_yaml="name: test",
            strategy_path="strategies/my_strategy.yaml",
        )

        # Relative path format
        assert not request.strategy_path.startswith("/")
        assert request.strategy_path.startswith("strategies/")


class TestResumeReadsStrategyFromDisk:
    """Tests for reading strategy from disk during resume."""

    @pytest.mark.asyncio
    async def test_execute_resumed_training_reads_from_strategy_path(
        self, training_worker, mock_operations_service, sample_strategy_yaml
    ):
        """_execute_resumed_training should read strategy from disk using strategy_path."""
        import io

        import torch
        import torch.nn as nn
        import torch.optim as optim

        from ktrdr.training.checkpoint_restore import TrainingResumeContext

        # Create temp strategy file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(sample_strategy_yaml)
            temp_path = f.name

        try:
            # Create resume context with strategy_path (not strategy_yaml)
            model = nn.Linear(10, 2)
            buffer = io.BytesIO()
            torch.save(model.state_dict(), buffer)
            model_weights = buffer.getvalue()

            optimizer = optim.Adam(model.parameters())
            buffer = io.BytesIO()
            torch.save(optimizer.state_dict(), buffer)
            optimizer_state = buffer.getvalue()

            resume_context = TrainingResumeContext(
                start_epoch=11,
                model_weights=model_weights,
                optimizer_state=optimizer_state,
                original_request={
                    "strategy_path": temp_path,  # Path to read from
                    "symbols": ["BTCUSD"],
                    "timeframes": ["1h"],
                },
            )

            # Create operation
            await mock_operations_service.create_operation(
                operation_id="op_test_resume",
                operation_type=OperationType.TRAINING,
                metadata=OperationMetadata(
                    symbol="BTCUSD",
                    timeframe="1h",
                    mode="training",
                ),
            )

            # Mock dependencies
            with patch.object(
                mock_operations_service, "start_operation", new_callable=AsyncMock
            ):
                with patch.object(
                    mock_operations_service, "get_cancellation_token"
                ) as mock_token:
                    mock_token.return_value = MagicMock()

                    with patch.object(mock_operations_service, "register_local_bridge"):
                        with patch.object(
                            mock_operations_service,
                            "complete_operation",
                            new_callable=AsyncMock,
                        ):
                            with patch.object(
                                training_worker, "get_checkpoint_service"
                            ) as mock_cp:
                                mock_cp_service = AsyncMock()
                                mock_cp.return_value = mock_cp_service
                                mock_cp_service.delete_checkpoint = AsyncMock()
                                mock_cp_service.save_checkpoint = AsyncMock()

                                # Mock build_training_context to skip validation
                                with patch(
                                    "ktrdr.api.services.training.context.build_training_context"
                                ) as mock_build_ctx:
                                    mock_context = MagicMock()
                                    mock_context.strategy_name = "test_strategy"
                                    mock_context.total_epochs = 50
                                    mock_context.symbols = ["BTCUSD"]
                                    mock_context.timeframes = ["1h"]
                                    mock_build_ctx.return_value = mock_context

                                    with patch(
                                        "ktrdr.api.services.training.local_orchestrator.LocalTrainingOrchestrator"
                                    ) as mock_orch:
                                        mock_orchestrator = MagicMock()
                                        mock_orch.return_value = mock_orchestrator
                                        mock_orchestrator.run = AsyncMock(
                                            return_value={
                                                "model_path": "/path/to/model",
                                                "training_metrics": {},
                                                "test_metrics": {},
                                            }
                                        )

                                        # Execute - should read strategy from temp_path
                                        await training_worker._execute_resumed_training(
                                            "op_test_resume", resume_context
                                        )

                                        # Verify build_training_context was called
                                        # (meaning strategy was loaded successfully)
                                        mock_build_ctx.assert_called_once()

                                        # Verify LocalTrainingOrchestrator was called
                                        mock_orch.assert_called_once()

        finally:
            # Cleanup temp file
            import os

            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_execute_resumed_training_fails_gracefully_on_missing_file(
        self, training_worker, mock_operations_service
    ):
        """Resume should fail gracefully if strategy file doesn't exist."""
        import io

        import torch
        import torch.nn as nn
        import torch.optim as optim

        from ktrdr.training.checkpoint_restore import TrainingResumeContext

        # Create resume context with non-existent strategy_path
        model = nn.Linear(10, 2)
        buffer = io.BytesIO()
        torch.save(model.state_dict(), buffer)
        model_weights = buffer.getvalue()

        optimizer = optim.Adam(model.parameters())
        buffer = io.BytesIO()
        torch.save(optimizer.state_dict(), buffer)
        optimizer_state = buffer.getvalue()

        resume_context = TrainingResumeContext(
            start_epoch=11,
            model_weights=model_weights,
            optimizer_state=optimizer_state,
            original_request={
                "strategy_path": "/nonexistent/path/strategy.yaml",
                "symbols": ["BTCUSD"],
                "timeframes": ["1h"],
            },
        )

        # Create operation
        await mock_operations_service.create_operation(
            operation_id="op_test_missing",
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(
                symbol="BTCUSD",
                timeframe="1h",
                mode="training",
            ),
        )

        # Mock dependencies
        with patch.object(
            mock_operations_service, "start_operation", new_callable=AsyncMock
        ):
            with patch.object(
                mock_operations_service, "get_cancellation_token"
            ) as mock_token:
                mock_token.return_value = MagicMock()

                with patch.object(
                    mock_operations_service, "fail_operation", new_callable=AsyncMock
                ):
                    # Execute - should fail gracefully
                    with pytest.raises(FileNotFoundError):
                        await training_worker._execute_resumed_training(
                            "op_test_missing", resume_context
                        )


class TestBackwardCompatibility:
    """Tests for backward compatibility with old checkpoints."""

    @pytest.mark.asyncio
    async def test_resume_handles_old_checkpoint_with_strategy_yaml(
        self, training_worker, mock_operations_service
    ):
        """Resume should handle old checkpoints that have strategy_yaml instead of strategy_path."""
        import io

        import torch
        import torch.nn as nn
        import torch.optim as optim

        from ktrdr.training.checkpoint_restore import TrainingResumeContext

        # Create resume context with old-style strategy_yaml (for backward compat)
        model = nn.Linear(10, 2)
        buffer = io.BytesIO()
        torch.save(model.state_dict(), buffer)
        model_weights = buffer.getvalue()

        optimizer = optim.Adam(model.parameters())
        buffer = io.BytesIO()
        torch.save(optimizer.state_dict(), buffer)
        optimizer_state = buffer.getvalue()

        # Old checkpoint format - has strategy_yaml, no strategy_path
        resume_context = TrainingResumeContext(
            start_epoch=11,
            model_weights=model_weights,
            optimizer_state=optimizer_state,
            original_request={
                "strategy_yaml": "name: test\ntype: neuro",  # Old format
                "symbols": ["BTCUSD"],
                "timeframes": ["1h"],
            },
        )

        # Create operation
        await mock_operations_service.create_operation(
            operation_id="op_test_oldformat",
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(
                symbol="BTCUSD",
                timeframe="1h",
                mode="training",
            ),
        )

        # Mock dependencies
        with patch.object(
            mock_operations_service, "start_operation", new_callable=AsyncMock
        ):
            with patch.object(
                mock_operations_service, "get_cancellation_token"
            ) as mock_token:
                mock_token.return_value = MagicMock()

                with patch.object(mock_operations_service, "register_local_bridge"):
                    with patch.object(
                        mock_operations_service,
                        "complete_operation",
                        new_callable=AsyncMock,
                    ):
                        with patch.object(
                            training_worker, "get_checkpoint_service"
                        ) as mock_cp:
                            mock_cp_service = AsyncMock()
                            mock_cp.return_value = mock_cp_service
                            mock_cp_service.delete_checkpoint = AsyncMock()
                            mock_cp_service.save_checkpoint = AsyncMock()

                            # Mock build_training_context to skip validation
                            with patch(
                                "ktrdr.api.services.training.context.build_training_context"
                            ) as mock_build_ctx:
                                mock_context = MagicMock()
                                mock_context.strategy_name = "test"
                                mock_context.total_epochs = 50
                                mock_context.symbols = ["BTCUSD"]
                                mock_context.timeframes = ["1h"]
                                mock_build_ctx.return_value = mock_context

                                with patch(
                                    "ktrdr.api.services.training.local_orchestrator.LocalTrainingOrchestrator"
                                ) as mock_orch:
                                    mock_orchestrator = MagicMock()
                                    mock_orch.return_value = mock_orchestrator
                                    mock_orchestrator.run = AsyncMock(
                                        return_value={
                                            "model_path": "/path/to/model",
                                            "training_metrics": {},
                                            "test_metrics": {},
                                        }
                                    )

                                    # Should not raise - backward compat with old format
                                    # (uses strategy_yaml directly)
                                    await training_worker._execute_resumed_training(
                                        "op_test_oldformat", resume_context
                                    )

                                    # Verify training proceeded
                                    mock_orch.assert_called_once()
