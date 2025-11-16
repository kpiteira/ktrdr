-- ================================================================
-- Migration 001: Add Checkpoint Persistence Tables
-- ================================================================
-- Description: Create operations and operation_checkpoints tables
--              for checkpoint persistence system
-- Date: 2025-01-14
-- Author: KTRDR Engineering
-- Dependencies: Migration 000 (TimescaleDB extension)
-- ================================================================

-- ================================================================
-- operations table
-- Stores operation metadata (enhanced from in-memory only)
-- ================================================================
CREATE TABLE IF NOT EXISTS operations (
    -- Primary key
    operation_id TEXT PRIMARY KEY,

    -- Operation classification
    operation_type TEXT NOT NULL,  -- 'training', 'backtesting', etc.
    status TEXT NOT NULL,  -- 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED'

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    last_updated TIMESTAMP WITH TIME ZONE,

    -- Operation data (JSON)
    metadata_json TEXT,  -- OperationMetadata as JSON
    result_summary_json TEXT,  -- Final results (set on completion)

    -- Error tracking
    error_message TEXT
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_operations_status ON operations(status);
CREATE INDEX IF NOT EXISTS idx_operations_type ON operations(operation_type);
CREATE INDEX IF NOT EXISTS idx_operations_created_at ON operations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_operations_status_type ON operations(status, operation_type);

-- ================================================================
-- operation_checkpoints table
-- Stores checkpoint metadata and state (ephemeral)
-- Design: ONE checkpoint per operation (the latest)
-- ================================================================
CREATE TABLE IF NOT EXISTS operation_checkpoints (
    -- Primary key: operation_id (only 1 checkpoint per operation)
    operation_id TEXT PRIMARY KEY,

    -- Checkpoint identification
    checkpoint_id TEXT NOT NULL,  -- For reference/debugging

    -- Checkpoint classification
    checkpoint_type TEXT NOT NULL,  -- 'epoch_snapshot', 'bar_snapshot', 'final'

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Checkpoint data
    checkpoint_metadata_json TEXT,  -- Small queryable metadata (epoch, metrics)
    state_json TEXT NOT NULL,  -- Full checkpoint state (without artifacts)

    -- Artifacts reference
    artifacts_path TEXT,  -- Path to directory with .pt files

    -- Size tracking (for monitoring)
    state_size_bytes BIGINT,
    artifacts_size_bytes BIGINT,

    -- Foreign key constraint (cascade delete)
    FOREIGN KEY (operation_id)
        REFERENCES operations(operation_id)
        ON DELETE CASCADE
);

-- ================================================================
-- Automatic cleanup trigger
-- Delete checkpoint when operation completes
-- ================================================================
CREATE OR REPLACE FUNCTION cleanup_checkpoint_on_completion()
RETURNS TRIGGER AS $$
BEGIN
    -- Only cleanup if status changed to COMPLETED and policy allows
    IF NEW.status = 'COMPLETED'
       AND OLD.status NOT IN ('COMPLETED', 'FAILED', 'CANCELLED') THEN

        -- Note: Actual artifact file deletion handled by application
        -- This just removes DB record (artifacts cleaned up via CheckpointService)
        DELETE FROM operation_checkpoints
        WHERE operation_id = NEW.operation_id;

    END IF;

    -- FAILED and CANCELLED operations keep checkpoint for resume

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop trigger if exists (for re-running migration)
DROP TRIGGER IF EXISTS trigger_cleanup_checkpoint ON operations;

CREATE TRIGGER trigger_cleanup_checkpoint
AFTER UPDATE ON operations
FOR EACH ROW
EXECUTE FUNCTION cleanup_checkpoint_on_completion();

-- ================================================================
-- Record this migration
-- ================================================================
INSERT INTO schema_version (version, description, applied_by)
VALUES (
    1,
    'Add operations and operation_checkpoints tables for checkpoint persistence',
    CURRENT_USER
)
ON CONFLICT (version) DO NOTHING;

-- ================================================================
-- Verification
-- ================================================================
DO $$
DECLARE
    operations_exists BOOLEAN;
    checkpoints_exists BOOLEAN;
    trigger_exists BOOLEAN;
BEGIN
    -- Verify operations table
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'operations'
    ) INTO operations_exists;

    IF NOT operations_exists THEN
        RAISE EXCEPTION 'operations table not created';
    END IF;

    -- Verify operation_checkpoints table
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'operation_checkpoints'
    ) INTO checkpoints_exists;

    IF NOT checkpoints_exists THEN
        RAISE EXCEPTION 'operation_checkpoints table not created';
    END IF;

    -- Verify trigger
    SELECT EXISTS (
        SELECT FROM pg_trigger
        WHERE tgname = 'trigger_cleanup_checkpoint'
    ) INTO trigger_exists;

    IF NOT trigger_exists THEN
        RAISE EXCEPTION 'trigger_cleanup_checkpoint not created';
    END IF;

    RAISE NOTICE 'Checkpoint persistence tables and triggers created successfully';
END $$;
