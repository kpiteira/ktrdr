"""Tests for milestone runner."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.milestone_runner import MilestoneResult, run_milestone
from orchestrator.models import Task, TaskResult
from orchestrator.state import OrchestratorState


@pytest.fixture
def sample_tasks() -> list[Task]:
    """Sample tasks for testing."""
    return [
        Task(
            id="1.1",
            title="First task",
            description="Do the first thing",
            file_path="test.py",
            acceptance_criteria=["Works correctly"],
            plan_file="test_plan.md",
            milestone_id="M1",
        ),
        Task(
            id="1.2",
            title="Second task",
            description="Do the second thing",
            file_path="test2.py",
            acceptance_criteria=["Also works"],
            plan_file="test_plan.md",
            milestone_id="M1",
        ),
        Task(
            id="1.3",
            title="Third task",
            description="Do the third thing",
            file_path="test3.py",
            acceptance_criteria=["All good"],
            plan_file="test_plan.md",
            milestone_id="M1",
        ),
    ]


@pytest.fixture
def mock_run_task() -> AsyncMock:
    """Mock for run_task that returns completed status."""

    async def _run_task(
        task: Task,
        sandbox: MagicMock,
        config: MagicMock,
        plan_path: str,
        on_tool_use=None,
    ) -> TaskResult:
        return TaskResult(
            task_id=task.id,
            status="completed",
            duration_seconds=10.0,
            tokens_used=1000,
            cost_usd=0.01,
            output="Task completed successfully",
            session_id="test-session",
        )

    return AsyncMock(side_effect=_run_task)


class TestRunMilestoneBasic:
    """Tests for basic milestone execution."""

    @pytest.mark.asyncio
    async def test_runs_all_tasks_sequentially(
        self, tmp_path: Path, sample_tasks: list[Task], mock_run_task: AsyncMock
    ) -> None:
        """All tasks are executed in order."""
        with (
            patch(
                "orchestrator.milestone_runner.parse_plan", return_value=sample_tasks
            ),
            patch("orchestrator.milestone_runner.run_task", mock_run_task),
            patch("orchestrator.milestone_runner.SandboxManager"),
        ):
            result = await run_milestone(
                plan_path="test_plan.md",
                state_dir=tmp_path,
            )

        assert result.status == "completed"
        assert mock_run_task.call_count == 3

        # Verify order of task IDs
        call_task_ids = [call.args[0].id for call in mock_run_task.call_args_list]
        assert call_task_ids == ["1.1", "1.2", "1.3"]

    @pytest.mark.asyncio
    async def test_saves_state_after_each_task(
        self, tmp_path: Path, sample_tasks: list[Task], mock_run_task: AsyncMock
    ) -> None:
        """State is saved after each task completion."""
        with (
            patch(
                "orchestrator.milestone_runner.parse_plan", return_value=sample_tasks
            ),
            patch("orchestrator.milestone_runner.run_task", mock_run_task),
            patch("orchestrator.milestone_runner.SandboxManager"),
        ):
            await run_milestone(
                plan_path="test_plan.md",
                state_dir=tmp_path,
            )

        # Load final state
        state = OrchestratorState.load(tmp_path, "test_plan")
        assert state is not None
        assert state.completed_tasks == ["1.1", "1.2", "1.3"]
        assert len(state.task_results) == 3

    @pytest.mark.asyncio
    async def test_returns_milestone_result_with_totals(
        self, tmp_path: Path, sample_tasks: list[Task], mock_run_task: AsyncMock
    ) -> None:
        """MilestoneResult contains aggregated totals."""
        with (
            patch(
                "orchestrator.milestone_runner.parse_plan", return_value=sample_tasks
            ),
            patch("orchestrator.milestone_runner.run_task", mock_run_task),
            patch("orchestrator.milestone_runner.SandboxManager"),
        ):
            result = await run_milestone(
                plan_path="test_plan.md",
                state_dir=tmp_path,
            )

        assert result.status == "completed"
        assert result.total_tasks == 3
        assert result.completed_tasks == 3
        assert result.total_cost_usd == pytest.approx(0.03)  # 3 tasks * $0.01
        assert result.total_tokens == 3000  # 3 tasks * 1000


class TestRunMilestoneResume:
    """Tests for milestone resume functionality."""

    @pytest.mark.asyncio
    async def test_resume_skips_completed_tasks(
        self, tmp_path: Path, sample_tasks: list[Task], mock_run_task: AsyncMock
    ) -> None:
        """Resume starts from first incomplete task."""
        # Create existing state with first task completed
        existing_state = OrchestratorState(
            milestone_id="test_plan",
            plan_path="test_plan.md",
            started_at=datetime.now(),
            completed_tasks=["1.1"],
            task_results={
                "1.1": {
                    "task_id": "1.1",
                    "status": "completed",
                    "duration_seconds": 5.0,
                    "tokens_used": 500,
                    "cost_usd": 0.005,
                }
            },
        )
        existing_state.save(tmp_path)

        with (
            patch(
                "orchestrator.milestone_runner.parse_plan", return_value=sample_tasks
            ),
            patch("orchestrator.milestone_runner.run_task", mock_run_task),
            patch("orchestrator.milestone_runner.SandboxManager"),
        ):
            await run_milestone(
                plan_path="test_plan.md",
                state_dir=tmp_path,
                resume=True,
            )

        # Should only run tasks 1.2 and 1.3
        assert mock_run_task.call_count == 2
        call_task_ids = [call.args[0].id for call in mock_run_task.call_args_list]
        assert call_task_ids == ["1.2", "1.3"]

    @pytest.mark.asyncio
    async def test_fresh_run_ignores_existing_state(
        self, tmp_path: Path, sample_tasks: list[Task], mock_run_task: AsyncMock
    ) -> None:
        """Fresh run (resume=False) starts from beginning."""
        # Create existing state with first task completed
        existing_state = OrchestratorState(
            milestone_id="test_plan",
            plan_path="test_plan.md",
            started_at=datetime.now(),
            completed_tasks=["1.1"],
        )
        existing_state.save(tmp_path)

        with (
            patch(
                "orchestrator.milestone_runner.parse_plan", return_value=sample_tasks
            ),
            patch("orchestrator.milestone_runner.run_task", mock_run_task),
            patch("orchestrator.milestone_runner.SandboxManager"),
        ):
            await run_milestone(
                plan_path="test_plan.md",
                state_dir=tmp_path,
                resume=False,  # Fresh run
            )

        # Should run all 3 tasks
        assert mock_run_task.call_count == 3


class TestRunMilestoneStatusHandling:
    """Tests for handling different task statuses."""

    @pytest.mark.asyncio
    async def test_stops_on_needs_human(
        self, tmp_path: Path, sample_tasks: list[Task]
    ) -> None:
        """Stops execution when task needs human input."""
        call_count = 0

        async def mock_task(
            task: Task, sandbox: MagicMock, config: MagicMock, plan_path: str, on_tool_use=None
        ) -> TaskResult:
            nonlocal call_count
            call_count += 1
            if task.id == "1.2":
                return TaskResult(
                    task_id=task.id,
                    status="needs_human",
                    duration_seconds=5.0,
                    tokens_used=500,
                    cost_usd=0.005,
                    output="I need clarification",
                    session_id="test",
                    question="Should I use approach A or B?",
                    options=["A", "B"],
                    recommendation="A",
                )
            return TaskResult(
                task_id=task.id,
                status="completed",
                duration_seconds=10.0,
                tokens_used=1000,
                cost_usd=0.01,
                output="Done",
                session_id="test",
            )

        with (
            patch(
                "orchestrator.milestone_runner.parse_plan", return_value=sample_tasks
            ),
            patch(
                "orchestrator.milestone_runner.run_task",
                AsyncMock(side_effect=mock_task),
            ),
            patch("orchestrator.milestone_runner.SandboxManager"),
        ):
            result = await run_milestone(
                plan_path="test_plan.md",
                state_dir=tmp_path,
            )

        assert result.status == "needs_human"
        assert call_count == 2  # Ran 1.1 and 1.2, stopped before 1.3
        assert result.completed_tasks == 1

    @pytest.mark.asyncio
    async def test_stops_on_failed(
        self, tmp_path: Path, sample_tasks: list[Task]
    ) -> None:
        """Stops execution when task fails."""
        call_count = 0

        async def mock_task(
            task: Task, sandbox: MagicMock, config: MagicMock, plan_path: str, on_tool_use=None
        ) -> TaskResult:
            nonlocal call_count
            call_count += 1
            if task.id == "1.2":
                return TaskResult(
                    task_id=task.id,
                    status="failed",
                    duration_seconds=5.0,
                    tokens_used=500,
                    cost_usd=0.005,
                    output="Something went wrong",
                    session_id="test",
                    error="Could not complete the task",
                )
            return TaskResult(
                task_id=task.id,
                status="completed",
                duration_seconds=10.0,
                tokens_used=1000,
                cost_usd=0.01,
                output="Done",
                session_id="test",
            )

        with (
            patch(
                "orchestrator.milestone_runner.parse_plan", return_value=sample_tasks
            ),
            patch(
                "orchestrator.milestone_runner.run_task",
                AsyncMock(side_effect=mock_task),
            ),
            patch("orchestrator.milestone_runner.SandboxManager"),
        ):
            result = await run_milestone(
                plan_path="test_plan.md",
                state_dir=tmp_path,
            )

        assert result.status == "failed"
        assert call_count == 2
        assert result.failed_tasks == 1


class TestMilestoneResult:
    """Tests for MilestoneResult dataclass."""

    def test_milestone_result_creation(self) -> None:
        """MilestoneResult can be created with all fields."""
        state = OrchestratorState(
            milestone_id="M1",
            plan_path="plan.md",
            started_at=datetime.now(),
        )

        result = MilestoneResult(
            status="completed",
            state=state,
            total_tasks=5,
            completed_tasks=5,
            failed_tasks=0,
            total_cost_usd=0.50,
            total_tokens=50000,
            total_duration_seconds=300.0,
        )

        assert result.status == "completed"
        assert result.total_tasks == 5
        assert result.total_cost_usd == 0.50


class TestTaskCompleteCallback:
    """Tests for on_task_complete callback functionality."""

    @pytest.mark.asyncio
    async def test_callback_called_for_each_completed_task(
        self, tmp_path: Path, sample_tasks: list[Task]
    ) -> None:
        """on_task_complete callback is called after each completed task."""
        callback_calls: list[tuple[Task, TaskResult]] = []

        def on_complete(task: Task, result: TaskResult) -> None:
            callback_calls.append((task, result))

        async def mock_task(
            task: Task, sandbox: MagicMock, config: MagicMock, plan_path: str, on_tool_use=None
        ) -> TaskResult:
            return TaskResult(
                task_id=task.id,
                status="completed",
                duration_seconds=10.0,
                tokens_used=1000,
                cost_usd=0.01,
                output=f"Summary for {task.id}",
                session_id="test",
            )

        with (
            patch(
                "orchestrator.milestone_runner.parse_plan", return_value=sample_tasks
            ),
            patch(
                "orchestrator.milestone_runner.run_task",
                AsyncMock(side_effect=mock_task),
            ),
            patch("orchestrator.milestone_runner.SandboxManager"),
        ):
            await run_milestone(
                plan_path="test_plan.md",
                state_dir=tmp_path,
                on_task_complete=on_complete,
            )

        # Callback should be called 3 times
        assert len(callback_calls) == 3

        # Verify callback received correct data
        assert callback_calls[0][0].id == "1.1"
        assert callback_calls[0][1].output == "Summary for 1.1"
        assert callback_calls[1][0].id == "1.2"
        assert callback_calls[2][0].id == "1.3"

    @pytest.mark.asyncio
    async def test_callback_not_called_for_failed_task(
        self, tmp_path: Path, sample_tasks: list[Task]
    ) -> None:
        """on_task_complete callback is NOT called for failed tasks."""
        callback_calls: list[tuple[Task, TaskResult]] = []

        def on_complete(task: Task, result: TaskResult) -> None:
            callback_calls.append((task, result))

        async def mock_task(
            task: Task, sandbox: MagicMock, config: MagicMock, plan_path: str, on_tool_use=None
        ) -> TaskResult:
            if task.id == "1.2":
                return TaskResult(
                    task_id=task.id,
                    status="failed",
                    duration_seconds=5.0,
                    tokens_used=500,
                    cost_usd=0.005,
                    output="Failed",
                    session_id="test",
                    error="Something broke",
                )
            return TaskResult(
                task_id=task.id,
                status="completed",
                duration_seconds=10.0,
                tokens_used=1000,
                cost_usd=0.01,
                output=f"Summary for {task.id}",
                session_id="test",
            )

        with (
            patch(
                "orchestrator.milestone_runner.parse_plan", return_value=sample_tasks
            ),
            patch(
                "orchestrator.milestone_runner.run_task",
                AsyncMock(side_effect=mock_task),
            ),
            patch("orchestrator.milestone_runner.SandboxManager"),
        ):
            await run_milestone(
                plan_path="test_plan.md",
                state_dir=tmp_path,
                on_task_complete=on_complete,
            )

        # Only task 1.1 completed, so only 1 callback
        assert len(callback_calls) == 1
        assert callback_calls[0][0].id == "1.1"

    @pytest.mark.asyncio
    async def test_callback_optional(
        self, tmp_path: Path, sample_tasks: list[Task], mock_run_task: AsyncMock
    ) -> None:
        """Milestone runs without callback (backward compatibility)."""
        with (
            patch(
                "orchestrator.milestone_runner.parse_plan", return_value=sample_tasks
            ),
            patch("orchestrator.milestone_runner.run_task", mock_run_task),
            patch("orchestrator.milestone_runner.SandboxManager"),
        ):
            # Should not raise - callback is optional
            result = await run_milestone(
                plan_path="test_plan.md",
                state_dir=tmp_path,
            )

        assert result.status == "completed"


class TestCreateMilestonePR:
    """Tests for create_milestone_pr function."""

    @pytest.mark.asyncio
    async def test_creates_pr_via_claude(self, tmp_path: Path) -> None:
        """create_milestone_pr invokes Claude with correct prompt."""
        from orchestrator.milestone_runner import create_milestone_pr
        from orchestrator.models import ClaudeResult

        mock_sandbox = MagicMock()
        mock_sandbox.invoke_claude = AsyncMock(
            return_value=ClaudeResult(
                is_error=False,
                result="PR created: https://github.com/user/repo/pull/123",
                total_cost_usd=0.02,
                duration_ms=5000,
                num_turns=3,
                session_id="pr-session",
            )
        )

        result = await create_milestone_pr(
            sandbox=mock_sandbox,
            milestone_id="health_check",
            completed_tasks=["1.1", "1.2", "1.3"],
            total_cost_usd=0.15,
        )

        # Verify Claude was invoked
        mock_sandbox.invoke_claude.assert_called_once()
        call_args = mock_sandbox.invoke_claude.call_args

        # Verify prompt contains key information
        prompt = call_args.kwargs.get("prompt") or call_args.args[0]
        assert "health_check" in prompt
        assert "1.1" in prompt
        assert "1.2" in prompt
        assert "1.3" in prompt

        # Verify result contains the expected PR URL
        assert result.result == "PR created: https://github.com/user/repo/pull/123"

    @pytest.mark.asyncio
    async def test_handles_claude_error(self, tmp_path: Path) -> None:
        """create_milestone_pr handles Claude errors gracefully."""
        from orchestrator.milestone_runner import create_milestone_pr
        from orchestrator.models import ClaudeResult

        mock_sandbox = MagicMock()
        mock_sandbox.invoke_claude = AsyncMock(
            return_value=ClaudeResult(
                is_error=True,
                result="Error: Failed to create PR",
                total_cost_usd=0.01,
                duration_ms=2000,
                num_turns=1,
                session_id="error-session",
            )
        )

        result = await create_milestone_pr(
            sandbox=mock_sandbox,
            milestone_id="test",
            completed_tasks=["1.1"],
            total_cost_usd=0.05,
        )

        assert result.is_error is True
