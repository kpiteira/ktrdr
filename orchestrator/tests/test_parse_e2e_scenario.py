"""Tests for parse_e2e_scenario function.

This function uses regex to extract E2E test scenarios from milestone plans.
It is kept as regex because E2E extraction is simpler than task extraction
and doesn't need LLM semantic understanding (Decision 10 in architecture).
"""

import textwrap

from orchestrator.milestone_runner import parse_e2e_scenario


class TestParseE2EScenario:
    """Test parsing of E2E test scenarios from plans."""

    def test_extracts_e2e_from_code_block(self):
        """Should extract E2E scenario from code block."""
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
