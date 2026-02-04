-- Migration: 000_create_schema
-- Description: Create the medic schema
-- Date: 2026-02-04

-- Create the medic schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS medic;

-- Add comment to document the schema
COMMENT ON SCHEMA medic IS 'Medic application schema for health monitoring and alerting';
