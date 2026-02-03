-- Migration: 011_create_playbooks
-- Description: Create playbooks and playbook_triggers tables for auto-remediation
-- Date: 2026-02-03
-- Related: US-025 - Add playbooks database schema, Linear: SRE-18

-- Create playbooks table for storing playbook definitions
-- Playbooks define remediation steps that can be executed automatically or manually
CREATE TABLE IF NOT EXISTS medic.playbooks
(
    playbook_id SERIAL,
    name TEXT NOT NULL,
    description TEXT,
    yaml_content TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT playbooks_pkey PRIMARY KEY (playbook_id),
    CONSTRAINT playbooks_name_unique UNIQUE (name),
    CONSTRAINT playbooks_version_positive CHECK (version > 0)
)
WITH (
    OIDS = FALSE
);

-- Create index on name for lookups
CREATE INDEX IF NOT EXISTS idx_playbooks_name
    ON medic.playbooks(name);

-- Create index on updated_at for sorting by most recently modified
CREATE INDEX IF NOT EXISTS idx_playbooks_updated_at
    ON medic.playbooks(updated_at DESC);

-- Create playbook_triggers table for storing trigger conditions
-- Triggers define when a playbook should be executed based on service patterns and failure counts
CREATE TABLE IF NOT EXISTS medic.playbook_triggers
(
    trigger_id SERIAL,
    playbook_id INTEGER NOT NULL,
    service_pattern TEXT NOT NULL,
    consecutive_failures INTEGER NOT NULL DEFAULT 1,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT playbook_triggers_pkey PRIMARY KEY (trigger_id),
    CONSTRAINT playbook_triggers_playbook_fk FOREIGN KEY (playbook_id)
        REFERENCES medic.playbooks(playbook_id) ON DELETE CASCADE,
    CONSTRAINT playbook_triggers_consecutive_failures_positive CHECK (
        consecutive_failures > 0
    )
)
WITH (
    OIDS = FALSE
);

-- Create index on playbook_id for joining with playbooks
CREATE INDEX IF NOT EXISTS idx_playbook_triggers_playbook_id
    ON medic.playbook_triggers(playbook_id);

-- Create index on service_pattern for trigger matching
CREATE INDEX IF NOT EXISTS idx_playbook_triggers_service_pattern
    ON medic.playbook_triggers(service_pattern);

-- Create index on enabled for filtering active triggers
CREATE INDEX IF NOT EXISTS idx_playbook_triggers_enabled
    ON medic.playbook_triggers(enabled) WHERE enabled = TRUE;

-- Create composite index for efficient trigger matching queries
CREATE INDEX IF NOT EXISTS idx_playbook_triggers_matching
    ON medic.playbook_triggers(enabled, service_pattern, consecutive_failures)
    WHERE enabled = TRUE;

-- Add comments to document the tables
COMMENT ON TABLE medic.playbooks IS
    'Playbook definitions for auto-remediation. Contains YAML content defining remediation steps.';
COMMENT ON COLUMN medic.playbooks.name IS
    'Unique name for the playbook (e.g., "restart-worker", "scale-up-pods")';
COMMENT ON COLUMN medic.playbooks.description IS
    'Human-readable description of what this playbook does';
COMMENT ON COLUMN medic.playbooks.yaml_content IS
    'YAML content defining the playbook steps (webhook, script, wait, condition)';
COMMENT ON COLUMN medic.playbooks.version IS
    'Version number, incremented on each update for audit trail';
COMMENT ON COLUMN medic.playbooks.created_at IS
    'Timestamp when this playbook was created';
COMMENT ON COLUMN medic.playbooks.updated_at IS
    'Timestamp when this playbook was last updated';

COMMENT ON TABLE medic.playbook_triggers IS
    'Trigger conditions that determine when a playbook should be executed';
COMMENT ON COLUMN medic.playbook_triggers.playbook_id IS
    'Foreign key to the playbook to execute when trigger conditions are met';
COMMENT ON COLUMN medic.playbook_triggers.service_pattern IS
    'Glob pattern to match service names (e.g., "worker-*", "api-prod-*", "*")';
COMMENT ON COLUMN medic.playbook_triggers.consecutive_failures IS
    'Number of consecutive heartbeat failures required before triggering (minimum 1)';
COMMENT ON COLUMN medic.playbook_triggers.enabled IS
    'Whether this trigger is active. Disabled triggers are skipped during matching.';
COMMENT ON COLUMN medic.playbook_triggers.created_at IS
    'Timestamp when this trigger was created';
COMMENT ON COLUMN medic.playbook_triggers.updated_at IS
    'Timestamp when this trigger was last updated';
