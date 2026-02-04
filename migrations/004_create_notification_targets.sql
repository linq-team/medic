-- Migration: 004_create_notification_targets
-- Description: Create notification_targets table for flexible alert routing
-- Date: 2026-02-03
-- Related: US-011 - Add notification targets schema

-- Create notification_targets table for storing multiple notification targets per service
-- Each service can have multiple targets with different types (slack, pagerduty, webhook)
CREATE TABLE IF NOT EXISTS medic.notification_targets
(
    target_id SERIAL,
    service_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    config JSONB NOT NULL DEFAULT '{}'::JSONB,
    priority INTEGER NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT target_id PRIMARY KEY (target_id),
    CONSTRAINT notification_targets_service_id_fk FOREIGN KEY (service_id)
        REFERENCES services(service_id) ON DELETE CASCADE,
    CONSTRAINT notification_targets_type_check CHECK (
        type IN ('slack', 'pagerduty', 'webhook')
    )
)
WITH (
    OIDS = FALSE
);

-- Create index on service_id for faster lookups when finding targets for a service
CREATE INDEX IF NOT EXISTS idx_notification_targets_service_id
    ON medic.notification_targets(service_id);

-- Create index on enabled for filtering active targets
CREATE INDEX IF NOT EXISTS idx_notification_targets_enabled
    ON medic.notification_targets(enabled) WHERE enabled = TRUE;

-- Create index on type for filtering by notification type
CREATE INDEX IF NOT EXISTS idx_notification_targets_type
    ON medic.notification_targets(type);

-- Create composite index for common query pattern: enabled targets ordered by priority
CREATE INDEX IF NOT EXISTS idx_notification_targets_service_priority
    ON medic.notification_targets(service_id, priority) WHERE enabled = TRUE;

-- Add comments to document the table
COMMENT ON TABLE medic.notification_targets IS
    'Notification targets for flexible alert routing per service';
COMMENT ON COLUMN medic.notification_targets.service_id IS
    'Service ID this target belongs to';
COMMENT ON COLUMN medic.notification_targets.type IS
    'Notification type: slack, pagerduty, or webhook';
COMMENT ON COLUMN medic.notification_targets.config IS
    'Type-specific configuration as JSON (e.g., channel_id for slack, service_key for pagerduty, url/headers for webhook)';
COMMENT ON COLUMN medic.notification_targets.priority IS
    'Priority for ordering targets (lower = higher priority, used in notify_until_success mode)';
COMMENT ON COLUMN medic.notification_targets.enabled IS
    'Whether this target is active';
