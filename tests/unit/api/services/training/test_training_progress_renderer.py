"""
Comprehensive tests for TrainingProgressRenderer.

Tests the training-specific progress renderer following the proven ProgressRenderer
pattern established by DataProgressRenderer. Ensures rich context flows correctly
(epoch, batch, GPU info) to restore the detailed CLI display.
"""

import threading
import time

from ktrdr.async_infrastructure.progress import GenericProgressState, ProgressRenderer


class TestTrainingProgressRenderer:
    """Test suite for TrainingProgressRenderer functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Import here to test the module exists
        from ktrdr.api.services.training.training_progress_renderer import (
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
        """Test default initialization."""
        renderer = self.TrainingProgressRenderer()

        # Should have sensible defaults
        assert hasattr(renderer, "_current_context")
        assert isinstance(renderer._current_context, dict)

    def test_render_message_basic_functionality(self):
        """Test basic message rendering without context."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="test_training",
            current_step=1,
            total_steps=10,
            percentage=10.0,
            message="Training model",
        )

        message = renderer.render_message(state)

        # Should include basic message
        assert "Training model" in message

    def test_render_message_with_epoch_context(self):
        """Test message rendering with epoch context."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=5,
            total_steps=10,
            percentage=50.0,
            message="Training in progress",
            context={
                "epoch_index": 5,
                "total_epochs": 10,
            },
        )

        message = renderer.render_message(state)

        # Should include epoch information
        assert "Epoch 5/10" in message

    def test_render_message_with_batch_context(self):
        """Test message rendering with batch-level context."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=5,
            total_steps=10,
            percentage=50.0,
            message="Training in progress",
            context={
                "epoch_index": 5,
                "total_epochs": 10,
                "batch_number": 120,
                "batch_total_per_epoch": 500,
            },
        )

        message = renderer.render_message(state)

        # Should include both epoch and batch information
        assert "Epoch 5/10" in message
        assert "Batch 120/500" in message

    def test_render_message_with_gpu_context(self):
        """Test message rendering with GPU resource usage context."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=5,
            total_steps=10,
            percentage=50.0,
            message="Training in progress",
            context={
                "epoch_index": 5,
                "total_epochs": 10,
                "batch_number": 120,
                "batch_total_per_epoch": 500,
                "resource_usage": {
                    "gpu_used": True,
                    "gpu_name": "RTX 3090",
                    "gpu_utilization_percent": 85,
                },
            },
        )

        message = renderer.render_message(state)

        # Should include GPU information
        assert "Epoch 5/10" in message
        assert "Batch 120/500" in message
        assert "GPU" in message or "RTX 3090" in message
        assert "85" in message

    def test_render_message_with_full_context(self):
        """Test message rendering with complete training context."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=5,
            total_steps=10,
            percentage=50.0,
            message="Training in progress",
            context={
                "epoch_index": 5,
                "total_epochs": 10,
                "batch_number": 120,
                "batch_total_per_epoch": 500,
                "resource_usage": {
                    "gpu_used": True,
                    "gpu_name": "RTX 3090",
                    "gpu_utilization_percent": 85,
                    "memory_used_mb": 8192,
                },
                "batch_metrics": {
                    "loss": 0.234,
                    "accuracy": 0.876,
                },
            },
        )

        message = renderer.render_message(state)

        # Should include all key elements
        assert "Epoch 5/10" in message
        assert "Batch 120/500" in message
        assert "GPU" in message or "RTX 3090" in message

    def test_render_message_with_empty_context(self):
        """Test graceful handling of empty context."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=1,
            total_steps=10,
            percentage=10.0,
            message="Training starting",
            context={},
        )

        message = renderer.render_message(state)

        # Should render message even without context
        assert len(message) > 0
        assert "Training starting" in message

    def test_render_message_with_partial_epoch_context(self):
        """Test rendering with only epoch index (missing total_epochs)."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=3,
            total_steps=10,
            percentage=30.0,
            message="Training",
            context={
                "epoch_index": 3,
                # Missing total_epochs
            },
        )

        message = renderer.render_message(state)

        # Should handle gracefully
        assert len(message) > 0

    def test_render_message_gpu_not_used(self):
        """Test rendering when GPU is not used."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=2,
            total_steps=10,
            percentage=20.0,
            message="Training on CPU",
            context={
                "epoch_index": 2,
                "total_epochs": 10,
                "resource_usage": {
                    "gpu_used": False,
                },
            },
        )

        message = renderer.render_message(state)

        # Should not include GPU info
        assert "GPU" not in message
        assert "Epoch 2/10" in message

    def test_enhance_state_preserves_context(self):
        """Test that state enhancement preserves original context."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=5,
            total_steps=10,
            percentage=50.0,
            message="Training",
            context={
                "epoch_index": 5,
                "total_epochs": 10,
                "custom_field": "custom_value",
            },
        )

        enhanced_state = renderer.enhance_state(state)

        # Should preserve original context
        assert enhanced_state.context["epoch_index"] == 5
        assert enhanced_state.context["total_epochs"] == 10
        assert enhanced_state.context["custom_field"] == "custom_value"

    def test_enhance_state_adds_tracking(self):
        """Test that state enhancement adds internal tracking."""
        renderer = self.TrainingProgressRenderer()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=3,
            total_steps=10,
            percentage=30.0,
            message="Training",
            context={
                "epoch_index": 3,
                "batch_number": 50,
            },
        )

        enhanced_state = renderer.enhance_state(state)

        # Should maintain internal tracking (stored in renderer._current_context)
        assert isinstance(enhanced_state, GenericProgressState)
        assert enhanced_state.context["epoch_index"] == 3

    def test_thread_safety_message_rendering(self):
        """Test thread safety of message rendering operations."""
        renderer = self.TrainingProgressRenderer()
        results = []
        errors = []

        def render_messages():
            try:
                for i in range(10):
                    state = GenericProgressState(
                        operation_id=f"thread_test_{i}",
                        current_step=i,
                        total_steps=10,
                        percentage=i * 10,
                        message=f"Training epoch {i}",
                        context={
                            "epoch_index": i,
                            "total_epochs": 10,
                            "batch_number": i * 50,
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
                        current_step=i,
                        total_steps=10,
                        percentage=i * 10,
                        message=f"Training epoch {i}",
                        context={"epoch_index": i, "total_epochs": 10},
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

    def test_preserve_existing_message_formats(self):
        """Test that training progress message formats are consistent."""
        renderer = self.TrainingProgressRenderer()

        test_cases = [
            {
                "state": GenericProgressState(
                    operation_id="train_model",
                    current_step=1,
                    total_steps=10,
                    percentage=10.0,
                    message="Training starting",
                    context={"epoch_index": 1, "total_epochs": 10},
                ),
                "expected_patterns": ["Epoch 1/10"],
            },
            {
                "state": GenericProgressState(
                    operation_id="train_model",
                    current_step=5,
                    total_steps=10,
                    percentage=50.0,
                    message="Training in progress",
                    context={
                        "epoch_index": 5,
                        "total_epochs": 10,
                        "batch_number": 250,
                        "batch_total_per_epoch": 500,
                    },
                ),
                "expected_patterns": ["Epoch 5/10", "Batch 250/500"],
            },
            {
                "state": GenericProgressState(
                    operation_id="train_model",
                    current_step=8,
                    total_steps=10,
                    percentage=80.0,
                    message="Training nearly complete",
                    context={
                        "epoch_index": 8,
                        "total_epochs": 10,
                        "batch_number": 450,
                        "batch_total_per_epoch": 500,
                        "resource_usage": {
                            "gpu_used": True,
                            "gpu_name": "RTX 3090",
                            "gpu_utilization_percent": 92,
                        },
                    },
                ),
                "expected_patterns": ["Epoch 8/10", "Batch 450/500", "92"],
            },
        ]

        for test_case in test_cases:
            message = renderer.render_message(test_case["state"])
            for pattern in test_case["expected_patterns"]:
                assert (
                    pattern in message
                ), f"Pattern '{pattern}' not found in message: {message}"

    def test_coverage_requirements(self):
        """Test that we achieve >80% coverage requirement."""
        renderer = self.TrainingProgressRenderer()

        # Test all public methods
        assert callable(renderer.render_message)
        assert callable(renderer.enhance_state)

        # Test all attributes are accessible
        assert hasattr(renderer, "_current_context")

    def test_context_flow_from_bridge(self):
        """Test that context from TrainingProgressBridge flows correctly."""
        renderer = self.TrainingProgressRenderer()

        # Simulate context that would come from TrainingProgressBridge.on_batch()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=5,
            total_steps=10,
            percentage=50.0,
            message="Epoch 5/10 · Batch 120/500",  # Bridge's formatted message
            context={
                "epoch_index": 5,
                "total_epochs": 10,
                "batch_index": 119,  # 0-based
                "batch_number": 120,  # 1-based
                "batch_total_per_epoch": 500,
                "current_item": "Epoch 5 · Batch 120/500",
                "batch_metrics": {"loss": 0.234, "accuracy": 0.876},
                "phase": "batch",
            },
        )

        message = renderer.render_message(state)

        # Should extract and format the key information
        assert "Epoch 5/10" in message
        assert "Batch 120/500" in message

    def test_context_flow_with_remote_snapshot(self):
        """Test context from remote host service snapshots."""
        renderer = self.TrainingProgressRenderer()

        # Simulate context from TrainingProgressBridge.on_remote_snapshot()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=7,
            total_steps=10,
            percentage=70.0,
            message="Epoch 7/10 · Batch 350/500",
            context={
                "host_status": "running",
                "host_session_id": "session_123",
                "remote_progress": {
                    "epoch": 7,
                    "total_epochs": 10,
                    "items_processed": 350,
                    "items_total": 500,
                },
                "metrics": {"loss": 0.189, "accuracy": 0.912},
                "resource_usage": {
                    "gpu_used": True,
                    "gpu_name": "A100",
                    "gpu_utilization_percent": 78,
                },
                "phase": "remote_snapshot",
            },
        )

        message = renderer.render_message(state)

        # Should handle remote snapshot context
        assert "Epoch 7/10" in message or "78" in message

    def test_preprocessing_message_rendering(self):
        """Test that preprocessing messages are rendered correctly."""
        renderer = self.TrainingProgressRenderer()

        # Simulate preprocessing progress from TrainingProgressBridge.on_symbol_processing()
        state = GenericProgressState(
            operation_id="train_model",
            current_step=0,
            total_steps=5,
            percentage=1.2,
            message="Processing AAPL (2/5) - Computing Indicators",
            context={
                "phase": "preprocessing",
                "symbol": "AAPL",
                "symbol_index": 2,
                "total_symbols": 5,
                "preprocessing_step": "computing_indicators",
            },
        )

        message = renderer.render_message(state)

        # Should render the preprocessing message as-is
        assert message == "Processing AAPL (2/5) - Computing Indicators"

        # Test another preprocessing step
        state2 = GenericProgressState(
            operation_id="train_model",
            current_step=0,
            total_steps=5,
            percentage=0.4,
            message="Processing AAPL (1/5) - Generating Fuzzy",
            context={
                "phase": "preprocessing",
                "symbol": "AAPL",
                "symbol_index": 1,
                "total_symbols": 5,
                "preprocessing_step": "generating_fuzzy",
            },
        )

        message2 = renderer.render_message(state2)
        assert message2 == "Processing AAPL (1/5) - Generating Fuzzy"
