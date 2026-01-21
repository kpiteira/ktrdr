"""Agent API Pydantic models."""

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

    brief: Optional[str] = None
    """Natural language guidance for the strategy designer.
    Injected into the agent's prompt to guide design decisions.
    Example: 'Design a simple RSI strategy for EURUSD 1h only.'"""

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
    child_operation_id: Optional[str] = None
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
