-- Migration: 010_add_grace_period_to_services
-- Description: Add grace_period_seconds column to services for delayed alerting
-- Date: 2026-02-03
-- Related: US-024 - Add grace periods to services
-- Linear: SRE-17 - Grace Periods & Flexible Schedules

-- Add grace_period_seconds column to services table
-- This defines the time to wait after a missed heartbeat before triggering an alert
-- Default is 0 (no grace period - alert immediately on missed heartbeat)
ALTER TABLE services
    ADD COLUMN IF NOT EXISTS grace_period_seconds INTEGER DEFAULT 0;

-- Add check constraint to ensure grace period is non-negative
ALTER TABLE services
    ADD CONSTRAINT services_grace_period_check CHECK (
        grace_period_seconds IS NULL OR grace_period_seconds >= 0
    );

-- Add comment for the new column
COMMENT ON COLUMN services.grace_period_seconds IS
    'Grace period in seconds to wait after expected heartbeat before alerting. 0 or NULL means alert immediately.';
