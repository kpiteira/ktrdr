"""Tests for orchestrator state persistence."""

import json
from datetime import datetime
from pathlib import Path

from orchestrator.state import OrchestratorState


class TestOrchestratorStateSave:
    """Tests for OrchestratorState.save()."""

    def test_save_creates_state_directory(self, tmp_path: Path) -> None:
        """State directory is created if it doesn't exist."""
        state_dir = tmp_path / "state"
        assert not state_dir.exists()

        state = OrchestratorState(
            milestone_id="test_m1",
            plan_path="test/plan.md",
            started_at=datetime(2025, 1, 15, 14, 23, 0),
        )
        state.save(state_dir)

        assert state_dir.exists()

    def test_save_creates_json_file(self, tmp_path: Path) -> None:
        """State is saved to JSON file with milestone ID."""
        state = OrchestratorState(
            milestone_id="test_m1",
            plan_path="test/plan.md",
            started_at=datetime(2025, 1, 15, 14, 23, 0),
        )
        state.save(tmp_path)

        expected_file = tmp_path / "test_m1_state.json"
        assert expected_file.exists()

    def test_save_serializes_datetime(self, tmp_path: Path) -> None:
        """Datetime is serialized to ISO format."""
        state = OrchestratorState(
            milestone_id="test_m1",
            plan_path="test/plan.md",
            started_at=datetime(2025, 1, 15, 14, 23, 0),
        )
        state.save(tmp_path)

        with open(tmp_path / "test_m1_state.json") as f:
            data = json.load(f)

        assert data["started_at"] == "2025-01-15T14:23:00"

    def test_save_includes_all_fields(self, tmp_path: Path) -> None:
        """All state fields are included in saved JSON."""
        state = OrchestratorState(
            milestone_id="test_m1",
            plan_path="test/plan.md",
            started_at=datetime(2025, 1, 15, 14, 23, 0),
            current_task_index=2,
            completed_tasks=["1.1", "1.2"],
            failed_tasks=["1.3"],
            task_results={"1.1": {"status": "completed", "cost_usd": 0.05}},
            e2e_status="pending",
        )
        state.save(tmp_path)

        with open(tmp_path / "test_m1_state.json") as f:
            data = json.load(f)

        assert data["milestone_id"] == "test_m1"
        assert data["plan_path"] == "test/plan.md"
        assert data["current_task_index"] == 2
        assert data["completed_tasks"] == ["1.1", "1.2"]
        assert data["failed_tasks"] == ["1.3"]
        assert data["task_results"] == {"1.1": {"status": "completed", "cost_usd": 0.05}}
        assert data["e2e_status"] == "pending"


class TestOrchestratorStateLoad:
    """Tests for OrchestratorState.load()."""

    def test_load_returns_none_when_no_file(self, tmp_path: Path) -> None:
        """Load returns None when state file doesn't exist."""
        result = OrchestratorState.load(tmp_path, "nonexistent")
        assert result is None

    def test_load_deserializes_datetime(self, tmp_path: Path) -> None:
        """Load correctly deserializes datetime from ISO format."""
        state_file = tmp_path / "test_m1_state.json"
        state_file.write_text(
            json.dumps(
                {
                    "milestone_id": "test_m1",
                    "plan_path": "test/plan.md",
                    "started_at": "2025-01-15T14:23:00",
                    "current_task_index": 0,
                    "completed_tasks": [],
                    "failed_tasks": [],
                    "task_results": {},
                    "e2e_status": None,
                    "task_attempt_counts": {},
                    "task_errors": {},
                    "e2e_attempt_count": 0,
                    "e2e_errors": [],
                }
            )
        )

        state = OrchestratorState.load(tmp_path, "test_m1")

        assert state is not None
        assert state.started_at == datetime(2025, 1, 15, 14, 23, 0)

    def test_load_restores_all_fields(self, tmp_path: Path) -> None:
        """Load correctly restores all state fields."""
        state_file = tmp_path / "test_m1_state.json"
        state_file.write_text(
            json.dumps(
                {
                    "milestone_id": "test_m1",
                    "plan_path": "test/plan.md",
                    "started_at": "2025-01-15T14:23:00",
                    "current_task_index": 2,
                    "completed_tasks": ["1.1", "1.2"],
                    "failed_tasks": ["1.3"],
                    "task_results": {"1.1": {"status": "completed"}},
                    "e2e_status": "passed",
                    "task_attempt_counts": {"1.3": 2},
                    "task_errors": {"1.3": ["Error 1", "Error 2"]},
                    "e2e_attempt_count": 1,
                    "e2e_errors": ["E2E failed"],
                }
            )
        )

        state = OrchestratorState.load(tmp_path, "test_m1")

        assert state is not None
        assert state.milestone_id == "test_m1"
        assert state.plan_path == "test/plan.md"
        assert state.current_task_index == 2
        assert state.completed_tasks == ["1.1", "1.2"]
        assert state.failed_tasks == ["1.3"]
        assert state.task_results == {"1.1": {"status": "completed"}}
        assert state.e2e_status == "passed"
        assert state.task_attempt_counts == {"1.3": 2}
        assert state.task_errors == {"1.3": ["Error 1", "Error 2"]}
        assert state.e2e_attempt_count == 1
        assert state.e2e_errors == ["E2E failed"]


class TestOrchestratorStateSaveLoadCycle:
    """Tests for complete save/load cycle."""

    def test_save_load_roundtrip(self, tmp_path: Path) -> None:
        """State survives complete save/load cycle."""
        original = OrchestratorState(
            milestone_id="test_m1",
            plan_path="test/plan.md",
            started_at=datetime(2025, 1, 15, 14, 23, 0),
            current_task_index=2,
            completed_tasks=["1.1", "1.2"],
            failed_tasks=["1.3"],
            task_results={"1.1": {"status": "completed", "cost_usd": 0.05}},
            e2e_status="pending",
            task_attempt_counts={"1.3": 2},
            task_errors={"1.3": ["Error 1"]},
            e2e_attempt_count=0,
            e2e_errors=[],
        )

        original.save(tmp_path)
        restored = OrchestratorState.load(tmp_path, "test_m1")

        assert restored is not None
        assert restored.milestone_id == original.milestone_id
        assert restored.plan_path == original.plan_path
        assert restored.started_at == original.started_at
        assert restored.current_task_index == original.current_task_index
        assert restored.completed_tasks == original.completed_tasks
        assert restored.failed_tasks == original.failed_tasks
        assert restored.task_results == original.task_results
        assert restored.e2e_status == original.e2e_status
        assert restored.task_attempt_counts == original.task_attempt_counts
        assert restored.task_errors == original.task_errors


class TestOrchestratorStateHelpers:
    """Tests for helper methods."""

    def test_mark_task_completed(self) -> None:
        """mark_task_completed updates state correctly."""
        state = OrchestratorState(
            milestone_id="test_m1",
            plan_path="test/plan.md",
            started_at=datetime.now(),
        )

        # Create a mock TaskResult-like dict
        task_result_dict = {
            "task_id": "1.1",
            "status": "completed",
            "duration_seconds": 42.0,
            "tokens_used": 1000,
            "cost_usd": 0.05,
            "output": "Task completed",
            "session_id": "abc123",
        }

        state.mark_task_completed("1.1", task_result_dict)

        assert "1.1" in state.completed_tasks
        assert state.task_results["1.1"] == task_result_dict
        assert state.current_task_index == 1

    def test_get_next_task_index_empty(self) -> None:
        """get_next_task_index returns 0 when no tasks completed."""
        state = OrchestratorState(
            milestone_id="test_m1",
            plan_path="test/plan.md",
            started_at=datetime.now(),
        )

        assert state.get_next_task_index() == 0

    def test_get_next_task_index_with_completed(self) -> None:
        """get_next_task_index returns count of completed tasks."""
        state = OrchestratorState(
            milestone_id="test_m1",
            plan_path="test/plan.md",
            started_at=datetime.now(),
            completed_tasks=["1.1", "1.2"],
        )

        assert state.get_next_task_index() == 2
