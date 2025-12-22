"""Tests for the OperationRecord database model."""

from datetime import datetime, timezone

from ktrdr.api.models.db.operations import OperationRecord


class TestOperationRecordModel:
    """Tests for OperationRecord SQLAlchemy model."""

    def test_model_has_required_columns(self):
        """Model should have all required columns defined."""
        # Check that the model has the expected columns
        columns = OperationRecord.__table__.columns

        required_columns = [
            'operation_id',
            'operation_type',
            'status',
            'worker_id',
            'is_backend_local',
            'created_at',
            'started_at',
            'completed_at',
            'progress_percent',
            'progress_message',
            'metadata',
            'result',
            'error_message',
            'last_heartbeat_at',
            'reconciliation_status',
        ]

        for col_name in required_columns:
            assert col_name in columns, f"Missing required column: {col_name}"

    def test_operation_id_is_primary_key(self):
        """operation_id should be the primary key."""
        columns = OperationRecord.__table__.columns
        assert columns['operation_id'].primary_key is True

    def test_status_is_not_nullable(self):
        """status should be required (not nullable)."""
        columns = OperationRecord.__table__.columns
        assert columns['status'].nullable is False

    def test_operation_type_is_not_nullable(self):
        """operation_type should be required (not nullable)."""
        columns = OperationRecord.__table__.columns
        assert columns['operation_type'].nullable is False

    def test_worker_id_is_nullable(self):
        """worker_id should be nullable (operations may not have a worker assigned)."""
        columns = OperationRecord.__table__.columns
        assert columns['worker_id'].nullable is True

    def test_created_at_has_default(self):
        """created_at should have a server default."""
        columns = OperationRecord.__table__.columns
        # Check that there's a server_default or default
        assert columns['created_at'].server_default is not None or columns['created_at'].default is not None

    def test_table_has_indexes(self):
        """Table should have indexes on status, worker_id, and operation_type."""
        indexes = list(OperationRecord.__table__.indexes)
        index_columns = set()
        for idx in indexes:
            for col in idx.columns:
                index_columns.add(col.name)

        # Check that the key columns are indexed
        assert 'status' in index_columns, "Missing index on 'status'"
        assert 'worker_id' in index_columns, "Missing index on 'worker_id'"
        assert 'operation_type' in index_columns, "Missing index on 'operation_type'"

    def test_tablename(self):
        """Table name should be 'operations'."""
        assert OperationRecord.__tablename__ == 'operations'

    def test_metadata_column_uses_jsonb(self):
        """metadata column should use JSONB type.

        Note: The Python attribute is `metadata_` to avoid SQLAlchemy reserved name,
        but the column name in the database is `metadata`.
        """
        columns = OperationRecord.__table__.columns
        # The column type should be JSONB (PostgreSQL JSON with binary storage)
        col_type = str(columns['metadata'].type)
        assert 'JSONB' in col_type.upper() or 'JSON' in col_type.upper()

    def test_result_column_uses_jsonb(self):
        """result column should use JSONB type."""
        columns = OperationRecord.__table__.columns
        col_type = str(columns['result'].type)
        assert 'JSONB' in col_type.upper() or 'JSON' in col_type.upper()


class TestOperationRecordCreation:
    """Tests for creating OperationRecord instances."""

    def test_create_minimal_operation_record(self):
        """Should be able to create a record with minimal required fields."""
        record = OperationRecord(
            operation_id="op_test_123",
            operation_type="training",
            status="PENDING",
        )

        assert record.operation_id == "op_test_123"
        assert record.operation_type == "training"
        assert record.status == "PENDING"
        assert record.worker_id is None
        # Note: is_backend_local default is applied at DB insert time, not at instance creation
        # The column has a default=False, but SQLAlchemy doesn't apply it until flush

    def test_is_backend_local_column_has_default(self):
        """is_backend_local should have a default of False."""
        columns = OperationRecord.__table__.columns
        assert columns['is_backend_local'].default is not None
        # The default arg returns a ColumnDefault object, the actual default is accessed via .arg
        assert columns['is_backend_local'].default.arg is False

    def test_create_full_operation_record(self):
        """Should be able to create a record with all fields populated."""
        now = datetime.now(timezone.utc)

        record = OperationRecord(
            operation_id="op_test_456",
            operation_type="backtesting",
            status="RUNNING",
            worker_id="worker-abc",
            is_backend_local=False,
            created_at=now,
            started_at=now,
            progress_percent=45.5,
            progress_message="Processing epoch 45/100",
            metadata_={"symbol": "EURUSD", "timeframe": "1h"},
            result=None,
            error_message=None,
            last_heartbeat_at=now,
            reconciliation_status=None,
        )

        assert record.operation_id == "op_test_456"
        assert record.status == "RUNNING"
        assert record.worker_id == "worker-abc"
        assert record.progress_percent == 45.5
        assert record.metadata_ == {"symbol": "EURUSD", "timeframe": "1h"}
