-- ================================================================
-- Migration 000: Initialize TimescaleDB Extension
-- ================================================================
-- Description: Enable TimescaleDB extension and create schema_version table
-- Date: 2025-01-13
-- Author: KTRDR Engineering
-- ================================================================

-- Enable TimescaleDB extension
-- This provides time-series database capabilities for future features
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create schema_version table to track migrations
-- This table records which migrations have been applied to the database
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    applied_by TEXT NOT NULL
);

-- Record this migration
INSERT INTO schema_version (version, description, applied_by)
VALUES (
    0,
    'Initialize TimescaleDB extension and schema_version table',
    CURRENT_USER
)
ON CONFLICT (version) DO NOTHING;

-- Verify TimescaleDB installation
DO $$
DECLARE
    timescaledb_version TEXT;
BEGIN
    SELECT extversion INTO timescaledb_version
    FROM pg_extension
    WHERE extname = 'timescaledb';

    IF timescaledb_version IS NULL THEN
        RAISE EXCEPTION 'TimescaleDB extension not found. Installation may have failed.';
    ELSE
        RAISE NOTICE 'TimescaleDB version % installed successfully', timescaledb_version;
    END IF;
END $$;
