"""
Unit tests for OperationsService persistence methods.

Tests saving and loading operations from PostgreSQL database.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationProgress,
    OperationStatus,
    OperationType,
)
from ktrdr.api.services.operations_service import OperationsService


class TestOperationsServicePersistence:
    """Test OperationsService database persistence."""

    @pytest.fixture
    def mock_db_connection(self):
        """Mock database connection."""
        with patch("ktrdr.database.connection.get_database_connection") as mock:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_db = MagicMock()
            mock_db.__enter__.return_value = mock_conn
            mock.return_value = mock_db
            yield mock_db, mock_conn, mock_cursor

    @pytest.fixture
    def operations_service(self):
        """Create OperationsService instance."""
        return OperationsService()

    @pytest.fixture
    def sample_operation(self):
        """Create sample operation for testing."""
        return OperationInfo(
            operation_id="op_test_001",
            operation_type=OperationType.TRAINING,
            status=OperationStatus.RUNNING,
            created_at=datetime(2025, 1, 17, 10, 0, 0, tzinfo=timezone.utc),
            started_at=datetime(2025, 1, 17, 10, 1, 0, tzinfo=timezone.utc),
            progress=OperationProgress(
                percentage=50.0,
                current_step="Epoch 5/10",
                steps_completed=5,
                steps_total=10,
            ),
            metadata=OperationMetadata(
                symbol="AAPL",
                timeframe="1d",
                mode="train",
            ),
        )

    @pytest.mark.asyncio
    async def test_persist_operation_insert(
        self, operations_service, sample_operation, mock_db_connection
    ):
        """Test persisting a new operation inserts into database."""
        mock_db, mock_conn, mock_cursor = mock_db_connection

        await operations_service.persist_operation(sample_operation)

        # Verify INSERT was called
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        sql = call_args[0]

        assert "INSERT INTO operations" in sql
        assert "operation_id" in sql
        assert "operation_type" in sql
        assert "status" in sql
        assert "ON CONFLICT (operation_id) DO UPDATE" in sql

        # Verify connection committed
        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_operation_serialization(
        self, operations_service, sample_operation, mock_db_connection
    ):
        """Test operation metadata is correctly serialized to JSON."""
        mock_db, mock_conn, mock_cursor = mock_db_connection

        await operations_service.persist_operation(sample_operation)

        call_args = mock_cursor.execute.call_args[0]
        params = call_args[1]

        # Verify metadata_json contains serialized metadata
        metadata_json = next(p for p in params if isinstance(p, str) and "AAPL" in p)
        metadata = json.loads(metadata_json)
        assert metadata["symbol"] == "AAPL"
        assert metadata["timeframe"] == "1d"

    @pytest.mark.asyncio
    async def test_persist_operation_error_handling(
        self, operations_service, sample_operation, mock_db_connection
    ):
        """Test persist_operation handles database errors gracefully."""
        mock_db, mock_conn, mock_cursor = mock_db_connection
        mock_cursor.execute.side_effect = Exception("Database error")

        # Should not raise exception, but log error
        await operations_service.persist_operation(sample_operation)

        # Verify rollback was called
        mock_conn.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_operations_all(self, operations_service, mock_db_connection):
        """Test loading all operations from database."""
        mock_db, mock_conn, mock_cursor = mock_db_connection

        # Mock database response
        mock_cursor.fetchall.return_value = [
            (
                "op_test_001",
                "training",
                "COMPLETED",
                datetime(2025, 1, 17, 10, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 17, 10, 1, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 17, 10, 10, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 17, 10, 10, 0, tzinfo=timezone.utc),
                '{"symbol": "AAPL", "timeframe": "1d"}',
                '{"final_epoch": 10}',
                None,
            ),
        ]

        operations = await operations_service.load_operations()

        # Verify SELECT was called
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "SELECT" in sql
        assert "FROM operations" in sql

        # Verify operations loaded correctly
        assert len(operations) == 1
        assert operations[0].operation_id == "op_test_001"
        assert operations[0].operation_type == OperationType.TRAINING
        assert operations[0].status == OperationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_load_operations_by_status(
        self, operations_service, mock_db_connection
    ):
        """Test loading operations filtered by status."""
        mock_db, mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = []

        await operations_service.load_operations(status=OperationStatus.RUNNING)

        # Verify WHERE clause includes status filter
        sql = mock_cursor.execute.call_args[0][0]
        assert "WHERE status = %s" in sql

        params = mock_cursor.execute.call_args[0][1]
        assert "RUNNING" in params

    @pytest.mark.asyncio
    async def test_load_operations_with_checkpoints(
        self, operations_service, mock_db_connection
    ):
        """Test loading operations with checkpoint metadata."""
        mock_db, mock_conn, mock_cursor = mock_db_connection

        # Mock database response with checkpoint info
        mock_cursor.fetchall.return_value = [
            (
                "op_test_001",
                "training",
                "FAILED",
                datetime(2025, 1, 17, 10, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 17, 10, 1, 0, tzinfo=timezone.utc),
                None,
                datetime(2025, 1, 17, 10, 10, 0, tzinfo=timezone.utc),
                '{"symbol": "AAPL"}',
                None,
                "Out of memory",
                "checkpoint_001",  # checkpoint_id
                52000000,  # checkpoint size
                datetime(
                    2025, 1, 17, 10, 9, 0, tzinfo=timezone.utc
                ),  # checkpoint created
            ),
        ]

        operations = await operations_service.load_operations_with_checkpoints()

        # Verify JOIN with operation_checkpoints table
        sql = mock_cursor.execute.call_args[0][0]
        assert "LEFT JOIN operation_checkpoints" in sql
        assert "checkpoint_id" in sql

        # Verify checkpoint info included in results
        assert len(operations) == 1
        op = operations[0]
        assert hasattr(op, "checkpoint_id")
        assert op.checkpoint_id == "checkpoint_001"
        assert hasattr(op, "checkpoint_size_bytes")
        assert op.checkpoint_size_bytes == 52000000

    @pytest.mark.asyncio
    async def test_load_operations_empty_result(
        self, operations_service, mock_db_connection
    ):
        """Test loading operations when database returns empty result."""
        mock_db, mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = []

        operations = await operations_service.load_operations()

        assert operations == []

    @pytest.mark.asyncio
    async def test_load_operations_error_handling(
        self, operations_service, mock_db_connection
    ):
        """Test load_operations handles database errors gracefully."""
        mock_db, mock_conn, mock_cursor = mock_db_connection
        mock_cursor.execute.side_effect = Exception("Database error")

        # Should return empty list on error (logged)
        operations = await operations_service.load_operations()

        assert operations == []


class TestOperationsServicePersistenceIntegration:
    """Integration tests for persistence with existing methods."""

    @pytest.fixture
    def mock_db_connection(self):
        """Mock database connection."""
        with patch("ktrdr.database.connection.get_database_connection") as mock:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_db = MagicMock()
            mock_db.__enter__.return_value = mock_conn
            mock.return_value = mock_db
            yield mock_db, mock_conn, mock_cursor

    @pytest.mark.asyncio
    async def test_create_operation_persists_to_database(self, mock_db_connection):
        """Test create_operation automatically persists to database."""
        mock_db, mock_conn, mock_cursor = mock_db_connection
        operations_service = OperationsService()

        operation_info = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            description="Test training",
            metadata=OperationMetadata(symbol="AAPL", timeframe="1d"),
        )

        # Verify operation persisted to database
        mock_cursor.execute.assert_called()
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO operations" in sql

    @pytest.mark.asyncio
    async def test_complete_operation_updates_database(self, mock_db_connection):
        """Test complete_operation updates database status."""
        mock_db, mock_conn, mock_cursor = mock_db_connection
        operations_service = OperationsService()

        # Create operation first
        operation_info = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            description="Test training",
        )

        # Reset mock to check complete_operation calls
        mock_cursor.reset_mock()

        # Complete operation
        await operations_service.complete_operation(
            operation_id=operation_info.operation_id,
            result_summary={"final_epoch": 10},
        )

        # Verify UPDATE was called
        mock_cursor.execute.assert_called()
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO operations" in sql or "UPDATE" in sql
        # Should update status to COMPLETED

    @pytest.mark.asyncio
    async def test_fail_operation_updates_database(self, mock_db_connection):
        """Test fail_operation updates database status and error message."""
        mock_db, mock_conn, mock_cursor = mock_db_connection
        operations_service = OperationsService()

        # Create operation first
        operation_info = await operations_service.create_operation(
            operation_type=OperationType.TRAINING,
            description="Test training",
        )

        # Reset mock
        mock_cursor.reset_mock()

        # Fail operation
        await operations_service.fail_operation(
            operation_id=operation_info.operation_id,
            error_message="Test error",
        )

        # Verify UPDATE was called with FAILED status
        mock_cursor.execute.assert_called()
        sql = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO operations" in sql or "UPDATE" in sql
        # Should set status to FAILED and error_message
