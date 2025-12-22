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


class TestBudgetEndpoint:
    """Test GET /agent/budget endpoint - M7 Task 7.3."""

    def test_budget_returns_200_with_status(self, client):
        """Budget endpoint returns 200 with budget status."""
        from unittest.mock import MagicMock

        mock_tracker = MagicMock()
        mock_tracker.get_status.return_value = {
            "date": "2025-12-17",
            "daily_limit": 5.0,
            "today_spend": 0.75,
            "remaining": 4.25,
            "cycles_affordable": 28,
            "spend_events": 2,
        }

        with patch(
            "ktrdr.api.endpoints.agent.get_budget_tracker",
            return_value=mock_tracker,
        ):
            response = client.get("/agent/budget")

        assert response.status_code == 200
        data = response.json()
        assert data["daily_limit"] == 5.0
        assert data["today_spend"] == 0.75
        assert data["remaining"] == 4.25
        assert data["cycles_affordable"] == 28

    def test_budget_includes_date(self, client):
        """Budget endpoint includes date in response."""
        from unittest.mock import MagicMock

        mock_tracker = MagicMock()
        mock_tracker.get_status.return_value = {
            "date": "2025-12-17",
            "daily_limit": 5.0,
            "today_spend": 0.0,
            "remaining": 5.0,
            "cycles_affordable": 33,
            "spend_events": 0,
        }

        with patch(
            "ktrdr.api.endpoints.agent.get_budget_tracker",
            return_value=mock_tracker,
        ):
            response = client.get("/agent/budget")

        assert response.status_code == 200
        data = response.json()
        assert "date" in data
        assert data["date"] == "2025-12-17"

    def test_budget_includes_cycles_affordable(self, client):
        """Budget endpoint includes cycles_affordable estimate."""
        from unittest.mock import MagicMock

        mock_tracker = MagicMock()
        mock_tracker.get_status.return_value = {
            "date": "2025-12-17",
            "daily_limit": 5.0,
            "today_spend": 4.55,
            "remaining": 0.45,
            "cycles_affordable": 3,
            "spend_events": 10,
        }

        with patch(
            "ktrdr.api.endpoints.agent.get_budget_tracker",
            return_value=mock_tracker,
        ):
            response = client.get("/agent/budget")

        assert response.status_code == 200
        data = response.json()
        assert data["cycles_affordable"] == 3
