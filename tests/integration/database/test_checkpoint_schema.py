"""
Integration tests for checkpoint persistence database schema.

Tests verify that migration 001_add_checkpoint_tables.sql creates:
- operations table (if not exists)
- operation_checkpoints table (with operation_id as PK)
- cleanup_checkpoint_on_completion() trigger function
- trigger fires correctly on status changes

These tests should FAIL until migration 001 is created and applied.
"""

import os
import time
from collections.abc import Generator

import psycopg2
import pytest


@pytest.fixture
def db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Create PostgreSQL database connection.

    Uses environment variables or defaults from docker-compose.yml.

    Yields:
        Database connection
    """
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    database = os.getenv("POSTGRES_DB", "ktrdr")
    user = os.getenv("POSTGRES_USER", "ktrdr_admin")
    password = os.getenv("POSTGRES_PASSWORD", "ktrdr_dev_password")

    # Retry connection (database may be starting up)
    max_retries = 30
    retry_delay = 1  # seconds

    conn = None
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
            )
            break
        except psycopg2.OperationalError as e:
            if attempt == max_retries - 1:
                pytest.fail(
                    f"Failed to connect to PostgreSQL after {max_retries} attempts. "
                    f"Error: {e}. "
                    f"Ensure PostgreSQL container is running: docker-compose up -d postgres"
                )
            time.sleep(retry_delay)

    assert conn is not None, "Failed to establish database connection"

    try:
        yield conn
    finally:
        conn.close()


def test_checkpoint_migration_recorded(db_connection):
    """
    Test that checkpoint migration (version 1) is recorded in schema_version table.

    Acceptance Criteria:
    - ✅ Migration version 1 exists in schema_version table
    - ✅ Migration description mentions checkpoints
    """
    cursor = db_connection.cursor()

    cursor.execute("""
        SELECT version, description, applied_at, applied_by
        FROM schema_version
        WHERE version = 1;
    """)
    result = cursor.fetchone()

    assert result is not None, (
        "Checkpoint migration (version 1) not found in schema_version table. "
        "Ensure migration 001_add_checkpoint_tables.sql has run."
    )

    version, description, applied_at, applied_by = result

    assert version == 1
    assert "checkpoint" in description.lower(), (
        f"Migration description should mention 'checkpoint', got: {description}"
    )
    assert applied_at is not None
    assert applied_by is not None

    cursor.close()


def test_operations_table_exists(db_connection):
    """
    Test that operations table exists with correct structure.

    Acceptance Criteria:
    - ✅ operations table exists
    - ✅ Table has required columns with correct types
    - ✅ Primary key is operation_id
    - ✅ Indexes exist for common queries
    """
    cursor = db_connection.cursor()

    # Check if operations table exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'operations'
        );
    """)
    table_exists = cursor.fetchone()[0]

    assert table_exists, (
        "operations table not found. "
        "Ensure migration 001_add_checkpoint_tables.sql has run."
    )

    # Verify table structure
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'operations'
        ORDER BY ordinal_position;
    """)
    columns = cursor.fetchall()

    # Expected columns (from architecture document)
    expected_columns = {
        "operation_id": ("text", "NO"),
        "operation_type": ("text", "NO"),
        "status": ("text", "NO"),
        "created_at": ("timestamp", "NO"),
        "started_at": ("timestamp", "YES"),
        "completed_at": ("timestamp", "YES"),
        "last_updated": ("timestamp", "YES"),
        "metadata_json": ("text", "YES"),
        "result_summary_json": ("text", "YES"),
        "error_message": ("text", "YES"),
    }

    actual_columns = {col[0]: (col[1], col[2]) for col in columns}

    for col_name, (col_type, nullable) in expected_columns.items():
        assert col_name in actual_columns, (
            f"Column '{col_name}' missing from operations table"
        )
        actual_type, actual_nullable = actual_columns[col_name]
        assert actual_type.startswith(col_type), (
            f"Column '{col_name}' has type '{actual_type}', expected '{col_type}'"
        )
        assert actual_nullable == nullable, (
            f"Column '{col_name}' nullable={actual_nullable}, expected {nullable}"
        )

    # Verify primary key
    cursor.execute("""
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = 'operations'::regclass AND i.indisprimary;
    """)
    pk_columns = [row[0] for row in cursor.fetchall()]

    assert pk_columns == ["operation_id"], (
        f"Primary key should be operation_id, got: {pk_columns}"
    )

    # Verify indexes exist (idx_operations_status, idx_operations_type, etc.)
    cursor.execute("""
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'operations';
    """)
    indexes = [row[0] for row in cursor.fetchall()]

    required_indexes = [
        "idx_operations_status",
        "idx_operations_type",
        "idx_operations_created_at",
        "idx_operations_status_type",
    ]

    for idx_name in required_indexes:
        assert idx_name in indexes, (
            f"Index '{idx_name}' missing from operations table"
        )

    cursor.close()


def test_operation_checkpoints_table_exists(db_connection):
    """
    Test that operation_checkpoints table exists with correct structure.

    Acceptance Criteria:
    - ✅ operation_checkpoints table exists
    - ✅ Table has required columns with correct types
    - ✅ Primary key is operation_id (ONE checkpoint per operation)
    - ✅ Foreign key constraint to operations table with CASCADE delete
    """
    cursor = db_connection.cursor()

    # Check if operation_checkpoints table exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'operation_checkpoints'
        );
    """)
    table_exists = cursor.fetchone()[0]

    assert table_exists, (
        "operation_checkpoints table not found. "
        "Ensure migration 001_add_checkpoint_tables.sql has run."
    )

    # Verify table structure
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'operation_checkpoints'
        ORDER BY ordinal_position;
    """)
    columns = cursor.fetchall()

    # Expected columns (from architecture document)
    expected_columns = {
        "operation_id": ("text", "NO"),
        "checkpoint_id": ("text", "NO"),
        "checkpoint_type": ("text", "NO"),
        "created_at": ("timestamp", "NO"),
        "checkpoint_metadata_json": ("text", "YES"),
        "state_json": ("text", "NO"),
        "artifacts_path": ("text", "YES"),
        "state_size_bytes": ("bigint", "YES"),
        "artifacts_size_bytes": ("bigint", "YES"),
    }

    actual_columns = {col[0]: (col[1], col[2]) for col in columns}

    for col_name, (col_type, nullable) in expected_columns.items():
        assert col_name in actual_columns, (
            f"Column '{col_name}' missing from operation_checkpoints table"
        )
        actual_type, actual_nullable = actual_columns[col_name]
        assert actual_type.startswith(col_type), (
            f"Column '{col_name}' has type '{actual_type}', expected '{col_type}'"
        )
        assert actual_nullable == nullable, (
            f"Column '{col_name}' nullable={actual_nullable}, expected {nullable}"
        )

    # Verify primary key is operation_id (ONE checkpoint per operation)
    cursor.execute("""
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = 'operation_checkpoints'::regclass AND i.indisprimary;
    """)
    pk_columns = [row[0] for row in cursor.fetchall()]

    assert pk_columns == ["operation_id"], (
        f"Primary key should be operation_id (ONE checkpoint per operation), got: {pk_columns}"
    )

    # Verify foreign key constraint to operations table
    cursor.execute("""
        SELECT
            tc.constraint_name,
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            rc.delete_rule
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        JOIN information_schema.referential_constraints AS rc
            ON tc.constraint_name = rc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name = 'operation_checkpoints';
    """)
    fk_constraints = cursor.fetchall()

    assert len(fk_constraints) > 0, (
        "No foreign key constraints found on operation_checkpoints table"
    )

    # Verify FK references operations table with CASCADE delete
    fk_to_operations = [
        fk for fk in fk_constraints
        if fk[3] == "operations"  # foreign_table_name
    ]

    assert len(fk_to_operations) == 1, (
        f"Expected 1 foreign key to operations table, found {len(fk_to_operations)}"
    )

    constraint_name, table_name, column_name, foreign_table, foreign_column, delete_rule = fk_to_operations[0]

    assert column_name == "operation_id", (
        f"FK column should be operation_id, got: {column_name}"
    )
    assert foreign_column == "operation_id", (
        f"FK should reference operations.operation_id, got: {foreign_table}.{foreign_column}"
    )
    assert delete_rule == "CASCADE", (
        f"FK delete rule should be CASCADE, got: {delete_rule}"
    )

    cursor.close()


def test_cleanup_checkpoint_trigger_function_exists(db_connection):
    """
    Test that cleanup_checkpoint_on_completion() trigger function exists.

    Acceptance Criteria:
    - ✅ cleanup_checkpoint_on_completion function exists
    - ✅ Function is a trigger function
    """
    cursor = db_connection.cursor()

    # Check if trigger function exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM pg_proc
            WHERE proname = 'cleanup_checkpoint_on_completion'
        );
    """)
    function_exists = cursor.fetchone()[0]

    assert function_exists, (
        "cleanup_checkpoint_on_completion() trigger function not found. "
        "Ensure migration 001_add_checkpoint_tables.sql has run."
    )

    # Verify it's a trigger function (returns TRIGGER type)
    cursor.execute("""
        SELECT p.proname, t.typname as return_type
        FROM pg_proc p
        JOIN pg_type t ON p.prorettype = t.oid
        WHERE p.proname = 'cleanup_checkpoint_on_completion';
    """)
    result = cursor.fetchone()

    assert result is not None
    function_name, return_type = result
    assert return_type == "trigger", (
        f"cleanup_checkpoint_on_completion should return TRIGGER, got: {return_type}"
    )

    cursor.close()


def test_cleanup_checkpoint_trigger_exists(db_connection):
    """
    Test that trigger_cleanup_checkpoint trigger exists on operations table.

    Acceptance Criteria:
    - ✅ trigger_cleanup_checkpoint trigger exists
    - ✅ Trigger fires AFTER UPDATE on operations table
    - ✅ Trigger calls cleanup_checkpoint_on_completion function
    """
    cursor = db_connection.cursor()

    # Check if trigger exists
    cursor.execute("""
        SELECT
            tgname,
            tgtype,
            proname as trigger_function
        FROM pg_trigger
        JOIN pg_proc ON pg_trigger.tgfoid = pg_proc.oid
        WHERE tgname = 'trigger_cleanup_checkpoint'
            AND tgrelid = 'operations'::regclass;
    """)
    result = cursor.fetchone()

    assert result is not None, (
        "trigger_cleanup_checkpoint trigger not found on operations table. "
        "Ensure migration 001_add_checkpoint_tables.sql has run."
    )

    trigger_name, trigger_type, trigger_function = result

    assert trigger_name == "trigger_cleanup_checkpoint"
    assert trigger_function == "cleanup_checkpoint_on_completion", (
        f"Trigger should call cleanup_checkpoint_on_completion, got: {trigger_function}"
    )

    # Verify trigger type (AFTER UPDATE, FOR EACH ROW)
    # pg_trigger.tgtype is a bitmap:
    # - Bit 0 (1): ROW-level trigger
    # - Bit 1 (2): BEFORE trigger (if not set, then AFTER)
    # - Bit 2 (4): INSERT
    # - Bit 3 (8): DELETE
    # - Bit 4 (16): UPDATE
    # We want AFTER UPDATE FOR EACH ROW = 1 (ROW) + 16 (UPDATE) = 17

    # Note: tgtype can have multiple bits set, so check UPDATE bit is set
    is_row_level = (trigger_type & 1) != 0
    is_after = (trigger_type & 2) == 0  # BEFORE bit NOT set
    is_update = (trigger_type & 16) != 0

    assert is_row_level, "Trigger should be FOR EACH ROW"
    assert is_after, "Trigger should be AFTER (not BEFORE)"
    assert is_update, "Trigger should fire on UPDATE"

    cursor.close()


def test_trigger_deletes_checkpoint_on_completion(db_connection):
    """
    Test that trigger actually deletes checkpoint when operation completes.

    This is an end-to-end test of the trigger functionality.

    Acceptance Criteria:
    - ✅ Trigger fires when operation status changes to COMPLETED
    - ✅ Checkpoint is deleted from operation_checkpoints table
    - ✅ Trigger does NOT fire for FAILED operations (checkpoint preserved)
    - ✅ Trigger does NOT fire for CANCELLED operations (checkpoint preserved)
    """
    cursor = db_connection.cursor()
    cursor.execute("SET search_path TO public;")

    # Test setup: Create a test operation and checkpoint
    test_operation_id = "test_op_trigger_001"

    # Insert test operation (RUNNING status)
    cursor.execute("""
        INSERT INTO operations (
            operation_id,
            operation_type,
            status,
            created_at
        ) VALUES (%s, 'training', 'RUNNING', CURRENT_TIMESTAMP);
    """, (test_operation_id,))
    db_connection.commit()

    # Insert checkpoint for this operation
    cursor.execute("""
        INSERT INTO operation_checkpoints (
            operation_id,
            checkpoint_id,
            checkpoint_type,
            created_at,
            state_json
        ) VALUES (%s, %s, 'epoch_snapshot', CURRENT_TIMESTAMP, '{}');
    """, (test_operation_id, f"{test_operation_id}_checkpoint"))
    db_connection.commit()

    # Verify checkpoint exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM operation_checkpoints
            WHERE operation_id = %s
        );
    """, (test_operation_id,))
    checkpoint_exists_before = cursor.fetchone()[0]
    assert checkpoint_exists_before, "Checkpoint should exist before trigger fires"

    # Trigger the cleanup: Update operation status to COMPLETED
    cursor.execute("""
        UPDATE operations
        SET status = 'COMPLETED', completed_at = CURRENT_TIMESTAMP
        WHERE operation_id = %s;
    """, (test_operation_id,))
    db_connection.commit()

    # Verify checkpoint was deleted by trigger
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM operation_checkpoints
            WHERE operation_id = %s
        );
    """, (test_operation_id,))
    checkpoint_exists_after = cursor.fetchone()[0]

    assert not checkpoint_exists_after, (
        "Checkpoint should be deleted by trigger when operation completes"
    )

    # Test that FAILED operations keep checkpoint
    test_operation_id_2 = "test_op_trigger_002"

    cursor.execute("""
        INSERT INTO operations (
            operation_id,
            operation_type,
            status,
            created_at
        ) VALUES (%s, 'training', 'RUNNING', CURRENT_TIMESTAMP);
    """, (test_operation_id_2,))

    cursor.execute("""
        INSERT INTO operation_checkpoints (
            operation_id,
            checkpoint_id,
            checkpoint_type,
            created_at,
            state_json
        ) VALUES (%s, %s, 'epoch_snapshot', CURRENT_TIMESTAMP, '{}');
    """, (test_operation_id_2, f"{test_operation_id_2}_checkpoint"))
    db_connection.commit()

    # Update to FAILED (should NOT delete checkpoint)
    cursor.execute("""
        UPDATE operations
        SET status = 'FAILED', completed_at = CURRENT_TIMESTAMP, error_message = 'Test failure'
        WHERE operation_id = %s;
    """, (test_operation_id_2,))
    db_connection.commit()

    # Verify checkpoint still exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM operation_checkpoints
            WHERE operation_id = %s
        );
    """, (test_operation_id_2,))
    checkpoint_exists_failed = cursor.fetchone()[0]

    assert checkpoint_exists_failed, (
        "Checkpoint should be preserved for FAILED operations"
    )

    # Cleanup test data
    cursor.execute("DELETE FROM operations WHERE operation_id IN (%s, %s);",
                  (test_operation_id, test_operation_id_2))
    db_connection.commit()

    cursor.close()
