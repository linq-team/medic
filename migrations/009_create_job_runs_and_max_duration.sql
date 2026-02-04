-- Migration: 009_create_job_runs_and_max_duration
-- Description: Create job_runs table for duration tracking and add max_duration to services
-- Date: 2026-02-03
-- Related: US-021 - Add duration tracking to services
-- Linear: SRE-16 - Duration Tracking & Alerts

-- Create job_runs table to track duration statistics for each job run
-- This table stores correlated STARTED/COMPLETED events with calculated duration
CREATE TABLE IF NOT EXISTS medic.job_runs
(
    run_id_pk SERIAL,
    service_id INTEGER NOT NULL,
    run_id TEXT NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,
    status TEXT NOT NULL DEFAULT 'STARTED',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT job_runs_pk PRIMARY KEY (run_id_pk),
    CONSTRAINT job_runs_service_fk FOREIGN KEY (service_id)
        REFERENCES services(service_id) ON DELETE CASCADE,
    CONSTRAINT job_runs_status_check CHECK (
        status IN ('STARTED', 'COMPLETED', 'FAILED')
    )
)
WITH (
    OIDS = FALSE
);

-- Create unique constraint on service_id + run_id to prevent duplicate runs
-- Same run_id can exist for different services
CREATE UNIQUE INDEX IF NOT EXISTS idx_job_runs_service_run_id
    ON medic.job_runs(service_id, run_id);

-- Create index for querying runs by service (common for stats calculation)
CREATE INDEX IF NOT EXISTS idx_job_runs_service_id
    ON medic.job_runs(service_id);

-- Create index for querying completed runs by service (for duration stats)
CREATE INDEX IF NOT EXISTS idx_job_runs_service_completed
    ON medic.job_runs(service_id, completed_at DESC)
    WHERE completed_at IS NOT NULL;

-- Create index for finding stale runs (STARTED but not completed)
CREATE INDEX IF NOT EXISTS idx_job_runs_started_only
    ON medic.job_runs(service_id, started_at)
    WHERE completed_at IS NULL AND status = 'STARTED';

-- Add comments to document the table
COMMENT ON TABLE medic.job_runs IS
    'Tracks job runs for duration statistics and timeout detection';
COMMENT ON COLUMN medic.job_runs.run_id_pk IS
    'Auto-increment primary key for the job run record';
COMMENT ON COLUMN medic.job_runs.service_id IS
    'Service that this job run belongs to';
COMMENT ON COLUMN medic.job_runs.run_id IS
    'Client-provided run identifier for correlating start/complete events';
COMMENT ON COLUMN medic.job_runs.started_at IS
    'Timestamp when the job started (from STARTED signal)';
COMMENT ON COLUMN medic.job_runs.completed_at IS
    'Timestamp when the job finished (from COMPLETED/FAILED signal), NULL if still running';
COMMENT ON COLUMN medic.job_runs.duration_ms IS
    'Calculated duration in milliseconds (completed_at - started_at), NULL if still running';
COMMENT ON COLUMN medic.job_runs.status IS
    'Final status: STARTED (running), COMPLETED (success), FAILED (error)';

-- Add max_duration column to services table
-- This defines the threshold for duration-based alerts
ALTER TABLE services
    ADD COLUMN IF NOT EXISTS max_duration_ms INTEGER;

-- Add comment for the new column
COMMENT ON COLUMN services.max_duration_ms IS
    'Maximum expected job duration in milliseconds. Alert if COMPLETED duration exceeds this or STARTED job runs longer than this without completing';
