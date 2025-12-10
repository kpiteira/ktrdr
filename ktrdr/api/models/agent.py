"""
Agent API Pydantic models.

Request/response models for the agent research system endpoints.
"""

from typing import Optional

from pydantic import BaseModel


class TriggerResponse(BaseModel):
    """Response model for POST /agent/trigger."""

    success: bool
    triggered: bool
    session_id: Optional[int] = None
    reason: Optional[str] = None
    active_session_id: Optional[int] = None
    message: Optional[str] = None
    dry_run: Optional[bool] = None
    would_trigger: Optional[bool] = None


class SessionInfo(BaseModel):
    """Detailed session information."""

    id: int
    phase: str
    strategy_name: Optional[str] = None
    operation_id: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None


class StatusResponse(BaseModel):
    """Response model for GET /agent/status."""

    has_active_session: bool
    session: Optional[SessionInfo] = None
    agent_enabled: bool
    recent_actions: Optional[list[dict]] = None


class SessionSummary(BaseModel):
    """Summary of a completed session."""

    id: int
    phase: str
    outcome: Optional[str] = None
    strategy_name: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


class SessionsListResponse(BaseModel):
    """Response model for GET /agent/sessions."""

    sessions: list[SessionSummary]
    total: int
