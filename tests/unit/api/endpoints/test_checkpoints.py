"""Unit tests for checkpoints API endpoint."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from ktrdr.api.main import app
from ktrdr.checkpoint.checkpoint_service import CheckpointData, CheckpointSummary


@pytest.fixture
def mock_checkpoint_service():
    """Create a mock CheckpointService for testing."""
    mock_service = AsyncMock()
    return mock_service


@pytest.fixture
def client(mock_checkpoint_service):
    """Create a test client with dependency overrides."""
    # Import here to avoid circular imports
    from ktrdr.api.endpoints.checkpoints import get_checkpoint_service

    # Override the dependency
    app.dependency_overrides[get_checkpoint_service] = lambda: mock_checkpoint_service

    client = TestClient(app)
    yield client

    # Clean up dependency overrides
    app.dependency_overrides.clear()


class TestListCheckpointsEndpoint:
    """Tests for GET /api/v1/checkpoints endpoint."""

    def test_list_checkpoints_empty(self, client, mock_checkpoint_service):
        """Test listing checkpoints when none exist."""
        mock_checkpoint_service.list_checkpoints.return_value = []

        response = client.get("/api/v1/checkpoints")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"] == []
        assert data["total_count"] == 0

    def test_list_checkpoints_with_data(self, client, mock_checkpoint_service):
        """Test listing checkpoints with data."""
        mock_checkpoint_service.list_checkpoints.return_value = [
            CheckpointSummary(
                operation_id="op_training_123",
                checkpoint_type="periodic",
                created_at=datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
                state_summary={"epoch": 10, "train_loss": 0.5},
                artifacts_size_bytes=1024000,
            ),
            CheckpointSummary(
                operation_id="op_training_456",
                checkpoint_type="cancellation",
                created_at=datetime(2025, 1, 15, 11, 0, 0, tzinfo=timezone.utc),
                state_summary={"epoch": 5, "train_loss": 0.8},
                artifacts_size_bytes=512000,
            ),
        ]

        response = client.get("/api/v1/checkpoints")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 2
        assert data["total_count"] == 2

        # Verify first checkpoint
        assert data["data"][0]["operation_id"] == "op_training_123"
        assert data["data"][0]["checkpoint_type"] == "periodic"
        assert data["data"][0]["state_summary"]["epoch"] == 10

    def test_list_checkpoints_with_older_than_days_filter(
        self, client, mock_checkpoint_service
    ):
        """Test listing checkpoints with older_than_days filter."""
        mock_checkpoint_service.list_checkpoints.return_value = []

        response = client.get("/api/v1/checkpoints?older_than_days=7")

        assert response.status_code == 200
        mock_checkpoint_service.list_checkpoints.assert_called_once_with(
            older_than_days=7
        )


class TestGetCheckpointEndpoint:
    """Tests for GET /api/v1/checkpoints/{operation_id} endpoint."""

    def test_get_checkpoint_found(self, client, mock_checkpoint_service):
        """Test getting a checkpoint that exists."""
        mock_checkpoint_service.load_checkpoint.return_value = CheckpointData(
            operation_id="op_training_123",
            checkpoint_type="periodic",
            created_at=datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            state={"epoch": 10, "train_loss": 0.5, "val_loss": 0.6},
            artifacts_path="/app/data/checkpoints/op_training_123",
        )

        response = client.get("/api/v1/checkpoints/op_training_123")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["operation_id"] == "op_training_123"
        assert data["data"]["checkpoint_type"] == "periodic"
        assert data["data"]["state"]["epoch"] == 10
        assert data["data"]["artifacts_path"] == "/app/data/checkpoints/op_training_123"

    def test_get_checkpoint_not_found(self, client, mock_checkpoint_service):
        """Test getting a checkpoint that doesn't exist returns 404."""
        mock_checkpoint_service.load_checkpoint.return_value = None

        response = client.get("/api/v1/checkpoints/nonexistent-op")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_checkpoint_does_not_load_artifacts(
        self, client, mock_checkpoint_service
    ):
        """Test that get checkpoint doesn't load artifact bytes by default."""
        mock_checkpoint_service.load_checkpoint.return_value = CheckpointData(
            operation_id="op_training_123",
            checkpoint_type="periodic",
            created_at=datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            state={"epoch": 10},
            artifacts_path="/app/data/checkpoints/op_training_123",
        )

        response = client.get("/api/v1/checkpoints/op_training_123")

        assert response.status_code == 200
        # Verify load_artifacts=False was passed
        mock_checkpoint_service.load_checkpoint.assert_called_once_with(
            "op_training_123", load_artifacts=False
        )


class TestDeleteCheckpointEndpoint:
    """Tests for DELETE /api/v1/checkpoints/{operation_id} endpoint."""

    def test_delete_checkpoint_success(self, client, mock_checkpoint_service):
        """Test deleting a checkpoint that exists."""
        mock_checkpoint_service.delete_checkpoint.return_value = True

        response = client.delete("/api/v1/checkpoints/op_training_123")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Checkpoint deleted"

    def test_delete_checkpoint_not_found(self, client, mock_checkpoint_service):
        """Test deleting a checkpoint that doesn't exist returns 404."""
        mock_checkpoint_service.delete_checkpoint.return_value = False

        response = client.delete("/api/v1/checkpoints/nonexistent-op")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_delete_checkpoint_removes_from_db_and_filesystem(
        self, client, mock_checkpoint_service
    ):
        """Test that delete calls the service correctly."""
        mock_checkpoint_service.delete_checkpoint.return_value = True

        response = client.delete("/api/v1/checkpoints/op_training_123")

        assert response.status_code == 200
        mock_checkpoint_service.delete_checkpoint.assert_called_once_with(
            "op_training_123"
        )


class TestCleanupCheckpointsEndpoint:
    """Tests for POST /api/v1/checkpoints/cleanup endpoint."""

    def test_cleanup_checkpoints_default_max_age(self, client, mock_checkpoint_service):
        """Test cleanup with default max_age_days (30)."""
        mock_checkpoint_service.cleanup_old_checkpoints.return_value = 5
        mock_checkpoint_service.cleanup_orphan_artifacts.return_value = 2

        response = client.post("/api/v1/checkpoints/cleanup")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["checkpoints_deleted"] == 5
        assert data["orphan_artifacts_cleaned"] == 2
        mock_checkpoint_service.cleanup_old_checkpoints.assert_called_once_with(
            max_age_days=30
        )

    def test_cleanup_checkpoints_custom_max_age(self, client, mock_checkpoint_service):
        """Test cleanup with custom max_age_days."""
        mock_checkpoint_service.cleanup_old_checkpoints.return_value = 10
        mock_checkpoint_service.cleanup_orphan_artifacts.return_value = 0

        response = client.post("/api/v1/checkpoints/cleanup?max_age_days=7")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["checkpoints_deleted"] == 10
        assert data["orphan_artifacts_cleaned"] == 0
        mock_checkpoint_service.cleanup_old_checkpoints.assert_called_once_with(
            max_age_days=7
        )

    def test_cleanup_checkpoints_nothing_to_clean(
        self, client, mock_checkpoint_service
    ):
        """Test cleanup when nothing needs cleaning."""
        mock_checkpoint_service.cleanup_old_checkpoints.return_value = 0
        mock_checkpoint_service.cleanup_orphan_artifacts.return_value = 0

        response = client.post("/api/v1/checkpoints/cleanup")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["checkpoints_deleted"] == 0
        assert data["orphan_artifacts_cleaned"] == 0


class TestCheckpointStatsEndpoint:
    """Tests for GET /api/v1/checkpoints/stats endpoint."""

    def test_get_stats_with_checkpoints(self, client, mock_checkpoint_service):
        """Test getting stats when checkpoints exist."""
        mock_checkpoint_service.list_checkpoints.return_value = [
            CheckpointSummary(
                operation_id="op_training_123",
                checkpoint_type="periodic",
                created_at=datetime(2025, 1, 10, 10, 0, 0, tzinfo=timezone.utc),
                state_summary={"epoch": 10},
                artifacts_size_bytes=1024000,
            ),
            CheckpointSummary(
                operation_id="op_training_456",
                checkpoint_type="cancellation",
                created_at=datetime(2025, 1, 15, 11, 0, 0, tzinfo=timezone.utc),
                state_summary={"epoch": 5},
                artifacts_size_bytes=512000,
            ),
        ]

        response = client.get("/api/v1/checkpoints/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_checkpoints"] == 2
        assert data["total_size_bytes"] == 1024000 + 512000
        assert data["oldest_checkpoint"] == "2025-01-10T10:00:00Z"

    def test_get_stats_no_checkpoints(self, client, mock_checkpoint_service):
        """Test getting stats when no checkpoints exist."""
        mock_checkpoint_service.list_checkpoints.return_value = []

        response = client.get("/api/v1/checkpoints/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_checkpoints"] == 0
        assert data["total_size_bytes"] == 0
        assert data["oldest_checkpoint"] is None

    def test_get_stats_with_null_artifact_sizes(self, client, mock_checkpoint_service):
        """Test stats calculation handles None artifact sizes."""
        mock_checkpoint_service.list_checkpoints.return_value = [
            CheckpointSummary(
                operation_id="op_training_123",
                checkpoint_type="periodic",
                created_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
                state_summary={"epoch": 10},
                artifacts_size_bytes=None,  # No artifacts
            ),
            CheckpointSummary(
                operation_id="op_training_456",
                checkpoint_type="cancellation",
                created_at=datetime(2025, 1, 15, 11, 0, 0, tzinfo=timezone.utc),
                state_summary={"epoch": 5},
                artifacts_size_bytes=512000,
            ),
        ]

        response = client.get("/api/v1/checkpoints/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_size_bytes"] == 512000  # Only counts non-None
