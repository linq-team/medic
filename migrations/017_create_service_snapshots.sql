-- Migration: 017_create_service_snapshots
-- Description: Create service_snapshots table for backup/restore functionality
-- Date: 2026-02-04
-- Linear: SRE-105

-- Service snapshots table stores point-in-time snapshots of service configurations
-- These snapshots are created before destructive actions (deactivate, bulk edit, etc.)
-- and can be used to restore services to their previous state

CREATE TABLE IF NOT EXISTS medic.service_snapshots
(
    snapshot_id SERIAL,
    service_id INTEGER NOT NULL,
    snapshot_data JSONB NOT NULL,
    action_type TEXT NOT NULL,
    actor TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    restored_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT service_snapshots_pkey PRIMARY KEY (snapshot_id),
    CONSTRAINT fk_service_snapshots_service FOREIGN KEY (service_id)
        REFERENCES medic.services(service_id) ON DELETE CASCADE,
    CONSTRAINT service_snapshots_action_type_check CHECK (
        action_type IN (
            'deactivate',
            'activate',
            'mute',
            'unmute',
            'edit',
            'bulk_edit',
            'priority_change',
            'team_change',
            'delete'
        )
    )
)
WITH (OIDS = FALSE);

-- Index for efficient lookups by service_id (most common query pattern)
CREATE INDEX IF NOT EXISTS idx_service_snapshots_service_id
    ON medic.service_snapshots(service_id);

-- Index for efficient date-range queries and sorting by recency
CREATE INDEX IF NOT EXISTS idx_service_snapshots_created_at
    ON medic.service_snapshots(created_at DESC);

-- Composite index for filtering by service and action type
CREATE INDEX IF NOT EXISTS idx_service_snapshots_service_action
    ON medic.service_snapshots(service_id, action_type);

-- Partial index for finding unrestored snapshots (for undo functionality)
CREATE INDEX IF NOT EXISTS idx_service_snapshots_unrestored
    ON medic.service_snapshots(service_id, created_at DESC)
    WHERE restored_at IS NULL;

-- Table and column documentation
COMMENT ON TABLE medic.service_snapshots IS 'Point-in-time snapshots of service configurations for backup/restore functionality';
COMMENT ON COLUMN medic.service_snapshots.snapshot_id IS 'Primary key for the snapshot record';
COMMENT ON COLUMN medic.service_snapshots.service_id IS 'Foreign key to the services table';
COMMENT ON COLUMN medic.service_snapshots.snapshot_data IS 'JSONB containing the complete service state at snapshot time';
COMMENT ON COLUMN medic.service_snapshots.action_type IS 'Type of action that triggered the snapshot (deactivate, edit, etc.)';
COMMENT ON COLUMN medic.service_snapshots.actor IS 'Username or identifier of who performed the action (nullable for system actions)';
COMMENT ON COLUMN medic.service_snapshots.created_at IS 'Timestamp when the snapshot was created';
COMMENT ON COLUMN medic.service_snapshots.restored_at IS 'Timestamp when this snapshot was restored (NULL if never restored)';
