"""Tests for E2E test plan files.

Verifies that e2e_will_pass.md and e2e_will_fail_fixable.md
are parseable by the plan_parser and contain valid E2E scenarios.
"""

from pathlib import Path

import pytest

from orchestrator.plan_parser import parse_e2e_scenario, parse_plan

TEST_PLANS_DIR = Path(__file__).parent.parent / "test_plans"


class TestE2EWillPassPlan:
    """Tests for e2e_will_pass.md test plan."""

    @pytest.fixture
    def plan_path(self) -> Path:
        """Return path to e2e_will_pass.md."""
        return TEST_PLANS_DIR / "e2e_will_pass.md"

    @pytest.fixture
    def plan_content(self, plan_path: Path) -> str:
        """Read plan content."""
        return plan_path.read_text()

    def test_plan_file_exists(self, plan_path: Path):
        """Plan file should exist."""
        assert plan_path.exists(), f"Plan file not found: {plan_path}"

    def test_plan_is_parseable(self, plan_path: Path):
        """Plan should be parseable by parse_plan."""
        tasks = parse_plan(plan_path)
        assert len(tasks) >= 1, "Should have at least one task"

    def test_has_calculator_task(self, plan_path: Path):
        """Should have a task to create calculator module."""
        tasks = parse_plan(plan_path)
        task_titles = [t.title.lower() for t in tasks]
        assert any("calculator" in title for title in task_titles), (
            "Should have a calculator-related task"
        )

    def test_has_test_task(self, plan_path: Path):
        """Should have a task to create tests."""
        tasks = parse_plan(plan_path)
        task_titles = [t.title.lower() for t in tasks]
        assert any("test" in title for title in task_titles), (
            "Should have a test-related task"
        )

    def test_e2e_scenario_extractable(self, plan_content: str):
        """E2E scenario should be extractable from plan."""
        scenario = parse_e2e_scenario(plan_content)
        assert scenario is not None, "Should have E2E scenario"

    def test_e2e_scenario_runs_pytest(self, plan_content: str):
        """E2E scenario should run pytest."""
        scenario = parse_e2e_scenario(plan_content)
        assert scenario is not None
        assert "pytest" in scenario.lower(), "E2E should run pytest"

    def test_e2e_scenario_tests_calculator(self, plan_content: str):
        """E2E scenario should test calculator."""
        scenario = parse_e2e_scenario(plan_content)
        assert scenario is not None
        assert "calculator" in scenario.lower(), "E2E should test calculator"


class TestE2EWillFailFixablePlan:
    """Tests for e2e_will_fail_fixable.md test plan."""

    @pytest.fixture
    def plan_path(self) -> Path:
        """Return path to e2e_will_fail_fixable.md."""
        return TEST_PLANS_DIR / "e2e_will_fail_fixable.md"

    @pytest.fixture
    def plan_content(self, plan_path: Path) -> str:
        """Read plan content."""
        return plan_path.read_text()

    def test_plan_file_exists(self, plan_path: Path):
        """Plan file should exist."""
        assert plan_path.exists(), f"Plan file not found: {plan_path}"

    def test_plan_is_parseable(self, plan_path: Path):
        """Plan should be parseable by parse_plan."""
        tasks = parse_plan(plan_path)
        assert len(tasks) >= 1, "Should have at least one task"

    def test_has_greeting_task(self, plan_path: Path):
        """Should have a task to create greeting module."""
        tasks = parse_plan(plan_path)
        task_titles = [t.title.lower() for t in tasks]
        assert any("greeting" in title for title in task_titles), (
            "Should have a greeting-related task"
        )

    def test_e2e_scenario_extractable(self, plan_content: str):
        """E2E scenario should be extractable from plan."""
        scenario = parse_e2e_scenario(plan_content)
        assert scenario is not None, "Should have E2E scenario"

    def test_e2e_scenario_tests_greeting(self, plan_content: str):
        """E2E scenario should test greeting function."""
        scenario = parse_e2e_scenario(plan_content)
        assert scenario is not None
        assert "greet" in scenario.lower(), "E2E should test greeting"

    def test_e2e_scenario_expects_failure(self, plan_content: str):
        """E2E scenario should mention expected failure."""
        scenario = parse_e2e_scenario(plan_content)
        assert scenario is not None
        # Should mention that it's expected to fail
        assert "fail" in scenario.lower() or "should" in scenario.lower(), (
            "E2E should indicate expected failure"
        )

    def test_task_mentions_intentional_bug(self, plan_path: Path):
        """Task description should mention intentional bug."""
        tasks = parse_plan(plan_path)
        # Find the greeting task
        greeting_tasks = [t for t in tasks if "greeting" in t.title.lower()]
        assert len(greeting_tasks) > 0, "Should have greeting task"

        # Check description mentions the bug
        greeting_task = greeting_tasks[0]
        desc_lower = greeting_task.description.lower()
        assert (
            "bug" in desc_lower or "intentional" in desc_lower or "miss" in desc_lower
        ), "Task should mention the intentional bug"


class TestBothPlansHaveValidStructure:
    """Cross-cutting tests for both test plans."""

    @pytest.fixture(params=["e2e_will_pass.md", "e2e_will_fail_fixable.md"])
    def plan_path(self, request) -> Path:
        """Return path to each plan file."""
        return TEST_PLANS_DIR / request.param

    def test_has_frontmatter(self, plan_path: Path):
        """Plan should have frontmatter with design/architecture refs."""
        content = plan_path.read_text()
        # Check for YAML frontmatter
        assert content.strip().startswith("---"), "Should start with frontmatter"
        # Find end of frontmatter
        second_dashes = content.find("---", 3)
        assert second_dashes > 0, "Should have closing frontmatter"

    def test_has_milestone_header(self, plan_path: Path):
        """Plan should have milestone/title header."""
        content = plan_path.read_text()
        # Should have a # header (not task header)
        lines = content.split("\n")
        has_main_header = any(
            line.startswith("# ") and "Task" not in line for line in lines
        )
        assert has_main_header, "Should have main milestone/title header"

    def test_tasks_have_acceptance_criteria(self, plan_path: Path):
        """All tasks should have acceptance criteria."""
        tasks = parse_plan(plan_path)
        for task in tasks:
            assert len(task.acceptance_criteria) > 0, (
                f"Task {task.id} should have acceptance criteria"
            )
