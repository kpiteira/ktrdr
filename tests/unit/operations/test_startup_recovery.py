"""
Unit tests for startup recovery logic.

Tests automatic recovery of interrupted operations on API restart.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.api.services.operations_service import OperationsService


class TestStartupRecovery:
    """Test startup recovery functionality."""

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

    @pytest.mark.asyncio
    async def test_recover_interrupted_operations_marks_running_as_failed(
        self, operations_service, mock_db_connection
    ):
        """Test recover_interrupted_operations marks RUNNING operations as FAILED."""
        mock_db, mock_conn, mock_cursor = mock_db_connection

        # Mock database to return 3 RUNNING operations
        mock_cursor.fetchall.return_value = [
            (
                "op_test_001",
                "training",
                "running",
                datetime(2025, 1, 17, 10, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 17, 10, 1, 0, tzinfo=timezone.utc),
                None,
                datetime(2025, 1, 17, 10, 5, 0, tzinfo=timezone.utc),
                '{"symbol": "AAPL"}',
                None,
                None,
            ),
            (
                "op_test_002",
                "backtesting",
                "running",
                datetime(2025, 1, 17, 11, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 17, 11, 1, 0, tzinfo=timezone.utc),
                None,
                datetime(2025, 1, 17, 11, 5, 0, tzinfo=timezone.utc),
                '{"symbol": "EURUSD"}',
                None,
                None,
            ),
            (
                "op_test_003",
                "data_load",
                "running",
                datetime(2025, 1, 17, 12, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 17, 12, 1, 0, tzinfo=timezone.utc),
                None,
                datetime(2025, 1, 17, 12, 2, 0, tzinfo=timezone.utc),
                '{"symbol": "BTCUSD"}',
                None,
                None,
            ),
        ]

        # Call recover
        recovered_count = await operations_service.recover_interrupted_operations()

        # Verify correct number recovered
        assert recovered_count == 3

        # Verify SELECT query for RUNNING operations
        assert mock_cursor.execute.call_count >= 1
        select_call = mock_cursor.execute.call_args_list[0][0]
        assert "SELECT" in select_call[0]
        assert "WHERE status = %s" in select_call[0]
        assert "running" in select_call[1]

        # Verify UPDATE query to mark as FAILED
        update_calls = [
            call
            for call in mock_cursor.execute.call_args_list
            if "UPDATE" in call[0][0]
        ]
        assert len(update_calls) == 3  # One UPDATE per operation

        # Verify each UPDATE sets status to FAILED and error_message
        for call in update_calls:
            sql = call[0][0]
            params = call[0][1]
            assert "UPDATE operations" in sql
            assert "SET status = %s" in sql
            assert "failed" in params
            assert "Operation interrupted by API restart" in params

        # Verify commit called
        assert mock_conn.commit.call_count >= 1

    @pytest.mark.asyncio
    async def test_recover_interrupted_operations_no_running_operations(
        self, operations_service, mock_db_connection
    ):
        """Test recover when no RUNNING operations found."""
        mock_db, mock_conn, mock_cursor = mock_db_connection

        # Mock empty result
        mock_cursor.fetchall.return_value = []

        recovered_count = await operations_service.recover_interrupted_operations()

        # Should return 0
        assert recovered_count == 0

        # Should still query database
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "SELECT" in sql
        assert "WHERE status = %s" in sql

    @pytest.mark.asyncio
    async def test_recover_interrupted_operations_sets_completed_at(
        self, operations_service, mock_db_connection
    ):
        """Test recovery sets completed_at timestamp."""
        mock_db, mock_conn, mock_cursor = mock_db_connection

        # Mock one RUNNING operation
        mock_cursor.fetchall.return_value = [
            (
                "op_test_001",
                "training",
                "RUNNING",
                datetime(2025, 1, 17, 10, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 17, 10, 1, 0, tzinfo=timezone.utc),
                None,
                datetime(2025, 1, 17, 10, 5, 0, tzinfo=timezone.utc),
                "{}",
                None,
                None,
            ),
        ]

        await operations_service.recover_interrupted_operations()

        # Verify UPDATE includes completed_at timestamp
        update_call = next(
            call
            for call in mock_cursor.execute.call_args_list
            if "UPDATE" in call[0][0]
        )
        sql = update_call[0][0]
        assert "completed_at = %s" in sql or "completed_at = NOW()" in sql

    @pytest.mark.asyncio
    async def test_recover_interrupted_operations_preserves_checkpoints(
        self, operations_service, mock_db_connection
    ):
        """Test recovery does not delete checkpoints (they remain for resume)."""
        mock_db, mock_conn, mock_cursor = mock_db_connection

        # Mock RUNNING operation
        mock_cursor.fetchall.return_value = [
            (
                "op_test_001",
                "training",
                "RUNNING",
                datetime(2025, 1, 17, 10, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 17, 10, 1, 0, tzinfo=timezone.utc),
                None,
                datetime(2025, 1, 17, 10, 5, 0, tzinfo=timezone.utc),
                "{}",
                None,
                None,
            ),
        ]

        await operations_service.recover_interrupted_operations()

        # Verify NO DELETE from operation_checkpoints
        delete_calls = [
            call
            for call in mock_cursor.execute.call_args_list
            if "DELETE FROM operation_checkpoints" in call[0][0]
        ]
        assert len(delete_calls) == 0

    @pytest.mark.asyncio
    async def test_recover_interrupted_operations_error_handling(
        self, operations_service, mock_db_connection
    ):
        """Test recovery handles database errors gracefully."""
        mock_db, mock_conn, mock_cursor = mock_db_connection

        # Simulate database error
        mock_cursor.execute.side_effect = Exception("Database connection lost")

        # Should not raise exception, but return 0
        recovered_count = await operations_service.recover_interrupted_operations()

        assert recovered_count == 0

        # Should attempt rollback
        mock_conn.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_recover_interrupted_operations_logs_recovery(
        self, operations_service, mock_db_connection
    ):
        """Test recovery logs the number of operations recovered."""
        mock_db, mock_conn, mock_cursor = mock_db_connection

        # Mock 2 RUNNING operations
        mock_cursor.fetchall.return_value = [
            (
                "op_test_001",
                "training",
                "RUNNING",
                datetime(2025, 1, 17, 10, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 17, 10, 1, 0, tzinfo=timezone.utc),
                None,
                datetime(2025, 1, 17, 10, 5, 0, tzinfo=timezone.utc),
                "{}",
                None,
                None,
            ),
            (
                "op_test_002",
                "backtesting",
                "RUNNING",
                datetime(2025, 1, 17, 11, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 17, 11, 1, 0, tzinfo=timezone.utc),
                None,
                datetime(2025, 1, 17, 11, 5, 0, tzinfo=timezone.utc),
                "{}",
                None,
                None,
            ),
        ]

        with patch("ktrdr.api.services.operations_service.logger") as mock_logger:
            recovered_count = await operations_service.recover_interrupted_operations()

            assert recovered_count == 2

            # Verify logging
            # Should log info about recovery
            info_calls = list(mock_logger.info.call_args_list)
            assert any("Startup recovery" in str(call) for call in info_calls)
            assert any("2" in str(call) for call in info_calls)


class TestStartupEventIntegration:
    """Test startup recovery integration with FastAPI lifespan event."""

    @pytest.mark.asyncio
    async def test_lifespan_calls_recover_interrupted_operations(self):
        """Test lifespan event calls recover_interrupted_operations on startup."""
        with patch(
            "ktrdr.api.services.operations_service.get_operations_service"
        ) as mock_get_operations_service:
            mock_operations_service = MagicMock()
            mock_operations_service.recover_interrupted_operations = AsyncMock(
                return_value=3
            )
            mock_get_operations_service.return_value = mock_operations_service

            # Import here to avoid early initialization
            # Create a mock FastAPI app
            from fastapi import FastAPI

            from ktrdr.api.startup import lifespan

            app = FastAPI()

            # Execute lifespan startup
            async with lifespan(app):
                pass  # Startup happens in __aenter__

            # Verify recover_interrupted_operations was called
            mock_operations_service.recover_interrupted_operations.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_logs_recovery_count(self):
        """Test lifespan logs the number of recovered operations."""
        with patch(
            "ktrdr.api.services.operations_service.get_operations_service"
        ) as mock_get_operations_service:
            mock_operations_service = MagicMock()
            mock_operations_service.recover_interrupted_operations = AsyncMock(
                return_value=5
            )
            mock_get_operations_service.return_value = mock_operations_service

            with patch("ktrdr.api.startup.logger") as mock_logger:
                from fastapi import FastAPI

                from ktrdr.api.startup import lifespan

                app = FastAPI()

                async with lifespan(app):
                    pass

                # Verify logging
                info_calls = list(mock_logger.info.call_args_list)
                assert any(
                    "5 interrupted operations" in str(call) for call in info_calls
                )
