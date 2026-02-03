-- Migration: 003_create_teams
-- Description: Create teams table and add team_id to services for alert routing
-- Date: 2026-02-03

-- Create teams table for organizing services and routing alerts
CREATE TABLE IF NOT EXISTS medic.teams
(
    team_id SERIAL,
    name TEXT NOT NULL,
    slack_channel_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT team_id PRIMARY KEY (team_id),
    CONSTRAINT teams_name_unique UNIQUE (name)
)
WITH (
    OIDS = FALSE
);

-- Create index on slack_channel_id for lookups when routing alerts
CREATE INDEX IF NOT EXISTS idx_teams_slack_channel_id ON medic.teams(slack_channel_id)
    WHERE slack_channel_id IS NOT NULL;

-- Add comments to document the table
COMMENT ON TABLE medic.teams IS 'Teams for organizing services and routing alerts';
COMMENT ON COLUMN medic.teams.name IS 'Unique team name';
COMMENT ON COLUMN medic.teams.slack_channel_id IS 'Slack channel ID for team alerts (optional)';

-- Add team_id column to services table for team-based alert routing
ALTER TABLE services
    ADD COLUMN IF NOT EXISTS team_id INTEGER;

-- Add foreign key constraint to services.team_id
ALTER TABLE services
    ADD CONSTRAINT services_team_id_fk FOREIGN KEY (team_id)
        REFERENCES medic.teams(team_id) ON DELETE SET NULL;

-- Create index on services.team_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_services_team_id ON services(team_id);

-- Add comment for the new column
COMMENT ON COLUMN services.team_id IS 'Optional team ID for routing alerts to team Slack channel';
