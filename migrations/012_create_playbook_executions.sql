-- Migration: 012_create_playbook_executions
-- Description: Create playbook_executions and playbook_step_results tables for tracking execution state
-- Date: 2026-02-03
-- Related: US-027 - Add playbook executions tracking
-- Linear: SRE-23 - Playbook Execution Engine

-- Create playbook_executions table to track playbook execution state
-- Executions persist state to survive restarts and support approval workflows
CREATE TABLE IF NOT EXISTS medic.playbook_executions
(
    execution_id SERIAL,
    playbook_id INTEGER NOT NULL,
    service_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pending_approval',
    current_step INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT playbook_executions_pkey PRIMARY KEY (execution_id),
    CONSTRAINT playbook_executions_playbook_fk FOREIGN KEY (playbook_id)
        REFERENCES medic.playbooks(playbook_id) ON DELETE CASCADE,
    CONSTRAINT playbook_executions_service_fk FOREIGN KEY (service_id)
        REFERENCES services(service_id) ON DELETE SET NULL,
    CONSTRAINT playbook_executions_status_check CHECK (
        status IN (
            'pending_approval',
            'running',
            'waiting',
            'completed',
            'failed',
            'cancelled'
        )
    ),
    CONSTRAINT playbook_executions_current_step_positive CHECK (current_step >= 0)
)
WITH (
    OIDS = FALSE
);

-- Create index on playbook_id for joining with playbooks
CREATE INDEX IF NOT EXISTS idx_playbook_executions_playbook_id
    ON medic.playbook_executions(playbook_id);

-- Create index on service_id for filtering executions by service
CREATE INDEX IF NOT EXISTS idx_playbook_executions_service_id
    ON medic.playbook_executions(service_id);

-- Create index on status for filtering active/pending executions
CREATE INDEX IF NOT EXISTS idx_playbook_executions_status
    ON medic.playbook_executions(status);

-- Create partial index for pending approval executions (common query)
CREATE INDEX IF NOT EXISTS idx_playbook_executions_pending_approval
    ON medic.playbook_executions(created_at DESC)
    WHERE status = 'pending_approval';

-- Create partial index for running/waiting executions (resume after restart)
CREATE INDEX IF NOT EXISTS idx_playbook_executions_active
    ON medic.playbook_executions(playbook_id, service_id)
    WHERE status IN ('running', 'waiting');

-- Create index on started_at for sorting/filtering by time
CREATE INDEX IF NOT EXISTS idx_playbook_executions_started_at
    ON medic.playbook_executions(started_at DESC);

-- Create playbook_step_results table to track individual step outcomes
-- Each step result captures the execution details and output
CREATE TABLE IF NOT EXISTS medic.playbook_step_results
(
    result_id SERIAL,
    execution_id INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    output TEXT,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT playbook_step_results_pkey PRIMARY KEY (result_id),
    CONSTRAINT playbook_step_results_execution_fk FOREIGN KEY (execution_id)
        REFERENCES medic.playbook_executions(execution_id) ON DELETE CASCADE,
    CONSTRAINT playbook_step_results_status_check CHECK (
        status IN ('pending', 'running', 'completed', 'failed', 'skipped')
    ),
    CONSTRAINT playbook_step_results_step_index_positive CHECK (step_index >= 0)
)
WITH (
    OIDS = FALSE
);

-- Create index on execution_id for joining with executions
CREATE INDEX IF NOT EXISTS idx_playbook_step_results_execution_id
    ON medic.playbook_step_results(execution_id);

-- Create unique constraint on execution_id + step_index to prevent duplicates
CREATE UNIQUE INDEX IF NOT EXISTS idx_playbook_step_results_execution_step
    ON medic.playbook_step_results(execution_id, step_index);

-- Create index on status for filtering by step status
CREATE INDEX IF NOT EXISTS idx_playbook_step_results_status
    ON medic.playbook_step_results(status);

-- Add comments to document the playbook_executions table
COMMENT ON TABLE medic.playbook_executions IS
    'Tracks playbook execution state. Persists state to survive restarts.';
COMMENT ON COLUMN medic.playbook_executions.execution_id IS
    'Auto-increment primary key for the execution record';
COMMENT ON COLUMN medic.playbook_executions.playbook_id IS
    'Foreign key to the playbook being executed';
COMMENT ON COLUMN medic.playbook_executions.service_id IS
    'Optional service this execution is running for (NULL for manual triggers)';
COMMENT ON COLUMN medic.playbook_executions.status IS
    'Execution state: pending_approval, running, waiting, completed, failed, cancelled';
COMMENT ON COLUMN medic.playbook_executions.current_step IS
    'Zero-based index of the currently executing step';
COMMENT ON COLUMN medic.playbook_executions.started_at IS
    'Timestamp when execution began (after approval if required)';
COMMENT ON COLUMN medic.playbook_executions.completed_at IS
    'Timestamp when execution finished (NULL if still running)';

-- Add comments to document the playbook_step_results table
COMMENT ON TABLE medic.playbook_step_results IS
    'Tracks individual step execution results within a playbook execution';
COMMENT ON COLUMN medic.playbook_step_results.result_id IS
    'Auto-increment primary key for the step result record';
COMMENT ON COLUMN medic.playbook_step_results.execution_id IS
    'Foreign key to the parent playbook execution';
COMMENT ON COLUMN medic.playbook_step_results.step_name IS
    'Name of the step from the playbook definition';
COMMENT ON COLUMN medic.playbook_step_results.step_index IS
    'Zero-based index of this step in the playbook';
COMMENT ON COLUMN medic.playbook_step_results.status IS
    'Step status: pending, running, completed, failed, skipped';
COMMENT ON COLUMN medic.playbook_step_results.output IS
    'Output captured from step execution (webhook response, script stdout, etc.)';
COMMENT ON COLUMN medic.playbook_step_results.error_message IS
    'Error message if step failed';
COMMENT ON COLUMN medic.playbook_step_results.started_at IS
    'Timestamp when step started executing';
COMMENT ON COLUMN medic.playbook_step_results.completed_at IS
    'Timestamp when step finished (NULL if still running)';
