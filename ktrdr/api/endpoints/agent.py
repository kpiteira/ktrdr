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

    Optionally specify model and brief via request body:
    - {"model": "haiku"} - Use Haiku for cheap testing
    - {"model": "opus"} - Use Opus for production quality
    - {} or no body - Use AGENT_MODEL env var or default (opus)

    Use brief to guide the agent's strategy design:
    - {"brief": "Design a simple RSI strategy for EURUSD 1h."}

    Use strategy to skip design and train an existing strategy directly:
    - {"strategy": "v3_minimal"} - Skip design, start training with v3_minimal
    Note: strategy and brief are mutually exclusive.

    Use bypass_gates to skip quality gates (for testing):
    - {"bypass_gates": true} - Skip training and backtest gates

    Returns 202 if triggered, 409 if cycle already active, 422 if invalid model/strategy.
    """
    try:
        result = await service.trigger(
            model=request.model,
            brief=request.brief,
            strategy=request.strategy,
            bypass_gates=request.bypass_gates,
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


@router.delete("/cancel/{operation_id}")
async def cancel_agent(
    operation_id: str,
    service: AgentService = Depends(get_agent_service),
):
    """Cancel a specific research by operation_id.

    Args:
        operation_id: The operation ID to cancel.

    Returns:
        200 with cancellation details if cancelled.
        404 if operation not found or not a research.
        409 if operation is not in a cancellable state.
    """
    try:
        result = await service.cancel(operation_id)

        if result["success"]:
            return result

        # Map reason to appropriate HTTP status code
        reason = result.get("reason", "")
        if reason == "not_found":
            return JSONResponse(result, status_code=404)
        if reason == "not_research":
            return JSONResponse(result, status_code=404)
        if reason == "not_cancellable":
            return JSONResponse(result, status_code=409)
        return JSONResponse(result, status_code=400)

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
