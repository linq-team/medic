# PRD: Medic UI Edit Functionality

## Introduction

Add comprehensive edit functionality to the Medic UI, enabling users to create, edit, and manage services without relying on curl commands or direct API calls. This includes inline editing for quick actions, a full edit modal for complex changes, bulk operations for managing multiple services, and a backup/restore system for recovering from destructive actions.

## Goals

- Enable non-technical users to fully manage services through the UI
- Reduce reliance on curl/API for day-to-day operations
- Provide quick inline toggles for common actions (mute, active, priority)
- Support bulk operations for efficient multi-service management
- Implement backup/restore functionality for destructive actions
- Maintain audit trail of all changes

## User Stories

### US-001: Add service snapshots database table
**Description:** As a developer, I need to store service state snapshots so users can restore previous configurations after destructive actions.

**Acceptance Criteria:**
- [ ] Create migration for `medic.service_snapshots` table with fields:
  - `snapshot_id` (PK)
  - `service_id` (FK to services)
  - `snapshot_data` (JSONB - full service state)
  - `action_type` (enum: 'deactivate', 'delete', 'bulk_edit', 'edit')
  - `actor` (who made the change)
  - `created_at` (timestamp)
  - `restored_at` (nullable timestamp - set when restored)
- [ ] Add index on `service_id` and `created_at`
- [ ] Migration runs successfully
- [ ] Typecheck passes

### US-002: Create snapshot API endpoints
**Description:** As a developer, I need API endpoints to create and restore snapshots so the UI can offer undo functionality.

**Acceptance Criteria:**
- [ ] `GET /v2/snapshots` - list snapshots with filters (service_id, action_type, date range)
- [ ] `GET /v2/snapshots/:id` - get single snapshot details
- [ ] `POST /v2/snapshots/:id/restore` - restore service to snapshot state
- [ ] Snapshots automatically created before destructive actions in existing endpoints
- [ ] Restore endpoint updates service and sets `restored_at` on snapshot
- [ ] All endpoints require authentication
- [ ] Typecheck passes

### US-003: Add Dialog component to UI
**Description:** As a developer, I need a reusable Dialog/Modal component for edit forms and confirmations.

**Acceptance Criteria:**
- [ ] Install/add shadcn Dialog component
- [ ] Component supports title, description, and custom content
- [ ] Component supports controlled open/close state
- [ ] Includes DialogTrigger, DialogContent, DialogHeader, DialogFooter variants
- [ ] Typecheck passes

### US-004: Add Toast notification component
**Description:** As a developer, I need a toast/notification system to show success and error messages after actions.

**Acceptance Criteria:**
- [ ] Install/add shadcn Toast component and Toaster provider
- [ ] Add Toaster to app layout
- [ ] Create `useToast` hook for triggering notifications
- [ ] Supports success, error, and info variants
- [ ] Toasts auto-dismiss after 5 seconds
- [ ] Typecheck passes

### US-005: Create useUpdateService mutation hook
**Description:** As a developer, I need a React Query mutation hook to update services so UI components can modify service data.

**Acceptance Criteria:**
- [ ] Create `useUpdateService` hook using `useMutation`
- [ ] Hook calls `apiClient.updateService()`
- [ ] Invalidates service queries on success
- [ ] Returns loading, error, and success states
- [ ] Supports optimistic updates
- [ ] Typecheck passes

### US-006: Create useCreateService mutation hook
**Description:** As a developer, I need a React Query mutation hook to create new services.

**Acceptance Criteria:**
- [ ] Create `useCreateService` hook using `useMutation`
- [ ] Hook calls `apiClient.createService()`
- [ ] Invalidates services list query on success
- [ ] Returns loading, error, and success states
- [ ] Typecheck passes

### US-007: Create useBulkUpdateServices mutation hook
**Description:** As a developer, I need a mutation hook for bulk service updates.

**Acceptance Criteria:**
- [ ] Create `useBulkUpdateServices` hook
- [ ] Accepts array of service IDs and update payload
- [ ] Creates snapshots before applying changes (via API)
- [ ] Invalidates all affected queries on success
- [ ] Returns progress state for large batches
- [ ] Typecheck passes

### US-008: Add inline mute/unmute toggle to Services table
**Description:** As a user, I want to quickly mute or unmute a service directly from the table so I don't have to open an edit modal.

**Acceptance Criteria:**
- [ ] Mute column shows toggle switch instead of text
- [ ] Clicking toggle immediately updates service
- [ ] Toggle shows loading state during update
- [ ] Toast notification on success/failure
- [ ] Optimistic UI update (instant feedback)
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

### US-009: Add inline active/inactive toggle to Services table
**Description:** As a user, I want to quickly activate or deactivate a service from the table.

**Acceptance Criteria:**
- [ ] Active column shows toggle switch
- [ ] Deactivating shows confirmation dialog (destructive action)
- [ ] Confirmation dialog warns about alert implications
- [ ] Creates snapshot before deactivation
- [ ] Toast notification on success/failure
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

### US-010: Add inline priority selector to Services table
**Description:** As a user, I want to quickly change a service's priority from the table.

**Acceptance Criteria:**
- [ ] Priority column shows dropdown selector on hover/focus
- [ ] Options: P1 (Critical), P2 (High), P3 (Normal)
- [ ] Selection immediately updates service
- [ ] Visual feedback during update
- [ ] Toast notification on success
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

### US-011: Create ServiceEditModal component
**Description:** As a user, I want to edit all service fields in a modal so I can make comprehensive changes.

**Acceptance Criteria:**
- [ ] Modal opens from "Edit" button on ServiceDetail page
- [ ] Modal opens from row action menu in Services table
- [ ] Form fields for: service_name, team, priority, alert_interval, threshold, runbook
- [ ] Current values pre-populated
- [ ] Client-side validation:
  - service_name: required, max 100 chars
  - alert_interval: required, positive integer, min 1
  - threshold: required, positive integer, min 1
  - runbook: optional, valid URL format
- [ ] Save button disabled while invalid or unchanged
- [ ] Cancel button closes modal without saving
- [ ] Toast notification on success/failure
- [ ] Modal closes on successful save
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

### US-012: Create ServiceCreateModal component
**Description:** As a user, I want to create new services through the UI so I don't need to use curl.

**Acceptance Criteria:**
- [ ] "Add Service" button in Services page header
- [ ] Modal with form fields: heartbeat_name, service_name, team, priority, alert_interval, threshold, runbook
- [ ] heartbeat_name field shows format hint (e.g., "my-service-heartbeat")
- [ ] Sensible defaults: priority=P3, alert_interval=5, threshold=1
- [ ] Client-side validation:
  - heartbeat_name: required, alphanumeric with hyphens, max 100 chars
  - service_name: required, max 100 chars
  - alert_interval: required, positive integer, min 1
  - threshold: required, positive integer, min 1
- [ ] Submit creates service and shows success toast
- [ ] Modal closes and table refreshes on success
- [ ] Error toast if heartbeat_name already exists
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

### US-013: Add Edit button to ServiceDetail page
**Description:** As a user, I want to edit a service from its detail page.

**Acceptance Criteria:**
- [ ] "Edit" button in ServiceDetail header next to Back button
- [ ] Button opens ServiceEditModal with current service data
- [ ] Page refreshes data after successful edit
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

### US-014: Add quick action buttons to ServiceDetail page
**Description:** As a user, I want quick mute/unmute and activate/deactivate buttons on the service detail page.

**Acceptance Criteria:**
- [ ] Action buttons section below header: Mute/Unmute, Activate/Deactivate
- [ ] Buttons show current state (e.g., "Unmute" if muted)
- [ ] Deactivate shows confirmation dialog
- [ ] Actions create snapshots for undo capability
- [ ] Toast notifications on success/failure
- [ ] Page data refreshes after action
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

### US-015: Add row selection to Services table
**Description:** As a user, I want to select multiple services to perform bulk actions.

**Acceptance Criteria:**
- [ ] Checkbox column on left side of table
- [ ] "Select all" checkbox in header (selects visible page)
- [ ] Selected count shown in toolbar when > 0 selected
- [ ] Selection persists during filtering (within same session)
- [ ] Clear selection button in toolbar
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

### US-016: Add bulk actions toolbar
**Description:** As a user, I want to perform actions on multiple selected services at once.

**Acceptance Criteria:**
- [ ] Toolbar appears when services are selected
- [ ] Actions: Mute, Unmute, Activate, Deactivate, Change Priority, Change Team
- [ ] Confirmation dialog for destructive actions showing count of affected services
- [ ] Confirmation lists service names being affected
- [ ] All bulk actions create snapshots before executing
- [ ] Progress indicator for bulk operations
- [ ] Summary toast on completion (e.g., "5 services muted")
- [ ] Selection cleared after successful action
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

### US-017: Add bulk edit modal for team/priority
**Description:** As a user, I want to change team or priority for multiple services at once.

**Acceptance Criteria:**
- [ ] Modal opens from bulk actions toolbar
- [ ] Shows list of selected services
- [ ] Dropdown for new team value
- [ ] Dropdown for new priority value
- [ ] Can set one or both fields
- [ ] Preview of changes before confirming
- [ ] Creates snapshots before applying
- [ ] Toast summary on completion
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

### US-018: Create useSnapshots query hook
**Description:** As a developer, I need a hook to fetch service snapshots for the restore UI.

**Acceptance Criteria:**
- [ ] Create `useSnapshots` hook with filters (service_id, action_type, date range)
- [ ] Create `useRestoreSnapshot` mutation hook
- [ ] Hooks properly typed with TypeScript
- [ ] Invalidates service queries on restore
- [ ] Typecheck passes

### US-019: Add History tab to ServiceDetail page
**Description:** As a user, I want to see change history for a service so I can track what changed and restore previous states.

**Acceptance Criteria:**
- [ ] New "History" tab on ServiceDetail page (alongside Overview)
- [ ] Shows list of snapshots for this service
- [ ] Each entry shows: action type, actor, timestamp, summary of changes
- [ ] "Restore" button on each snapshot entry
- [ ] Restore confirmation dialog showing what will change
- [ ] Already-restored snapshots show "Restored at [timestamp]" badge
- [ ] Empty state message if no history
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

### US-020: Add Service History page
**Description:** As a user, I want a dedicated page to view and restore service changes across all services.

**Acceptance Criteria:**
- [ ] New route: `/history` or `/service-history`
- [ ] Add link in sidebar navigation
- [ ] Table showing all snapshots with columns: Service, Action, Actor, Date, Status
- [ ] Filters: service name search, action type, date range
- [ ] Sortable by date (default: newest first)
- [ ] Pagination for large result sets
- [ ] "Restore" action on each row
- [ ] Click row to expand and show full snapshot details
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

### US-021: Add undo toast for destructive actions
**Description:** As a user, I want an "Undo" option in the success toast after destructive actions so I can quickly revert mistakes.

**Acceptance Criteria:**
- [ ] Destructive action toasts include "Undo" button
- [ ] Undo button visible for 10 seconds (extended toast duration)
- [ ] Clicking Undo immediately restores from snapshot
- [ ] Undo button shows loading state during restore
- [ ] Second toast confirms "Action undone"
- [ ] Undo only available for most recent action per service
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

### US-022: Add row actions menu to Services table
**Description:** As a user, I want a context menu on each table row for quick access to actions.

**Acceptance Criteria:**
- [ ] Three-dot menu icon on each row (or on hover)
- [ ] Menu items: Edit, Mute/Unmute, Activate/Deactivate, View History
- [ ] Menu items show appropriate labels based on current state
- [ ] Keyboard accessible (Enter to open, arrow keys to navigate)
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

## Functional Requirements

- FR-1: Store service state snapshots in `medic.service_snapshots` table before any destructive action
- FR-2: Provide REST API endpoints for listing, viewing, and restoring snapshots
- FR-3: Display inline toggle switches for mute/active fields in Services table
- FR-4: Display inline priority dropdown in Services table
- FR-5: Show confirmation dialog before deactivating services (single or bulk)
- FR-6: Show confirmation dialog before any bulk action affecting multiple services
- FR-7: Provide full edit modal for all service fields accessible from table and detail page
- FR-8: Provide create service modal accessible from Services page
- FR-9: Support multi-select in Services table with select-all for current page
- FR-10: Provide bulk actions toolbar when services are selected (mute, unmute, activate, deactivate, change team, change priority)
- FR-11: Show change history on ServiceDetail page with restore capability
- FR-12: Provide dedicated Service History page for viewing all snapshots across services
- FR-13: Include "Undo" button in toast notifications for destructive actions
- FR-14: Validate all form inputs client-side before submission
- FR-15: Show toast notifications for all action success/failure states
- FR-16: Create snapshots automatically when updating services through existing API endpoints (backward compatible)

## Non-Goals

- No real-time collaboration (multiple users editing same service)
- No draft/auto-save functionality for forms
- No bulk import/export (CSV, JSON)
- No scheduled changes (change priority at 5pm)
- No approval workflow for changes
- No service deletion (only deactivation) - this is intentional
- No snapshot expiration/cleanup in this phase (can add later)
- No S3 backup (database storage is sufficient for this use case)

## Design Considerations

- Reuse existing shadcn/ui components (Button, Card, Table, Badge, Select, Input)
- Add shadcn Dialog component for modals
- Add shadcn Toast component for notifications
- Follow existing color scheme: P1=red, P2=yellow, P3=gray
- Inline edits should feel instant (optimistic updates)
- Confirmation dialogs should clearly state what will happen
- History/restore UI should make it clear what state will be restored

## Technical Considerations

- Use React Query mutations with optimistic updates for inline edits
- Snapshots stored as JSONB for flexibility (schema changes won't break old snapshots)
- Snapshot restore is a simple UPDATE from JSONB data
- Keep bulk operations transactional where possible
- Consider rate limiting on bulk operations (max 100 services per request)
- Add `actor` field to snapshots from authenticated user context
- Existing `POST /service/:name` endpoint should auto-create snapshot when `active` changes from 1 to 0

## Success Metrics

- Users can create a new service in under 30 seconds
- Users can edit any service field in under 3 clicks
- Users can mute/unmute in 1 click (inline toggle)
- Users can bulk update 10+ services in under 10 seconds
- Users can restore a previous state in under 5 clicks
- Zero data loss from accidental deactivations (100% recoverable via snapshots)

## Open Questions

- Should snapshots have a retention policy (e.g., keep for 90 days)?
- Should we limit the number of snapshots per service?
- Should restore create a new snapshot (for undo-redo chain)?
- Should bulk actions be processed in background for very large selections (100+)?
