-- Migration: 016_create_secrets
-- Description: Create secrets table for storing encrypted secrets used in playbooks
-- Date: 2026-02-03
-- Related: US-044 - Add secrets encryption for playbooks

-- Create secrets table for storing encrypted secrets
-- Secrets are encrypted using AES-256-GCM with a server-side key
-- Decryption only happens at playbook execution time
CREATE TABLE IF NOT EXISTS medic.secrets
(
    secret_id SERIAL,
    name TEXT NOT NULL,
    encrypted_value BYTEA NOT NULL,
    nonce BYTEA NOT NULL,
    tag BYTEA NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by TEXT,
    CONSTRAINT secrets_pkey PRIMARY KEY (secret_id),
    CONSTRAINT secrets_name_unique UNIQUE (name),
    CONSTRAINT secrets_name_format CHECK (
        name ~ '^[A-Za-z_][A-Za-z0-9_]*$'
    ),
    CONSTRAINT secrets_nonce_length CHECK (LENGTH(nonce) = 12),
    CONSTRAINT secrets_tag_length CHECK (LENGTH(tag) = 16)
)
WITH (
    OIDS = FALSE
);

-- Create index on name for fast lookups by secret name
CREATE INDEX IF NOT EXISTS idx_secrets_name
    ON medic.secrets(name);

-- Create index on created_at for sorting by creation time
CREATE INDEX IF NOT EXISTS idx_secrets_created_at
    ON medic.secrets(created_at DESC);

-- Create index on created_by for filtering by creator
CREATE INDEX IF NOT EXISTS idx_secrets_created_by
    ON medic.secrets(created_by);

-- Add comments to document the table
COMMENT ON TABLE medic.secrets IS
    'Encrypted secrets for use in playbook execution. Values are encrypted with AES-256-GCM.';
COMMENT ON COLUMN medic.secrets.secret_id IS
    'Unique identifier for the secret';
COMMENT ON COLUMN medic.secrets.name IS
    'Unique name for the secret (e.g., "API_TOKEN", "DB_PASSWORD"). Must match [A-Za-z_][A-Za-z0-9_]* format. Referenced in playbooks as ${secrets.NAME}.';
COMMENT ON COLUMN medic.secrets.encrypted_value IS
    'AES-256-GCM encrypted secret value (ciphertext only)';
COMMENT ON COLUMN medic.secrets.nonce IS
    'Unique 12-byte nonce/IV used for AES-GCM encryption';
COMMENT ON COLUMN medic.secrets.tag IS
    '16-byte GCM authentication tag for integrity verification';
COMMENT ON COLUMN medic.secrets.description IS
    'Optional description of what this secret is used for';
COMMENT ON COLUMN medic.secrets.created_at IS
    'Timestamp when this secret was created';
COMMENT ON COLUMN medic.secrets.updated_at IS
    'Timestamp when this secret was last updated';
COMMENT ON COLUMN medic.secrets.created_by IS
    'User or system that created this secret';
