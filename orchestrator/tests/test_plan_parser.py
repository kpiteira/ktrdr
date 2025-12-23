"""Tests for plan parser module.

These tests verify parsing of milestone markdown files into Task objects.
"""

import textwrap
from tempfile import NamedTemporaryFile


class TestParseTaskId:
    """Test parsing of task IDs from headers."""

    def test_parse_task_id_from_header(self):
        """Should parse task ID like '2.1' from header."""
        from orchestrator.plan_parser import parse_plan

        content = textwrap.dedent("""
            # Milestone 2: Test

            ## Task 2.1: Create package

            **Description:**
            Set up the package structure.

            **Acceptance Criteria:**
            - [ ] Package works
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            tasks = parse_plan(f.name)

        assert len(tasks) == 1
        assert tasks[0].id == "2.1"

    def test_parse_multiple_tasks(self):
        """Should parse multiple tasks from a plan."""
        from orchestrator.plan_parser import parse_plan

        content = textwrap.dedent("""
            # Milestone 2

            ## Task 2.1: First task

            **Description:** First description

            **Acceptance Criteria:**
            - [ ] Criterion 1

            ---

            ## Task 2.2: Second task

            **Description:** Second description

            **Acceptance Criteria:**
            - [ ] Criterion 2
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            tasks = parse_plan(f.name)

        assert len(tasks) == 2
        assert tasks[0].id == "2.1"
        assert tasks[1].id == "2.2"

    def test_parse_task_with_triple_header(self):
        """Should parse task ID from ### header too."""
        from orchestrator.plan_parser import parse_plan

        content = textwrap.dedent("""
            # Milestone

            ### Task 1.1: Create file

            **Description:** Create a file

            **Acceptance Criteria:**
            - [ ] File exists
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            tasks = parse_plan(f.name)

        assert len(tasks) == 1
        assert tasks[0].id == "1.1"


class TestParseTaskTitle:
    """Test parsing of task titles."""

    def test_parse_title_from_header(self):
        """Should extract title from task header."""
        from orchestrator.plan_parser import parse_plan

        content = textwrap.dedent("""
            # Milestone

            ## Task 2.1: Create Orchestrator Package Structure

            **Description:** Setup package

            **Acceptance Criteria:**
            - [ ] Package works
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            tasks = parse_plan(f.name)

        assert tasks[0].title == "Create Orchestrator Package Structure"


class TestParseFilePath:
    """Test parsing of file paths."""

    def test_parse_file_path(self):
        """Should extract file path from **File:** field."""
        from orchestrator.plan_parser import parse_plan

        content = textwrap.dedent("""
            # Milestone

            ## Task 2.1: Create config

            **File:** orchestrator/config.py

            **Description:** Create config module

            **Acceptance Criteria:**
            - [ ] Config works
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            tasks = parse_plan(f.name)

        assert tasks[0].file_path == "orchestrator/config.py"

    def test_parse_files_plural(self):
        """Should handle **Files:** (plural) field."""
        from orchestrator.plan_parser import parse_plan

        content = textwrap.dedent("""
            # Milestone

            ## Task 2.1: Create files

            **Files:**
            - orchestrator/__init__.py
            - orchestrator/__main__.py

            **Description:** Create package files

            **Acceptance Criteria:**
            - [ ] Files exist
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            tasks = parse_plan(f.name)

        # Should capture first file or combine them
        assert tasks[0].file_path is not None

    def test_missing_file_path_is_none(self):
        """Should return None for file_path when not specified."""
        from orchestrator.plan_parser import parse_plan

        content = textwrap.dedent("""
            # Milestone

            ## Task 2.1: Research task

            **Description:** Research something

            **Acceptance Criteria:**
            - [ ] Research complete
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            tasks = parse_plan(f.name)

        assert tasks[0].file_path is None


class TestParseAcceptanceCriteria:
    """Test parsing of acceptance criteria."""

    def test_parse_acceptance_criteria(self):
        """Should extract acceptance criteria from checkbox list."""
        from orchestrator.plan_parser import parse_plan

        content = textwrap.dedent("""
            # Milestone

            ## Task 2.1: Create package

            **Description:** Setup

            **Acceptance Criteria:**
            - [ ] Package is importable
            - [ ] CLI works
            - [ ] Type hints enabled
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            tasks = parse_plan(f.name)

        assert len(tasks[0].acceptance_criteria) == 3
        assert "Package is importable" in tasks[0].acceptance_criteria[0]
        assert "CLI works" in tasks[0].acceptance_criteria[1]

    def test_parse_criteria_without_checkboxes(self):
        """Should handle criteria without checkboxes."""
        from orchestrator.plan_parser import parse_plan

        content = textwrap.dedent("""
            # Milestone

            ## Task 2.1: Create package

            **Description:** Setup

            **Acceptance Criteria:**
            - Package is importable
            - CLI works
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            tasks = parse_plan(f.name)

        assert len(tasks[0].acceptance_criteria) == 2


class TestParseDescription:
    """Test parsing of task descriptions."""

    def test_parse_description(self):
        """Should extract description text."""
        from orchestrator.plan_parser import parse_plan

        content = textwrap.dedent("""
            # Milestone

            ## Task 2.1: Create package

            **Description:**
            Set up the orchestrator as a Python package with entry point.

            **Acceptance Criteria:**
            - [ ] Works
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            tasks = parse_plan(f.name)

        assert "orchestrator" in tasks[0].description.lower()
        assert "Python package" in tasks[0].description


class TestParseMilestoneId:
    """Test extraction of milestone ID."""

    def test_extract_milestone_id(self):
        """Should extract milestone ID from plan."""
        from orchestrator.plan_parser import parse_plan

        content = textwrap.dedent("""
            # Milestone 2: Single Task Execution

            ## Task 2.1: Create package

            **Description:** Setup

            **Acceptance Criteria:**
            - [ ] Works
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            tasks = parse_plan(f.name)

        assert tasks[0].milestone_id == "M2"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_plan_returns_empty_list(self):
        """Should return empty list for plan with no tasks."""
        from orchestrator.plan_parser import parse_plan

        content = textwrap.dedent("""
            # Milestone 1

            Just some overview text with no tasks.
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            tasks = parse_plan(f.name)

        assert tasks == []

    def test_plan_file_path_stored(self):
        """Should store the plan file path in each task."""
        from orchestrator.plan_parser import parse_plan

        content = textwrap.dedent("""
            # Milestone

            ## Task 1.1: Test

            **Description:** Test

            **Acceptance Criteria:**
            - [ ] Works
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            tasks = parse_plan(f.name)

        assert tasks[0].plan_file == f.name

    def test_handles_task_with_code_blocks(self):
        """Should handle tasks that contain code blocks."""
        from orchestrator.plan_parser import parse_plan

        content = textwrap.dedent("""
            # Milestone

            ## Task 2.1: Create config

            **File:** config.py

            **Description:**
            Create config with this structure:

            ```python
            @dataclass
            class Config:
                value: str = "default"
            ```

            **Acceptance Criteria:**
            - [ ] Config works
        """)

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            tasks = parse_plan(f.name)

        assert len(tasks) == 1
        assert tasks[0].id == "2.1"


class TestParseE2EScenario:
    """Test parsing of E2E test scenarios from plans."""

    def test_extracts_e2e_from_code_block(self):
        """Should extract E2E scenario from code block."""
        from orchestrator.plan_parser import parse_e2e_scenario

        content = textwrap.dedent("""
            # Milestone

            ## E2E Test

            ```bash
            cd /workspace
            python -m pytest test_calculator.py -v
            ```
        """)

        result = parse_e2e_scenario(content)

        assert result is not None
        assert "cd /workspace" in result
        assert "pytest test_calculator.py" in result

    def test_extracts_e2e_from_code_block_with_scenario_suffix(self):
        """Should handle 'E2E Test Scenario' header."""
        from orchestrator.plan_parser import parse_e2e_scenario

        content = textwrap.dedent("""
            # Milestone

            ## E2E Test Scenario

            ```bash
            curl http://localhost:8000/health
            ```
        """)

        result = parse_e2e_scenario(content)

        assert result is not None
        assert "curl" in result

    def test_extracts_e2e_from_plain_text(self):
        """Should extract E2E from plain text when no code block."""
        from orchestrator.plan_parser import parse_e2e_scenario

        content = textwrap.dedent("""
            # Milestone

            ## E2E Test

            Run the calculator tests with pytest.
            Verify all tests pass.

            ## Next Section
        """)

        result = parse_e2e_scenario(content)

        assert result is not None
        assert "calculator" in result.lower()
        assert "pytest" in result.lower()

    def test_returns_none_when_no_e2e_section(self):
        """Should return None when no E2E section exists."""
        from orchestrator.plan_parser import parse_e2e_scenario

        content = textwrap.dedent("""
            # Milestone

            ## Task 1.1: Create something

            **Description:** Create a thing

            **Acceptance Criteria:**
            - [ ] Thing exists
        """)

        result = parse_e2e_scenario(content)

        assert result is None

    def test_extracts_multiple_code_blocks(self):
        """Should extract multiple code blocks in E2E section."""
        from orchestrator.plan_parser import parse_e2e_scenario

        content = textwrap.dedent("""
            # Milestone

            ## E2E Test

            ```bash
            # First test
            python test_a.py
            ```

            Then verify:

            ```bash
            # Second test
            python test_b.py
            ```

            ## Tasks
        """)

        result = parse_e2e_scenario(content)

        assert result is not None
        assert "test_a.py" in result
        assert "test_b.py" in result

    def test_handles_code_block_without_language(self):
        """Should handle code blocks without language specifier."""
        from orchestrator.plan_parser import parse_e2e_scenario

        content = textwrap.dedent("""
            # Milestone

            ## E2E Test

            ```
            python -m pytest
            ```
        """)

        result = parse_e2e_scenario(content)

        assert result is not None
        assert "pytest" in result

    def test_stops_at_next_section(self):
        """Should stop extracting at next ## section."""
        from orchestrator.plan_parser import parse_e2e_scenario

        content = textwrap.dedent("""
            # Milestone

            ## E2E Test

            Run the tests.

            ## Verification

            This should not be included.
        """)

        result = parse_e2e_scenario(content)

        assert result is not None
        assert "Run the tests" in result
        assert "not be included" not in result
