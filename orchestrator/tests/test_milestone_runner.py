"""Tests for milestone runner."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.llm.haiku_brain import ExtractedTask
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
def sample_extracted_tasks() -> list[ExtractedTask]:
    """Sample extracted tasks for HaikuBrain mocking."""
    return [
        ExtractedTask(id="1.1", title="First task", description="Do the first thing"),
        ExtractedTask(id="1.2", title="Second task", description="Do the second thing"),
        ExtractedTask(id="1.3", title="Third task", description="Do the third thing"),
    ]


@pytest.fixture
def mock_run_task_with_escalation() -> AsyncMock:
    """Mock for run_task_with_escalation that returns completed status."""

    async def _run_task_with_escalation(
        task: Task,
        container: MagicMock,
        config: MagicMock,
        plan_path: str,
        tracer,
        notify: bool = True,
        on_tool_use=None,
        model: str | None = None,
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

    return AsyncMock(side_effect=_run_task_with_escalation)


@pytest.fixture
def basic_plan_file(tmp_path: Path) -> Path:
    """Create a basic test plan file without E2E section."""
    plan_path = tmp_path / "test_plan.md"
    plan_path.write_text("# Test Milestone\n\nNo E2E scenario.\n")
    return plan_path


def configure_haiku_mock(mock_brain_class: MagicMock) -> None:
    """Configure HaikuBrain mock to return sample extracted tasks."""
    mock_brain_class.return_value.extract_tasks.return_value = [
        ExtractedTask(id="1.1", title="First task", description="Do the first thing"),
        ExtractedTask(id="1.2", title="Second task", description="Do the second thing"),
        ExtractedTask(id="1.3", title="Third task", description="Do the third thing"),
    ]


class TestRunMilestoneBasic:
    """Tests for basic milestone execution."""

    @pytest.mark.asyncio
    async def test_runs_all_tasks_sequentially(
        self,
        tmp_path: Path,
        basic_plan_file: Path,
        sample_tasks: list[Task],
        mock_run_task_with_escalation: AsyncMock,
    ) -> None:
        """All tasks are executed in order."""
        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                mock_run_task_with_escalation,
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
        ):
            configure_haiku_mock(mock_brain_class)
            result = await run_milestone(
                plan_path=str(basic_plan_file),
                state_dir=tmp_path,
            )

        assert result.status == "completed"
        assert mock_run_task_with_escalation.call_count == 3

        # Verify order of task IDs
        call_task_ids = [
            call.args[0].id for call in mock_run_task_with_escalation.call_args_list
        ]
        assert call_task_ids == ["1.1", "1.2", "1.3"]

    @pytest.mark.asyncio
    async def test_saves_state_after_each_task(
        self,
        tmp_path: Path,
        basic_plan_file: Path,
        sample_tasks: list[Task],
        mock_run_task_with_escalation: AsyncMock,
    ) -> None:
        """State is saved after each task completion."""
        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                mock_run_task_with_escalation,
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
        ):
            configure_haiku_mock(mock_brain_class)
            await run_milestone(
                plan_path=str(basic_plan_file),
                state_dir=tmp_path,
            )

        # Load final state
        state = OrchestratorState.load(tmp_path, basic_plan_file.stem)
        assert state is not None
        assert state.completed_tasks == ["1.1", "1.2", "1.3"]
        assert len(state.task_results) == 3

    @pytest.mark.asyncio
    async def test_returns_milestone_result_with_totals(
        self,
        tmp_path: Path,
        basic_plan_file: Path,
        sample_tasks: list[Task],
        mock_run_task_with_escalation: AsyncMock,
    ) -> None:
        """MilestoneResult contains aggregated totals."""
        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                mock_run_task_with_escalation,
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
        ):
            configure_haiku_mock(mock_brain_class)
            result = await run_milestone(
                plan_path=str(basic_plan_file),
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
        self,
        tmp_path: Path,
        basic_plan_file: Path,
        sample_tasks: list[Task],
        mock_run_task_with_escalation: AsyncMock,
    ) -> None:
        """Resume starts from first incomplete task."""
        # Create existing state with first task completed
        existing_state = OrchestratorState(
            milestone_id=basic_plan_file.stem,
            plan_path=str(basic_plan_file),
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
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                mock_run_task_with_escalation,
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
        ):
            configure_haiku_mock(mock_brain_class)
            await run_milestone(
                plan_path=str(basic_plan_file),
                state_dir=tmp_path,
                resume=True,
            )

        # Should only run tasks 1.2 and 1.3
        assert mock_run_task_with_escalation.call_count == 2
        call_task_ids = [
            call.args[0].id for call in mock_run_task_with_escalation.call_args_list
        ]
        assert call_task_ids == ["1.2", "1.3"]

    @pytest.mark.asyncio
    async def test_fresh_run_ignores_existing_state(
        self,
        tmp_path: Path,
        basic_plan_file: Path,
        sample_tasks: list[Task],
        mock_run_task_with_escalation: AsyncMock,
    ) -> None:
        """Fresh run (resume=False) starts from beginning."""
        # Create existing state with first task completed
        existing_state = OrchestratorState(
            milestone_id=basic_plan_file.stem,
            plan_path=str(basic_plan_file),
            started_at=datetime.now(),
            completed_tasks=["1.1"],
        )
        existing_state.save(tmp_path)

        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                mock_run_task_with_escalation,
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
        ):
            configure_haiku_mock(mock_brain_class)
            await run_milestone(
                plan_path=str(basic_plan_file),
                state_dir=tmp_path,
                resume=False,  # Fresh run
            )

        # Should run all 3 tasks
        assert mock_run_task_with_escalation.call_count == 3


class TestRunMilestoneStatusHandling:
    """Tests for handling different task statuses."""

    @pytest.mark.asyncio
    async def test_stops_on_needs_human(
        self, tmp_path: Path, basic_plan_file: Path, sample_tasks: list[Task]
    ) -> None:
        """Stops execution when task needs human input."""
        call_count = 0

        async def mock_task_with_escalation(
            task: Task,
            container: MagicMock,
            config: MagicMock,
            plan_path: str,
            tracer,
            notify: bool = True,
            on_tool_use=None,
            model: str | None = None,
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
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                AsyncMock(side_effect=mock_task_with_escalation),
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
        ):
            configure_haiku_mock(mock_brain_class)
            result = await run_milestone(
                plan_path=str(basic_plan_file),
                state_dir=tmp_path,
            )

        assert result.status == "needs_human"
        assert call_count == 2  # Ran 1.1 and 1.2, stopped before 1.3
        assert result.completed_tasks == 1

    @pytest.mark.asyncio
    async def test_stops_on_failed(
        self, tmp_path: Path, basic_plan_file: Path, sample_tasks: list[Task]
    ) -> None:
        """Stops execution when task fails."""
        call_count = 0

        async def mock_task_with_escalation(
            task: Task,
            container: MagicMock,
            config: MagicMock,
            plan_path: str,
            tracer,
            notify: bool = True,
            on_tool_use=None,
            model: str | None = None,
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
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                AsyncMock(side_effect=mock_task_with_escalation),
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
        ):
            configure_haiku_mock(mock_brain_class)
            result = await run_milestone(
                plan_path=str(basic_plan_file),
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
        self, tmp_path: Path, basic_plan_file: Path, sample_tasks: list[Task]
    ) -> None:
        """on_task_complete callback is called after each completed task."""
        callback_calls: list[tuple[Task, TaskResult]] = []

        def on_complete(task: Task, result: TaskResult) -> None:
            callback_calls.append((task, result))

        async def mock_task_with_escalation(
            task: Task,
            container: MagicMock,
            config: MagicMock,
            plan_path: str,
            tracer,
            notify: bool = True,
            on_tool_use=None,
            model: str | None = None,
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
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                AsyncMock(side_effect=mock_task_with_escalation),
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
        ):
            configure_haiku_mock(mock_brain_class)
            await run_milestone(
                plan_path=str(basic_plan_file),
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
        self, tmp_path: Path, basic_plan_file: Path, sample_tasks: list[Task]
    ) -> None:
        """on_task_complete callback is NOT called for failed tasks."""
        callback_calls: list[tuple[Task, TaskResult]] = []

        def on_complete(task: Task, result: TaskResult) -> None:
            callback_calls.append((task, result))

        async def mock_task_with_escalation(
            task: Task,
            container: MagicMock,
            config: MagicMock,
            plan_path: str,
            tracer,
            notify: bool = True,
            on_tool_use=None,
            model: str | None = None,
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
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                AsyncMock(side_effect=mock_task_with_escalation),
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
        ):
            configure_haiku_mock(mock_brain_class)
            await run_milestone(
                plan_path=str(basic_plan_file),
                state_dir=tmp_path,
                on_task_complete=on_complete,
            )

        # Only task 1.1 completed, so only 1 callback
        assert len(callback_calls) == 1
        assert callback_calls[0][0].id == "1.1"

    @pytest.mark.asyncio
    async def test_callback_optional(
        self,
        tmp_path: Path,
        basic_plan_file: Path,
        sample_tasks: list[Task],
        mock_run_task_with_escalation: AsyncMock,
    ) -> None:
        """Milestone runs without callback (backward compatibility)."""
        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                mock_run_task_with_escalation,
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
        ):
            # Should not raise - callback is optional
            configure_haiku_mock(mock_brain_class)
            result = await run_milestone(
                plan_path=str(basic_plan_file),
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

        mock_container = MagicMock()
        mock_container.invoke_claude = AsyncMock(
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
            container=mock_container,
            milestone_id="health_check",
            completed_tasks=["1.1", "1.2", "1.3"],
            total_cost_usd=0.15,
        )

        # Verify Claude was invoked
        mock_container.invoke_claude.assert_called_once()
        call_args = mock_container.invoke_claude.call_args

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

        mock_container = MagicMock()
        mock_container.invoke_claude = AsyncMock(
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
            container=mock_container,
            milestone_id="test",
            completed_tasks=["1.1"],
            total_cost_usd=0.05,
        )

        assert result.is_error is True


class TestLoopDetectionIntegration:
    """Tests for loop detection integration in milestone runner."""

    @pytest.mark.asyncio
    async def test_haiku_brain_handles_retry_decisions(
        self, tmp_path: Path, basic_plan_file: Path, sample_tasks: list[Task]
    ) -> None:
        """HaikuBrain handles retry/escalate decisions (not LoopDetector)."""
        task_ids_called: list[str] = []

        async def mock_task_with_escalation(
            task: Task,
            container: MagicMock,
            config: MagicMock,
            plan_path: str,
            tracer,
            notify: bool = True,
            on_tool_use=None,
            model: str | None = None,
        ) -> TaskResult:
            # Track which tasks were called
            task_ids_called.append(task.id)
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
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                AsyncMock(side_effect=mock_task_with_escalation),
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
        ):
            configure_haiku_mock(mock_brain_class)
            await run_milestone(
                plan_path=str(basic_plan_file),
                state_dir=tmp_path,
            )

        # All tasks should be called
        assert len(task_ids_called) == 3
        assert task_ids_called == ["1.1", "1.2", "1.3"]

    @pytest.mark.asyncio
    async def test_state_persisted_for_resume(
        self, tmp_path: Path, basic_plan_file: Path, sample_tasks: list[Task]
    ) -> None:
        """Task state survives resume (completed_tasks, failed_tasks)."""
        # First run: task 1.2 fails
        call_count = 0

        async def first_run_mock(
            task: Task,
            container: MagicMock,
            config: MagicMock,
            plan_path: str,
            tracer,
            notify: bool = True,
            on_tool_use=None,
            model: str | None = None,
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
                    output="Failed",
                    session_id="test",
                    error="First failure",
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
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                AsyncMock(side_effect=first_run_mock),
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
        ):
            configure_haiku_mock(mock_brain_class)
            await run_milestone(
                plan_path=str(basic_plan_file),
                state_dir=tmp_path,
            )

        # Load state and verify task state was persisted
        state = OrchestratorState.load(tmp_path, basic_plan_file.stem)
        assert state is not None
        assert "1.1" in state.completed_tasks
        assert "1.2" in state.failed_tasks

    @pytest.mark.asyncio
    async def test_milestone_stops_on_failed_task(
        self, tmp_path: Path, basic_plan_file: Path, sample_tasks: list[Task]
    ) -> None:
        """Milestone stops when task fails."""
        call_count = 0

        async def failed_task_mock(
            task: Task,
            container: MagicMock,
            config: MagicMock,
            plan_path: str,
            tracer,
            notify: bool = True,
            on_tool_use=None,
            model: str | None = None,
        ) -> TaskResult:
            nonlocal call_count
            call_count += 1

            if task.id == "1.2":
                # Simulate task failure (HaikuBrain escalation triggered)
                return TaskResult(
                    task_id=task.id,
                    status="failed",
                    duration_seconds=0.0,
                    tokens_used=0,
                    cost_usd=0.0,
                    output="",
                    session_id="",
                    error="Task failed after multiple attempts",
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
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                AsyncMock(side_effect=failed_task_mock),
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
        ):
            configure_haiku_mock(mock_brain_class)
            result = await run_milestone(
                plan_path=str(basic_plan_file),
                state_dir=tmp_path,
            )

        # Milestone should stop with failed status
        assert result.status == "failed"
        # Should only run 1.1 (completed) and 1.2 (failed)
        assert call_count == 2
        assert result.failed_tasks == 1

    @pytest.mark.asyncio
    async def test_resume_skips_previously_completed_tasks(
        self, tmp_path: Path, basic_plan_file: Path, sample_tasks: list[Task]
    ) -> None:
        """Resume skips previously completed tasks."""
        # Create state with existing completed tasks
        existing_state = OrchestratorState(
            milestone_id=basic_plan_file.stem,
            plan_path=str(basic_plan_file),
            started_at=datetime.now(),
            completed_tasks=["1.1"],  # 1.1 already completed
        )
        existing_state.save(tmp_path)

        tasks_called: list[str] = []

        async def check_tasks_mock(
            task: Task,
            container: MagicMock,
            config: MagicMock,
            plan_path: str,
            tracer,
            notify: bool = True,
            on_tool_use=None,
            model: str | None = None,
        ) -> TaskResult:
            tasks_called.append(task.id)
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
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                AsyncMock(side_effect=check_tasks_mock),
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
        ):
            configure_haiku_mock(mock_brain_class)
            await run_milestone(
                plan_path=str(basic_plan_file),
                state_dir=tmp_path,
                resume=True,
            )

        # Verify 1.1 was skipped (already completed)
        assert "1.1" not in tasks_called
        # Verify 1.2 and 1.3 were run
        assert tasks_called == ["1.2", "1.3"]


class TestDiscordNotificationIntegration:
    """Tests for Discord notification integration in milestone runner."""

    @pytest.mark.asyncio
    async def test_sends_milestone_started_notification(
        self, tmp_path: Path, basic_plan_file: Path, mock_run_task_with_escalation: AsyncMock
    ) -> None:
        """Discord notification sent when milestone starts."""
        from orchestrator.config import OrchestratorConfig

        config = OrchestratorConfig(discord_webhook_url="https://discord.com/test")

        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                mock_run_task_with_escalation,
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
            patch(
                "orchestrator.milestone_runner.send_discord_message",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            configure_haiku_mock(mock_brain_class)
            await run_milestone(
                plan_path=str(basic_plan_file),
                state_dir=tmp_path,
                config=config,
            )

        # Should have sent milestone started notification
        assert mock_send.called
        # First call should be milestone started (format_milestone_started returns blue embed)
        first_call_embed = mock_send.call_args_list[0][0][1]
        assert "Started" in first_call_embed.title or "🚀" in first_call_embed.title

    @pytest.mark.asyncio
    async def test_sends_task_completed_notifications(
        self, tmp_path: Path, basic_plan_file: Path, mock_run_task_with_escalation: AsyncMock
    ) -> None:
        """Discord notification sent for each completed task."""
        from orchestrator.config import OrchestratorConfig

        config = OrchestratorConfig(discord_webhook_url="https://discord.com/test")

        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                mock_run_task_with_escalation,
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
            patch(
                "orchestrator.milestone_runner.send_discord_message",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            configure_haiku_mock(mock_brain_class)
            await run_milestone(
                plan_path=str(basic_plan_file),
                state_dir=tmp_path,
                config=config,
            )

        # Should have sent: 1 milestone started + 3 task completed + 1 milestone completed = 5
        assert mock_send.call_count >= 4  # At least started + 3 tasks

    @pytest.mark.asyncio
    async def test_sends_task_failed_notification(
        self, tmp_path: Path, basic_plan_file: Path
    ) -> None:
        """Discord notification sent when task fails."""
        from orchestrator.config import OrchestratorConfig

        config = OrchestratorConfig(discord_webhook_url="https://discord.com/test")

        async def mock_task_with_failure(
            task: Task,
            container: MagicMock,
            config: MagicMock,
            plan_path: str,
            tracer,
            **kwargs,
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
                    error="Connection refused",
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
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                AsyncMock(side_effect=mock_task_with_failure),
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
            patch(
                "orchestrator.milestone_runner.send_discord_message",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            configure_haiku_mock(mock_brain_class)
            await run_milestone(
                plan_path=str(basic_plan_file),
                state_dir=tmp_path,
                config=config,
            )

        # Should have sent task failed notification (red color)
        call_embeds = [call[0][1] for call in mock_send.call_args_list]
        failed_embeds = [e for e in call_embeds if "Failed" in e.title or "❌" in e.title]
        assert len(failed_embeds) >= 1

    @pytest.mark.asyncio
    async def test_sends_milestone_completed_notification(
        self, tmp_path: Path, basic_plan_file: Path, mock_run_task_with_escalation: AsyncMock
    ) -> None:
        """Discord notification sent when milestone completes."""
        from orchestrator.config import OrchestratorConfig

        config = OrchestratorConfig(discord_webhook_url="https://discord.com/test")

        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                mock_run_task_with_escalation,
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
            patch(
                "orchestrator.milestone_runner.send_discord_message",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            configure_haiku_mock(mock_brain_class)
            await run_milestone(
                plan_path=str(basic_plan_file),
                state_dir=tmp_path,
                config=config,
            )

        # Last notification should be milestone completed (purple color)
        last_call_embed = mock_send.call_args_list[-1][0][1]
        assert "Complete" in last_call_embed.title or "🎉" in last_call_embed.title

    @pytest.mark.asyncio
    async def test_no_notifications_when_discord_disabled(
        self, tmp_path: Path, basic_plan_file: Path, mock_run_task_with_escalation: AsyncMock
    ) -> None:
        """No Discord notifications when webhook URL is not set."""
        from orchestrator.config import OrchestratorConfig

        config = OrchestratorConfig(discord_webhook_url=None)

        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                mock_run_task_with_escalation,
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
            patch(
                "orchestrator.milestone_runner.send_discord_message",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            configure_haiku_mock(mock_brain_class)
            await run_milestone(
                plan_path=str(basic_plan_file),
                state_dir=tmp_path,
                config=config,
            )

        # Should not have sent any notifications
        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_notifications_complete_with_milestone(
        self, tmp_path: Path, basic_plan_file: Path, mock_run_task_with_escalation: AsyncMock
    ) -> None:
        """Discord notifications are awaited and complete with the milestone.

        Notifications are now awaited to ensure delivery. The HTTP client
        has a 5-second timeout, so notifications won't block indefinitely.
        """
        from orchestrator.config import OrchestratorConfig

        config = OrchestratorConfig(discord_webhook_url="https://discord.com/test")

        # Track notification calls
        notification_calls = []

        async def track_discord_message(*args, **kwargs):
            notification_calls.append(args)

        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                mock_run_task_with_escalation,
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
            patch(
                "orchestrator.milestone_runner.send_discord_message",
                side_effect=track_discord_message,
            ),
        ):
            configure_haiku_mock(mock_brain_class)
            await run_milestone(
                plan_path=str(basic_plan_file),
                state_dir=tmp_path,
                config=config,
            )

        # Should have sent milestone started + task completed + milestone completed
        assert len(notification_calls) >= 2, "Expected at least 2 notifications"

    @pytest.mark.asyncio
    async def test_graceful_failure_with_invalid_webhook(
        self, tmp_path: Path, basic_plan_file: Path, mock_run_task_with_escalation: AsyncMock
    ) -> None:
        """Milestone completes successfully even if webhook fails.

        The send_discord_message function handles exceptions internally,
        so we mock at the httpx level to trigger that error handling.
        """
        import httpx

        from orchestrator.config import OrchestratorConfig

        config = OrchestratorConfig(discord_webhook_url="https://invalid.webhook")

        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                mock_run_task_with_escalation,
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
            patch(
                "orchestrator.discord_notifier.httpx.AsyncClient.post",
                new_callable=AsyncMock,
                side_effect=httpx.ConnectError("Connection failed"),
            ),
        ):
            configure_haiku_mock(mock_brain_class)
            # Should not raise even if Discord fails
            result = await run_milestone(
                plan_path=str(basic_plan_file),
                state_dir=tmp_path,
                config=config,
            )

        # Milestone should still complete successfully
        assert result.status == "completed"


class TestE2EIntegration:
    """Tests for E2E test integration in milestone runner."""

    @pytest.fixture
    def plan_file(self, tmp_path: Path) -> Path:
        """Create a test plan file."""
        plan_path = tmp_path / "test_plan.md"
        plan_path.write_text(
            """# Test Milestone

## E2E Test

```bash
pytest tests/ -v
```
"""
        )
        return plan_path

    @pytest.mark.asyncio
    async def test_runs_e2e_after_tasks_complete(
        self,
        tmp_path: Path,
        plan_file: Path,
        sample_tasks: list[Task],
        mock_run_task_with_escalation: AsyncMock,
    ) -> None:
        """E2E tests are run after all tasks complete successfully."""
        from orchestrator.runner import E2EResult

        mock_e2e_result = E2EResult(
            status="passed",
            duration_seconds=45.0,
            tokens_used=5000,
            cost_usd=0.05,
            raw_output="E2E_STATUS: passed",
        )

        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                mock_run_task_with_escalation,
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
            patch(
                "orchestrator.milestone_runner.run_e2e_tests",
                AsyncMock(return_value=mock_e2e_result),
            ) as mock_run_e2e,
        ):
            configure_haiku_mock(mock_brain_class)
            result = await run_milestone(
                plan_path=str(plan_file),
                state_dir=tmp_path,
            )

        # E2E should have been called
        mock_run_e2e.assert_called_once()
        assert result.status == "completed"
        assert result.state.e2e_status == "passed"

    @pytest.mark.asyncio
    async def test_skips_e2e_when_no_scenario(
        self,
        tmp_path: Path,
        sample_tasks: list[Task],
        mock_run_task_with_escalation: AsyncMock,
    ) -> None:
        """E2E is skipped when no scenario in plan."""
        # Create a plan file without E2E section
        no_e2e_plan = tmp_path / "no_e2e_plan.md"
        no_e2e_plan.write_text("# Test Milestone\n\nNo E2E here.\n")

        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                mock_run_task_with_escalation,
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
            patch(
                "orchestrator.milestone_runner.run_e2e_tests",
                AsyncMock(),
            ) as mock_run_e2e,
        ):
            configure_haiku_mock(mock_brain_class)
            result = await run_milestone(
                plan_path=str(no_e2e_plan),
                state_dir=tmp_path,
            )

        # E2E should NOT have been called
        mock_run_e2e.assert_not_called()
        assert result.status == "completed"
        assert result.state.e2e_status is None

    @pytest.mark.asyncio
    async def test_e2e_failure_returns_e2e_failed_status(
        self, tmp_path: Path, plan_file: Path, sample_tasks: list[Task]
    ) -> None:
        """E2E failure that can't be fixed returns e2e_failed status."""
        from orchestrator.runner import E2EResult

        async def mock_task_success(
            task: Task,
            container: MagicMock,
            config: MagicMock,
            plan_path: str,
            tracer,
            **kwargs,
        ) -> TaskResult:
            return TaskResult(
                task_id=task.id,
                status="completed",
                duration_seconds=10.0,
                tokens_used=1000,
                cost_usd=0.01,
                output="Done",
                session_id="test",
            )

        mock_e2e_result = E2EResult(
            status="failed",
            duration_seconds=30.0,
            tokens_used=3000,
            cost_usd=0.03,
            diagnosis="External API is down",
            is_fixable=False,
            raw_output="E2E_STATUS: failed\nDIAGNOSIS: External API is down",
        )

        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                AsyncMock(side_effect=mock_task_success),
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
            patch(
                "orchestrator.milestone_runner.run_e2e_tests",
                AsyncMock(return_value=mock_e2e_result),
            ),
            patch(
                "orchestrator.milestone_runner.escalate_and_wait",
                AsyncMock(return_value="Skip for now"),
            ),
        ):
            configure_haiku_mock(mock_brain_class)
            result = await run_milestone(
                plan_path=str(plan_file),
                state_dir=tmp_path,
            )

        assert result.status == "e2e_failed"
        assert result.state.e2e_status == "failed"

    @pytest.mark.asyncio
    async def test_e2e_fixable_prompts_and_applies_fix(
        self, tmp_path: Path, plan_file: Path, sample_tasks: list[Task]
    ) -> None:
        """Fixable E2E failure prompts user and applies fix."""
        from orchestrator.runner import E2EResult

        async def mock_task_success(
            task: Task,
            container: MagicMock,
            config: MagicMock,
            plan_path: str,
            tracer,
            **kwargs,
        ) -> TaskResult:
            return TaskResult(
                task_id=task.id,
                status="completed",
                duration_seconds=10.0,
                tokens_used=1000,
                cost_usd=0.01,
                output="Done",
                session_id="test",
            )

        # First call fails, second call passes after fix
        e2e_results = [
            E2EResult(
                status="failed",
                duration_seconds=30.0,
                tokens_used=3000,
                cost_usd=0.03,
                diagnosis="Missing router",
                fix_suggestion="Add router to main.py",
                is_fixable=True,
                raw_output="E2E_STATUS: failed\nFIXABLE: yes",
            ),
            E2EResult(
                status="passed",
                duration_seconds=30.0,
                tokens_used=3000,
                cost_usd=0.03,
                raw_output="E2E_STATUS: passed",
            ),
        ]
        e2e_call_count = 0

        async def mock_run_e2e(*args, **kwargs):
            nonlocal e2e_call_count
            result = e2e_results[e2e_call_count]
            e2e_call_count += 1
            return result

        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                AsyncMock(side_effect=mock_task_success),
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
            patch(
                "orchestrator.milestone_runner.run_e2e_tests",
                AsyncMock(side_effect=mock_run_e2e),
            ),
            patch(
                "orchestrator.milestone_runner.apply_e2e_fix",
                AsyncMock(return_value=True),
            ) as mock_apply_fix,
            patch(
                "orchestrator.milestone_runner.prompt_for_fix",
                return_value=True,
            ),
        ):
            configure_haiku_mock(mock_brain_class)
            result = await run_milestone(
                plan_path=str(plan_file),
                state_dir=tmp_path,
            )

        # Fix should have been applied
        mock_apply_fix.assert_called_once()
        # E2E should have been called twice (fail + pass after fix)
        assert e2e_call_count == 2
        assert result.status == "completed"
        assert result.state.e2e_status == "passed"

    @pytest.mark.asyncio
    async def test_e2e_loop_detection_stops_fix_cycle(
        self, tmp_path: Path, plan_file: Path, sample_tasks: list[Task]
    ) -> None:
        """Loop detection stops E2E fix cycle."""
        from orchestrator.runner import E2EResult

        async def mock_task_success(
            task: Task,
            container: MagicMock,
            config: MagicMock,
            plan_path: str,
            tracer,
            **kwargs,
        ) -> TaskResult:
            return TaskResult(
                task_id=task.id,
                status="completed",
                duration_seconds=10.0,
                tokens_used=1000,
                cost_usd=0.01,
                output="Done",
                session_id="test",
            )

        # Keep returning failed
        mock_e2e_result = E2EResult(
            status="failed",
            duration_seconds=30.0,
            tokens_used=3000,
            cost_usd=0.03,
            diagnosis="Same error",
            fix_suggestion="Try fix",
            is_fixable=True,
            raw_output="E2E_STATUS: failed",
        )

        e2e_call_count = 0

        async def mock_run_e2e(*args, **kwargs):
            nonlocal e2e_call_count
            e2e_call_count += 1
            return mock_e2e_result

        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                AsyncMock(side_effect=mock_task_success),
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
            patch(
                "orchestrator.milestone_runner.run_e2e_tests",
                AsyncMock(side_effect=mock_run_e2e),
            ),
            patch(
                "orchestrator.milestone_runner.apply_e2e_fix",
                AsyncMock(return_value=True),
            ),
            patch(
                "orchestrator.milestone_runner.prompt_for_fix",
                return_value=True,  # User keeps saying yes
            ),
        ):
            configure_haiku_mock(mock_brain_class)
            result = await run_milestone(
                plan_path=str(plan_file),
                state_dir=tmp_path,
            )

        # Should stop due to loop detection (max 5 E2E attempts by default)
        assert e2e_call_count <= 5
        assert result.status == "e2e_failed"

    @pytest.mark.asyncio
    async def test_e2e_unclear_escalates_to_human(
        self, tmp_path: Path, plan_file: Path, sample_tasks: list[Task]
    ) -> None:
        """Unclear E2E status escalates to human."""
        from orchestrator.runner import E2EResult

        async def mock_task_success(
            task: Task,
            container: MagicMock,
            config: MagicMock,
            plan_path: str,
            tracer,
            **kwargs,
        ) -> TaskResult:
            return TaskResult(
                task_id=task.id,
                status="completed",
                duration_seconds=10.0,
                tokens_used=1000,
                cost_usd=0.01,
                output="Done",
                session_id="test",
            )

        mock_e2e_result = E2EResult(
            status="unclear",
            duration_seconds=30.0,
            tokens_used=3000,
            cost_usd=0.03,
            raw_output="Some ambiguous output",
        )

        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                AsyncMock(side_effect=mock_task_success),
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
            patch(
                "orchestrator.milestone_runner.run_e2e_tests",
                AsyncMock(return_value=mock_e2e_result),
            ),
            patch(
                "orchestrator.milestone_runner.escalate_and_wait",
                AsyncMock(return_value="Skip"),
            ) as mock_escalate,
        ):
            configure_haiku_mock(mock_brain_class)
            result = await run_milestone(
                plan_path=str(plan_file),
                state_dir=tmp_path,
            )

        # Should escalate for unclear status
        mock_escalate.assert_called_once()
        assert result.status == "e2e_failed"

    @pytest.mark.asyncio
    async def test_e2e_state_persisted(
        self, tmp_path: Path, plan_file: Path, sample_tasks: list[Task]
    ) -> None:
        """E2E status is persisted to state."""
        from orchestrator.runner import E2EResult

        async def mock_task_success(
            task: Task,
            container: MagicMock,
            config: MagicMock,
            plan_path: str,
            tracer,
            **kwargs,
        ) -> TaskResult:
            return TaskResult(
                task_id=task.id,
                status="completed",
                duration_seconds=10.0,
                tokens_used=1000,
                cost_usd=0.01,
                output="Done",
                session_id="test",
            )

        mock_e2e_result = E2EResult(
            status="passed",
            duration_seconds=30.0,
            tokens_used=3000,
            cost_usd=0.03,
            raw_output="E2E_STATUS: passed",
        )

        with (
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                AsyncMock(side_effect=mock_task_success),
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
            patch(
                "orchestrator.milestone_runner.run_e2e_tests",
                AsyncMock(return_value=mock_e2e_result),
            ),
        ):
            configure_haiku_mock(mock_brain_class)
            await run_milestone(
                plan_path=str(plan_file),
                state_dir=tmp_path,
            )

        # Load state and verify E2E status was persisted
        state = OrchestratorState.load(tmp_path, plan_file.stem)
        assert state is not None
        assert state.e2e_status == "passed"

    @pytest.mark.asyncio
    async def test_e2e_skipped_when_tasks_fail(
        self, tmp_path: Path, plan_file: Path, sample_tasks: list[Task]
    ) -> None:
        """E2E is not run when tasks fail."""
        call_count = 0

        async def mock_task_with_failure(
            task: Task,
            container: MagicMock,
            config: MagicMock,
            plan_path: str,
            tracer,
            **kwargs,
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
                    output="Failed",
                    session_id="test",
                    error="Error",
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
            patch("orchestrator.milestone_runner.HaikuBrain") as mock_brain_class,
            patch(
                "orchestrator.milestone_runner.run_task_with_escalation",
                AsyncMock(side_effect=mock_task_with_failure),
            ),
            patch("orchestrator.milestone_runner.CodingAgentContainer"),
            patch("orchestrator.milestone_runner.validate_environment"),
            patch(
                "orchestrator.milestone_runner.run_e2e_tests",
                AsyncMock(),
            ) as mock_run_e2e,
        ):
            configure_haiku_mock(mock_brain_class)
            result = await run_milestone(
                plan_path=str(plan_file),
                state_dir=tmp_path,
            )

        # E2E should NOT be called when tasks fail
        mock_run_e2e.assert_not_called()
        assert result.status == "failed"
