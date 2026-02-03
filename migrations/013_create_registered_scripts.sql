-- Migration: 013_create_registered_scripts
-- Description: Create registered_scripts table for pre-registered scripts used in playbook execution
-- Date: 2026-02-03
-- Related: US-030 - Add registered scripts schema, Linear: SRE-20

-- Create registered_scripts table for storing pre-registered scripts
-- Scripts must be pre-registered before they can be executed by playbooks
-- This ensures security by preventing arbitrary code execution
CREATE TABLE IF NOT EXISTS medic.registered_scripts
(
    script_id SERIAL,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    interpreter TEXT NOT NULL DEFAULT 'bash',
    timeout_seconds INTEGER NOT NULL DEFAULT 30,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT registered_scripts_pkey PRIMARY KEY (script_id),
    CONSTRAINT registered_scripts_name_unique UNIQUE (name),
    CONSTRAINT registered_scripts_interpreter_check CHECK (
        interpreter IN ('bash', 'python')
    ),
    CONSTRAINT registered_scripts_timeout_positive CHECK (timeout_seconds > 0)
)
WITH (
    OIDS = FALSE
);

-- Create index on name for lookups by script name
CREATE INDEX IF NOT EXISTS idx_registered_scripts_name
    ON medic.registered_scripts(name);

-- Create index on interpreter for filtering by interpreter type
CREATE INDEX IF NOT EXISTS idx_registered_scripts_interpreter
    ON medic.registered_scripts(interpreter);

-- Create index on created_at for sorting by creation time
CREATE INDEX IF NOT EXISTS idx_registered_scripts_created_at
    ON medic.registered_scripts(created_at DESC);

-- Add comments to document the table
COMMENT ON TABLE medic.registered_scripts IS
    'Pre-registered scripts that can be executed by playbooks. Only scripts in this table can be executed for security.';
COMMENT ON COLUMN medic.registered_scripts.script_id IS
    'Unique identifier for the script';
COMMENT ON COLUMN medic.registered_scripts.name IS
    'Unique name for the script (e.g., "restart-service", "clear-cache"). Referenced by playbook steps.';
COMMENT ON COLUMN medic.registered_scripts.content IS
    'The actual script content to be executed. Variables can be substituted at execution time.';
COMMENT ON COLUMN medic.registered_scripts.interpreter IS
    'Interpreter to use for executing the script: bash or python';
COMMENT ON COLUMN medic.registered_scripts.timeout_seconds IS
    'Maximum execution time in seconds before the script is terminated (default 30)';
COMMENT ON COLUMN medic.registered_scripts.created_at IS
    'Timestamp when this script was registered';
COMMENT ON COLUMN medic.registered_scripts.updated_at IS
    'Timestamp when this script was last updated';
