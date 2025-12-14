"""Unit tests for simplified Agent API endpoints.

Tests cover:
- POST /api/v1/agent/trigger - Trigger research cycle (202/409)
- GET /api/v1/agent/status - Get current status

Task 1.5 of M1: Simplified endpoints with correct HTTP status codes.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


class TestAgentTriggerEndpoint:
    """Tests for POST /api/v1/agent/trigger endpoint."""

    @pytest.fixture
    def mock_agent_service(self):
        """Create a mock agent service."""
        service = MagicMock()
        service.trigger = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_trigger_success_returns_202(self, mock_agent_service):
        """Test triggering a new research cycle returns 202 Accepted."""
        from fastapi import FastAPI

        from ktrdr.api.endpoints.agent import get_agent_service, router

        app = FastAPI()
        app.include_router(router)

        mock_agent_service.trigger.return_value = {
            "triggered": True,
            "operation_id": "op_agent_research_12345",
            "message": "Research cycle started",
        }

        app.dependency_overrides[get_agent_service] = lambda: mock_agent_service

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/agent/trigger")

        assert response.status_code == 202
        data = response.json()
        assert data["triggered"] is True
        assert data["operation_id"] == "op_agent_research_12345"

    @pytest.mark.asyncio
    async def test_trigger_active_cycle_returns_409(self, mock_agent_service):
        """Test trigger when active cycle exists returns 409 Conflict."""
        from fastapi import FastAPI

        from ktrdr.api.endpoints.agent import get_agent_service, router

        app = FastAPI()
        app.include_router(router)

        mock_agent_service.trigger.return_value = {
            "triggered": False,
            "reason": "active_cycle_exists",
            "operation_id": "op_agent_research_existing",
            "message": "Active cycle exists: op_agent_research_existing",
        }

        app.dependency_overrides[get_agent_service] = lambda: mock_agent_service

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/agent/trigger")

        assert response.status_code == 409
        data = response.json()
        assert data["triggered"] is False
        assert data["reason"] == "active_cycle_exists"

    @pytest.mark.asyncio
    async def test_trigger_service_error_returns_500(self, mock_agent_service):
        """Test trigger when service raises an error returns 500."""
        from fastapi import FastAPI

        from ktrdr.api.endpoints.agent import get_agent_service, router

        app = FastAPI()
        app.include_router(router)

        mock_agent_service.trigger.side_effect = Exception("Unexpected error")

        app.dependency_overrides[get_agent_service] = lambda: mock_agent_service

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/agent/trigger")

        assert response.status_code == 500


class TestAgentStatusEndpoint:
    """Tests for GET /api/v1/agent/status endpoint."""

    @pytest.fixture
    def mock_agent_service(self):
        """Create a mock agent service."""
        service = MagicMock()
        service.get_status = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_status_active_cycle(self, mock_agent_service):
        """Test status when there's an active cycle."""
        from fastapi import FastAPI

        from ktrdr.api.endpoints.agent import get_agent_service, router

        app = FastAPI()
        app.include_router(router)

        mock_agent_service.get_status.return_value = {
            "status": "active",
            "operation_id": "op_agent_research_12345",
            "phase": "training",
            "progress": None,
            "strategy_name": "momentum_v1",
            "started_at": "2024-12-13T10:00:00Z",
        }

        app.dependency_overrides[get_agent_service] = lambda: mock_agent_service

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/agent/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["operation_id"] == "op_agent_research_12345"
        assert data["phase"] == "training"

    @pytest.mark.asyncio
    async def test_status_idle_no_previous(self, mock_agent_service):
        """Test status when idle with no previous cycle."""
        from fastapi import FastAPI

        from ktrdr.api.endpoints.agent import get_agent_service, router

        app = FastAPI()
        app.include_router(router)

        mock_agent_service.get_status.return_value = {
            "status": "idle",
            "last_cycle": None,
        }

        app.dependency_overrides[get_agent_service] = lambda: mock_agent_service

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/agent/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "idle"
        assert data["last_cycle"] is None

    @pytest.mark.asyncio
    async def test_status_idle_with_last_cycle(self, mock_agent_service):
        """Test status when idle with previous cycle info."""
        from fastapi import FastAPI

        from ktrdr.api.endpoints.agent import get_agent_service, router

        app = FastAPI()
        app.include_router(router)

        mock_agent_service.get_status.return_value = {
            "status": "idle",
            "last_cycle": {
                "operation_id": "op_agent_research_previous",
                "outcome": "completed",
                "strategy_name": "momentum_v1",
                "completed_at": "2024-12-13T12:00:00Z",
            },
        }

        app.dependency_overrides[get_agent_service] = lambda: mock_agent_service

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/agent/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "idle"
        assert data["last_cycle"]["outcome"] == "completed"


class TestNoSessionEndpoints:
    """Verify session-related endpoints are removed."""

    @pytest.mark.asyncio
    async def test_sessions_endpoint_not_found(self):
        """GET /agent/sessions should return 404."""
        from fastapi import FastAPI

        from ktrdr.api.endpoints.agent import router

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/agent/sessions")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_session_endpoint_not_found(self):
        """DELETE /agent/sessions/{id}/cancel should return 404."""
        from fastapi import FastAPI

        from ktrdr.api.endpoints.agent import router

        app = FastAPI()
        app.include_router(router)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.delete("/agent/sessions/42/cancel")

        assert response.status_code == 404
