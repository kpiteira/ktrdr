"""
Agent API endpoints for the KTRDR research system.

Endpoints:
- POST /agent/trigger - Trigger a research cycle
- GET /agent/status - Get current agent status
- GET /agent/sessions - List recent sessions
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ktrdr import get_logger
from ktrdr.api.models.agent import (
    SessionsListResponse,
    StatusResponse,
    TriggerResponse,
)
from ktrdr.api.services.agent_service import AgentService

logger = get_logger(__name__)

# Create router for agent endpoints
router = APIRouter(prefix="/agent")


# Singleton service instance
_agent_service: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    """Get agent service instance (singleton)."""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service


@router.post("/trigger", response_model=TriggerResponse)
async def trigger_agent(
    dry_run: bool = Query(False, description="Dry run mode - don't actually trigger"),
    service: AgentService = Depends(get_agent_service),
) -> TriggerResponse:
    """
    Trigger a research cycle.

    Starts a new research cycle if conditions are met (no active session,
    budget available, agent enabled).
    """
    try:
        result = await service.trigger(dry_run=dry_run)
        return TriggerResponse(**result)
    except Exception as e:
        logger.error(f"Failed to trigger agent: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/status", response_model=StatusResponse)
async def get_agent_status(
    verbose: bool = Query(False, description="Include detailed information"),
    service: AgentService = Depends(get_agent_service),
) -> StatusResponse:
    """
    Get current agent status.

    Returns information about the active session (if any) and agent state.
    """
    try:
        result = await service.get_status(verbose=verbose)
        return StatusResponse(**result)
    except Exception as e:
        logger.error(f"Failed to get agent status: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions", response_model=SessionsListResponse)
async def list_sessions(
    limit: int = Query(10, ge=1, le=100, description="Number of sessions to return"),
    service: AgentService = Depends(get_agent_service),
) -> SessionsListResponse:
    """
    List recent sessions.

    Returns a list of recent research sessions with their outcomes.
    """
    try:
        result = await service.list_sessions(limit=limit)
        return SessionsListResponse(**result)
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
