"""State management for orchestrator persistence.

Provides OrchestratorState dataclass that tracks milestone execution progress
and supports save/load for resumability after interruption.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class OrchestratorState:
    """Persistent state for orchestrator milestone execution.

    Tracks completed tasks, task results, and loop detection counters.
    State is saved after each task completion for resumability.

    Attributes:
        milestone_id: Identifier for the milestone being executed
        plan_path: Path to the milestone plan file
        started_at: When milestone execution started
        current_task_index: Index of next task to execute
        completed_tasks: List of completed task IDs
        failed_tasks: List of failed task IDs
        task_results: Map of task_id to TaskResult dict
        e2e_status: Status of E2E tests (None, "pending", "passed", "failed")
        task_attempt_counts: Map of task_id to attempt count (for loop detection)
        task_errors: Map of task_id to list of error messages
        e2e_attempt_count: Number of E2E fix attempts
        e2e_errors: List of E2E error messages
    """

    milestone_id: str
    plan_path: str
    started_at: datetime
    current_task_index: int = 0
    completed_tasks: list[str] = field(default_factory=list)
    failed_tasks: list[str] = field(default_factory=list)
    task_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    e2e_status: str | None = None
    # Loop detection state (for M4)
    task_attempt_counts: dict[str, int] = field(default_factory=dict)
    task_errors: dict[str, list[str]] = field(default_factory=dict)
    e2e_attempt_count: int = 0
    e2e_errors: list[str] = field(default_factory=list)

    def save(self, state_dir: Path) -> None:
        """Persist state to JSON file.

        Creates state directory if it doesn't exist.

        Args:
            state_dir: Directory to save state file in
        """
        state_dir.mkdir(exist_ok=True)
        path = state_dir / f"{self.milestone_id}_state.json"

        data = asdict(self)
        data["started_at"] = self.started_at.isoformat()

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, state_dir: Path, milestone_id: str) -> "OrchestratorState | None":
        """Load state from JSON file if it exists.

        Args:
            state_dir: Directory containing state files
            milestone_id: Milestone ID to load state for

        Returns:
            OrchestratorState if file exists, None otherwise
        """
        path = state_dir / f"{milestone_id}_state.json"
        if not path.exists():
            return None

        with open(path) as f:
            data = json.load(f)

        data["started_at"] = datetime.fromisoformat(data["started_at"])
        return cls(**data)

    def mark_task_completed(self, task_id: str, result: dict[str, Any]) -> None:
        """Mark a task as completed and update state.

        Args:
            task_id: ID of the completed task
            result: TaskResult as dict (from dataclasses.asdict)
        """
        self.completed_tasks.append(task_id)
        self.task_results[task_id] = result
        self.current_task_index += 1

    def get_next_task_index(self) -> int:
        """Get the index of the next task to execute.

        Returns:
            Index into task list (count of completed tasks)
        """
        return len(self.completed_tasks)
