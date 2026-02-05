-- Migration: 000_create_base_tables
-- Description: Create the base tables for Medic (services, heartbeatEvents, alerts)
-- Date: 2026-02-05
-- Note: These tables were originally created manually per README instructions.
--       This migration ensures they exist for CI and fresh deployments.

-- Create the medic schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS medic;

-- Services table: Registration info for each heartbeat source
CREATE TABLE IF NOT EXISTS medic.services
(
    service_id SERIAL PRIMARY KEY,
    heartbeat_name text NOT NULL UNIQUE,
    service_name text,
    active integer NOT NULL DEFAULT 1,
    alert_interval integer NOT NULL,
    threshold integer NOT NULL DEFAULT 1,
    team text NOT NULL DEFAULT 'site-reliability',
    priority text NOT NULL DEFAULT 'p3',
    muted integer NOT NULL DEFAULT 0,
    down integer NOT NULL DEFAULT 0,
    runbook text,
    date_added timestamp with time zone DEFAULT NOW(),
    date_modified timestamp with time zone DEFAULT NOW(),
    date_muted timestamp with time zone
);

COMMENT ON TABLE medic.services IS 'Heartbeat service registrations and alert configuration';

-- Heartbeat Events table: Timestamped record of each heartbeat
CREATE TABLE IF NOT EXISTS medic."heartbeatEvents"
(
    heartbeat_id SERIAL PRIMARY KEY,
    "time" timestamp with time zone NOT NULL DEFAULT NOW(),
    status text NOT NULL,
    service_id integer NOT NULL REFERENCES medic.services(service_id)
);

CREATE INDEX IF NOT EXISTS idx_heartbeat_events_service_id
    ON medic."heartbeatEvents"(service_id);
CREATE INDEX IF NOT EXISTS idx_heartbeat_events_time
    ON medic."heartbeatEvents"("time");

COMMENT ON TABLE medic."heartbeatEvents" IS 'Timestamped heartbeat events from services';

-- Alerts table: Active and historical alerts
CREATE TABLE IF NOT EXISTS medic.alerts
(
    alert_id SERIAL PRIMARY KEY,
    alert_name text,
    service_id integer NOT NULL REFERENCES medic.services(service_id),
    active integer NOT NULL DEFAULT 1,
    external_reference_id text,
    alert_cycle integer NOT NULL DEFAULT 1,
    created_date timestamp with time zone DEFAULT NOW(),
    closed_date timestamp with time zone
);

CREATE INDEX IF NOT EXISTS idx_alerts_service_id
    ON medic.alerts(service_id);
CREATE INDEX IF NOT EXISTS idx_alerts_active
    ON medic.alerts(active);

COMMENT ON TABLE medic.alerts IS 'Active and historical alerts triggered by missed heartbeats';
