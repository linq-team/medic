-- Migration: 001_create_api_keys
-- Description: Create api_keys table for API authentication
-- Date: 2026-02-03

-- Create api_keys table for storing API keys
-- Key hashes are stored using argon2 algorithm
-- Scopes: 'read', 'write', 'admin'
CREATE TABLE IF NOT EXISTS medic.api_keys
(
    api_key_id SERIAL,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    scopes TEXT[] NOT NULL DEFAULT ARRAY['read']::TEXT[],
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT api_key_id PRIMARY KEY (api_key_id),
    CONSTRAINT api_keys_name_unique UNIQUE (name),
    CONSTRAINT api_keys_scopes_check CHECK (
        scopes <@ ARRAY['read', 'write', 'admin']::TEXT[]
    )
)
WITH (
    OIDS = FALSE
);

-- Create index on key_hash for faster lookups during authentication
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON medic.api_keys(key_hash);

-- Add comment to document the table
COMMENT ON TABLE medic.api_keys IS 'API keys for authenticating requests to Medic API';
COMMENT ON COLUMN medic.api_keys.key_hash IS 'Argon2 hash of the API key';
COMMENT ON COLUMN medic.api_keys.scopes IS 'Array of permission scopes: read, write, admin';
COMMENT ON COLUMN medic.api_keys.expires_at IS 'Optional expiration timestamp, NULL means no expiration';
