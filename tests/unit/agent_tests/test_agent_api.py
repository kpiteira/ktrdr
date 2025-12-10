"""
Unit tests for Agent API endpoints.

Tests cover:
- POST /api/v1/agent/trigger - Trigger research cycle
- GET /api/v1/agent/status - Get current status
- GET /api/v1/agent/sessions - List recent sessions

These tests use mocked services to verify endpoint behavior.
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
    async def test_trigger_success_new_cycle(self, mock_agent_service):
        """Test triggering a new research cycle successfully."""
        from fastapi import FastAPI

        from ktrdr.api.endpoints.agent import get_agent_service, router

        app = FastAPI()
        # Router already has prefix="/agent", no need to add another
        app.include_router(router)

        # Mock service response for successful trigger
        mock_agent_service.trigger.return_value = {
            "success": True,
            "triggered": True,
            "session_id": 42,
            "message": "Research cycle started",
        }

        app.dependency_overrides[get_agent_service] = lambda: mock_agent_service

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/agent/trigger")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["triggered"] is True
        assert data["session_id"] == 42

    @pytest.mark.asyncio
    async def test_trigger_active_session_exists(self, mock_agent_service):
        """Test trigger when active session already exists."""
        from fastapi import FastAPI

        from ktrdr.api.endpoints.agent import get_agent_service, router

        app = FastAPI()
        app.include_router(router)

        # Mock service response when active session exists
        mock_agent_service.trigger.return_value = {
            "success": True,
            "triggered": False,
            "reason": "active_session_exists",
            "active_session_id": 41,
            "message": "Active session already exists",
        }

        app.dependency_overrides[get_agent_service] = lambda: mock_agent_service

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/agent/trigger")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["triggered"] is False
        assert data["reason"] == "active_session_exists"

    @pytest.mark.asyncio
    async def test_trigger_agent_disabled(self, mock_agent_service):
        """Test trigger when agent is disabled."""
        from fastapi import FastAPI

        from ktrdr.api.endpoints.agent import get_agent_service, router

        app = FastAPI()
        app.include_router(router)

        # Mock service response when agent is disabled
        mock_agent_service.trigger.return_value = {
            "success": True,
            "triggered": False,
            "reason": "disabled",
            "message": "Agent trigger is disabled",
        }

        app.dependency_overrides[get_agent_service] = lambda: mock_agent_service

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/agent/trigger")

        assert response.status_code == 200
        data = response.json()
        assert data["triggered"] is False
        assert data["reason"] == "disabled"

    @pytest.mark.asyncio
    async def test_trigger_with_dry_run(self, mock_agent_service):
        """Test trigger with dry_run parameter."""
        from fastapi import FastAPI

        from ktrdr.api.endpoints.agent import get_agent_service, router

        app = FastAPI()
        app.include_router(router)

        mock_agent_service.trigger.return_value = {
            "success": True,
            "triggered": False,
            "dry_run": True,
            "would_trigger": True,
            "message": "Dry run - would trigger new cycle",
        }

        app.dependency_overrides[get_agent_service] = lambda: mock_agent_service

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/agent/trigger", params={"dry_run": True})

        assert response.status_code == 200
        data = response.json()
        assert data["dry_run"] is True

    @pytest.mark.asyncio
    async def test_trigger_service_error(self, mock_agent_service):
        """Test trigger when service raises an error."""
        from fastapi import FastAPI

        from ktrdr.api.endpoints.agent import get_agent_service, router

        app = FastAPI()
        app.include_router(router)

        mock_agent_service.trigger.side_effect = Exception("Database connection failed")

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
    async def test_status_with_active_session(self, mock_agent_service):
        """Test status when there's an active session."""
        from fastapi import FastAPI

        from ktrdr.api.endpoints.agent import get_agent_service, router

        app = FastAPI()
        app.include_router(router)

        mock_agent_service.get_status.return_value = {
            "has_active_session": True,
            "session": {
                "id": 42,
                "phase": "designing",
                "strategy_name": None,
                "operation_id": None,
                "created_at": "2024-12-09T10:00:00Z",
                "updated_at": "2024-12-09T10:05:00Z",
            },
            "agent_enabled": True,
        }

        app.dependency_overrides[get_agent_service] = lambda: mock_agent_service

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/agent/status")

        assert response.status_code == 200
        data = response.json()
        assert data["has_active_session"] is True
        assert data["session"]["id"] == 42
        assert data["session"]["phase"] == "designing"

    @pytest.mark.asyncio
    async def test_status_no_active_session(self, mock_agent_service):
        """Test status when there's no active session."""
        from fastapi import FastAPI

        from ktrdr.api.endpoints.agent import get_agent_service, router

        app = FastAPI()
        app.include_router(router)

        mock_agent_service.get_status.return_value = {
            "has_active_session": False,
            "session": None,
            "agent_enabled": True,
        }

        app.dependency_overrides[get_agent_service] = lambda: mock_agent_service

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/agent/status")

        assert response.status_code == 200
        data = response.json()
        assert data["has_active_session"] is False
        assert data["session"] is None

    @pytest.mark.asyncio
    async def test_status_with_verbose_flag(self, mock_agent_service):
        """Test status with verbose flag for extra details."""
        from fastapi import FastAPI

        from ktrdr.api.endpoints.agent import get_agent_service, router

        app = FastAPI()
        app.include_router(router)

        mock_agent_service.get_status.return_value = {
            "has_active_session": True,
            "session": {
                "id": 42,
                "phase": "designing",
                "strategy_name": None,
                "operation_id": None,
                "created_at": "2024-12-09T10:00:00Z",
                "updated_at": "2024-12-09T10:05:00Z",
            },
            "agent_enabled": True,
            "recent_actions": [
                {"tool_name": "get_available_indicators", "result": "success"}
            ],
        }

        app.dependency_overrides[get_agent_service] = lambda: mock_agent_service

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/agent/status", params={"verbose": True})

        assert response.status_code == 200
        # Verbose flag should be passed to service
        mock_agent_service.get_status.assert_called_once_with(verbose=True)


class TestAgentSessionsEndpoint:
    """Tests for GET /api/v1/agent/sessions endpoint."""

    @pytest.fixture
    def mock_agent_service(self):
        """Create a mock agent service."""
        service = MagicMock()
        service.list_sessions = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_list_sessions_default_limit(self, mock_agent_service):
        """Test listing sessions with default limit."""
        from fastapi import FastAPI

        from ktrdr.api.endpoints.agent import get_agent_service, router

        app = FastAPI()
        app.include_router(router)

        mock_agent_service.list_sessions.return_value = {
            "sessions": [
                {
                    "id": 42,
                    "phase": "designed",
                    "outcome": "success",
                    "strategy_name": "momentum_v1",
                    "created_at": "2024-12-09T10:00:00Z",
                    "completed_at": "2024-12-09T10:30:00Z",
                },
                {
                    "id": 41,
                    "phase": "designed",
                    "outcome": "failed_training",
                    "strategy_name": "rsi_divergence_v1",
                    "created_at": "2024-12-09T09:00:00Z",
                    "completed_at": "2024-12-09T09:20:00Z",
                },
            ],
            "total": 2,
        }

        app.dependency_overrides[get_agent_service] = lambda: mock_agent_service

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/agent/sessions")

        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) == 2
        assert data["total"] == 2
        # Default limit is 10
        mock_agent_service.list_sessions.assert_called_once_with(limit=10)

    @pytest.mark.asyncio
    async def test_list_sessions_custom_limit(self, mock_agent_service):
        """Test listing sessions with custom limit."""
        from fastapi import FastAPI

        from ktrdr.api.endpoints.agent import get_agent_service, router

        app = FastAPI()
        app.include_router(router)

        mock_agent_service.list_sessions.return_value = {
            "sessions": [],
            "total": 0,
        }

        app.dependency_overrides[get_agent_service] = lambda: mock_agent_service

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/agent/sessions", params={"limit": 5})

        assert response.status_code == 200
        mock_agent_service.list_sessions.assert_called_once_with(limit=5)


class TestAgentAPIModels:
    """Tests for Agent API Pydantic models."""

    def test_trigger_response_model(self):
        """Test TriggerResponse model."""
        from ktrdr.api.models.agent import TriggerResponse

        response = TriggerResponse(
            success=True,
            triggered=True,
            session_id=42,
            message="Research cycle started",
        )
        assert response.success is True
        assert response.triggered is True
        assert response.session_id == 42

    def test_trigger_response_with_reason(self):
        """Test TriggerResponse model with reason."""
        from ktrdr.api.models.agent import TriggerResponse

        response = TriggerResponse(
            success=True,
            triggered=False,
            reason="active_session_exists",
            active_session_id=41,
            message="Active session already exists",
        )
        assert response.triggered is False
        assert response.reason == "active_session_exists"
        assert response.active_session_id == 41

    def test_session_info_model(self):
        """Test SessionInfo model."""
        from ktrdr.api.models.agent import SessionInfo

        session = SessionInfo(
            id=42,
            phase="designing",
            strategy_name=None,
            operation_id=None,
            created_at="2024-12-09T10:00:00Z",
            updated_at="2024-12-09T10:05:00Z",
        )
        assert session.id == 42
        assert session.phase == "designing"

    def test_status_response_model(self):
        """Test StatusResponse model."""
        from ktrdr.api.models.agent import SessionInfo, StatusResponse

        response = StatusResponse(
            has_active_session=True,
            session=SessionInfo(
                id=42,
                phase="designing",
                strategy_name=None,
                operation_id=None,
                created_at="2024-12-09T10:00:00Z",
                updated_at="2024-12-09T10:05:00Z",
            ),
            agent_enabled=True,
        )
        assert response.has_active_session is True
        assert response.session.id == 42

    def test_sessions_list_response_model(self):
        """Test SessionsListResponse model."""
        from ktrdr.api.models.agent import SessionsListResponse, SessionSummary

        response = SessionsListResponse(
            sessions=[
                SessionSummary(
                    id=42,
                    phase="designed",
                    outcome="success",
                    strategy_name="momentum_v1",
                    created_at="2024-12-09T10:00:00Z",
                    completed_at="2024-12-09T10:30:00Z",
                )
            ],
            total=1,
        )
        assert len(response.sessions) == 1
        assert response.total == 1
