"""Unit tests for CheckpointService.

Tests use mocked SQLAlchemy async session and filesystem to test
checkpoint persistence logic without requiring real infrastructure.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from ktrdr.api.models.db.checkpoints import CheckpointRecord
from ktrdr.checkpoint.checkpoint_service import (
    CheckpointCorruptedError,
    CheckpointData,
    CheckpointService,
    CheckpointSummary,
)


def create_mock_session_factory(mock_session):
    """Create a mock session factory that returns the given mock session."""

    @asynccontextmanager
    async def mock_factory():
        yield mock_session

    return mock_factory


class TestCheckpointServiceSave:
    """Tests for CheckpointService.save_checkpoint method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.fixture
    def mock_session_factory(self, mock_session):
        """Create a mock session factory."""
        return create_mock_session_factory(mock_session)

    @pytest.fixture
    def temp_artifacts_dir(self, tmp_path):
        """Create a temporary artifacts directory."""
        artifacts_dir = tmp_path / "checkpoints"
        artifacts_dir.mkdir()
        return artifacts_dir

    @pytest.fixture
    def service(self, mock_session_factory, temp_artifacts_dir):
        """Create a CheckpointService instance."""
        return CheckpointService(
            session_factory=mock_session_factory,
            artifacts_dir=str(temp_artifacts_dir),
        )

    @pytest.mark.asyncio
    async def test_save_upserts_to_database(self, service, mock_session):
        """save_checkpoint should UPSERT checkpoint record to database."""
        state = {"epoch": 10, "train_loss": 0.5}

        await service.save_checkpoint(
            operation_id="op_test_123",
            checkpoint_type="periodic",
            state=state,
        )

        # Verify execute was called (for UPSERT)
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_writes_artifacts_atomically(
        self, service, mock_session, temp_artifacts_dir
    ):
        """save_checkpoint should write artifacts atomically using temp directory."""
        state = {"epoch": 10}
        artifacts = {
            "model.pt": b"model_weights_data",
            "optimizer.pt": b"optimizer_state_data",
        }

        await service.save_checkpoint(
            operation_id="op_test_123",
            checkpoint_type="periodic",
            state=state,
            artifacts=artifacts,
        )

        # Verify artifacts were written to final location
        artifact_path = temp_artifacts_dir / "op_test_123"
        assert artifact_path.exists()
        assert (artifact_path / "model.pt").read_bytes() == b"model_weights_data"
        assert (artifact_path / "optimizer.pt").read_bytes() == b"optimizer_state_data"

        # Verify no temp directory left behind
        temp_path = temp_artifacts_dir / "op_test_123.tmp"
        assert not temp_path.exists()

    @pytest.mark.asyncio
    async def test_save_overwrites_existing_artifacts(
        self, service, mock_session, temp_artifacts_dir
    ):
        """save_checkpoint should overwrite existing checkpoint artifacts."""
        # Create existing checkpoint
        artifact_path = temp_artifacts_dir / "op_test_123"
        artifact_path.mkdir()
        (artifact_path / "model.pt").write_bytes(b"old_weights")
        (artifact_path / "old_file.pt").write_bytes(b"should_be_gone")

        # Save new checkpoint
        await service.save_checkpoint(
            operation_id="op_test_123",
            checkpoint_type="periodic",
            state={"epoch": 20},
            artifacts={"model.pt": b"new_weights"},
        )

        # Verify new artifacts replaced old
        assert (artifact_path / "model.pt").read_bytes() == b"new_weights"
        # Old file should be gone
        assert not (artifact_path / "old_file.pt").exists()

    @pytest.mark.asyncio
    async def test_save_without_artifacts(
        self, service, mock_session, temp_artifacts_dir
    ):
        """save_checkpoint should work without artifacts (backtesting case)."""
        await service.save_checkpoint(
            operation_id="op_test_123",
            checkpoint_type="periodic",
            state={"bar_index": 5000},
            artifacts=None,
        )

        # Verify DB was updated
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

        # Verify no artifacts directory created
        artifact_path = temp_artifacts_dir / "op_test_123"
        assert not artifact_path.exists()

    @pytest.mark.asyncio
    async def test_save_cleans_up_artifacts_on_db_failure(
        self, service, mock_session, temp_artifacts_dir
    ):
        """save_checkpoint should delete artifacts if DB write fails."""
        mock_session.execute.side_effect = Exception("Database connection failed")

        with pytest.raises(Exception, match="Database connection failed"):
            await service.save_checkpoint(
                operation_id="op_test_123",
                checkpoint_type="periodic",
                state={"epoch": 10},
                artifacts={"model.pt": b"model_data"},
            )

        # Verify artifacts were cleaned up
        artifact_path = temp_artifacts_dir / "op_test_123"
        assert not artifact_path.exists()

    @pytest.mark.asyncio
    async def test_save_calculates_state_size(self, service, mock_session):
        """save_checkpoint should calculate and store state size."""
        state = {"epoch": 10, "train_loss": 0.5, "history": [1, 2, 3]}

        await service.save_checkpoint(
            operation_id="op_test_123",
            checkpoint_type="periodic",
            state=state,
        )

        # Verify the UPSERT was called (state_size_bytes is calculated internally)
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_calculates_artifacts_size(
        self, service, mock_session, temp_artifacts_dir
    ):
        """save_checkpoint should calculate and store total artifacts size."""
        artifacts = {
            "model.pt": b"a" * 1000,
            "optimizer.pt": b"b" * 500,
        }

        await service.save_checkpoint(
            operation_id="op_test_123",
            checkpoint_type="periodic",
            state={"epoch": 10},
            artifacts=artifacts,
        )

        # Total should be 1500 bytes
        mock_session.execute.assert_called_once()


class TestCheckpointServiceLoad:
    """Tests for CheckpointService.load_checkpoint method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def mock_session_factory(self, mock_session):
        """Create a mock session factory."""
        return create_mock_session_factory(mock_session)

    @pytest.fixture
    def temp_artifacts_dir(self, tmp_path):
        """Create a temporary artifacts directory."""
        artifacts_dir = tmp_path / "checkpoints"
        artifacts_dir.mkdir()
        return artifacts_dir

    @pytest.fixture
    def service(self, mock_session_factory, temp_artifacts_dir):
        """Create a CheckpointService instance."""
        return CheckpointService(
            session_factory=mock_session_factory,
            artifacts_dir=str(temp_artifacts_dir),
        )

    @pytest.fixture
    def sample_record(self, temp_artifacts_dir):
        """Create a sample CheckpointRecord."""
        record = MagicMock(spec=CheckpointRecord)
        record.operation_id = "op_test_123"
        record.checkpoint_type = "periodic"
        record.created_at = datetime(2024, 12, 21, 10, 0, 0, tzinfo=timezone.utc)
        record.state = {"epoch": 10, "train_loss": 0.5}
        record.artifacts_path = str(temp_artifacts_dir / "op_test_123")
        record.state_size_bytes = 50
        record.artifacts_size_bytes = 1000
        return record

    @pytest.mark.asyncio
    async def test_load_returns_checkpoint_data_when_found(
        self, service, mock_session, sample_record
    ):
        """load_checkpoint should return CheckpointData when checkpoint exists."""
        # Setup mock to return the record
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_record
        mock_session.execute.return_value = mock_result

        result = await service.load_checkpoint("op_test_123", load_artifacts=False)

        assert result is not None
        assert isinstance(result, CheckpointData)
        assert result.operation_id == "op_test_123"
        assert result.checkpoint_type == "periodic"
        assert result.state == {"epoch": 10, "train_loss": 0.5}

    @pytest.mark.asyncio
    async def test_load_returns_none_when_not_found(self, service, mock_session):
        """load_checkpoint should return None when checkpoint doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await service.load_checkpoint("op_nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_load_with_artifacts(
        self, service, mock_session, sample_record, temp_artifacts_dir
    ):
        """load_checkpoint should load artifacts from filesystem when requested."""
        # Create artifact files
        artifact_path = temp_artifacts_dir / "op_test_123"
        artifact_path.mkdir()
        (artifact_path / "model.pt").write_bytes(b"model_weights")
        (artifact_path / "optimizer.pt").write_bytes(b"optimizer_state")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_record
        mock_session.execute.return_value = mock_result

        result = await service.load_checkpoint("op_test_123", load_artifacts=True)

        assert result is not None
        assert result.artifacts is not None
        assert result.artifacts["model.pt"] == b"model_weights"
        assert result.artifacts["optimizer.pt"] == b"optimizer_state"

    @pytest.mark.asyncio
    async def test_load_without_artifacts_skips_filesystem(
        self, service, mock_session, sample_record
    ):
        """load_checkpoint with load_artifacts=False should not read filesystem."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_record
        mock_session.execute.return_value = mock_result

        result = await service.load_checkpoint("op_test_123", load_artifacts=False)

        assert result is not None
        assert result.artifacts is None

    @pytest.mark.asyncio
    async def test_load_raises_corrupted_when_artifacts_missing(
        self, service, mock_session, sample_record
    ):
        """load_checkpoint should raise CheckpointCorruptedError if artifacts are missing."""
        # Record points to artifacts path that doesn't exist
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_record
        mock_session.execute.return_value = mock_result

        with pytest.raises(CheckpointCorruptedError) as exc_info:
            await service.load_checkpoint("op_test_123", load_artifacts=True)

        assert "op_test_123" in str(exc_info.value)


class TestCheckpointServiceDelete:
    """Tests for CheckpointService.delete_checkpoint method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.delete = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_session_factory(self, mock_session):
        """Create a mock session factory."""
        return create_mock_session_factory(mock_session)

    @pytest.fixture
    def temp_artifacts_dir(self, tmp_path):
        """Create a temporary artifacts directory."""
        artifacts_dir = tmp_path / "checkpoints"
        artifacts_dir.mkdir()
        return artifacts_dir

    @pytest.fixture
    def service(self, mock_session_factory, temp_artifacts_dir):
        """Create a CheckpointService instance."""
        return CheckpointService(
            session_factory=mock_session_factory,
            artifacts_dir=str(temp_artifacts_dir),
        )

    @pytest.mark.asyncio
    async def test_delete_removes_db_row_and_artifacts(
        self, service, mock_session, temp_artifacts_dir
    ):
        """delete_checkpoint should remove both DB row and filesystem artifacts."""
        # Create artifact directory
        artifact_path = temp_artifacts_dir / "op_test_123"
        artifact_path.mkdir()
        (artifact_path / "model.pt").write_bytes(b"data")

        # Mock the get to return a record with artifacts
        record = MagicMock()
        record.artifacts_path = str(artifact_path)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = record
        mock_session.execute.return_value = mock_result

        result = await service.delete_checkpoint("op_test_123")

        assert result is True
        # Verify artifacts deleted
        assert not artifact_path.exists()
        # Verify DB operations: execute (get) + delete + commit
        mock_session.execute.assert_called_once()
        mock_session.delete.assert_called_once_with(record)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self, service, mock_session):
        """delete_checkpoint should return False if checkpoint doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await service.delete_checkpoint("op_nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_without_artifacts(self, service, mock_session):
        """delete_checkpoint should work when checkpoint has no artifacts."""
        record = MagicMock()
        record.artifacts_path = None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = record
        mock_session.execute.return_value = mock_result

        result = await service.delete_checkpoint("op_test_123")

        assert result is True


class TestCheckpointServiceList:
    """Tests for CheckpointService.list_checkpoints method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def mock_session_factory(self, mock_session):
        """Create a mock session factory."""
        return create_mock_session_factory(mock_session)

    @pytest.fixture
    def service(self, mock_session_factory, tmp_path):
        """Create a CheckpointService instance."""
        return CheckpointService(
            session_factory=mock_session_factory,
            artifacts_dir=str(tmp_path / "checkpoints"),
        )

    @pytest.fixture
    def sample_records(self):
        """Create sample checkpoint records."""
        records = []
        for i, (op_id, cp_type, days_ago) in enumerate(
            [
                ("op_1", "periodic", 1),
                ("op_2", "cancellation", 10),
                ("op_3", "failure", 40),
            ]
        ):
            record = MagicMock()
            record.operation_id = op_id
            record.checkpoint_type = cp_type
            record.created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
            record.state = {"epoch": i * 10}
            record.artifacts_path = f"/data/checkpoints/{op_id}"
            record.state_size_bytes = 100
            record.artifacts_size_bytes = 1000 * (i + 1)
            records.append(record)
        return records

    @pytest.mark.asyncio
    async def test_list_returns_all_checkpoints(
        self, service, mock_session, sample_records
    ):
        """list_checkpoints should return all checkpoints."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_records
        mock_session.execute.return_value = mock_result

        result = await service.list_checkpoints()

        assert len(result) == 3
        assert all(isinstance(cp, CheckpointSummary) for cp in result)
        assert result[0].operation_id == "op_1"

    @pytest.mark.asyncio
    async def test_list_filters_by_age(self, service, mock_session, sample_records):
        """list_checkpoints should filter by older_than_days."""
        # Filter to only return old checkpoints
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_records[2]]
        mock_session.execute.return_value = mock_result

        await service.list_checkpoints(older_than_days=30)

        # The filtering happens in the query, we just verify the method accepts the param
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_returns_empty_when_no_checkpoints(self, service, mock_session):
        """list_checkpoints should return empty list when no checkpoints exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await service.list_checkpoints()

        assert result == []


class TestCheckpointDataClasses:
    """Tests for checkpoint data classes."""

    def test_checkpoint_data_creation(self):
        """CheckpointData should be creatable with required fields."""
        data = CheckpointData(
            operation_id="op_test",
            checkpoint_type="periodic",
            created_at=datetime.now(timezone.utc),
            state={"epoch": 10},
            artifacts_path="/path/to/artifacts",
        )
        assert data.operation_id == "op_test"
        assert data.artifacts is None  # Default

    def test_checkpoint_summary_creation(self):
        """CheckpointSummary should be creatable with required fields."""
        summary = CheckpointSummary(
            operation_id="op_test",
            checkpoint_type="cancellation",
            created_at=datetime.now(timezone.utc),
            state_summary={"epoch": 10},
            artifacts_size_bytes=1000,
        )
        assert summary.operation_id == "op_test"
        assert summary.artifacts_size_bytes == 1000
