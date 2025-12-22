"""Agent API Pydantic models.

Note: These models are kept for backwards compatibility but the API
now returns plain JSON responses. See ktrdr/api/endpoints/agent.py.
"""

from typing import Any, Optional

from pydantic import BaseModel, field_validator


class AgentTriggerRequest(BaseModel):
    """Request model for POST /agent/trigger.

    Allows specifying model at trigger time for easy switching between
    opus/sonnet/haiku without restarting Docker.
    """

    model: Optional[str] = None
    """Model to use: 'opus', 'sonnet', 'haiku', or full model ID.
    If None, uses AGENT_MODEL env var or defaults to opus."""

    bypass_gates: bool = False
    """If True, skip quality gates between phases (for testing)."""

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: Optional[str]) -> Optional[str]:
        """Validate model is a known alias or model ID."""
        if v is None:
            return None
        # Import here to avoid circular dependency
        from ktrdr.agents.invoker import MODEL_ALIASES, VALID_MODELS

        v_lower = v.lower()
        if v_lower in MODEL_ALIASES or v in VALID_MODELS:
            return v
        valid_options = list(MODEL_ALIASES.keys()) + list(VALID_MODELS.keys())
        raise ValueError(
            f"Invalid model '{v}'. Valid options: {', '.join(sorted(set(valid_options)))}"
        )


class LastCycleInfo(BaseModel):
    """Information about the last completed research cycle."""

    operation_id: str
    outcome: str
    strategy_name: Optional[str] = None
    completed_at: Optional[str] = None


class AgentStatusResponse(BaseModel):
    """Response model for GET /agent/status."""

    status: str  # "active" or "idle"
    operation_id: Optional[str] = None
    phase: Optional[str] = None
    progress: Optional[dict[str, Any]] = None
    strategy_name: Optional[str] = None
    started_at: Optional[str] = None
    last_cycle: Optional[LastCycleInfo] = None


class AgentTriggerResponse(BaseModel):
    """Response model for POST /agent/trigger."""

    triggered: bool
    operation_id: Optional[str] = None
    reason: Optional[str] = None
    message: Optional[str] = None


# Legacy models - kept for backwards compatibility
# TODO: Remove these after CLI is updated


class TriggerResponse(BaseModel):
    """Legacy response model for POST /agent/trigger."""

    success: bool = True  # Deprecated field
    triggered: bool
    operation_id: Optional[str] = None
    session_id: Optional[int] = None  # Deprecated field
    reason: Optional[str] = None
    active_session_id: Optional[int] = None  # Deprecated field
    message: Optional[str] = None
    dry_run: Optional[bool] = None  # Deprecated field
    would_trigger: Optional[bool] = None  # Deprecated field
    status: Optional[str] = None  # Deprecated field


class SessionInfo(BaseModel):
    """Legacy detailed session information."""

    id: int
    phase: str
    strategy_name: Optional[str] = None
    operation_id: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None


class StatusResponse(BaseModel):
    """Legacy response model for GET /agent/status."""

    has_active_session: bool
    session: Optional[SessionInfo] = None
    agent_enabled: bool = True  # Default to True since agent is always enabled
    recent_actions: Optional[list[dict]] = None


class SessionSummary(BaseModel):
    """Legacy summary of a completed session."""

    id: int
    phase: str
    outcome: Optional[str] = None
    strategy_name: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


class SessionsListResponse(BaseModel):
    """Legacy response model for GET /agent/sessions."""

    sessions: list[SessionSummary]
    total: int


class CancelSessionResponse(BaseModel):
    """Legacy response model for DELETE /agent/sessions/{session_id}/cancel."""

    success: bool
    session_id: int
    operation_id: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
