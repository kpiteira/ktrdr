"""
Unit tests for Task 2.6: Update Agent Prompt for Full Cycle.

These tests verify that the prompt correctly reflects the TriggerService-controlled
state machine, where:
- Agent is invoked for design (START_NEW_CYCLE) and assessment (BACKTEST_COMPLETED)
- TriggerService handles state transitions and starting training/backtest operations
- Agent doesn't need update_agent_state tool (doesn't exist)

Key behavior:
- DESIGNING phase: Design strategy, save config. That's it.
- ASSESSING phase: Analyze results, write assessment output. System handles state.
"""

import pytest

from research_agents.prompts.strategy_designer import (
    PromptContext,
    StrategyDesignerPromptBuilder,
    TriggerReason,
)


class TestFullCyclePromptStartNewCycle:
    """Tests for START_NEW_CYCLE prompt behavior in full cycle context."""

    @pytest.fixture
    def builder(self):
        """Create a prompt builder instance."""
        return StrategyDesignerPromptBuilder()

    def test_start_new_cycle_does_not_require_agent_to_start_training(self, builder):
        """Agent should NOT be told to start training - TriggerService handles this.

        The TriggerService automatically starts training after agent saves the
        strategy configuration. The agent's job is just to design and save.
        """
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="designing",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Look for the START_NEW_CYCLE instructions section
        # It should NOT say "Start training" as a required step
        # or should clarify that training is handled automatically

        # The system prompt has numbered instructions. We need to verify:
        # - Agent is NOT required to call start_training
        # - Agent understands system handles training after save

        # Check that we don't have explicit instructions to "Start training"
        # as a required action step
        start_new_cycle_section = _extract_section(
            system, "start_new_cycle", "training_completed"
        )

        # Should mention saving the strategy
        assert (
            "save" in start_new_cycle_section.lower()
        ), "Should mention saving strategy"

        # Should NOT have "8. Start training" as a numbered instruction
        # or should clarify it's automatic
        if "start training" in start_new_cycle_section.lower():
            # If it mentions starting training, it should clarify it's automatic
            # or optional (handled by system)
            assert (
                "automatic" in start_new_cycle_section.lower()
                or "system" in start_new_cycle_section.lower()
                or "optional" in start_new_cycle_section.lower()
            ), "If mentioning training, should clarify it's automatic/optional"

    def test_start_new_cycle_does_not_require_state_update_to_training(self, builder):
        """Agent should NOT be told to update state to TRAINING.

        The TriggerService handles state transitions. The agent doesn't have
        an update_agent_state tool.
        """
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="designing",
        )
        result = builder.build(ctx)
        system = result["system"]

        start_new_cycle_section = _extract_section(
            system, "start_new_cycle", "training_completed"
        )

        # Should NOT instruct agent to "Update your state to phase: training"
        assert 'phase: "training"' not in start_new_cycle_section.lower()
        assert (
            "update your state to phase" not in start_new_cycle_section.lower()
            or "update state" not in start_new_cycle_section.lower()
        )

    def test_start_new_cycle_mentions_system_handles_next_steps(self, builder):
        """Agent should understand the system handles what happens next.

        After agent saves the strategy, the system (TriggerService) takes over
        to start training automatically.
        """
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="designing",
        )
        result = builder.build(ctx)
        system = result["system"]

        start_new_cycle_section = _extract_section(
            system, "start_new_cycle", "training_completed"
        )

        # Should mention that system/TriggerService handles training or next steps
        # or that training starts automatically after save
        has_automation_note = (
            "automatic" in start_new_cycle_section.lower()
            or "system" in start_new_cycle_section.lower()
            or "trigger" in start_new_cycle_section.lower()
            or "will start" in start_new_cycle_section.lower()
            or "handled" in start_new_cycle_section.lower()
        )
        assert (
            has_automation_note
        ), "Should mention automation of training or next steps"


class TestFullCyclePromptBacktestCompleted:
    """Tests for BACKTEST_COMPLETED (assessment phase) prompt behavior."""

    @pytest.fixture
    def builder(self):
        """Create a prompt builder instance."""
        return StrategyDesignerPromptBuilder()

    def test_backtest_completed_focuses_on_assessment_output(self, builder):
        """Agent should focus on writing assessment, not state updates.

        The agent's job is to analyze results and provide assessment text.
        State transitions are handled by the system.
        """
        ctx = PromptContext(
            trigger_reason=TriggerReason.BACKTEST_COMPLETED,
            session_id=1,
            phase="assessing",
            backtest_results={"sharpe_ratio": 0.8, "win_rate": 0.55},
        )
        result = builder.build(ctx)
        system = result["system"]

        backtest_section = _extract_section(system, "backtest_completed", None)

        # Should emphasize analysis and assessment
        assert (
            "analyze" in backtest_section.lower()
            or "assess" in backtest_section.lower()
        )

        # Should mention what the assessment should include
        assert (
            "strength" in backtest_section.lower()
            or "weakness" in backtest_section.lower()
            or "improve" in backtest_section.lower()
        )

    def test_backtest_completed_does_not_require_update_agent_state(self, builder):
        """Agent should NOT be told to use update_agent_state tool.

        The update_agent_state tool doesn't exist. The system handles
        state transitions and storing assessment.
        """
        ctx = PromptContext(
            trigger_reason=TriggerReason.BACKTEST_COMPLETED,
            session_id=1,
            phase="assessing",
            backtest_results={"sharpe_ratio": 0.8, "win_rate": 0.55},
        )
        result = builder.build(ctx)
        system = result["system"]

        backtest_section = _extract_section(system, "backtest_completed", None)

        # Should NOT instruct agent to call update_agent_state
        # The old prompt said "Update your state with: assessment:..."
        assert (
            "update your state with:" not in backtest_section.lower()
        ), "Should not tell agent to update state (no tool exists)"

        # Should NOT have the numbered instruction format "4. Update your state"
        assert (
            ". update your state" not in backtest_section.lower()
        ), "Should not have update state as an instruction step"

    def test_backtest_completed_clarifies_session_completion(self, builder):
        """Agent should understand their assessment completes the session.

        The system will mark the session as complete based on successful
        agent response. Agent just needs to provide the assessment.
        """
        ctx = PromptContext(
            trigger_reason=TriggerReason.BACKTEST_COMPLETED,
            session_id=1,
            phase="assessing",
            backtest_results={"sharpe_ratio": 0.8, "win_rate": 0.55},
        )
        result = builder.build(ctx)
        system = result["system"]

        backtest_section = _extract_section(system, "backtest_completed", None)

        # Should mention completion or finishing
        has_completion_note = (
            "complete" in backtest_section.lower()
            or "finish" in backtest_section.lower()
            or "cycle" in backtest_section.lower()
        )
        assert has_completion_note, "Should mention completing the cycle/session"


class TestFullCyclePromptAvailableTools:
    """Tests for available tools listing in full cycle context."""

    @pytest.fixture
    def builder(self):
        """Create a prompt builder instance."""
        return StrategyDesignerPromptBuilder()

    def test_available_tools_does_not_list_update_agent_state(self, builder):
        """update_agent_state should NOT be listed as available tool.

        This tool doesn't exist in the ToolExecutor. The TriggerService
        handles all state transitions.
        """
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="designing",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Should NOT list update_agent_state as an available tool
        assert (
            "update_agent_state" not in system
        ), "Should not list update_agent_state (doesn't exist)"

    def test_available_tools_does_not_list_get_agent_state(self, builder):
        """get_agent_state should NOT be listed as available tool.

        This tool doesn't exist in the ToolExecutor. The agent doesn't
        need to check its own state - context is provided in the prompt.
        """
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="designing",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Should NOT list get_agent_state as an available tool
        assert (
            "get_agent_state" not in system
        ), "Should not list get_agent_state (doesn't exist)"

    def test_available_tools_lists_actual_tools(self, builder):
        """Available tools section should list tools that actually exist.

        The actual tools in ToolExecutor are:
        - validate_strategy_config
        - save_strategy_config
        - get_available_indicators
        - get_available_symbols
        - get_recent_strategies
        - start_training
        - start_backtest
        """
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="designing",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Should list the actual tools
        assert "save_strategy_config" in system
        assert "get_available_indicators" in system or "get_available_symbol" in system
        assert "get_recent_strategies" in system


class TestFullCyclePromptOutputFormat:
    """Tests for output format in full cycle context."""

    @pytest.fixture
    def builder(self):
        """Create a prompt builder instance."""
        return StrategyDesignerPromptBuilder()

    def test_output_format_for_assessment_phase(self, builder):
        """Assessment output format should focus on analysis content.

        The agent should output their assessment clearly so the system
        can capture and store it.
        """
        ctx = PromptContext(
            trigger_reason=TriggerReason.BACKTEST_COMPLETED,
            session_id=1,
            phase="assessing",
            backtest_results={"sharpe_ratio": 0.8, "win_rate": 0.55},
        )
        result = builder.build(ctx)

        # Either system or user prompt should guide assessment output
        combined = result["system"] + result["user"]

        # Should guide what to include in assessment
        assert "assess" in combined.lower() or "analys" in combined.lower()


# Helper function to extract sections from system prompt
def _extract_section(text: str, start_marker: str, end_marker: str | None) -> str:
    """Extract a section of text between markers.

    Args:
        text: Full text to search.
        start_marker: Start marker to find (case-insensitive).
        end_marker: End marker to find (case-insensitive), or None for rest of text.

    Returns:
        Extracted section text.
    """
    lower_text = text.lower()
    start_idx = lower_text.find(start_marker.lower())

    if start_idx == -1:
        return ""

    if end_marker is None:
        return text[start_idx:]

    end_idx = lower_text.find(end_marker.lower(), start_idx + len(start_marker))

    if end_idx == -1:
        return text[start_idx:]

    return text[start_idx:end_idx]
