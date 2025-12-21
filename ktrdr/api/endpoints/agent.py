"""Agent API endpoints.

Simplified endpoints for agent research cycle management.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from ktrdr import get_logger
from ktrdr.agents.budget import get_budget_tracker
from ktrdr.api.models.agent import AgentTriggerRequest
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
    request: AgentTriggerRequest = AgentTriggerRequest(),
    service: AgentService = Depends(get_agent_service),
):
    """Start a new research cycle.

    Optionally specify model via request body:
    - {"model": "haiku"} - Use Haiku for cheap testing
    - {"model": "opus"} - Use Opus for production quality
    - {} or no body - Use AGENT_MODEL env var or default (opus)

    Use bypass_gates to skip quality gates (for testing):
    - {"bypass_gates": true} - Skip training and backtest gates

    Returns 202 if triggered, 409 if cycle already active, 422 if invalid model.
    """
    try:
        result = await service.trigger(
            model=request.model, bypass_gates=request.bypass_gates
        )

        if result["triggered"]:
            return JSONResponse(result, status_code=202)
        return JSONResponse(result, status_code=409)

    except ValueError as e:
        # Invalid model
        raise HTTPException(status_code=422, detail=str(e)) from e
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


@router.delete("/cancel")
async def cancel_agent(
    service: AgentService = Depends(get_agent_service),
):
    """Cancel the active research cycle.

    Returns 200 with cancellation details if cancelled.
    Returns 404 if no active cycle.
    """
    try:
        result = await service.cancel()

        if result["success"]:
            return result
        return JSONResponse(result, status_code=404)

    except Exception as e:
        logger.error(f"Failed to cancel agent: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/budget")
async def get_budget_status():
    """Get current budget status.

    Returns daily limit, today's spend, remaining budget,
    and estimated number of cycles affordable.
    """
    try:
        tracker = get_budget_tracker()
        return tracker.get_status()
    except Exception as e:
        logger.error(f"Failed to get budget status: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
