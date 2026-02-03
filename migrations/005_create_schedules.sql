-- Migration: 005_create_schedules
-- Description: Create schedules table for working hours and add schedule_id to services
-- Date: 2026-02-03
-- Related: US-013 - Add working hours schema

-- Create schedules table for storing working hours definitions
-- Each schedule defines when services are considered "during working hours"
CREATE TABLE IF NOT EXISTS medic.schedules
(
    schedule_id SERIAL,
    name TEXT NOT NULL,
    timezone TEXT NOT NULL,
    hours JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT schedule_id PRIMARY KEY (schedule_id),
    CONSTRAINT schedules_name_unique UNIQUE (name),
    CONSTRAINT schedules_timezone_format CHECK (
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
CREATE INDEX IF NOT EXISTS idx_schedules_name
    ON medic.schedules(name);

-- Add comments to document the table
COMMENT ON TABLE medic.schedules IS
    'Working hours schedules for time-based alert routing';
COMMENT ON COLUMN medic.schedules.name IS
    'Unique schedule name (e.g., "US Business Hours", "EU Support Hours")';
COMMENT ON COLUMN medic.schedules.timezone IS
    'IANA timezone name (e.g., "America/Chicago", "Europe/London", "UTC")';
COMMENT ON COLUMN medic.schedules.hours IS
    'Working hours definition as JSON. Format: {"monday": [{"start": "09:00", "end": "17:00"}], ...}';

-- Add schedule_id column to services table for working hours-based routing
ALTER TABLE services
    ADD COLUMN IF NOT EXISTS schedule_id INTEGER;

-- Add foreign key constraint to services.schedule_id
ALTER TABLE services
    ADD CONSTRAINT services_schedule_id_fk FOREIGN KEY (schedule_id)
        REFERENCES medic.schedules(schedule_id) ON DELETE SET NULL;

-- Create index on services.schedule_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_services_schedule_id ON services(schedule_id);

-- Add comment for the new column
COMMENT ON COLUMN services.schedule_id IS
    'Optional schedule ID for working hours-based alert routing';
