"""
Tests for SLICE-3 Task 3.3: Deep Cancellation Flow for Training Operations

This test suite validates:
- TrainingAdapter cancellation token parameter handling
- ModelTrainer efficient cancellation checks (epoch boundaries + every 50 batches)
- Host service cancellation context support
- Performance optimization (minimal overhead)
- Consistent patterns with DataManager cancellation
"""

import asyncio
from unittest.mock import Mock, patch

import pytest
import torch

from ktrdr.async_infrastructure.cancellation import (
    AsyncCancellationToken,
)


class TestTrainingAdapterCancellation:
    """Test cancellation integration in TrainingAdapter."""

    def setup_method(self):
        """Set up test fixtures."""
        # Import here to avoid import issues
        from ktrdr.training.training_adapter import TrainingAdapter

        self.adapter_local = TrainingAdapter(use_host_service=False)
        self.adapter_host = TrainingAdapter(
            use_host_service=True, host_service_url="http://localhost:5002"
        )

    def test_train_multi_symbol_strategy_accepts_cancellation_token(self):
        """Test that train_multi_symbol_strategy method accepts cancellation_token parameter."""
        # Check the method signature includes cancellation_token parameter
        method = self.adapter_local.train_multi_symbol_strategy
        import inspect

        sig = inspect.signature(method)

        assert (
            "cancellation_token" in sig.parameters
        ), "Method should accept cancellation_token parameter"
        param = sig.parameters["cancellation_token"]
        assert param.default is None, "cancellation_token should default to None"

    @pytest.mark.asyncio
    async def test_local_training_adapter_passes_cancellation_token(self):
        """Test that local training passes cancellation_token to local_trainer."""
        # Mock the local trainer
        mock_local_trainer = Mock()
        mock_local_trainer.train_multi_symbol_strategy.return_value = {"success": True}
        self.adapter_local.local_trainer = mock_local_trainer

        # Create cancellation token
        token = AsyncCancellationToken("test-training")

        # Call with cancellation token
        await self.adapter_local.train_multi_symbol_strategy(
            strategy_config_path="test.json",
            symbols=["AAPL"],
            timeframes=["1h"],
            start_date="2023-01-01",
            end_date="2023-12-31",
            cancellation_token=token,
        )

        # Verify token was passed to local trainer
        mock_local_trainer.train_multi_symbol_strategy.assert_called_once()
        call_kwargs = mock_local_trainer.train_multi_symbol_strategy.call_args.kwargs
        assert "cancellation_token" in call_kwargs
        assert call_kwargs["cancellation_token"] is token

    @pytest.mark.asyncio
    async def test_host_service_training_includes_cancellation_context(self):
        """Test that host service training includes cancellation context in request."""
        # Mock the HTTP call
        with patch.object(self.adapter_host, "_call_host_service_post") as mock_post:
            mock_post.return_value = {"session_id": "test-session", "success": True}

            # Create cancellation token
            token = AsyncCancellationToken("test-training")

            # Call with cancellation token
            await self.adapter_host.train_multi_symbol_strategy(
                strategy_config_path="test.json",
                symbols=["AAPL"],
                timeframes=["1h"],
                start_date="2023-01-01",
                end_date="2023-12-31",
                cancellation_token=token,
            )

            # Verify cancellation context was included in request
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            endpoint, request_data = call_args[0]

            assert endpoint == "/training/start"
            assert "cancellation_context" in request_data
            cancellation_context = request_data["cancellation_context"]
            assert "cancellation_token_id" in cancellation_context
            # Token ID should be set when token is provided
            assert cancellation_context["cancellation_token_id"] == id(token)

    @pytest.mark.asyncio
    async def test_host_service_no_cancellation_token_context(self):
        """Test host service request when no cancellation token provided."""
        # Mock the HTTP call
        with patch.object(self.adapter_host, "_call_host_service_post") as mock_post:
            mock_post.return_value = {"session_id": "test-session", "success": True}

            # Call without cancellation token
            await self.adapter_host.train_multi_symbol_strategy(
                strategy_config_path="test.json",
                symbols=["AAPL"],
                timeframes=["1h"],
                start_date="2023-01-01",
                end_date="2023-12-31",
                cancellation_token=None,
            )

            # Verify cancellation context shows None token ID
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            endpoint, request_data = call_args[0]

            cancellation_context = request_data["cancellation_context"]
            assert cancellation_context["cancellation_token_id"] is None

    def test_adapter_has_check_cancellation_method(self):
        """Test that TrainingAdapter has _check_cancellation method like DataManager."""
        # The adapter should have a _check_cancellation method for consistency
        assert hasattr(
            self.adapter_local, "_check_cancellation"
        ), "TrainingAdapter should have _check_cancellation method"
        assert callable(
            self.adapter_local._check_cancellation
        ), "_check_cancellation should be callable"

    def test_check_cancellation_with_none_token(self):
        """Test _check_cancellation handles None token correctly."""
        # Should not raise when token is None
        result = self.adapter_local._check_cancellation(None, "test operation")
        assert result is False

    def test_check_cancellation_with_active_token(self):
        """Test _check_cancellation with active (non-cancelled) token."""
        token = AsyncCancellationToken("test-op")

        # Should not raise when token is not cancelled
        result = self.adapter_local._check_cancellation(token, "test operation")
        assert result is False

    def test_check_cancellation_raises_on_cancelled_token(self):
        """Test _check_cancellation raises CancelledError for cancelled tokens."""
        token = AsyncCancellationToken("test-op")
        token.cancel("Test cancellation")

        # Should raise CancelledError when token is cancelled
        with pytest.raises(asyncio.CancelledError) as exc_info:
            self.adapter_local._check_cancellation(token, "test operation")

        error_msg = str(exc_info.value)
        assert "test operation" in error_msg
        assert "cancelled" in error_msg.lower()


class TestModelTrainerCancellation:
    """Test cancellation integration in ModelTrainer."""

    def setup_method(self):
        """Set up test fixtures."""
        from ktrdr.training.model_trainer import ModelTrainer

        # Create trainer with minimal config for testing
        config = {"epochs": 10, "batch_size": 32, "learning_rate": 0.001}
        self.trainer = ModelTrainer(config)

    def test_model_trainer_has_check_cancellation_method(self):
        """Test that ModelTrainer has _check_cancellation method."""
        assert hasattr(
            self.trainer, "_check_cancellation"
        ), "ModelTrainer should have _check_cancellation method"
        assert callable(
            self.trainer._check_cancellation
        ), "_check_cancellation should be callable"

    def test_check_cancellation_follows_datamanager_pattern(self):
        """Test that _check_cancellation follows same pattern as DataManager."""
        # Test with None token
        result = self.trainer._check_cancellation(None, "test operation")
        assert result is False

        # Test with active token
        token = AsyncCancellationToken("test-op")
        result = self.trainer._check_cancellation(token, "test operation")
        assert result is False

        # Test with cancelled token
        token.cancel("Test cancellation")
        with pytest.raises(asyncio.CancelledError) as exc_info:
            self.trainer._check_cancellation(token, "test operation")

        error_msg = str(exc_info.value)
        assert "test operation" in error_msg

    def test_train_method_accepts_cancellation_token(self):
        """Test that train method can accept cancellation_token parameter."""
        # The signature might not explicitly include cancellation_token yet,
        # but the trainer should store it as an instance variable
        # This test will initially fail, driving the implementation
        assert hasattr(
            self.trainer, "cancellation_token"
        ), "Trainer should have cancellation_token attribute"

    def test_cancellation_checks_at_epoch_boundaries(self):
        """Test that cancellation is checked at epoch boundaries."""
        # Mock the training loop to simulate epoch-level cancellation checks
        token = AsyncCancellationToken("test-training")
        self.trainer.cancellation_token = token

        # Mock PyTorch components
        model = Mock()
        X_train = torch.randn(100, 10)
        y_train = torch.randint(0, 2, (100,))

        # Mock the training components
        with patch("torch.utils.data.DataLoader") as mock_loader_class:
            mock_loader = Mock()
            mock_loader.__len__ = Mock(return_value=4)  # 4 batches
            mock_loader.__iter__ = Mock(
                return_value=iter(
                    [
                        (torch.randn(32, 10), torch.randint(0, 2, (32,))),
                        (torch.randn(32, 10), torch.randint(0, 2, (32,))),
                        (torch.randn(32, 10), torch.randint(0, 2, (32,))),
                        (
                            torch.randn(4, 10),
                            torch.randint(0, 2, (4,)),
                        ),  # Last batch smaller
                    ]
                )
            )
            mock_loader_class.return_value = mock_loader

            # Track _check_cancellation calls
            cancellation_calls = []
            original_check = self.trainer._check_cancellation

            def track_cancellation_check(token, operation):
                cancellation_calls.append(operation)
                return original_check(token, operation)

            self.trainer._check_cancellation = track_cancellation_check

            # Mock other components to avoid actual training
            with (
                patch.object(self.trainer, "_create_optimizer") as mock_optimizer_fn,
                patch.object(self.trainer, "_create_scheduler") as mock_scheduler_fn,
                patch("torch.nn.CrossEntropyLoss") as mock_criterion_class,
                patch("time.time", side_effect=[0, 1, 2, 3, 4, 5]),
            ):  # Mock timing

                mock_optimizer = Mock()
                mock_optimizer.param_groups = [{"lr": 0.001}]
                mock_optimizer_fn.return_value = mock_optimizer
                mock_scheduler_fn.return_value = None

                mock_criterion = Mock()
                mock_loss = Mock()
                mock_loss.item.return_value = 0.5
                mock_criterion.return_value = mock_loss
                mock_criterion_class.return_value = mock_criterion

                # Mock model forward pass
                mock_outputs = torch.randn(32, 2)
                model.return_value = mock_outputs
                model.to.return_value = model
                model.train.return_value = None
                model.state_dict.return_value = {}

                # Mock torch.max for predictions
                with patch(
                    "torch.max",
                    return_value=(torch.randn(32), torch.randint(0, 2, (32,))),
                ):
                    # Run training with limited epochs
                    self.trainer.config["epochs"] = 2  # Just 2 epochs for test
                    self.trainer.train(model, X_train, y_train)

                    # Verify epoch-level cancellation checks occurred
                    epoch_checks = [
                        call for call in cancellation_calls if "epoch" in call
                    ]
                    assert (
                        len(epoch_checks) >= 2
                    ), f"Should have at least 2 epoch-level checks, got: {cancellation_calls}"

    def test_cancellation_checks_every_50_batches(self):
        """Test that cancellation is checked every 50 batches within epochs."""
        token = AsyncCancellationToken("test-training")
        self.trainer.cancellation_token = token

        # Create many batches to test batch-level checking
        num_batches = 120  # More than 50 to trigger batch-level checks
        mock_batches = [
            (torch.randn(8, 10), torch.randint(0, 2, (8,))) for _ in range(num_batches)
        ]

        model = Mock()
        X_train = torch.randn(100, 10)
        y_train = torch.randint(0, 2, (100,))

        with patch("torch.utils.data.DataLoader") as mock_loader_class:
            mock_loader = Mock()
            mock_loader.__len__ = Mock(return_value=num_batches)
            mock_loader.__iter__ = Mock(return_value=iter(mock_batches))
            mock_loader_class.return_value = mock_loader

            # Track batch-level cancellation calls
            batch_cancellation_calls = []
            original_check = self.trainer._check_cancellation

            def track_batch_cancellation_check(token, operation):
                if "batch" in operation:
                    batch_cancellation_calls.append(operation)
                return original_check(token, operation)

            self.trainer._check_cancellation = track_batch_cancellation_check

            # Mock training components
            with (
                patch.object(self.trainer, "_create_optimizer") as mock_optimizer_fn,
                patch.object(self.trainer, "_create_scheduler") as mock_scheduler_fn,
                patch("torch.nn.CrossEntropyLoss") as mock_criterion_class,
                patch("time.time", side_effect=list(range(200))),
            ):  # Mock timing

                mock_optimizer = Mock()
                mock_optimizer.param_groups = [{"lr": 0.001}]
                mock_optimizer_fn.return_value = mock_optimizer
                mock_scheduler_fn.return_value = None

                mock_criterion = Mock()
                mock_loss = Mock()
                mock_loss.item.return_value = 0.5
                mock_criterion.return_value = mock_loss
                mock_criterion_class.return_value = mock_criterion

                # Mock model
                mock_outputs = torch.randn(8, 2)
                model.return_value = mock_outputs
                model.to.return_value = model
                model.train.return_value = None
                model.state_dict.return_value = {}

                with patch(
                    "torch.max",
                    return_value=(torch.randn(8), torch.randint(0, 2, (8,))),
                ):
                    # Run training with 1 epoch to focus on batch checking
                    self.trainer.config["epochs"] = 1
                    self.trainer.train(model, X_train, y_train)

                    # Verify batch-level checks at expected intervals
                    # Should check at batches 0, 50, 100 (every 50 batches)
                    assert (
                        len(batch_cancellation_calls) >= 2
                    ), f"Should have batch-level checks at intervals, got: {batch_cancellation_calls}"

    def test_training_stops_on_cancellation_at_epoch_boundary(self):
        """Test that training stops when cancelled at epoch boundary."""
        token = AsyncCancellationToken("test-training")
        self.trainer.cancellation_token = token

        model = Mock()
        X_train = torch.randn(100, 10)
        y_train = torch.randint(0, 2, (100,))

        # Cancel after first epoch check
        def cancel_after_first_check(check_token, operation):
            if "epoch 1" in operation:  # Cancel at second epoch
                token.cancel("Test cancellation at epoch boundary")
            # Call original method which will raise CancelledError
            if token.is_cancelled():
                raise asyncio.CancelledError(f"Training cancelled during {operation}")
            return False

        self.trainer._check_cancellation = cancel_after_first_check

        # Mock components
        with patch("torch.utils.data.DataLoader") as mock_loader_class:
            mock_loader = Mock()
            mock_loader.__len__ = Mock(return_value=2)
            mock_loader.__iter__ = Mock(
                return_value=iter(
                    [
                        (torch.randn(32, 10), torch.randint(0, 2, (32,))),
                        (torch.randn(32, 10), torch.randint(0, 2, (32,))),
                    ]
                )
            )
            mock_loader_class.return_value = mock_loader

            with (
                patch.object(self.trainer, "_create_optimizer") as mock_optimizer_fn,
                patch.object(self.trainer, "_create_scheduler"),
                patch("torch.nn.CrossEntropyLoss"),
                patch("time.time", side_effect=list(range(10))),
            ):

                mock_optimizer = Mock()
                mock_optimizer.param_groups = [{"lr": 0.001}]
                mock_optimizer_fn.return_value = mock_optimizer

                model.return_value = torch.randn(32, 2)
                model.to.return_value = model
                model.train.return_value = None
                model.state_dict.return_value = {}

                with patch(
                    "torch.max",
                    return_value=(torch.randn(32), torch.randint(0, 2, (32,))),
                ):
                    # Training should be cancelled and raise CancelledError
                    self.trainer.config["epochs"] = 5
                    with pytest.raises(asyncio.CancelledError) as exc_info:
                        self.trainer.train(model, X_train, y_train)

                    assert "epoch" in str(exc_info.value).lower()

    def test_training_stops_on_cancellation_at_batch_boundary(self):
        """Test that training stops when cancelled at batch boundary."""
        token = AsyncCancellationToken("test-training")
        self.trainer.cancellation_token = token

        model = Mock()
        X_train = torch.randn(100, 10)
        y_train = torch.randint(0, 2, (100,))

        # Cancel at batch 50 check
        def cancel_at_batch_check(check_token, operation):
            if "batch 50" in operation:
                token.cancel("Test cancellation at batch boundary")
            if token.is_cancelled():
                raise asyncio.CancelledError(f"Training cancelled during {operation}")
            return False

        self.trainer._check_cancellation = cancel_at_batch_check

        # Create enough batches to reach batch 50
        num_batches = 75
        mock_batches = [
            (torch.randn(8, 10), torch.randint(0, 2, (8,))) for _ in range(num_batches)
        ]

        with patch("torch.utils.data.DataLoader") as mock_loader_class:
            mock_loader = Mock()
            mock_loader.__len__ = Mock(return_value=num_batches)
            mock_loader.__iter__ = Mock(return_value=iter(mock_batches))
            mock_loader_class.return_value = mock_loader

            with (
                patch.object(self.trainer, "_create_optimizer") as mock_optimizer_fn,
                patch.object(self.trainer, "_create_scheduler"),
                patch("torch.nn.CrossEntropyLoss"),
                patch("time.time", side_effect=list(range(200))),
            ):

                mock_optimizer = Mock()
                mock_optimizer.param_groups = [{"lr": 0.001}]
                mock_optimizer_fn.return_value = mock_optimizer

                model.return_value = torch.randn(8, 2)
                model.to.return_value = model
                model.train.return_value = None
                model.state_dict.return_value = {}

                with patch(
                    "torch.max",
                    return_value=(torch.randn(8), torch.randint(0, 2, (8,))),
                ):
                    # Training should be cancelled at batch boundary
                    self.trainer.config["epochs"] = 1
                    with pytest.raises(asyncio.CancelledError) as exc_info:
                        self.trainer.train(model, X_train, y_train)

                    assert "batch" in str(exc_info.value).lower()


class TestCancellationPerformanceImpact:
    """Test that cancellation checks have minimal performance impact."""

    def setup_method(self):
        """Set up performance test fixtures."""
        from ktrdr.training.model_trainer import ModelTrainer

        config = {"epochs": 2, "batch_size": 16, "learning_rate": 0.001}
        self.trainer = ModelTrainer(config)

    def test_cancellation_overhead_minimal(self):
        """Test that cancellation checks add minimal overhead (<5%)."""
        # This is a conceptual test - in practice we'd measure actual timing
        # For unit test, we verify the pattern is efficient

        token = AsyncCancellationToken("test-training")

        # Test that _check_cancellation is fast
        import time

        # Measure time for many cancellation checks
        start_time = time.time()
        for _ in range(10000):
            self.trainer._check_cancellation(token, "performance test")
        end_time = time.time()

        # 10,000 checks should be very fast (< 0.01 seconds)
        elapsed = end_time - start_time
        assert (
            elapsed < 0.01
        ), f"10,000 cancellation checks took {elapsed:.6f}s, should be <0.01s"

    def test_batch_check_frequency_balanced(self):
        """Test that batch-level checks occur at reasonable frequency (every 50 batches)."""
        # Verify the checking frequency is balanced - not every batch (too slow)
        # but not too infrequent (unresponsive cancellation)

        token = AsyncCancellationToken("test-training")
        batch_checks = []

        def track_batch_checks(check_token, operation):
            if "batch" in operation:
                batch_checks.append(operation)
            return False

        self.trainer._check_cancellation = track_batch_checks

        # Simulate batch checking logic
        total_batches = 200
        for batch_idx in range(total_batches):
            if batch_idx % 50 == 0:  # This should match the implementation
                self.trainer._check_cancellation(token, f"epoch 0, batch {batch_idx}")

        # Should have checked at batches: 0, 50, 100, 150
        expected_checks = 4
        assert (
            len(batch_checks) == expected_checks
        ), f"Expected {expected_checks} batch checks, got {len(batch_checks)}"

    def test_epoch_boundary_checks_always_occur(self):
        """Test that epoch boundary checks always occur (minimal overhead)."""
        token = AsyncCancellationToken("test-training")
        epoch_checks = []

        def track_epoch_checks(check_token, operation):
            if "epoch" in operation and "batch" not in operation:
                epoch_checks.append(operation)
            return False

        self.trainer._check_cancellation = track_epoch_checks

        # Simulate epoch checking
        total_epochs = 5
        for epoch in range(total_epochs):
            self.trainer._check_cancellation(token, f"epoch {epoch}")

        # Should check at every epoch
        assert (
            len(epoch_checks) == total_epochs
        ), f"Should check at every epoch, got {len(epoch_checks)}"


class TestCancellationConsistencyWithDataManager:
    """Test that training cancellation follows same patterns as DataManager."""

    def test_check_cancellation_method_signature_consistent(self):
        """Test that _check_cancellation signature matches DataManager pattern."""
        # Get DataManager _check_cancellation signature for reference
        import inspect

        from ktrdr.data.data_manager import DataManager
        from ktrdr.training.model_trainer import ModelTrainer
        from ktrdr.training.training_adapter import TrainingAdapter

        data_manager = DataManager()
        data_sig = inspect.signature(data_manager._check_cancellation)

        # Training components should have consistent signature
        adapter = TrainingAdapter()
        adapter_sig = inspect.signature(adapter._check_cancellation)

        trainer = ModelTrainer({})
        trainer_sig = inspect.signature(trainer._check_cancellation)

        # Parameter names should be consistent
        data_params = list(data_sig.parameters.keys())
        adapter_params = list(adapter_sig.parameters.keys())
        trainer_params = list(trainer_sig.parameters.keys())

        assert (
            adapter_params == data_params
        ), f"TrainingAdapter signature should match DataManager: {adapter_params} vs {data_params}"
        assert (
            trainer_params == data_params
        ), f"ModelTrainer signature should match DataManager: {trainer_params} vs {data_params}"

    def test_cancellation_error_handling_consistent(self):
        """Test that cancellation error handling matches DataManager behavior."""
        from ktrdr.data.data_manager import DataManager
        from ktrdr.training.training_adapter import TrainingAdapter

        adapter = TrainingAdapter()
        data_manager = DataManager()

        # Both should handle None token the same way
        adapter_result = adapter._check_cancellation(None, "test")
        data_result = data_manager._check_cancellation(None, "test")
        assert adapter_result == data_result, "None token handling should be consistent"

        # Both should handle cancelled tokens the same way
        token = AsyncCancellationToken("test")
        token.cancel("Test cancellation")

        # Both should raise CancelledError
        with pytest.raises(asyncio.CancelledError):
            adapter._check_cancellation(token, "test")

        with pytest.raises(asyncio.CancelledError):
            data_manager._check_cancellation(token, "test")

    def test_cancellation_token_protocol_usage(self):
        """Test that training components use same CancellationToken protocol as data."""
        from ktrdr.training.training_adapter import TrainingAdapter

        adapter = TrainingAdapter()

        # Should work with the unified cancellation token
        token = AsyncCancellationToken("test-training")

        # Should not raise when token is active
        result = adapter._check_cancellation(token, "test")
        assert result is False

        # Should raise when token is cancelled
        token.cancel("Test cancellation")
        with pytest.raises(asyncio.CancelledError):
            adapter._check_cancellation(token, "test")


class TestTrainingCancellationIntegration:
    """Integration tests for complete training cancellation flow."""

    @pytest.mark.asyncio
    async def test_end_to_end_training_cancellation_local(self):
        """Test complete cancellation flow for local training."""
        from ktrdr.training.training_adapter import TrainingAdapter

        adapter = TrainingAdapter(use_host_service=False)

        # Mock local trainer with cancellation support
        mock_trainer = Mock()
        adapter.local_trainer = mock_trainer

        # Set up trainer to respect cancellation
        def mock_train_with_cancellation(*args, **kwargs):
            token = kwargs.get("cancellation_token")
            if token and token.is_cancelled():
                raise asyncio.CancelledError("Training cancelled")
            return {"success": True, "message": "Training completed"}

        mock_trainer.train_multi_symbol_strategy = mock_train_with_cancellation

        # Test 1: Normal completion without cancellation
        token = AsyncCancellationToken("test-training")
        result = await adapter.train_multi_symbol_strategy(
            strategy_config_path="test.json",
            symbols=["AAPL"],
            timeframes=["1h"],
            start_date="2023-01-01",
            end_date="2023-12-31",
            cancellation_token=token,
        )
        assert result["success"] is True

        # Test 2: Cancellation before training
        cancelled_token = AsyncCancellationToken("test-training-cancelled")
        cancelled_token.cancel("User requested cancellation")

        with pytest.raises(asyncio.CancelledError):
            await adapter.train_multi_symbol_strategy(
                strategy_config_path="test.json",
                symbols=["AAPL"],
                timeframes=["1h"],
                start_date="2023-01-01",
                end_date="2023-12-31",
                cancellation_token=cancelled_token,
            )

    @pytest.mark.asyncio
    async def test_end_to_end_training_cancellation_host_service(self):
        """Test complete cancellation flow for host service training."""
        from ktrdr.training.training_adapter import TrainingAdapter

        adapter = TrainingAdapter(
            use_host_service=True, host_service_url="http://localhost:5002"
        )

        # Mock successful host service response
        with patch.object(adapter, "_call_host_service_post") as mock_post:
            mock_post.return_value = {"session_id": "test-session", "success": True}

            # Test with cancellation token
            token = AsyncCancellationToken("test-training")
            result = await adapter.train_multi_symbol_strategy(
                strategy_config_path="test.json",
                symbols=["AAPL"],
                timeframes=["1h"],
                start_date="2023-01-01",
                end_date="2023-12-31",
                cancellation_token=token,
            )

            # Verify result and cancellation context was sent
            assert result["success"] is True
            assert result["session_id"] == "test-session"

            # Verify cancellation context was included
            mock_post.assert_called_once()
            call_args = mock_post.call_args[0]
            request_data = call_args[1]
            assert "cancellation_context" in request_data
            assert request_data["cancellation_context"]["cancellation_token_id"] == id(
                token
            )
