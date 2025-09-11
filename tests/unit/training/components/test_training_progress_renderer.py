"""
Comprehensive tests for TrainingProgressRenderer.

Tests all functionality required by SLICE-3 Task 3.2 including:
- ProgressRenderer interface compliance
- Training context formatting with smart truncation
- Multi-symbol/timeframe scenarios with readability
- Both coarse (epoch) and fine (batch) progress
- Context includes model type, symbols, timeframes, epochs, batches
"""

import threading
import time

from ktrdr.async_infrastructure.progress import GenericProgressState, ProgressRenderer


class TestTrainingProgressRenderer:
    """Test suite for TrainingProgressRenderer functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Import here to test the module exists
        from ktrdr.training.components.training_progress_renderer import (
            TrainingProgressRenderer,
        )

        self.TrainingProgressRenderer = TrainingProgressRenderer

    def test_progress_renderer_interface_compliance(self):
        """Test that TrainingProgressRenderer implements ProgressRenderer interface."""
        renderer = self.TrainingProgressRenderer()

        # Should implement ProgressRenderer
        assert isinstance(renderer, ProgressRenderer)

        # Should have required methods
        assert hasattr(renderer, "render_message")
        assert hasattr(renderer, "enhance_state")
        assert callable(renderer.render_message)
        assert callable(renderer.enhance_state)

    def test_initialization_default(self):
        """Test initialization with default parameters."""
        renderer = self.TrainingProgressRenderer()

        # Should have default values
        assert hasattr(renderer, "_current_context")
        assert renderer._current_context == {}

    def test_render_message_basic_training_context(self):
        """Test basic training message rendering with minimal context."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_mlp_model",
            current_step=1,
            total_steps=4,
            percentage=25.0,
            message="Training model",
            context={
                "model_type": "MLP",
                "symbols": ["AAPL"],
                "timeframes": ["1H"],
                "current_epoch": 5,
                "total_epochs": 50,
                "current_batch": 100,
                "total_batches": 500,
            },
        )

        message = renderer.render_message(state)

        # Should include training-specific elements
        assert "Training MLP model" in message
        assert "AAPL" in message
        assert "[1H]" in message
        assert "[epoch 5/50]" in message
        assert "(batch 100/500)" in message
        assert "[1/4]" in message  # Step progress

    def test_render_message_single_symbol_format(self):
        """Test single symbol training message format."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=2,
            total_steps=4,
            percentage=50.0,
            message="Training",
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

        # Expected: "Training MLP model on AAPL [1H] [epoch 15/50] (batch 342/500) [2/4]"
        assert (
            "Training MLP model on AAPL [1H] [epoch 15/50] (batch 342/500) [2/4]"
            in message
        )

    def test_render_message_multi_symbol_no_truncation(self):
        """Test multi-symbol training message without truncation (2 symbols)."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=3,
            total_steps=4,
            percentage=75.0,
            message="Training",
            context={
                "model_type": "MLP",
                "symbols": ["AAPL", "MSFT"],
                "timeframes": ["1H", "4H"],
                "current_epoch": 15,
                "total_epochs": 50,
                "current_batch": 0,  # No current batch
                "total_batches": 0,
            },
        )

        message = renderer.render_message(state)

        # Expected: "Training MLP model on AAPL, MSFT [1H, 4H] [epoch 15/50] [3/4]"
        assert (
            "Training MLP model on AAPL, MSFT [1H, 4H] [epoch 15/50] [3/4]" in message
        )
        # Should not include batch info when totals are 0
        assert "batch" not in message

    def test_render_message_multi_symbol_with_truncation(self):
        """Test multi-symbol training message with smart truncation."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=1,
            total_steps=4,
            percentage=25.0,
            message="Training",
            context={
                "model_type": "CNN",
                "symbols": ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"],  # 5 symbols
                "timeframes": ["1H", "4H", "1D"],  # 3 timeframes
                "current_epoch": 8,
                "total_epochs": 20,
                "current_batch": 156,
                "total_batches": 800,
            },
        )

        message = renderer.render_message(state)

        # Expected: "Training CNN model on AAPL, MSFT (+3 more) [1H, 4H (+1 more)] [epoch 8/20] (batch 156/800) [1/4]"
        assert "Training CNN model" in message
        assert "AAPL, MSFT (+3 more)" in message  # Smart truncation for symbols
        assert "[1H, 4H (+1 more)]" in message  # Smart truncation for timeframes
        assert "[epoch 8/20]" in message
        assert "(batch 156/800)" in message
        assert "[1/4]" in message

    def test_render_message_different_model_types(self):
        """Test rendering with different model types."""
        renderer = self.TrainingProgressRenderer()

        model_types = ["MLP", "CNN", "LSTM", "GRU", "Transformer"]

        for model_type in model_types:
            state = GenericProgressState(
                operation_id="train_model",
                current_step=1,
                total_steps=4,
                percentage=25.0,
                message="Training",
                context={
                    "model_type": model_type,
                    "symbols": ["AAPL"],
                    "timeframes": ["5M"],
                    "current_epoch": 1,
                    "total_epochs": 10,
                },
            )

            message = renderer.render_message(state)
            assert f"Training {model_type} model" in message

    def test_render_message_missing_context_graceful_handling(self):
        """Test graceful handling of missing context fields."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=1,
            total_steps=4,
            percentage=25.0,
            message="Training",
            context={
                # Missing most fields - should handle gracefully
                "model_type": "MLP",
            },
        )

        message = renderer.render_message(state)

        # Should still render something meaningful
        assert "Training MLP model" in message
        assert "[1/4]" in message  # Step progress should always be there

    def test_render_message_no_context(self):
        """Test rendering with completely empty context."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=1,
            total_steps=4,
            percentage=25.0,
            message="Training",
            context={},
        )

        message = renderer.render_message(state)

        # Should render a basic message with unknown model
        assert "Training unknown model" in message or "Training" in message
        assert "[1/4]" in message

    def test_enhance_state_basic_functionality(self):
        """Test basic state enhancement functionality."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=1,
            total_steps=4,
            percentage=25.0,
            message="Training",
            context={
                "model_type": "MLP",
                "symbols": ["AAPL"],
                "current_epoch": 5,
                "total_epochs": 50,
            },
        )

        enhanced_state = renderer.enhance_state(state)

        # Should preserve original state
        assert enhanced_state.operation_id == state.operation_id
        assert enhanced_state.current_step == state.current_step
        assert enhanced_state.percentage == state.percentage

        # Should maintain or enhance context
        assert enhanced_state.context is not None

    def test_enhance_state_context_preservation(self):
        """Test that enhance_state preserves and enhances context properly."""
        renderer = self.TrainingProgressRenderer()
        original_context = {
            "model_type": "CNN",
            "symbols": ["AAPL", "MSFT"],
            "timeframes": ["1H"],
            "current_epoch": 10,
            "total_epochs": 50,
            "current_batch": 200,
            "total_batches": 1000,
        }

        state = GenericProgressState(
            operation_id="train_model",
            current_step=1,
            total_steps=4,
            percentage=25.0,
            message="Training",
            context=original_context.copy(),
        )

        enhanced_state = renderer.enhance_state(state)

        # Should preserve all original context
        for key, value in original_context.items():
            assert enhanced_state.context[key] == value

    def test_thread_safety_message_rendering(self):
        """Test thread safety of message rendering operations."""
        renderer = self.TrainingProgressRenderer()
        results = []
        errors = []

        def render_messages():
            try:
                for i in range(10):
                    state = GenericProgressState(
                        operation_id=f"train_model_{i}",
                        current_step=i + 1,
                        total_steps=10,
                        percentage=(i + 1) * 10,
                        message=f"Training model {i}",
                        context={
                            "model_type": "MLP",
                            "symbols": ["AAPL"],
                            "timeframes": ["1H"],
                            "current_epoch": i + 1,
                            "total_epochs": 20,
                        },
                    )
                    message = renderer.render_message(state)
                    results.append(message)
                    time.sleep(0.001)  # Small delay to encourage race conditions
            except Exception as e:
                errors.append(e)

        # Run multiple threads concurrently
        threads = [threading.Thread(target=render_messages) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should not have any errors
        assert len(errors) == 0, f"Thread safety errors: {errors}"

        # Should have rendered all messages
        assert len(results) == 30  # 3 threads * 10 messages each

        # All messages should contain expected patterns
        for message in results:
            assert "Training MLP model" in message
            assert "AAPL" in message
            assert "[1H]" in message
            assert "epoch" in message

    def test_thread_safety_state_enhancement(self):
        """Test thread safety of state enhancement operations."""
        renderer = self.TrainingProgressRenderer()
        results = []
        errors = []

        def enhance_states():
            try:
                for i in range(10):
                    state = GenericProgressState(
                        operation_id=f"enhance_test_{i}",
                        current_step=i + 1,
                        total_steps=10,
                        percentage=(i + 1) * 10,
                        message=f"Enhancement test {i}",
                        context={
                            "model_type": "CNN",
                            "test_id": i,
                            "current_epoch": i,
                            "total_epochs": 10,
                        },
                    )
                    enhanced = renderer.enhance_state(state)
                    results.append(enhanced.operation_id)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        # Run multiple threads
        threads = [threading.Thread(target=enhance_states) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should not have errors
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(results) == 30

    def test_smart_truncation_edge_cases(self):
        """Test smart truncation with edge cases."""
        renderer = self.TrainingProgressRenderer()

        # Test exactly 3 symbols (boundary case)
        state = GenericProgressState(
            operation_id="train_model",
            current_step=1,
            total_steps=4,
            percentage=25.0,
            message="Training",
            context={
                "model_type": "MLP",
                "symbols": ["AAPL", "MSFT", "GOOGL"],  # Exactly 3
                "timeframes": ["1H", "4H"],  # Exactly 2
                "current_epoch": 5,
                "total_epochs": 50,
            },
        )

        message = renderer.render_message(state)

        # With 3 symbols, should not truncate yet (show all 3)
        assert "AAPL, MSFT, GOOGL" in message
        # With 2 timeframes, should not truncate
        assert "[1H, 4H]" in message

    def test_coverage_requirements(self):
        """Test that we achieve high coverage requirement."""
        renderer = self.TrainingProgressRenderer()

        # Test all public methods exist and are callable
        assert callable(renderer.render_message)
        assert callable(renderer.enhance_state)

        # Test attributes exist
        assert hasattr(renderer, "_current_context")

        # Test various message formats work
        contexts = [
            {"model_type": "MLP"},
            {"model_type": "CNN", "symbols": ["AAPL"]},
            {"model_type": "LSTM", "symbols": ["AAPL", "MSFT"], "timeframes": ["1H"]},
            {
                "model_type": "GRU",
                "symbols": ["AAPL", "MSFT", "GOOGL", "TSLA"],
                "timeframes": ["1H", "4H", "1D"],
                "current_epoch": 10,
                "total_epochs": 50,
                "current_batch": 500,
                "total_batches": 1000,
            },
        ]

        for context in contexts:
            state = GenericProgressState(
                operation_id="test",
                current_step=1,
                total_steps=4,
                percentage=25.0,
                message="Testing",
                context=context,
            )

            # Both methods should work without error
            message = renderer.render_message(state)
            enhanced = renderer.enhance_state(state)

            assert isinstance(message, str)
            assert len(message) > 0
            assert enhanced is not None

    def test_preserve_training_message_formats(self):
        """Test that training message formats match specification examples."""
        renderer = self.TrainingProgressRenderer()

        # Test case 1: Single symbol format
        state1 = GenericProgressState(
            operation_id="train_model",
            current_step=2,
            total_steps=4,
            percentage=50.0,
            message="Training",
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
        # Expected: "Training MLP model on AAPL [1H] [epoch 15/50] (batch 342/500) [2/4]"
        expected_elements1 = [
            "Training MLP model on AAPL",
            "[1H]",
            "[epoch 15/50]",
            "(batch 342/500)",
            "[2/4]",
        ]
        for element in expected_elements1:
            assert element in message1, f"Missing '{element}' in: {message1}"

        # Test case 2: Multi-symbol with truncation
        state2 = GenericProgressState(
            operation_id="train_model",
            current_step=3,
            total_steps=4,
            percentage=75.0,
            message="Training",
            context={
                "model_type": "MLP",
                "symbols": ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"],
                "timeframes": ["1H", "4H"],
                "current_epoch": 15,
                "total_epochs": 50,
            },
        )

        message2 = renderer.render_message(state2)
        # Expected: "Training MLP model on AAPL, MSFT (+3 more) [1H, 4H] [epoch 15/50] [3/4]"
        expected_elements2 = [
            "Training MLP model on AAPL, MSFT (+3 more)",
            "[1H, 4H]",
            "[epoch 15/50]",
            "[3/4]",
        ]
        for element in expected_elements2:
            assert element in message2, f"Missing '{element}' in: {message2}"

        # Test case 3: Different model type
        state3 = GenericProgressState(
            operation_id="train_model",
            current_step=1,
            total_steps=4,
            percentage=25.0,
            message="Training",
            context={
                "model_type": "CNN",
                "symbols": ["TSLA"],
                "timeframes": ["5M"],
                "current_epoch": 8,
                "total_epochs": 20,
                "current_batch": 156,
                "total_batches": 800,
            },
        )

        message3 = renderer.render_message(state3)
        # Expected: "Training CNN model on TSLA [5M] [epoch 8/20] (batch 156/800) [1/4]"
        expected_elements3 = [
            "Training CNN model on TSLA",
            "[5M]",
            "[epoch 8/20]",
            "(batch 156/800)",
            "[1/4]",
        ]
        for element in expected_elements3:
            assert element in message3, f"Missing '{element}' in: {message3}"
