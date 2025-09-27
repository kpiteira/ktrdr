"""Tests for the stub training progress bridge."""

from collections import deque
from typing import Any

import pytest

from ktrdr.api.services.training.progress_bridge import TrainingProgressBridge
from ktrdr.async_infrastructure.progress import GenericProgressManager


class TestTrainingProgressBridge:
    """Behaviour tests for the placeholder progress bridge."""

    def test_updates_generic_progress_manager(self):
        states = deque()

        progress_manager = GenericProgressManager(callback=states.append)
        progress_manager.start_operation("training", total_steps=5)

        bridge = TrainingProgressBridge(
            progress_manager=progress_manager, total_steps=5
        )

        bridge.on_phase("data_loading")
        assert states[-1].message == "Phase: data_loading"
        assert states[-1].current_step == 0
        assert states[-1].percentage == 0.0

        bridge.on_epoch(1, total_epochs=10)
        assert states[-1].message == "Epoch 1/10"
        assert states[-1].current_step == 0

        bridge.on_complete("done")
        assert states[-1].message == "done"
        assert states[-1].current_step == 5
        assert states[-1].percentage == pytest.approx(100.0)

    def test_works_with_update_callback(self):
        captured: list[dict[str, Any]] = []

        def fake_update(**kwargs):
            captured.append(kwargs)

        bridge = TrainingProgressBridge(
            update_progress_callback=fake_update, total_steps=3
        )

        bridge.on_epoch(2, total_epochs=8, metrics={"loss": 0.5})
        assert captured[-1]["step"] == 0
        assert captured[-1]["message"] == "Epoch 2/8"
        assert captured[-1]["items_processed"] == 0
        assert captured[-1]["phase"] == "epoch"
        assert captured[-1]["metrics"] == {"loss": 0.5}

        bridge.on_complete()
        assert captured[-1]["step"] == 3
        assert captured[-1]["items_processed"] == 3
        assert captured[-1]["phase"] == "completed"
        assert captured[-1]["message"] == "Training complete"
