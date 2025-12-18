"""Tests for agent API endpoints - Task 6.1."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ktrdr.api.endpoints.agent import router


@pytest.fixture
def app():
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestCancelEndpoint:
    """Test DELETE /agent/cancel endpoint."""

    def test_cancel_returns_200_when_cycle_cancelled(self, client):
        """Cancel returns 200 with success data when cycle is cancelled."""
        mock_service = AsyncMock()
        mock_service.cancel.return_value = {
            "success": True,
            "operation_id": "op_agent_research_1",
            "child_cancelled": "op_training_2",
            "message": "Research cycle cancelled",
        }

        with patch(
            "ktrdr.api.endpoints.agent._get_agent_service",
            return_value=mock_service,
        ):
            response = client.delete("/agent/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["operation_id"] == "op_agent_research_1"
        assert data["child_cancelled"] == "op_training_2"

    def test_cancel_returns_404_when_no_active_cycle(self, client):
        """Cancel returns 404 when no active cycle exists."""
        mock_service = AsyncMock()
        mock_service.cancel.return_value = {
            "success": False,
            "reason": "no_active_cycle",
            "message": "No active research cycle to cancel",
        }

        with patch(
            "ktrdr.api.endpoints.agent._get_agent_service",
            return_value=mock_service,
        ):
            response = client.delete("/agent/cancel")

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["reason"] == "no_active_cycle"

    def test_cancel_returns_500_on_exception(self, client):
        """Cancel returns 500 when service raises exception."""
        mock_service = AsyncMock()
        mock_service.cancel.side_effect = Exception("Internal error")

        with patch(
            "ktrdr.api.endpoints.agent._get_agent_service",
            return_value=mock_service,
        ):
            response = client.delete("/agent/cancel")

        assert response.status_code == 500

    def test_cancel_returns_child_cancelled_none(self, client):
        """Cancel returns child_cancelled=None when no child op."""
        mock_service = AsyncMock()
        mock_service.cancel.return_value = {
            "success": True,
            "operation_id": "op_agent_research_1",
            "child_cancelled": None,
            "message": "Research cycle cancelled",
        }

        with patch(
            "ktrdr.api.endpoints.agent._get_agent_service",
            return_value=mock_service,
        ):
            response = client.delete("/agent/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["child_cancelled"] is None
