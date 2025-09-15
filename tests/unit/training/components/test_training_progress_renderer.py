"""
Comprehensive tests for TrainingProgressRenderer.

Tests all TrainingProgressRenderer features following the DataProgressRenderer pattern,
including ServiceOrchestrator integration, training-specific context, and message formatting.

Following TDD methodology - these tests define the expected behavior for Task 3.2.
"""

import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

from ktrdr.async_infrastructure.progress import GenericProgressState, ProgressRenderer
from ktrdr.async_infrastructure.time_estimation import TimeEstimationEngine


class TestTrainingProgressRenderer:
    """Test suite for TrainingProgressRenderer functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Import here to test the module exists
        from ktrdr.training.components.training_progress_renderer import (
            TrainingProgressRenderer,
        )

        self.TrainingProgressRenderer = TrainingProgressRenderer

        # Create mock time estimation engine
        self.mock_time_estimator = Mock(spec=TimeEstimationEngine)
        self.mock_time_estimator.estimate_duration.return_value = 60.0  # 60 seconds

    def test_progress_renderer_interface_compliance(self):
        """Test that TrainingProgressRenderer implements ProgressRenderer interface."""
        renderer = self.TrainingProgressRenderer()

        # Should implement ProgressRenderer (like DataProgressRenderer)
        assert isinstance(renderer, ProgressRenderer)

        # Should have required methods
        assert hasattr(renderer, "render_message")
        assert hasattr(renderer, "enhance_state")
        assert callable(renderer.render_message)
        assert callable(renderer.enhance_state)

    def test_initialization_follows_data_progress_renderer_pattern(self):
        """Test initialization follows exact DataProgressRenderer pattern."""
        renderer = self.TrainingProgressRenderer(
            time_estimation_engine=self.mock_time_estimator,
            enable_hierarchical_progress=True,
        )

        # Should follow DataProgressRenderer pattern exactly
        assert renderer.time_estimator is self.mock_time_estimator
        assert renderer.enable_hierarchical is True
        assert renderer._operation_start_time is None
        assert renderer._operation_type is None
        assert isinstance(renderer._current_context, dict)

    def test_initialization_without_time_estimation(self):
        """Test initialization without TimeEstimationEngine (like DataProgressRenderer)."""
        renderer = self.TrainingProgressRenderer()

        assert renderer.time_estimator is None
        assert renderer.enable_hierarchical is True  # Default value

    def test_render_message_basic_training_functionality(self):
        """Test basic training message rendering without context."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_mlp_model",
            current_step=5,
            total_steps=50,
            percentage=10.0,
            message="Training epoch",
        )

        message = renderer.render_message(state)

        # Should include step progress (like DataProgressRenderer)
        assert "Training epoch" in message
        # Should include progress information
        assert "10.0%" in message or "[5/50]" in message or "5/50" in message

    def test_render_message_with_training_context(self):
        """Test message rendering with training-specific context."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_multi_symbol_strategy",
            current_step=15,
            total_steps=50,
            percentage=30.0,
            message="Training MLP model",
            context={
                "model_type": "MLP",
                "symbols": ["AAPL"],
                "timeframes": ["1H"],
                "current_epoch": 15,
                "total_epochs": 50,
                "current_batch": 342,
                "total_batches": 500,
            },
        )

        message = renderer.render_message(state)

        # Should include training-specific context (following task requirements)
        assert "Training MLP model" in message
        # Should include symbol and timeframe like data renderer does
        assert "AAPL" in message
        assert "1H" in message or "[1H]" in message
        # Should include epoch information (training-specific)
        assert "15" in message  # Current epoch
        assert "50" in message  # Total epochs

    def test_render_message_multi_symbol_smart_truncation(self):
        """Test multi-symbol scenario with smart truncation (task requirement)."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_multi_symbol_strategy",
            current_step=15,
            total_steps=50,
            percentage=30.0,
            message="Training MLP model",
            context={
                "model_type": "MLP",
                "symbols": ["AAPL", "MSFT", "TSLA", "GOOGL", "AMZN"],  # 5 symbols
                "timeframes": ["1H", "4H"],
                "current_epoch": 15,
                "total_epochs": 50,
            },
        )

        message = renderer.render_message(state)

        # Should handle multi-symbol truncation smartly
        assert "Training MLP model" in message
        # Should show truncation for many symbols (like "AAPL, MSFT (+3 more)")
        symbol_count = len(
            [s for s in ["AAPL", "MSFT", "TSLA", "GOOGL", "AMZN"] if s in message]
        )
        # Should either show limited symbols or indicate "+N more"
        assert symbol_count <= 3 or "+2 more" in message or "+3 more" in message

    def test_render_message_multi_timeframe_smart_truncation(self):
        """Test multi-timeframe scenario with smart truncation (task requirement)."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_multi_timeframe_strategy",
            current_step=10,
            total_steps=30,
            percentage=33.3,
            message="Training CNN model",
            context={
                "model_type": "CNN",
                "symbols": ["TSLA"],
                "timeframes": ["5m", "15m", "1H", "4H", "1D"],  # 5 timeframes
                "current_epoch": 8,
                "total_epochs": 20,
            },
        )

        message = renderer.render_message(state)

        # Should handle multi-timeframe truncation
        assert "Training CNN model" in message
        assert "TSLA" in message
        # Should show timeframe information efficiently
        tf_count = len([tf for tf in ["5m", "15m", "1H", "4H", "1D"] if tf in message])
        assert tf_count <= 3 or "+" in message  # Truncated display

    def test_render_message_includes_epoch_and_batch_progress(self):
        """Test that training messages include both epoch and batch progress (task requirement)."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=1,
            total_steps=1,
            percentage=50.0,
            message="Training epoch",
            context={
                "model_type": "LSTM",
                "symbols": ["AAPL"],
                "timeframes": ["1H"],
                "current_epoch": 8,
                "total_epochs": 20,
                "current_batch": 156,
                "total_batches": 800,
            },
        )

        message = renderer.render_message(state)

        # Should include both coarse (epoch) and fine (batch) progress information
        assert "8" in message  # Current epoch
        assert "20" in message  # Total epochs
        # Should include batch progress for fine-grained tracking
        assert "156" in message or "batch" in message.lower()

    def test_render_message_different_model_types(self):
        """Test rendering with different model types (MLP, CNN, LSTM)."""
        renderer = self.TrainingProgressRenderer()

        model_types = ["MLP", "CNN", "LSTM", "Transformer"]
        for model_type in model_types:
            state = GenericProgressState(
                operation_id=f"train_{model_type.lower()}_model",
                current_step=1,
                total_steps=10,
                percentage=10.0,
                message=f"Training {model_type} model",
                context={
                    "model_type": model_type,
                    "symbols": ["AAPL"],
                    "timeframes": ["1H"],
                    "current_epoch": 5,
                    "total_epochs": 50,
                },
            )

            message = renderer.render_message(state)

            # Should include model type in message
            assert model_type in message
            assert "AAPL" in message

    def test_enhance_state_follows_data_progress_renderer_pattern(self):
        """Test state enhancement follows DataProgressRenderer pattern exactly."""
        renderer = self.TrainingProgressRenderer(
            time_estimation_engine=self.mock_time_estimator,
            enable_hierarchical_progress=True,
        )

        # Simulate training operation start
        state = GenericProgressState(
            operation_id="train_multi_symbol_strategy",
            current_step=0,
            total_steps=50,
            percentage=0.0,
            message="Starting training",
            context={
                "model_type": "MLP",
                "symbols": ["AAPL", "MSFT"],
                "timeframes": ["1H"],
            },
        )

        enhanced_state = renderer.enhance_state(state)

        # Should preserve original state (like DataProgressRenderer)
        assert enhanced_state.operation_id == state.operation_id
        assert enhanced_state.context["model_type"] == "MLP"
        assert enhanced_state.context["symbols"] == ["AAPL", "MSFT"]

        # Should track operation start time (like DataProgressRenderer)
        assert renderer._operation_start_time is not None
        assert renderer._operation_type == "train_multi_symbol_strategy"

    def test_enhance_state_with_time_estimation(self):
        """Test state enhancement with time estimation (following DataProgressRenderer)."""
        renderer = self.TrainingProgressRenderer(
            time_estimation_engine=self.mock_time_estimator
        )

        # Simulate training in progress
        start_time = datetime.now() - timedelta(minutes=10)  # 10 minutes elapsed
        state = GenericProgressState(
            operation_id="train_model",
            current_step=15,
            total_steps=50,
            percentage=30.0,  # 30% complete
            message="Training in progress",
            start_time=start_time,
            context={
                "model_type": "MLP",
                "symbols": ["AAPL"],
                "current_epoch": 15,
                "total_epochs": 50,
            },
        )

        # Set up renderer state as if operation started
        renderer._operation_start_time = start_time
        renderer._operation_type = "train_model"

        enhanced_state = renderer.enhance_state(state)

        # Should have calculated estimated remaining time (like DataProgressRenderer)
        # 10 minutes elapsed at 30% = ~23 minutes remaining
        assert enhanced_state.estimated_remaining is not None
        remaining_minutes = enhanced_state.estimated_remaining.total_seconds() / 60
        assert (
            15 <= remaining_minutes <= 35
        )  # Reasonable range for 30% at 10min elapsed

    def test_service_orchestrator_integration_automatic(self):
        """Test automatic ServiceOrchestrator integration (task requirement)."""
        renderer = self.TrainingProgressRenderer()

        # Test that renderer can handle ServiceOrchestrator progress callbacks
        state = GenericProgressState(
            operation_id="train_strategy",
            current_step=1,
            total_steps=1,
            percentage=0.0,
            message="Training started",
            context={
                "model_type": "MLP",
                "symbols": ["AAPL"],
                "timeframes": ["1H"],
                "current_epoch": 1,
                "total_epochs": 50,
            },
        )

        # Should handle ServiceOrchestrator state without errors
        try:
            enhanced_state = renderer.enhance_state(state)
            renderer.render_message(enhanced_state)
            # If we get here, integration works
            assert True
        except Exception as e:
            pytest.fail(f"ServiceOrchestrator integration failed: {e}")

    def test_cli_structured_progress_elimination_of_string_parsing(self):
        """Test that renderer provides structured context eliminating CLI string parsing."""
        renderer = self.TrainingProgressRenderer()

        state = GenericProgressState(
            operation_id="train_model",
            current_step=15,
            total_steps=50,
            percentage=30.0,
            message="Training epoch",
            context={
                "model_type": "MLP",
                "symbols": ["AAPL", "MSFT"],
                "timeframes": ["1H", "4H"],
                "current_epoch": 15,
                "total_epochs": 50,
                "current_batch": 342,
                "total_batches": 500,
            },
        )

        enhanced_state = renderer.enhance_state(state)

        # CLI should be able to access structured data directly (no parsing needed)
        context = enhanced_state.context

        # Should have clean, structured data access
        assert context["model_type"] == "MLP"
        assert context["symbols"] == ["AAPL", "MSFT"]
        assert context["timeframes"] == ["1H", "4H"]
        assert context["current_epoch"] == 15
        assert context["total_epochs"] == 50
        assert context["current_batch"] == 342
        assert context["total_batches"] == 500

        # This eliminates the need for 50+ lines of brittle string parsing

    def test_progress_format_examples_from_task_spec(self):
        """Test progress format examples from task specification."""
        renderer = self.TrainingProgressRenderer()

        # Test case 1: Single symbol format
        # Expected: "Training MLP model on AAPL [1H] [epoch 15/50] (batch 342/500)"
        state1 = GenericProgressState(
            operation_id="train_single_symbol",
            current_step=15,
            total_steps=50,
            percentage=30.0,
            message="Training MLP model",
            context={
                "model_type": "MLP",
                "symbols": ["AAPL"],
                "timeframes": ["1H"],
                "current_epoch": 15,
                "total_epochs": 50,
                "current_batch": 342,
                "total_batches": 500,
            },
        )

        message1 = renderer.render_message(state1)
        # Should contain all required elements
        assert "MLP" in message1
        assert "AAPL" in message1
        assert "1H" in message1 or "[1H]" in message1
        assert "15" in message1 and "50" in message1  # epoch progress
        assert "342" in message1 or "batch" in message1.lower()  # batch info

        # Test case 2: Multi-symbol format
        # Expected: "Training MLP model on AAPL, MSFT (+2 more) [1H, 4H] [epoch 15/50]"
        state2 = GenericProgressState(
            operation_id="train_multi_symbol",
            current_step=15,
            total_steps=50,
            percentage=30.0,
            message="Training MLP model",
            context={
                "model_type": "MLP",
                "symbols": ["AAPL", "MSFT", "TSLA", "GOOGL"],  # 4 symbols
                "timeframes": ["1H", "4H"],
                "current_epoch": 15,
                "total_epochs": 50,
            },
        )

        message2 = renderer.render_message(state2)
        # Should handle multi-symbol display with truncation
        assert "MLP" in message2
        # Should show some symbols (not necessarily all)
        symbol_mentioned = any(symbol in message2 for symbol in ["AAPL", "MSFT"])
        assert symbol_mentioned

        # Test case 3: Different model type
        # Expected: "Training CNN model on TSLA [5m] [epoch 8/20] (batch 156/800)"
        state3 = GenericProgressState(
            operation_id="train_cnn_model",
            current_step=8,
            total_steps=20,
            percentage=40.0,
            message="Training CNN model",
            context={
                "model_type": "CNN",
                "symbols": ["TSLA"],
                "timeframes": ["5m"],
                "current_epoch": 8,
                "total_epochs": 20,
                "current_batch": 156,
                "total_batches": 800,
            },
        )

        message3 = renderer.render_message(state3)
        assert "CNN" in message3
        assert "TSLA" in message3
        assert "5m" in message3
        assert "8" in message3 and "20" in message3  # epoch progress

    def test_thread_safety_training_message_rendering(self):
        """Test thread safety of training message rendering (like DataProgressRenderer)."""
        renderer = self.TrainingProgressRenderer()
        results = []
        errors = []

        def render_training_messages():
            try:
                for i in range(10):
                    state = GenericProgressState(
                        operation_id=f"train_thread_test_{i}",
                        current_step=i,
                        total_steps=10,
                        percentage=i * 10,
                        message=f"Training epoch {i}",
                        context={
                            "model_type": "MLP",
                            "symbols": ["AAPL"],
                            "timeframes": ["1H"],
                            "current_epoch": i,
                            "total_epochs": 10,
                        },
                    )
                    message = renderer.render_message(state)
                    results.append(message)
                    time.sleep(0.001)  # Small delay to encourage race conditions
            except Exception as e:
                errors.append(e)

        # Run multiple threads concurrently
        threads = [threading.Thread(target=render_training_messages) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should not have any errors
        assert len(errors) == 0, f"Thread safety errors: {errors}"

        # Should have rendered all messages
        assert len(results) == 30  # 3 threads * 10 messages each

        # All messages should contain expected training patterns
        for message in results:
            assert "MLP" in message or "AAPL" in message or "Training" in message

    def test_time_estimation_engine_integration_training(self):
        """Test TimeEstimationEngine integration for training operations."""
        # Create real TimeEstimationEngine for integration test
        cache_file = Path("/tmp/test_training_progress_cache.pkl")
        if cache_file.exists():
            cache_file.unlink()

        time_estimator = TimeEstimationEngine(cache_file)
        renderer = self.TrainingProgressRenderer(time_estimation_engine=time_estimator)

        # First training operation - no history
        state1 = GenericProgressState(
            operation_id="train_model",
            current_step=0,
            total_steps=50,
            percentage=0.0,
            message="Starting training",
            context={
                "model_type": "MLP",
                "symbols": ["AAPL"],
                "timeframes": ["1H"],
                "current_epoch": 0,
                "total_epochs": 50,
            },
        )

        enhanced1 = renderer.enhance_state(state1)
        # No time estimation yet (no history)
        assert enhanced1.estimated_remaining is None

        # Simulate training in progress after some time
        renderer._operation_start_time = datetime.now() - timedelta(minutes=5)
        state2 = GenericProgressState(
            operation_id="train_model",
            current_step=10,
            total_steps=50,
            percentage=20.0,
            message="Training in progress",
            context=state1.context,
        )

        enhanced2 = renderer.enhance_state(state2)
        # Should have time estimation based on current progress
        assert enhanced2.estimated_remaining is not None

        # Clean up
        if cache_file.exists():
            cache_file.unlink()

    def test_follows_exact_data_progress_renderer_pattern(self):
        """Test that TrainingProgressRenderer follows exact DataProgressRenderer pattern."""
        renderer = self.TrainingProgressRenderer(
            time_estimation_engine=self.mock_time_estimator,
            enable_hierarchical_progress=True,
        )

        # Should have same attributes as DataProgressRenderer
        assert hasattr(renderer, "time_estimator")
        assert hasattr(renderer, "enable_hierarchical")
        assert hasattr(renderer, "_current_context")
        assert hasattr(renderer, "_operation_start_time")
        assert hasattr(renderer, "_operation_type")

        # Should have same method signatures as DataProgressRenderer
        assert callable(renderer.render_message)
        assert callable(renderer.enhance_state)

        # Should follow same initialization pattern
        assert renderer.time_estimator is self.mock_time_estimator
        assert renderer.enable_hierarchical is True
        assert isinstance(renderer._current_context, dict)

    def test_coverage_requirements_training_specific(self):
        """Test comprehensive coverage of training-specific functionality."""
        renderer = self.TrainingProgressRenderer(
            time_estimation_engine=self.mock_time_estimator,
            enable_hierarchical_progress=True,
        )

        # Test all training-specific methods exist
        assert callable(renderer.render_message)
        assert callable(renderer.enhance_state)

        # Test training-specific attributes
        assert hasattr(renderer, "time_estimator")
        assert hasattr(renderer, "enable_hierarchical")
        assert hasattr(renderer, "_current_context")

        # Should handle training context properly
        training_context = {
            "model_type": "MLP",
            "symbols": ["AAPL", "MSFT"],
            "timeframes": ["1H", "4H"],
            "current_epoch": 15,
            "total_epochs": 50,
            "current_batch": 342,
            "total_batches": 500,
        }

        state = GenericProgressState(
            operation_id="comprehensive_test",
            current_step=1,
            total_steps=1,
            percentage=30.0,
            message="Training test",
            context=training_context,
        )

        # Should handle all context elements without errors
        try:
            enhanced_state = renderer.enhance_state(state)
            message = renderer.render_message(enhanced_state)
            assert "Training test" in message
            assert True  # If we get here, comprehensive handling works
        except Exception as e:
            pytest.fail(f"Comprehensive training context handling failed: {e}")
