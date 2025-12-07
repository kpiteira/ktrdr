"""
Phase 0 test prompt for research agents.

This minimal prompt proves the plumbing works by executing a simple 3-step flow:
1. Create a new agent session
2. Update state to "testing" phase
3. Complete the session

No actual strategy design - just validates tool calling works end-to-end.
"""

PHASE0_SYSTEM_PROMPT = """You are a test agent for the KTRDR autonomous research system.

Your purpose is to validate that the agent infrastructure works correctly by executing
a simple 3-step workflow using MCP tools. You are not designing strategies yet - just
proving the plumbing works.

Available MCP tools:
- create_agent_session(): Creates a new session and returns session_id
- get_agent_state(session_id): Get current session state
- update_agent_state(session_id, phase, ...): Update session state

Always use the exact tool names and parameter formats shown above."""

PHASE0_TEST_PROMPT = """Execute this test workflow to validate the agent infrastructure:

1. Call create_agent_session() to start a new session
   - Note the returned session_id

2. Call update_agent_state() with:
   - session_id: (from step 1)
   - phase: "testing"

3. Call update_agent_state() with:
   - session_id: (from step 1)
   - phase: "complete"

After completing all 3 steps, report:
- The session_id that was created
- Confirmation that each step completed successfully

This proves the MCP tool infrastructure is working correctly."""


def get_phase0_prompt(session_id: int | None = None) -> dict:
    """Get the Phase 0 test prompt as a dict with system and user messages.

    Args:
        session_id: Optional session ID to include in the prompt. If provided,
            the prompt will instruct the agent to continue with this session
            rather than creating a new one.

    Returns:
        Dict with 'system' and 'user' keys containing the respective prompts.
    """
    user_prompt = PHASE0_TEST_PROMPT

    if session_id is not None:
        user_prompt = f"""Continue testing with existing session {session_id}.

The session was already created. Execute these remaining steps:

1. Call update_agent_state() with:
   - session_id: {session_id}
   - phase: "testing"

2. Call update_agent_state() with:
   - session_id: {session_id}
   - phase: "complete"

After completing, report confirmation that each step completed successfully."""

    return {
        "system": PHASE0_SYSTEM_PROMPT,
        "user": user_prompt,
    }
