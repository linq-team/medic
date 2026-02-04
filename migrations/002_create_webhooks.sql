-- Migration: 002_create_webhooks
-- Description: Create webhooks and webhook_deliveries tables for webhook notifications
-- Date: 2026-02-03

-- Create webhooks table for storing webhook configurations
-- service_id is nullable to support global webhooks (applied to all services)
CREATE TABLE IF NOT EXISTS medic.webhooks
(
    webhook_id SERIAL,
    service_id INTEGER,
    url TEXT NOT NULL,
    headers JSONB NOT NULL DEFAULT '{}'::JSONB,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT webhook_id PRIMARY KEY (webhook_id),
    CONSTRAINT webhooks_service_id_fk FOREIGN KEY (service_id)
        REFERENCES services(service_id) ON DELETE CASCADE,
    CONSTRAINT webhooks_url_valid CHECK (url ~ '^https?://')
)
WITH (
    OIDS = FALSE
);

-- Create index on service_id for faster lookups when finding webhooks for a service
CREATE INDEX IF NOT EXISTS idx_webhooks_service_id ON medic.webhooks(service_id);

-- Create index on enabled for filtering active webhooks
CREATE INDEX IF NOT EXISTS idx_webhooks_enabled ON medic.webhooks(enabled) WHERE enabled = TRUE;

-- Add comments to document the table
COMMENT ON TABLE medic.webhooks IS 'Webhook configurations for sending notifications to external services';
COMMENT ON COLUMN medic.webhooks.service_id IS 'Optional service ID - NULL means global webhook applied to all services';
COMMENT ON COLUMN medic.webhooks.url IS 'Webhook URL endpoint (must be HTTP or HTTPS)';
COMMENT ON COLUMN medic.webhooks.headers IS 'Custom HTTP headers to include in webhook requests as JSON object';
COMMENT ON COLUMN medic.webhooks.enabled IS 'Whether this webhook is active';

-- Create webhook_deliveries table for tracking webhook delivery attempts
CREATE TABLE IF NOT EXISTS medic.webhook_deliveries
(
    delivery_id SERIAL,
    webhook_id INTEGER NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    response_code INTEGER,
    response_body TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT delivery_id PRIMARY KEY (delivery_id),
    CONSTRAINT webhook_deliveries_webhook_id_fk FOREIGN KEY (webhook_id)
        REFERENCES medic.webhooks(webhook_id) ON DELETE CASCADE,
    CONSTRAINT webhook_deliveries_status_check CHECK (
        status IN ('pending', 'success', 'failed', 'retrying')
    )
)
WITH (
    OIDS = FALSE
);

-- Create index on webhook_id for faster lookups when finding deliveries for a webhook
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_webhook_id ON medic.webhook_deliveries(webhook_id);

-- Create index on status for filtering pending/retrying deliveries
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_status ON medic.webhook_deliveries(status)
    WHERE status IN ('pending', 'retrying');

-- Create index on created_at for time-based queries and cleanup
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_created_at ON medic.webhook_deliveries(created_at);

-- Add comments to document the table
COMMENT ON TABLE medic.webhook_deliveries IS 'Tracks webhook delivery attempts and their results';
COMMENT ON COLUMN medic.webhook_deliveries.webhook_id IS 'Reference to the webhook configuration';
COMMENT ON COLUMN medic.webhook_deliveries.payload IS 'JSON payload sent to the webhook';
COMMENT ON COLUMN medic.webhook_deliveries.status IS 'Delivery status: pending, success, failed, retrying';
COMMENT ON COLUMN medic.webhook_deliveries.attempts IS 'Number of delivery attempts made';
COMMENT ON COLUMN medic.webhook_deliveries.last_attempt_at IS 'Timestamp of the last delivery attempt';
COMMENT ON COLUMN medic.webhook_deliveries.response_code IS 'HTTP response code from the last attempt';
COMMENT ON COLUMN medic.webhook_deliveries.response_body IS 'Response body from the last attempt (truncated if large)';
