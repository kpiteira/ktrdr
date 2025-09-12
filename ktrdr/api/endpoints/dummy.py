"""
DummyService API endpoints.

This module implements the API endpoints for the DummyService - the perfect demonstration
of how ServiceOrchestrator makes API endpoints trivially simple. Just 5-10 lines of
code calling the service directly!
"""

from fastapi import APIRouter

from ktrdr import get_logger
from ktrdr.api.models.dummy import DummyOperationResponse
from ktrdr.api.services.dummy_service import DummyService

# Setup module-level logger
logger = get_logger(__name__)

# Create router for dummy endpoints
router = APIRouter()


@router.post(
    "/dummy/start",
    response_model=DummyOperationResponse,
    tags=["Dummy"],
    summary="Start awesome dummy task",
    description="The most beautiful async operation ever - ServiceOrchestrator handles everything!",
)
async def start_dummy_task() -> DummyOperationResponse:
    """Start the most awesome dummy task ever! ServiceOrchestrator does ALL the work!"""

    try:
        # ServiceOrchestrator handles EVERYTHING - operations service, progress, cancellation!
        dummy_service = DummyService()
        result = await dummy_service.start_dummy_task()

        # ServiceOrchestrator already formatted the response perfectly
        return DummyOperationResponse(
            success=True, data=result, error=None  # Contains operation_id, status, etc.
        )

    except Exception as e:
        logger.error(f"Failed to start dummy task: {e}")
        return DummyOperationResponse(
            success=False,
            data=None,
            error={"code": "DUMMY-001", "message": f"Failed to start: {e}"},
        )
