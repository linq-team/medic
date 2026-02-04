-- Migration: 014_create_approval_requests
-- Description: Create approval_requests table for tracking playbook approval requests
-- Date: 2026-02-03
-- Related: US-035 - Add approval requests tracking

-- Create approval_requests table to track approval requests for playbooks
-- Each pending_approval playbook execution gets an approval request record
CREATE TABLE IF NOT EXISTS medic.approval_requests
(
    request_id SERIAL,
    execution_id INTEGER NOT NULL,
    requested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    status TEXT NOT NULL DEFAULT 'pending',
    decided_by TEXT,
    decided_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT approval_requests_pkey PRIMARY KEY (request_id),
    CONSTRAINT approval_requests_execution_fk FOREIGN KEY (execution_id)
        REFERENCES medic.playbook_executions(execution_id) ON DELETE CASCADE,
    CONSTRAINT approval_requests_execution_unique UNIQUE (execution_id),
    CONSTRAINT approval_requests_status_check CHECK (
        status IN ('pending', 'approved', 'rejected', 'expired')
    ),
    CONSTRAINT approval_requests_decided_at_requires_status CHECK (
        (status IN ('approved', 'rejected') AND decided_at IS NOT NULL AND decided_by IS NOT NULL) OR
        (status = 'expired' AND decided_at IS NOT NULL) OR
        (status = 'pending' AND decided_at IS NULL AND decided_by IS NULL)
    )
)
WITH (
    OIDS = FALSE
);

-- Create index on execution_id for joining with playbook_executions
CREATE INDEX IF NOT EXISTS idx_approval_requests_execution_id
    ON medic.approval_requests(execution_id);

-- Create index on status for filtering pending/approved/rejected requests
CREATE INDEX IF NOT EXISTS idx_approval_requests_status
    ON medic.approval_requests(status);

-- Create partial index for pending requests (common query for approval UI)
CREATE INDEX IF NOT EXISTS idx_approval_requests_pending
    ON medic.approval_requests(requested_at DESC)
    WHERE status = 'pending';

-- Create index on expires_at for finding expired requests
CREATE INDEX IF NOT EXISTS idx_approval_requests_expires_at
    ON medic.approval_requests(expires_at)
    WHERE status = 'pending' AND expires_at IS NOT NULL;

-- Create index on decided_by for audit queries
CREATE INDEX IF NOT EXISTS idx_approval_requests_decided_by
    ON medic.approval_requests(decided_by)
    WHERE decided_by IS NOT NULL;

-- Create index on decided_at for time-based audit queries
CREATE INDEX IF NOT EXISTS idx_approval_requests_decided_at
    ON medic.approval_requests(decided_at DESC)
    WHERE decided_at IS NOT NULL;

-- Add comments to document the approval_requests table
COMMENT ON TABLE medic.approval_requests IS
    'Tracks approval requests for playbook executions that require human approval before running.';
COMMENT ON COLUMN medic.approval_requests.request_id IS
    'Auto-increment primary key for the approval request record';
COMMENT ON COLUMN medic.approval_requests.execution_id IS
    'Foreign key to the playbook execution that requires approval (unique per execution)';
COMMENT ON COLUMN medic.approval_requests.requested_at IS
    'Timestamp when the approval was requested';
COMMENT ON COLUMN medic.approval_requests.expires_at IS
    'Timestamp when this approval request expires (NULL = no expiration). From playbook approval timeout setting.';
COMMENT ON COLUMN medic.approval_requests.status IS
    'Approval status: pending (awaiting decision), approved (user approved), rejected (user rejected), expired (timed out)';
COMMENT ON COLUMN medic.approval_requests.decided_by IS
    'Identifier of who made the decision (Slack user ID, API key name, etc.). NULL for pending/expired.';
COMMENT ON COLUMN medic.approval_requests.decided_at IS
    'Timestamp when decision was made (approval, rejection, or expiration). NULL for pending.';
COMMENT ON COLUMN medic.approval_requests.created_at IS
    'Timestamp when record was created (usually same as requested_at)';
COMMENT ON COLUMN medic.approval_requests.updated_at IS
    'Timestamp when record was last updated';
