-- Migration: 015_create_remediation_audit_log
-- Description: Create remediation_audit_log table for tracking all playbook execution actions
-- Date: 2026-02-03
-- Related: US-039 - Add remediation audit log schema
-- Linear: SRE-23 - Playbook Execution Engine

-- Create remediation_audit_log table to provide immutable audit trail
-- Every action during playbook execution is logged for compliance and debugging
CREATE TABLE IF NOT EXISTS medic.remediation_audit_log
(
    log_id SERIAL,
    execution_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}',
    actor TEXT,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT remediation_audit_log_pkey PRIMARY KEY (log_id),
    CONSTRAINT remediation_audit_log_execution_fk FOREIGN KEY (execution_id)
        REFERENCES medic.playbook_executions(execution_id) ON DELETE CASCADE,
    CONSTRAINT remediation_audit_log_action_type_check CHECK (
        action_type IN (
            'execution_started',
            'step_completed',
            'step_failed',
            'approval_requested',
            'approved',
            'rejected',
            'execution_completed',
            'execution_failed'
        )
    )
)
WITH (
    OIDS = FALSE
);

-- Create index on execution_id for filtering logs by execution
CREATE INDEX IF NOT EXISTS idx_remediation_audit_log_execution_id
    ON medic.remediation_audit_log(execution_id);

-- Create index on action_type for filtering by action type
CREATE INDEX IF NOT EXISTS idx_remediation_audit_log_action_type
    ON medic.remediation_audit_log(action_type);

-- Create index on timestamp for time-based queries
CREATE INDEX IF NOT EXISTS idx_remediation_audit_log_timestamp
    ON medic.remediation_audit_log(timestamp DESC);

-- Create index on actor for filtering by who performed actions
CREATE INDEX IF NOT EXISTS idx_remediation_audit_log_actor
    ON medic.remediation_audit_log(actor)
    WHERE actor IS NOT NULL;

-- Create composite index for common query pattern: execution + time order
CREATE INDEX IF NOT EXISTS idx_remediation_audit_log_execution_timestamp
    ON medic.remediation_audit_log(execution_id, timestamp ASC);

-- Create GIN index on details JSONB for flexible querying of audit details
CREATE INDEX IF NOT EXISTS idx_remediation_audit_log_details_gin
    ON medic.remediation_audit_log USING GIN (details);

-- Add comments to document the remediation_audit_log table
COMMENT ON TABLE medic.remediation_audit_log IS
    'Immutable audit log for all playbook execution actions. Used for compliance, debugging, and analytics.';
COMMENT ON COLUMN medic.remediation_audit_log.log_id IS
    'Auto-increment primary key for the audit log entry';
COMMENT ON COLUMN medic.remediation_audit_log.execution_id IS
    'Foreign key to the playbook execution being audited';
COMMENT ON COLUMN medic.remediation_audit_log.action_type IS
    'Type of action: execution_started, step_completed, step_failed, approval_requested, approved, rejected, execution_completed, execution_failed';
COMMENT ON COLUMN medic.remediation_audit_log.details IS
    'JSONB field containing action-specific details (step name, output, error message, etc.)';
COMMENT ON COLUMN medic.remediation_audit_log.actor IS
    'User or system that performed the action (NULL for automated actions, user ID for approvals)';
COMMENT ON COLUMN medic.remediation_audit_log.timestamp IS
    'When the action occurred';
COMMENT ON COLUMN medic.remediation_audit_log.created_at IS
    'When the log entry was created (may differ from timestamp for delayed logging)';
