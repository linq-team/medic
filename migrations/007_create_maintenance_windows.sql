-- Migration: 007_create_maintenance_windows
-- Description: Create maintenance_windows table for scheduled maintenance periods
-- Date: 2026-02-03
-- Related: US-016 - Add maintenance windows schema

-- Create maintenance_windows table for storing maintenance window definitions
-- Maintenance windows suppress alerts for affected services during the defined period
CREATE TABLE IF NOT EXISTS medic.maintenance_windows
(
    window_id SERIAL,
    name TEXT NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    recurrence TEXT,  -- Cron expression for recurring windows (nullable for one-time)
    timezone TEXT NOT NULL DEFAULT 'UTC',
    service_ids INTEGER[] NOT NULL DEFAULT '{}',  -- Empty array means all services
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT maintenance_windows_pkey PRIMARY KEY (window_id),
    CONSTRAINT maintenance_windows_name_unique UNIQUE (name),
    CONSTRAINT maintenance_windows_end_after_start CHECK (end_time > start_time),
    CONSTRAINT maintenance_windows_timezone_format CHECK (
        -- Basic IANA timezone format check (Area/Location pattern)
        timezone ~ '^[A-Z][a-zA-Z0-9_]+/[A-Za-z0-9_/+-]+$'
        OR timezone = 'UTC'
        OR timezone ~ '^Etc/'
    )
)
WITH (
    OIDS = FALSE
);

-- Create index on name for lookups
CREATE INDEX IF NOT EXISTS idx_maintenance_windows_name
    ON medic.maintenance_windows(name);

-- Create index on start_time and end_time for finding active windows
CREATE INDEX IF NOT EXISTS idx_maintenance_windows_time_range
    ON medic.maintenance_windows(start_time, end_time);

-- Create GIN index on service_ids for efficient array containment queries
CREATE INDEX IF NOT EXISTS idx_maintenance_windows_service_ids
    ON medic.maintenance_windows USING GIN (service_ids);

-- Create index on recurrence to quickly filter recurring vs one-time windows
CREATE INDEX IF NOT EXISTS idx_maintenance_windows_recurrence
    ON medic.maintenance_windows(recurrence) WHERE recurrence IS NOT NULL;

-- Add comments to document the table
COMMENT ON TABLE medic.maintenance_windows IS
    'Scheduled maintenance windows that suppress alerts for affected services';
COMMENT ON COLUMN medic.maintenance_windows.name IS
    'Unique name for the maintenance window (e.g., "Weekly DB Maintenance", "Q1 Infrastructure Update")';
COMMENT ON COLUMN medic.maintenance_windows.start_time IS
    'Start time of the maintenance window (UTC stored, timezone-aware)';
COMMENT ON COLUMN medic.maintenance_windows.end_time IS
    'End time of the maintenance window (UTC stored, timezone-aware)';
COMMENT ON COLUMN medic.maintenance_windows.recurrence IS
    'Cron expression for recurring windows (e.g., "0 2 * * 0" for every Sunday at 2am). NULL for one-time windows';
COMMENT ON COLUMN medic.maintenance_windows.timezone IS
    'IANA timezone name for interpreting recurrence (e.g., "America/Chicago", "UTC")';
COMMENT ON COLUMN medic.maintenance_windows.service_ids IS
    'Array of service IDs affected by this window. Empty array means ALL services';
COMMENT ON COLUMN medic.maintenance_windows.created_at IS
    'Timestamp when this maintenance window was created';
COMMENT ON COLUMN medic.maintenance_windows.updated_at IS
    'Timestamp when this maintenance window was last updated';
