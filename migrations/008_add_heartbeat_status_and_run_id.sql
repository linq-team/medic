-- Migration: 008_add_heartbeat_status_and_run_id
-- Description: Add STARTED/COMPLETED/FAILED status values and run_id column for job tracking
-- Date: 2026-02-03
-- Related: US-019 - Add start/complete signal statuses
-- Linear: SRE-15 - Start/Complete Signals

-- Add run_id column to heartbeatEvents table
-- This allows correlating STARTED and COMPLETED/FAILED events for the same job run
-- Nullable because existing heartbeats and simple "UP" heartbeats don't need run correlation
ALTER TABLE "heartbeatEvents"
    ADD COLUMN IF NOT EXISTS run_id TEXT;

-- Create index on run_id for efficient lookups when correlating start/complete events
-- Partial index only on non-null values since most heartbeats won't have run_id
CREATE INDEX IF NOT EXISTS idx_heartbeat_events_run_id
    ON "heartbeatEvents"(run_id) WHERE run_id IS NOT NULL;

-- Create composite index for common query: finding runs by service and run_id
CREATE INDEX IF NOT EXISTS idx_heartbeat_events_service_run_id
    ON "heartbeatEvents"(service_id, run_id) WHERE run_id IS NOT NULL;

-- Add comment to document the column
COMMENT ON COLUMN "heartbeatEvents".run_id IS
    'Optional identifier to correlate STARTED/COMPLETED/FAILED events for the same job run';

-- Note: The status column already exists and accepts TEXT values
-- New status values (STARTED, COMPLETED, FAILED) will be enforced at application level
-- rather than database level to maintain backwards compatibility with existing integrations
-- Valid status values: UP, DOWN, STARTED, COMPLETED, FAILED
COMMENT ON COLUMN "heartbeatEvents".status IS
    'Heartbeat status: UP (alive), DOWN (dead), STARTED (job began), COMPLETED (job finished), FAILED (job error)';
