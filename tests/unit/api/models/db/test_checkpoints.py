"""Tests for the CheckpointRecord database model."""

from datetime import datetime, timezone

from ktrdr.api.models.db.checkpoints import CheckpointRecord


class TestCheckpointRecordModel:
    """Tests for CheckpointRecord SQLAlchemy model."""

    def test_model_has_required_columns(self):
        """Model should have all required columns defined."""
        columns = CheckpointRecord.__table__.columns

        required_columns = [
            "operation_id",
            "checkpoint_type",
            "created_at",
            "state",
            "artifacts_path",
            "state_size_bytes",
            "artifacts_size_bytes",
        ]

        for col_name in required_columns:
            assert col_name in columns, f"Missing required column: {col_name}"

    def test_operation_id_is_primary_key(self):
        """operation_id should be the primary key."""
        columns = CheckpointRecord.__table__.columns
        assert columns["operation_id"].primary_key is True

    def test_operation_id_is_foreign_key(self):
        """operation_id should have a foreign key to operations table."""
        columns = CheckpointRecord.__table__.columns
        foreign_keys = list(columns["operation_id"].foreign_keys)
        assert (
            len(foreign_keys) == 1
        ), "operation_id should have exactly one foreign key"
        assert (
            foreign_keys[0].target_fullname == "operations.operation_id"
        ), "Foreign key should reference operations.operation_id"

    def test_checkpoint_type_is_not_nullable(self):
        """checkpoint_type should be required (not nullable)."""
        columns = CheckpointRecord.__table__.columns
        assert columns["checkpoint_type"].nullable is False

    def test_created_at_has_default(self):
        """created_at should have a server default."""
        columns = CheckpointRecord.__table__.columns
        assert (
            columns["created_at"].server_default is not None
            or columns["created_at"].default is not None
        ), "created_at should have a default"

    def test_created_at_is_not_nullable(self):
        """created_at should be required (not nullable)."""
        columns = CheckpointRecord.__table__.columns
        assert columns["created_at"].nullable is False

    def test_state_is_not_nullable(self):
        """state should be required (not nullable)."""
        columns = CheckpointRecord.__table__.columns
        assert columns["state"].nullable is False

    def test_state_column_uses_jsonb(self):
        """state column should use JSONB type."""
        columns = CheckpointRecord.__table__.columns
        col_type = str(columns["state"].type)
        assert "JSONB" in col_type.upper() or "JSON" in col_type.upper()

    def test_artifacts_path_is_nullable(self):
        """artifacts_path should be nullable (backtesting has no artifacts)."""
        columns = CheckpointRecord.__table__.columns
        assert columns["artifacts_path"].nullable is True

    def test_state_size_bytes_is_nullable(self):
        """state_size_bytes should be nullable."""
        columns = CheckpointRecord.__table__.columns
        assert columns["state_size_bytes"].nullable is True

    def test_artifacts_size_bytes_is_nullable(self):
        """artifacts_size_bytes should be nullable."""
        columns = CheckpointRecord.__table__.columns
        assert columns["artifacts_size_bytes"].nullable is True

    def test_table_has_indexes(self):
        """Table should have indexes on created_at and checkpoint_type."""
        indexes = list(CheckpointRecord.__table__.indexes)
        index_columns = set()
        for idx in indexes:
            for col in idx.columns:
                index_columns.add(col.name)

        # Check that cleanup-related columns are indexed
        assert "created_at" in index_columns, "Missing index on 'created_at'"
        assert "checkpoint_type" in index_columns, "Missing index on 'checkpoint_type'"

    def test_tablename(self):
        """Table name should be 'operation_checkpoints'."""
        assert CheckpointRecord.__tablename__ == "operation_checkpoints"


class TestCheckpointRecordCreation:
    """Tests for creating CheckpointRecord instances."""

    def test_create_minimal_checkpoint_record(self):
        """Should be able to create a record with minimal required fields."""
        record = CheckpointRecord(
            operation_id="op_test_123",
            checkpoint_type="periodic",
            state={"epoch": 10, "train_loss": 0.5},
        )

        assert record.operation_id == "op_test_123"
        assert record.checkpoint_type == "periodic"
        assert record.state == {"epoch": 10, "train_loss": 0.5}
        assert record.artifacts_path is None

    def test_create_full_checkpoint_record(self):
        """Should be able to create a record with all fields populated."""
        now = datetime.now(timezone.utc)

        record = CheckpointRecord(
            operation_id="op_test_456",
            checkpoint_type="cancellation",
            created_at=now,
            state={
                "epoch": 45,
                "train_loss": 0.28,
                "val_loss": 0.32,
                "train_accuracy": 0.85,
                "val_accuracy": 0.82,
                "learning_rate": 0.001,
                "best_val_loss": 0.30,
                "training_history": {
                    "train_loss": [0.9, 0.7, 0.5, 0.4, 0.28],
                    "val_loss": [0.95, 0.75, 0.55, 0.45, 0.32],
                },
            },
            artifacts_path="/app/data/checkpoints/op_test_456",
            state_size_bytes=1024,
            artifacts_size_bytes=524288000,  # 500MB
        )

        assert record.operation_id == "op_test_456"
        assert record.checkpoint_type == "cancellation"
        assert record.created_at == now
        assert record.state["epoch"] == 45
        assert record.artifacts_path == "/app/data/checkpoints/op_test_456"
        assert record.state_size_bytes == 1024
        assert record.artifacts_size_bytes == 524288000

    def test_checkpoint_types_are_valid_strings(self):
        """Checkpoint types should be string values (periodic, cancellation, failure, shutdown)."""
        valid_types = ["periodic", "cancellation", "failure", "shutdown"]

        for checkpoint_type in valid_types:
            record = CheckpointRecord(
                operation_id=f"op_test_{checkpoint_type}",
                checkpoint_type=checkpoint_type,
                state={"epoch": 10},
            )
            assert record.checkpoint_type == checkpoint_type

    def test_repr(self):
        """repr should return a useful string representation."""
        record = CheckpointRecord(
            operation_id="op_test_repr",
            checkpoint_type="periodic",
            state={"epoch": 10},
        )
        repr_str = repr(record)
        assert "CheckpointRecord" in repr_str
        assert "op_test_repr" in repr_str
        assert "periodic" in repr_str
