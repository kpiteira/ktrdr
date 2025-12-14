"""Agent API endpoints.

Simplified endpoints for agent research cycle management.
Cancel functionality uses the operations API: DELETE /operations/{op_id}
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from ktrdr import get_logger
from ktrdr.api.services.agent_service import AgentService
from ktrdr.api.services.agent_service import get_agent_service as _get_agent_service

logger = get_logger(__name__)

# Create router for agent endpoints
router = APIRouter(prefix="/agent", tags=["agent"])


def get_agent_service() -> AgentService:
    """Get agent service instance (for dependency injection)."""
    return _get_agent_service()


@router.post("/trigger")
async def trigger_agent(
    service: AgentService = Depends(get_agent_service),
):
    """Start a new research cycle.

    Returns 202 if triggered, 409 if cycle already active.
    """
    try:
        result = await service.trigger()

        if result["triggered"]:
            return JSONResponse(result, status_code=202)
        return JSONResponse(result, status_code=409)

    except Exception as e:
        logger.error(f"Failed to trigger agent: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/status")
async def get_agent_status(
    service: AgentService = Depends(get_agent_service),
):
    """Get current agent status.

    Returns current phase if active, or last cycle info if idle.
    """
    try:
        return await service.get_status()
    except Exception as e:
        logger.error(f"Failed to get agent status: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
