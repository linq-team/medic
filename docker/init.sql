-- Medic Database Initialization Script
-- This script creates the base schema and tables required by Medic
-- It runs automatically when the PostgreSQL container is first initialized

-- Create the medic schema
CREATE SCHEMA IF NOT EXISTS medic;

-- Set search path to include medic schema
SET search_path TO medic, public;

-- Create base tables
-- ============================================================================

-- Services table - tracks registered heartbeat services
CREATE TABLE IF NOT EXISTS medic.services
(
    service_id SERIAL,
    heartbeat_name text COLLATE pg_catalog."default" NOT NULL,
    active integer NOT NULL,
    alert_interval integer NOT NULL,
    team text COLLATE pg_catalog."default" NOT NULL DEFAULT 'site-reliability'::text,
    priority text COLLATE pg_catalog."default" NOT NULL DEFAULT 'p3'::text,
    muted integer NOT NULL DEFAULT 0,
    down integer NOT NULL DEFAULT 0,
    threshold integer NOT NULL DEFAULT 1,
    service_name text COLLATE pg_catalog."default",
    runbook text COLLATE pg_catalog."default",
    date_added timestamp with time zone,
    date_modified timestamp with time zone,
    date_muted timestamp with time zone,
    CONSTRAINT service_id PRIMARY KEY (service_id),
    CONSTRAINT heartbeat_name UNIQUE (heartbeat_name)
)
WITH (
    OIDS = FALSE
);

-- Heartbeat events table - stores incoming heartbeat events
CREATE TABLE IF NOT EXISTS medic."heartbeatEvents"
(
    heartbeat_id SERIAL,
    "time" timestamp with time zone NOT NULL,
    status text COLLATE pg_catalog."default" NOT NULL,
    service_id integer NOT NULL,
    CONSTRAINT heartbeat_id PRIMARY KEY (heartbeat_id)
)
WITH (
    OIDS = FALSE
);

-- Alerts table - tracks active and historical alerts
CREATE TABLE IF NOT EXISTS medic.alerts
(
    alert_id SERIAL,
    alert_name text COLLATE pg_catalog."default",
    service_id integer NOT NULL,
    active integer NOT NULL DEFAULT 1,
    external_reference_id text COLLATE pg_catalog."default",
    alert_cycle integer NOT NULL,
    created_date timestamp with time zone,
    closed_date timestamp with time zone,
    CONSTRAINT alert_id PRIMARY KEY (alert_id)
)
WITH (
    OIDS = FALSE
);

-- API keys table - stores API keys for authentication
CREATE TABLE IF NOT EXISTS medic.api_keys
(
    api_key_id SERIAL,
    name text COLLATE pg_catalog."default" NOT NULL,
    key_hash text COLLATE pg_catalog."default" NOT NULL,
    scopes text[] NOT NULL DEFAULT ARRAY['read']::text[],
    expires_at timestamp with time zone,
    created_at timestamp with time zone NOT NULL DEFAULT NOW(),
    updated_at timestamp with time zone NOT NULL DEFAULT NOW(),
    CONSTRAINT api_key_id PRIMARY KEY (api_key_id),
    CONSTRAINT api_keys_name_unique UNIQUE (name),
    CONSTRAINT api_keys_scopes_check CHECK (
        scopes <@ ARRAY['read', 'write', 'admin']::text[]
    )
)
WITH (
    OIDS = FALSE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON medic.api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_heartbeat_events_service_id ON medic."heartbeatEvents"(service_id);
CREATE INDEX IF NOT EXISTS idx_heartbeat_events_time ON medic."heartbeatEvents"("time");
CREATE INDEX IF NOT EXISTS idx_alerts_service_id ON medic.alerts(service_id);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON medic.alerts(active);

-- Schema migrations tracking table (used by run_migrations.py)
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Mark base schema as "applied" so migrations don't try to recreate these tables
-- Note: Migrations 001+ add additional tables/columns on top of this base schema
INSERT INTO schema_migrations (version) VALUES ('000') ON CONFLICT DO NOTHING;

-- Grant permissions (for containerized environments)
GRANT ALL PRIVILEGES ON SCHEMA medic TO medic;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA medic TO medic;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA medic TO medic;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Medic base schema initialized successfully';
END $$;
