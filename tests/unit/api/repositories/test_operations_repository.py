"""Unit tests for OperationsRepository.

Tests use mocked SQLAlchemy async session to test repository logic
without requiring a real database connection.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from ktrdr.api.models.db.operations import OperationRecord
from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationProgress,
    OperationStatus,
    OperationType,
)
from ktrdr.api.repositories.operations_repository import OperationsRepository


class TestOperationsRepositoryCreate:
    """Tests for OperationsRepository.create method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def sample_operation_info(self) -> OperationInfo:
        """Create a sample OperationInfo for testing."""
        return OperationInfo(
            operation_id="op_test_123",
            operation_type=OperationType.TRAINING,
            status=OperationStatus.PENDING,
            created_at=datetime(2024, 12, 21, 10, 0, 0, tzinfo=timezone.utc),
            progress=OperationProgress(
                percentage=0.0,
                current_step=None,
                steps_completed=0,
                steps_total=10,
            ),
            metadata=OperationMetadata(
                symbol="EURUSD",
                timeframe="1h",
            ),
        )

    @pytest.mark.asyncio
    async def test_create_adds_record_to_session(
        self, mock_session, sample_operation_info
    ):
        """create should add an OperationRecord to the session."""
        repo = OperationsRepository(mock_session)

        await repo.create(sample_operation_info)

        # Verify session.add was called with an OperationRecord
        mock_session.add.assert_called_once()
        call_args = mock_session.add.call_args[0][0]
        assert isinstance(call_args, OperationRecord)
        assert call_args.operation_id == "op_test_123"

    @pytest.mark.asyncio
    async def test_create_commits_session(self, mock_session, sample_operation_info):
        """create should commit the session."""
        repo = OperationsRepository(mock_session)

        await repo.create(sample_operation_info)

        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_returns_operation_info(
        self, mock_session, sample_operation_info
    ):
        """create should return the created OperationInfo."""
        repo = OperationsRepository(mock_session)

        result = await repo.create(sample_operation_info)

        assert isinstance(result, OperationInfo)
        assert result.operation_id == sample_operation_info.operation_id
        assert result.operation_type == sample_operation_info.operation_type

    @pytest.mark.asyncio
    async def test_create_converts_metadata_correctly(
        self, mock_session, sample_operation_info
    ):
        """create should convert OperationMetadata to JSONB correctly."""
        repo = OperationsRepository(mock_session)

        await repo.create(sample_operation_info)

        call_args = mock_session.add.call_args[0][0]
        assert call_args.metadata_["symbol"] == "EURUSD"
        assert call_args.metadata_["timeframe"] == "1h"

    @pytest.mark.asyncio
    async def test_create_converts_progress_correctly(
        self, mock_session, sample_operation_info
    ):
        """create should store progress_percent and progress_message correctly."""
        sample_operation_info.progress = OperationProgress(
            percentage=45.5,
            current_step="Training epoch 5/10",
            steps_completed=5,
            steps_total=10,
        )
        repo = OperationsRepository(mock_session)

        await repo.create(sample_operation_info)

        call_args = mock_session.add.call_args[0][0]
        assert call_args.progress_percent == 45.5
        assert call_args.progress_message == "Training epoch 5/10"


class TestOperationsRepositoryGet:
    """Tests for OperationsRepository.get method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def sample_record(self) -> OperationRecord:
        """Create a sample OperationRecord for testing."""
        return OperationRecord(
            operation_id="op_test_456",
            operation_type="training",
            status="running",
            worker_id="worker-abc",
            is_backend_local=False,
            created_at=datetime(2024, 12, 21, 10, 0, 0, tzinfo=timezone.utc),
            started_at=datetime(2024, 12, 21, 10, 1, 0, tzinfo=timezone.utc),
            progress_percent=50.0,
            progress_message="Processing batch 50/100",
            metadata_={"symbol": "AAPL", "timeframe": "1d"},
            result=None,
            error_message=None,
        )

    @pytest.mark.asyncio
    async def test_get_returns_operation_info_when_found(
        self, mock_session, sample_record
    ):
        """get should return OperationInfo when record exists."""
        # Set up mock to return the sample record
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_record
        mock_session.execute.return_value = mock_result

        repo = OperationsRepository(mock_session)

        result = await repo.get("op_test_456")

        assert result is not None
        assert isinstance(result, OperationInfo)
        assert result.operation_id == "op_test_456"
        assert result.status == OperationStatus.RUNNING

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(self, mock_session):
        """get should return None when record doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = OperationsRepository(mock_session)

        result = await repo.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_converts_record_to_operation_info(
        self, mock_session, sample_record
    ):
        """get should correctly convert OperationRecord to OperationInfo."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_record
        mock_session.execute.return_value = mock_result

        repo = OperationsRepository(mock_session)

        result = await repo.get("op_test_456")

        assert result.operation_type == OperationType.TRAINING
        assert result.progress.percentage == 50.0
        assert result.progress.current_step == "Processing batch 50/100"
        assert result.metadata.symbol == "AAPL"
        assert result.metadata.timeframe == "1d"


class TestOperationsRepositoryUpdate:
    """Tests for OperationsRepository.update method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def sample_record(self) -> OperationRecord:
        """Create a sample OperationRecord for testing."""
        return OperationRecord(
            operation_id="op_test_789",
            operation_type="training",
            status="running",
            worker_id="worker-abc",
            is_backend_local=False,
            created_at=datetime(2024, 12, 21, 10, 0, 0, tzinfo=timezone.utc),
            progress_percent=25.0,
            progress_message="Processing...",
            metadata_={"symbol": "EURUSD"},
        )

    @pytest.mark.asyncio
    async def test_update_modifies_status(self, mock_session, sample_record):
        """update should modify the status field."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_record
        mock_session.execute.return_value = mock_result

        repo = OperationsRepository(mock_session)

        result = await repo.update("op_test_789", status="completed")

        assert result is not None
        assert sample_record.status == "completed"
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_modifies_progress(self, mock_session, sample_record):
        """update should modify progress fields."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_record
        mock_session.execute.return_value = mock_result

        repo = OperationsRepository(mock_session)

        result = await repo.update(
            "op_test_789",
            progress_percent=75.0,
            progress_message="Almost done",
        )

        assert result is not None
        assert sample_record.progress_percent == 75.0
        assert sample_record.progress_message == "Almost done"

    @pytest.mark.asyncio
    async def test_update_returns_none_when_not_found(self, mock_session):
        """update should return None when record doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = OperationsRepository(mock_session)

        result = await repo.update("nonexistent", status="completed")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_sets_completed_at_timestamp(self, mock_session, sample_record):
        """update should set completed_at when status becomes terminal."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_record
        mock_session.execute.return_value = mock_result

        repo = OperationsRepository(mock_session)

        await repo.update("op_test_789", status="completed")

        assert sample_record.completed_at is not None

    @pytest.mark.asyncio
    async def test_update_returns_converted_operation_info(
        self, mock_session, sample_record
    ):
        """update should return OperationInfo after updating."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_record
        mock_session.execute.return_value = mock_result

        repo = OperationsRepository(mock_session)

        result = await repo.update("op_test_789", status="completed")

        assert isinstance(result, OperationInfo)
        assert result.operation_id == "op_test_789"


class TestOperationsRepositoryList:
    """Tests for OperationsRepository.list method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def sample_records(self) -> list[OperationRecord]:
        """Create sample OperationRecords for testing."""
        return [
            OperationRecord(
                operation_id="op_1",
                operation_type="training",
                status="running",
                worker_id="worker-1",
                created_at=datetime(2024, 12, 21, 10, 0, 0, tzinfo=timezone.utc),
                progress_percent=50.0,
                metadata_={},
            ),
            OperationRecord(
                operation_id="op_2",
                operation_type="backtesting",
                status="completed",
                worker_id="worker-2",
                created_at=datetime(2024, 12, 21, 11, 0, 0, tzinfo=timezone.utc),
                progress_percent=100.0,
                metadata_={},
            ),
            OperationRecord(
                operation_id="op_3",
                operation_type="training",
                status="running",
                worker_id="worker-1",
                created_at=datetime(2024, 12, 21, 12, 0, 0, tzinfo=timezone.utc),
                progress_percent=25.0,
                metadata_={},
            ),
        ]

    @pytest.mark.asyncio
    async def test_list_returns_all_operations(self, mock_session, sample_records):
        """list should return all operations when no filters specified."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_records
        mock_session.execute.return_value = mock_result

        repo = OperationsRepository(mock_session)

        result = await repo.list()

        assert len(result) == 3
        assert all(isinstance(op, OperationInfo) for op in result)

    @pytest.mark.asyncio
    async def test_list_filters_by_status(self, mock_session, sample_records):
        """list should filter by status when specified."""
        # Filter should be applied in the query
        running_records = [r for r in sample_records if r.status == "running"]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = running_records
        mock_session.execute.return_value = mock_result

        repo = OperationsRepository(mock_session)

        result = await repo.list(status="running")

        assert len(result) == 2
        assert all(op.status == OperationStatus.RUNNING for op in result)

    @pytest.mark.asyncio
    async def test_list_filters_by_worker_id(self, mock_session, sample_records):
        """list should filter by worker_id when specified."""
        worker1_records = [r for r in sample_records if r.worker_id == "worker-1"]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = worker1_records
        mock_session.execute.return_value = mock_result

        repo = OperationsRepository(mock_session)

        result = await repo.list(worker_id="worker-1")

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_returns_empty_list_when_no_matches(self, mock_session):
        """list should return empty list when no operations match."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        repo = OperationsRepository(mock_session)

        result = await repo.list(status="failed")

        assert result == []


class TestOperationsRepositoryDelete:
    """Tests for OperationsRepository.delete method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        session = AsyncMock()
        session.delete = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def sample_record(self) -> OperationRecord:
        """Create a sample OperationRecord for testing."""
        return OperationRecord(
            operation_id="op_to_delete",
            operation_type="training",
            status="failed",
            created_at=datetime(2024, 12, 21, 10, 0, 0, tzinfo=timezone.utc),
            metadata_={},
        )

    @pytest.mark.asyncio
    async def test_delete_returns_true_when_found(self, mock_session, sample_record):
        """delete should return True when record exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_record
        mock_session.execute.return_value = mock_result

        repo = OperationsRepository(mock_session)

        result = await repo.delete("op_to_delete")

        assert result is True
        mock_session.delete.assert_called_once_with(sample_record)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self, mock_session):
        """delete should return False when record doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = OperationsRepository(mock_session)

        result = await repo.delete("nonexistent")

        assert result is False
        mock_session.delete.assert_not_called()


class TestOperationsRepositoryConversion:
    """Tests for model conversion between OperationRecord and OperationInfo."""

    def test_record_to_info_converts_all_fields(self):
        """Conversion should map all fields from OperationRecord to OperationInfo."""
        record = OperationRecord(
            operation_id="op_conv_test",
            operation_type="backtesting",
            status="completed",
            worker_id="worker-xyz",
            is_backend_local=False,
            created_at=datetime(2024, 12, 21, 10, 0, 0, tzinfo=timezone.utc),
            started_at=datetime(2024, 12, 21, 10, 1, 0, tzinfo=timezone.utc),
            completed_at=datetime(2024, 12, 21, 11, 0, 0, tzinfo=timezone.utc),
            progress_percent=100.0,
            progress_message="Completed successfully",
            metadata_={
                "symbol": "BTCUSD",
                "timeframe": "4h",
                "start_date": "2024-01-01T00:00:00Z",
            },
            result={"total_trades": 150, "win_rate": 0.65},
            error_message=None,
        )

        info = OperationsRepository._record_to_info(record)

        assert info.operation_id == "op_conv_test"
        assert info.operation_type == OperationType.BACKTESTING
        assert info.status == OperationStatus.COMPLETED
        assert info.created_at == datetime(2024, 12, 21, 10, 0, 0, tzinfo=timezone.utc)
        assert info.progress.percentage == 100.0
        assert info.progress.current_step == "Completed successfully"
        assert info.metadata.symbol == "BTCUSD"
        assert info.result_summary == {"total_trades": 150, "win_rate": 0.65}

    def test_info_to_record_converts_all_fields(self):
        """Conversion should map all fields from OperationInfo to OperationRecord."""
        info = OperationInfo(
            operation_id="op_info_test",
            operation_type=OperationType.TRAINING,
            status=OperationStatus.RUNNING,
            created_at=datetime(2024, 12, 21, 10, 0, 0, tzinfo=timezone.utc),
            started_at=datetime(2024, 12, 21, 10, 5, 0, tzinfo=timezone.utc),
            progress=OperationProgress(
                percentage=33.3,
                current_step="Epoch 10/30",
                steps_completed=10,
                steps_total=30,
            ),
            metadata=OperationMetadata(
                symbol="ETHUSDT",
                timeframe="15m",
                parameters={"batch_size": 32},
            ),
        )

        record = OperationsRepository._info_to_record(info)

        assert record.operation_id == "op_info_test"
        assert record.operation_type == "training"
        assert record.status == "running"
        assert record.progress_percent == 33.3
        assert record.progress_message == "Epoch 10/30"
        assert record.metadata_["symbol"] == "ETHUSDT"
        assert record.metadata_["timeframe"] == "15m"

    def test_conversion_handles_none_values(self):
        """Conversion should handle None values gracefully."""
        record = OperationRecord(
            operation_id="op_none_test",
            operation_type="training",
            status="pending",
            created_at=datetime(2024, 12, 21, 10, 0, 0, tzinfo=timezone.utc),
            progress_percent=0.0,
            progress_message=None,
            metadata_={},
            result=None,
            error_message=None,
            worker_id=None,
        )

        info = OperationsRepository._record_to_info(record)

        assert info.progress.current_step is None
        assert info.result_summary is None
        assert info.error_message is None
