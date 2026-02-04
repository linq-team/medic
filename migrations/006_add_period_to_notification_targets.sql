-- Migration: 006_add_period_to_notification_targets
-- Description: Add period column for working hours-aware alert routing
-- Date: 2026-02-03
-- Related: US-015 - Add working hours to alert routing

-- Add period column to notification_targets table
-- Values: 'always' (default), 'during_hours', 'after_hours'
-- Targets with 'always' are used regardless of working hours
-- Targets with 'during_hours' are only used during working hours
-- Targets with 'after_hours' are only used outside working hours
ALTER TABLE medic.notification_targets
    ADD COLUMN IF NOT EXISTS period TEXT NOT NULL DEFAULT 'always';

-- Add CHECK constraint for valid period values
ALTER TABLE medic.notification_targets
    ADD CONSTRAINT notification_targets_period_check CHECK (
        period IN ('always', 'during_hours', 'after_hours')
    );

-- Create index on period for filtering by working hours period
CREATE INDEX IF NOT EXISTS idx_notification_targets_period
    ON medic.notification_targets(period);

-- Create composite index for common query: enabled targets for a period
CREATE INDEX IF NOT EXISTS idx_notification_targets_service_period
    ON medic.notification_targets(service_id, period) WHERE enabled = TRUE;

-- Add comment to document the column
COMMENT ON COLUMN medic.notification_targets.period IS
    'When this target is active: always, during_hours, or after_hours';
