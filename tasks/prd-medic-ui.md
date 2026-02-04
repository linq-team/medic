# PRD: Medic UI Dashboard

## Introduction

Create a web-based user interface for the Medic heartbeat monitoring service. The UI will primarily serve as an administrative interface for managing services, heartbeats, alerts, and playbooks, while also providing monitoring capabilities for visibility into system health. The application will be built with React and TypeScript, containerized with nginx, and deployed alongside the existing Medic API infrastructure.

## Goals

- Provide a centralized administrative interface for managing Medic services and heartbeats
- Enable real-time visibility into service health status and active alerts via WebSocket/SSE
- Allow configuration management (mute/unmute, update intervals, thresholds, teams, priorities)
- Support full playbook lifecycle: creation, editing, execution, and approval workflows
- Provide audit log access for compliance and troubleshooting
- Reduce reliance on CLI and direct API calls for day-to-day operations
- Support both SRE/DevOps engineers and development teams
- Deliver a polished, ADA-compliant interface with light and dark modes adhering to Linq brand guidelines

## Linear Project Configuration

All user stories in this PRD should be created as Linear issues with:

- **Team:** Site Reliability
- **Project:** Medic v2
- **Labels:** `ui`, `frontend` (add additional labels as appropriate per story)

### Issue Creation Guidelines:
- Create one Linear issue per user story (US-XXX)
- Title format: `[UI] US-XXX: <User Story Title>`
- Copy the Description and Acceptance Criteria from this PRD into the issue
- Set appropriate priority based on dependencies
- Link blocking/blocked relationships between dependent stories
- Milestone: Create "Medic UI MVP" milestone for initial release stories

### Suggested Phases/Milestones:
1. **Phase 1 - Foundation** (US-001 through US-005): Scaffolding, design system, auth, WebSocket
2. **Phase 2 - Core Features** (US-006 through US-015): Navigation, dashboard, services, alerts
3. **Phase 3 - Playbooks** (US-016 through US-019): Playbook CRUD, execution, approvals
4. **Phase 4 - Polish** (US-020 through US-027): Audit logs, settings, accessibility, docs

## Definition of Done

Per Linq's engineering standards, each user story is not complete until:

1. **Tests** - Unit, integration, and E2E tests are written and passing
2. **QA** - Manual test plan completed, edge cases checked, QA signoff obtained
3. **Monitoring** - Alerts configured in Grafana, dashboards created, we know if it breaks before users tell us
4. **Telemetry** - Usage and performance tracked via Grafana Faro, we know what's working
5. **Tooling** - Debug and usage tooling exists where needed
6. **Runbook** - Documentation for how it works exists
7. **Handoff** - Clear ownership, Ops/Sales/CS know what changed

## User Stories

### US-001: Project scaffolding and Docker setup
**Description:** As a developer, I need the React project scaffolded with TypeScript and Docker configuration so that we have a foundation to build upon.

**Linear Labels:** `ui`, `frontend`, `infrastructure`, `phase-1`

**Acceptance Criteria:**
- [ ] Create React app with Vite + TypeScript in `ui/` directory
- [ ] Configure ESLint, Prettier, and Husky for code quality
- [ ] Create `ui/Dockerfile` with multi-stage build (Node build → nginx serve)
- [ ] Update `docker-compose.yml` to include ui service with nginx reverse proxy
- [ ] nginx routes `/api/*` to medic-api, `/ws` for WebSocket, `/*` to static React files
- [ ] Environment variable support for API base URL (runtime injection via env.js)
- [ ] `npm run build` produces production-ready static files
- [ ] Typecheck passes
- [ ] Unit tests for build configuration pass
- [ ] Documentation: README with setup instructions

---

### US-002: Design system and theming foundation
**Description:** As a developer, I need a design system with Linq brand compliance so that the UI has consistent styling aligned with company identity.

**Linear Labels:** `ui`, `frontend`, `design-system`, `phase-1`

**Acceptance Criteria:**
- [ ] Evaluate and select component library (Radix UI, shadcn/ui, Chakra UI, or Mantine)
- [ ] Implement theme provider with light and dark mode support
- [ ] Define color palette per Linq Brand Guidelines:

**Linq Brand Colors:**
| Token | Light Mode | Dark Mode | Usage |
|-------|------------|-----------|-------|
| `--color-neutral-900` | #141414 | #FFFFFF | Primary text |
| `--color-neutral-100` | #FCF9E9 | #141414 | Backgrounds |
| `--color-neutral-400` | #B0BFB7 | #B0BFB7 | Borders, muted text |
| `--color-primary-500` | #1B3D67 | #4F9FDF | Primary actions, links |
| `--color-primary-400` | #4F9FDF | #4F9FDF | Hover states, accents |
| `--color-accent-500` | #83B149 | #83B149 | Success, healthy status |
| `--color-accent-400` | #E8DF6E | #E8DF6E | Warning states |

**Medic-specific Status Colors (ADA compliant):**
| Status | Light Mode | Dark Mode | Contrast Ratio |
|--------|------------|-----------|----------------|
| Healthy | #83B149 | #83B149 | 4.5:1+ on both |
| Warning | #CA8A04 | #EAB308 | 4.5:1+ on both |
| Error | #DC2626 | #EF4444 | 4.5:1+ on both |
| Critical | #991B1B | #DC2626 | 4.5:1+ on both |
| Muted | #6B7280 | #9CA3AF | 4.5:1+ on both |

- [ ] All colors verified with WCAG 2.1 AA contrast checker (4.5:1 text, 3:1 UI)
- [ ] Typography using Geist (body) and Geist Mono (numerals, code, buttons) per brand guidelines
- [ ] Create base components: Button, Input, Card, Badge, Table, Modal, Toast
- [ ] Theme toggle persists to localStorage
- [ ] Typecheck passes
- [ ] Storybook setup for component documentation
- [ ] Verify in browser using dev-browser skill

---

### US-003: Authentication and API client setup
**Description:** As a user, I need to authenticate with an API key so that I can securely access Medic functionality.

**Linear Labels:** `ui`, `frontend`, `auth`, `phase-1`

**Acceptance Criteria:**
- [ ] Create API client module using fetch with TypeScript types
- [ ] Implement API key authentication header injection
- [ ] Create login screen for API key entry (styled with Linq/Medic branding)
- [ ] Store API key securely in session storage (not localStorage)
- [ ] Implement logout functionality that clears session
- [ ] Show authentication errors with clear messages
- [ ] Redirect unauthenticated users to login
- [ ] Typecheck passes
- [ ] Unit tests for API client
- [ ] Verify in browser using dev-browser skill

---

### US-004: WebSocket backend implementation
**Description:** As a developer, I need WebSocket support in the Medic API so that the UI can receive real-time updates.

**Linear Labels:** `backend`, `api`, `websocket`, `phase-1`

**Blocks:** US-005

**Acceptance Criteria:**
- [ ] Add Flask-SocketIO or similar WebSocket library to requirements.txt
- [ ] Create `/ws` WebSocket endpoint in Flask
- [ ] Emit events on: heartbeat_received, alert_created, alert_resolved, service_status_changed
- [ ] Support authentication via API key in connection handshake
- [ ] Implement connection heartbeat/ping-pong for connection health
- [ ] Handle graceful disconnection and cleanup
- [ ] Add WebSocket connection to health check status
- [ ] Unit tests for WebSocket handlers
- [ ] Integration tests for event emission
- [ ] Update API documentation

---

### US-005: Real-time updates infrastructure (Frontend)
**Description:** As an SRE, I need real-time updates so that I see status changes immediately without manual refresh.

**Linear Labels:** `ui`, `frontend`, `websocket`, `phase-1`

**Blocked By:** US-004

**Acceptance Criteria:**
- [ ] Implement WebSocket client connecting to `/ws` endpoint
- [ ] Create connection status indicator in header (connected/disconnected/reconnecting)
- [ ] Automatic reconnection with exponential backoff (1s, 2s, 4s, 8s, max 30s)
- [ ] Graceful fallback to polling (30s interval) if WebSocket unavailable
- [ ] Real-time events update React Query cache automatically
- [ ] Visual indicator when data is stale (WebSocket disconnected)
- [ ] Typecheck passes
- [ ] Unit tests for WebSocket client and reconnection logic
- [ ] Integration tests for cache updates

---

### US-006: Navigation and layout structure
**Description:** As a user, I want a consistent navigation layout so that I can easily move between different sections of the application.

**Linear Labels:** `ui`, `frontend`, `navigation`, `phase-2`

**Blocked By:** US-002

**Acceptance Criteria:**
- [ ] Create responsive sidebar navigation component
- [ ] Navigation items: Dashboard, Services, Alerts, Playbooks, Audit Logs, Settings
- [ ] Highlight active navigation item
- [ ] Collapsible sidebar for mobile/tablet views (hamburger menu)
- [ ] Header with Medic logo (`docs/assets/medic-icon-all-green.png`) and user session info
- [ ] Footer with Linq Cube logo + "Built by Linq" text (black logo light mode, white logo dark mode per brand guidelines)
- [ ] Theme toggle (sun/moon icon) in header
- [ ] Pending approvals badge on Playbooks nav item (real-time count)
- [ ] Connection status indicator in header
- [ ] Typecheck passes
- [ ] Unit tests for navigation state
- [ ] Verify in browser using dev-browser skill

---

### US-007: Keyboard shortcuts system
**Description:** As a power user, I want keyboard shortcuts so that I can navigate and perform actions quickly.

**Linear Labels:** `ui`, `frontend`, `ux`, `accessibility`, `phase-2`

**Acceptance Criteria:**
- [ ] Implement keyboard shortcut system with `useHotkeys` or similar
- [ ] Global shortcuts:
  - `?` - Open keyboard shortcuts help modal
  - `g d` - Go to Dashboard
  - `g s` - Go to Services
  - `g a` - Go to Alerts
  - `g p` - Go to Playbooks
  - `g l` - Go to Audit Logs
  - `/` or `Cmd+K` - Open global search/command palette
  - `Escape` - Close modals, clear selection
  - `t` - Toggle theme (light/dark)
- [ ] Context shortcuts (when on Services page):
  - `n` - New service registration
  - `m` - Mute selected service
  - `e` - Edit selected service
- [ ] Shortcuts respect focus (don't trigger when typing in inputs)
- [ ] Shortcuts displayed in tooltips on buttons
- [ ] Keyboard shortcuts help modal (triggered by `?`)
- [ ] Typecheck passes
- [ ] Unit tests for shortcut handlers
- [ ] Verify in browser using dev-browser skill

---

### US-008: Dashboard overview page
**Description:** As an SRE, I want a dashboard overview so that I can quickly assess the health of all monitored services at a glance.

**Linear Labels:** `ui`, `frontend`, `dashboard`, `phase-2`

**Blocked By:** US-005, US-006

**Acceptance Criteria:**
- [ ] Display summary cards: Total Services, Active Services, Down Services, Active Alerts
- [ ] Cards use Linq color scheme (green #83B149 for healthy, red for critical)
- [ ] Show list of currently down/unhealthy services with priority badges
- [ ] Display recent alerts (last 10) with status indicators
- [ ] Real-time updates via WebSocket (cards update live)
- [ ] Manual refresh button as backup
- [ ] Loading skeletons for all data fetches
- [ ] Empty states when no alerts or down services
- [ ] Typecheck passes
- [ ] Unit tests for dashboard components
- [ ] E2E test for dashboard load
- [ ] Grafana dashboard for UI metrics created
- [ ] Verify in browser using dev-browser skill

---

### US-009: Services list page
**Description:** As a developer, I want to view all registered services so that I can see what heartbeats are configured in Medic.

**Linear Labels:** `ui`, `frontend`, `services`, `phase-2`

**Blocked By:** US-006

**Acceptance Criteria:**
- [ ] Display paginated table of all services (default 25 per page)
- [ ] Columns: Service Name, Heartbeat Name, Status (active/inactive), Down, Muted, Team, Priority, Alert Interval, Last Heartbeat
- [ ] Sort by any column (default: service name ascending)
- [ ] Filter by: active/inactive, muted/unmuted, down/up, team (multi-select)
- [ ] Search by service name or heartbeat name (debounced 300ms)
- [ ] Click row to navigate to service detail page
- [ ] Bulk actions: mute/unmute selected services (checkbox selection)
- [ ] Real-time status updates via WebSocket
- [ ] URL reflects current filters/sort for shareability
- [ ] Keyboard navigation: arrow keys for row selection, Enter to open
- [ ] Typecheck passes
- [ ] Unit tests for table filtering/sorting logic
- [ ] Verify in browser using dev-browser skill

---

### US-010: Service detail page
**Description:** As a developer, I want to view detailed information about a specific service so that I can understand its configuration and recent activity.

**Linear Labels:** `ui`, `frontend`, `services`, `phase-2`

**Blocked By:** US-009

**Acceptance Criteria:**
- [ ] Display all service fields: heartbeat_name, service_name, active, alert_interval, threshold, team, priority, muted, down, runbook, dates
- [ ] Show heartbeat history chart (last 24 hours) using Recharts or similar
- [ ] Display recent heartbeat events in a table (last 50)
- [ ] Show alert history for this service
- [ ] Link to runbook if configured (opens in new tab)
- [ ] Edit button to open edit modal (keyboard: `e`)
- [ ] Quick action buttons: Mute/Unmute (`m`), Activate/Deactivate
- [ ] Real-time updates for heartbeat events
- [ ] Typecheck passes
- [ ] Unit tests for service detail components
- [ ] Verify in browser using dev-browser skill

---

### US-011: Service edit functionality
**Description:** As an SRE, I want to edit service configuration so that I can adjust monitoring parameters without using the CLI.

**Linear Labels:** `ui`, `frontend`, `services`, `phase-2`

**Blocked By:** US-010

**Acceptance Criteria:**
- [ ] Modal form for editing service properties
- [ ] Editable fields: service_name, active, alert_interval, threshold, team (dropdown), priority (dropdown), runbook, muted
- [ ] Form validation with inline error messages (Zod schema)
- [ ] Confirm dialog for deactivating a service (destructive action)
- [ ] Success/error toast notifications on save
- [ ] Optimistic UI update with rollback on error
- [ ] Keyboard accessible (Tab navigation, Enter to submit, Escape to cancel)
- [ ] Typecheck passes
- [ ] Unit tests for form validation
- [ ] Verify in browser using dev-browser skill

---

### US-012: Service registration
**Description:** As a developer, I want to register a new service/heartbeat so that I can start monitoring my application.

**Linear Labels:** `ui`, `frontend`, `services`, `phase-2`

**Blocked By:** US-009

**Acceptance Criteria:**
- [ ] "Register Service" button on services list page (keyboard: `n`)
- [ ] Modal form with required fields: heartbeat_name, service_name, alert_interval
- [ ] Optional fields: environment, threshold, team, priority, runbook
- [ ] Environment prefix preview (shows final heartbeat_name with prefix)
- [ ] Async validation for unique heartbeat_name (check on blur)
- [ ] Success toast with link to new service detail page
- [ ] Typecheck passes
- [ ] Unit tests for registration form validation
- [ ] E2E test for full registration flow
- [ ] Verify in browser using dev-browser skill

---

### US-013: Mute/unmute service quick action
**Description:** As an SRE, I want to quickly mute or unmute a service so that I can suppress alerts during maintenance.

**Linear Labels:** `ui`, `frontend`, `services`, `phase-2`

**Blocked By:** US-009

**Acceptance Criteria:**
- [ ] Mute/unmute toggle button on service list rows
- [ ] Mute/unmute button on service detail page (keyboard: `m`)
- [ ] Confirmation dialog before muting with optional reason/duration field
- [ ] Duration options: 1 hour, 4 hours, 8 hours, 24 hours, indefinite
- [ ] Visual indicator for muted services (muted icon + subtle gray styling)
- [ ] Show mute timestamp and remaining duration on muted services
- [ ] Audit log entry created on mute/unmute
- [ ] Typecheck passes
- [ ] Unit tests for mute functionality
- [ ] Verify in browser using dev-browser skill

---

### US-014: Alerts list page
**Description:** As an SRE, I want to view all alerts so that I can track current and historical incidents.

**Linear Labels:** `ui`, `frontend`, `alerts`, `phase-2`

**Blocked By:** US-006

**Acceptance Criteria:**
- [ ] Display paginated table of alerts (default 25 per page)
- [ ] Columns: Alert Name, Service, Status (active/resolved), Priority, Created Date, Closed Date, Duration, Alert Cycles
- [ ] Filter by: active/resolved, priority (P1/P2/P3), date range
- [ ] Sort by any column (default: created date descending)
- [ ] Color-coded priority badges using Linq palette
- [ ] Click to view alert details
- [ ] Real-time updates for new/resolved alerts via WebSocket
- [ ] Typecheck passes
- [ ] Unit tests for alert filtering
- [ ] Verify in browser using dev-browser skill

---

### US-015: Alert detail page
**Description:** As an SRE, I want to view detailed alert information so that I can understand and respond to incidents.

**Linear Labels:** `ui`, `frontend`, `alerts`, `phase-2`

**Blocked By:** US-014

**Acceptance Criteria:**
- [ ] Display all alert fields with human-readable timestamps (relative + absolute)
- [ ] Link to associated service detail page
- [ ] Show external reference ID with clickable link to PagerDuty if available
- [ ] Display alert timeline visualization (created → cycles → resolved)
- [ ] Link to runbook from associated service (prominent placement)
- [ ] Show related playbook executions if any were triggered
- [ ] Typecheck passes
- [ ] Unit tests for alert detail
- [ ] Verify in browser using dev-browser skill

---

### US-016: Playbooks list page
**Description:** As an SRE, I want to view all configured playbooks so that I can manage automated remediation.

**Linear Labels:** `ui`, `frontend`, `playbooks`, `phase-3`

**Blocked By:** US-006

**Acceptance Criteria:**
- [ ] Display table of playbooks with name, description, trigger type, last run, status
- [ ] Filter by: active/inactive, trigger type (manual/alert/scheduled)
- [ ] Search by playbook name
- [ ] Click to view playbook details
- [ ] "Create Playbook" button (prominent)
- [ ] "Execute" button for manual triggering (per row)
- [ ] Pending approvals section at top if any pending (highlighted)
- [ ] Typecheck passes
- [ ] Unit tests for playbooks list
- [ ] Verify in browser using dev-browser skill

---

### US-017: Playbook creation and editing
**Description:** As an SRE, I want to create and edit playbooks in the UI so that I can manage automated remediation without editing YAML files.

**Linear Labels:** `ui`, `frontend`, `playbooks`, `phase-3`

**Blocked By:** US-016

**Acceptance Criteria:**
- [ ] Create playbook form with: name, description, active toggle
- [ ] Trigger configuration: manual, on alert (with service/priority filters), scheduled (cron)
- [ ] Step builder with drag-and-drop reordering
- [ ] Step types supported:
  - **Webhook**: URL, method, headers, body template
  - **Wait**: duration (seconds/minutes)
  - **Condition**: expression builder or raw expression
  - **Script**: sandboxed script with timeout
- [ ] Each step: name, type-specific config, continue on error toggle
- [ ] Approval settings: require approval toggle, approvers list (users/groups)
- [ ] YAML preview panel (read-only, for export/reference)
- [ ] Validation before save with clear error messages
- [ ] Edit existing playbook (loads into form)
- [ ] Delete playbook with confirmation dialog
- [ ] Version history (optional, if backend supports)
- [ ] Typecheck passes
- [ ] Unit tests for playbook builder validation
- [ ] E2E test for create playbook flow
- [ ] Verify in browser using dev-browser skill

---

### US-018: Playbook detail and execution
**Description:** As an SRE, I want to view playbook details and trigger execution so that I can run automated remediation manually.

**Linear Labels:** `ui`, `frontend`, `playbooks`, `phase-3`

**Blocked By:** US-016

**Acceptance Criteria:**
- [ ] Display playbook configuration in readable format
- [ ] Visual step flow diagram (vertical timeline or flowchart)
- [ ] Show execution history table with: status, duration, timestamps, triggered by
- [ ] "Execute Now" button with optional variables input modal
- [ ] Confirmation dialog before execution
- [ ] Real-time status updates during execution via WebSocket
- [ ] Live execution log viewer (step-by-step progress)
- [ ] View historical execution logs and step results
- [ ] Typecheck passes
- [ ] Unit tests for execution components
- [ ] Verify in browser using dev-browser skill

---

### US-019: Playbook approval workflow
**Description:** As an SRE, I want to approve or reject pending playbook executions so that I can control automated actions.

**Linear Labels:** `ui`, `frontend`, `playbooks`, `phase-3`

**Blocked By:** US-016, US-005

**Acceptance Criteria:**
- [ ] Show pending approvals badge in navigation (real-time WebSocket count)
- [ ] Pending approvals list/panel with: playbook name, trigger reason, requested time, requester
- [ ] Approve/Reject buttons with confirmation
- [ ] Optional comment field for approval decisions
- [ ] Real-time notification when new approval is pending
- [ ] Browser notification option (with permission prompt)
- [ ] Approval/rejection reflected immediately in UI
- [ ] Typecheck passes
- [ ] Unit tests for approval workflow
- [ ] E2E test for approve/reject flow
- [ ] Verify in browser using dev-browser skill

---

### US-020: Audit logs page
**Description:** As an SRE, I want to view audit logs so that I can track all actions taken in the system for compliance.

**Linear Labels:** `ui`, `frontend`, `audit`, `phase-4`

**Blocked By:** US-006

**Acceptance Criteria:**
- [ ] Display paginated table of audit log entries
- [ ] Columns: Timestamp, Action Type, Actor, Service/Execution ID, Summary
- [ ] Filter by: action type (dropdown), actor (search), service_id, date range
- [ ] Search by execution_id
- [ ] Export to CSV button (exports with current filters applied)
- [ ] Date range picker with presets (last hour, 24h, 7d, 30d, custom)
- [ ] Expandable rows for quick detail preview
- [ ] Typecheck passes
- [ ] Unit tests for audit log filtering
- [ ] Verify in browser using dev-browser skill

---

### US-021: Audit log detail view
**Description:** As an SRE, I want to view detailed audit log entries so that I can understand exactly what happened.

**Linear Labels:** `ui`, `frontend`, `audit`, `phase-4`

**Blocked By:** US-020

**Acceptance Criteria:**
- [ ] Slide-out panel or modal showing full audit entry details
- [ ] Display full context/metadata with JSON syntax highlighting
- [ ] Links to related service or execution if applicable
- [ ] Copy to clipboard button for JSON data
- [ ] Previous/Next navigation between entries
- [ ] Typecheck passes
- [ ] Unit tests for detail view
- [ ] Verify in browser using dev-browser skill

---

### US-022: Health check and metrics page
**Description:** As an SRE, I want to view Medic's own health status so that I can ensure the monitoring system is healthy.

**Linear Labels:** `ui`, `frontend`, `monitoring`, `phase-4`

**Blocked By:** US-005, US-006

**Acceptance Criteria:**
- [ ] Display Medic API health status with visual indicator (green/yellow/red)
- [ ] Show component health: Database connection, Worker status, WebSocket server
- [ ] Link to Prometheus metrics endpoint (`/metrics`)
- [ ] Configurable link to Grafana dashboard (via env var `VITE_GRAFANA_URL`)
- [ ] Display current version and uptime
- [ ] Real-time updates via WebSocket
- [ ] Typecheck passes
- [ ] Unit tests for health components
- [ ] Verify in browser using dev-browser skill

---

### US-023: Settings page
**Description:** As a user, I want to configure my UI preferences so that I can customize my experience.

**Linear Labels:** `ui`, `frontend`, `settings`, `phase-4`

**Blocked By:** US-006

**Acceptance Criteria:**
- [ ] Theme toggle (light/dark mode) with live preview
- [ ] Auto-refresh interval configuration (for polling fallback): 15s, 30s, 60s, disabled
- [ ] Default filters persistence (remember last-used filters per page)
- [ ] Notification preferences (browser notifications on/off)
- [ ] Keyboard shortcuts enabled/disabled toggle
- [ ] Settings persisted in localStorage
- [ ] Reset to defaults button with confirmation
- [ ] Typecheck passes
- [ ] Unit tests for settings persistence
- [ ] Verify in browser using dev-browser skill

---

### US-024: Error handling and loading states
**Description:** As a user, I want clear feedback during loading and errors so that I understand the application state.

**Linear Labels:** `ui`, `frontend`, `ux`, `phase-4`

**Blocked By:** US-002

**Acceptance Criteria:**
- [ ] Skeleton loaders for all data-fetching components (matching Linq theme)
- [ ] Error boundaries to catch and display React errors gracefully
- [ ] API error handling with user-friendly messages (not raw error text)
- [ ] Retry button for failed requests
- [ ] Network offline indicator (banner)
- [ ] WebSocket disconnected indicator with reconnection status
- [ ] 404 page for invalid routes (styled with Medic branding)
- [ ] 500/error page for unrecoverable errors
- [ ] Typecheck passes
- [ ] Unit tests for error boundary
- [ ] Verify in browser using dev-browser skill

---

### US-025: Responsive design and accessibility
**Description:** As a user, I want the UI to work on different screen sizes and be accessible so that everyone can use it.

**Linear Labels:** `ui`, `frontend`, `accessibility`, `phase-4`

**Blocked By:** US-002

**Acceptance Criteria:**
- [ ] Mobile-friendly navigation (hamburger menu, bottom nav consideration)
- [ ] Tables scroll horizontally on small screens with sticky first column
- [ ] Cards stack vertically on mobile
- [ ] Touch-friendly button sizes (min 44x44px tap targets)
- [ ] Tested on breakpoints: 320px, 768px, 1024px, 1440px
- [ ] Keyboard navigation for all interactive elements
- [ ] ARIA labels on icons and non-text elements
- [ ] Focus indicators visible in both light and dark mode (using #4F9FDF outline)
- [ ] Screen reader tested with VoiceOver and NVDA
- [ ] Automated accessibility audit with axe-core (zero violations)
- [ ] Typecheck passes
- [ ] Accessibility audit documented
- [ ] Verify in browser using dev-browser skill

---

### US-026: Observability with Grafana Faro
**Description:** As a product owner, I need frontend observability so that we understand performance and errors in production.

**Linear Labels:** `ui`, `frontend`, `observability`, `phase-4`

**Blocked By:** US-001

**Acceptance Criteria:**
- [ ] Integrate Grafana Faro SDK for frontend observability
- [ ] Configure Faro to send to existing Grafana Cloud/Loki instance
- [ ] Track page views and navigation
- [ ] Track Web Vitals (LCP, FID, CLS, TTFB)
- [ ] Capture JavaScript errors with stack traces
- [ ] Capture failed API requests
- [ ] Track key user actions: service created, service muted, playbook executed, alert viewed
- [ ] Session replay (optional, if privacy-acceptable)
- [ ] User ID correlation (API key hash, not raw key)
- [ ] Privacy: no PII in telemetry, configurable opt-out
- [ ] Grafana dashboard for frontend metrics
- [ ] Typecheck passes
- [ ] Unit tests for Faro initialization

---

### US-027: Documentation and runbook
**Description:** As a developer and operator, I need documentation so that I can understand, deploy, and troubleshoot the UI.

**Linear Labels:** `ui`, `frontend`, `documentation`, `phase-4`

**Acceptance Criteria:**
- [ ] README.md with: overview, local setup, development workflow, testing
- [ ] Architecture Decision Records (ADRs) for: component library choice, state management, real-time strategy
- [ ] Storybook deployed with all components documented
- [ ] Deployment guide: Docker build, environment variables, nginx configuration
- [ ] Runbook: common issues, debugging steps, log locations, rollback procedure
- [ ] API client documentation with TypeScript types
- [ ] Keyboard shortcuts reference (in-app and docs)
- [ ] Handoff completed: Ops team briefed on deployment and monitoring
- [ ] Demo/walkthrough recorded for CS team

---

## Functional Requirements

- FR-1: The UI must authenticate users via API key before allowing access to any functionality
- FR-2: The UI must provide real-time updates via WebSocket with automatic reconnection and polling fallback
- FR-3: The UI must allow full CRUD operations on services (create, read, update, deactivate)
- FR-4: The UI must display active and historical alerts with filtering, sorting, and real-time updates
- FR-5: The UI must allow muting/unmuting services with duration options, confirmation, and audit logging
- FR-6: The UI must support full playbook lifecycle: create, edit, view, execute, delete
- FR-7: The UI must support playbook approval workflows (approve/reject pending executions)
- FR-8: The UI must provide access to audit logs with filtering, search, and CSV export
- FR-9: The UI must display Medic's own health status with real-time updates
- FR-10: The UI must persist user preferences (theme, settings) locally
- FR-11: The UI must handle API and WebSocket errors gracefully with user-friendly messages and retry options
- FR-12: The UI must be fully responsive (mobile, tablet, desktop) and WCAG 2.1 AA compliant
- FR-13: The UI must support light and dark themes following Linq brand guidelines
- FR-14: The UI must display Linq branding in the footer (Cube logo, "Built by Linq")
- FR-15: The UI must provide keyboard shortcuts for power users with discoverability (? for help)
- FR-16: The UI must integrate with Grafana Faro for frontend observability

## Non-Goals (Out of Scope)

- User management and role-based access control (uses existing API key auth)
- Push notifications to mobile devices
- Internationalization (i18n) - English only for now
- Offline mode / Progressive Web App features
- Integration with external identity providers (SSO/SAML/OAuth)
- Custom dashboard widgets or user-configurable layouts
- Mobile native apps
- Environment switching within UI (separate deployments for dev/prod)

## Design Considerations

### Linq Brand Compliance

**Logo Usage (per Brand Guidelines):**
- Use "The Cube" logo in footer (appropriate for internal tools)
- Light mode: Black Cube on light background (#141414)
- Dark mode: White Cube on dark background (#FFFFFF)
- Maintain 0.5x clear space around logo
- Never distort, crop, add effects, or change colors of logo

**Color Palette (from Linq Brand Guidelines page 12):**

| Color Name | Hex | RGB | Usage |
|------------|-----|-----|-------|
| Black | #141414 | R20, G20, B20 | Primary text (light mode), backgrounds (dark mode) |
| Cream | #FCF9E9 | R252, G249, B233 | Backgrounds (light mode), subtle highlights |
| Sage | #B0BFB7 | R176, G191, B183 | Borders, muted text, secondary elements |
| Linq Blue | #4F9FDF | R79, G159, B223 | Primary actions, links, focus states |
| Navy | #1B3D67 | R27, G61, B103 | Headers, primary buttons (light mode) |
| Linq Green | #83B149 | R131, G177, B73 | Success, healthy status, positive actions |
| Lime | #E8DF6E | R232, G223, B110 | Warning states, attention |

**Typography (per Brand Guidelines):**
- **Geist**: Headlines, body text (FK Display alternative for web)
- **Geist Mono**: Numerals, technical specs, buttons, code, timestamps
- Leading: 120%, Tracking: 0%

**Medic-specific Additions:**
- Medic logo in header (provided icon)
- Status colors harmonized with Linq palette while maintaining ADA compliance

### Keyboard Shortcuts Reference

| Shortcut | Action |
|----------|--------|
| `?` | Open keyboard shortcuts help |
| `g d` | Go to Dashboard |
| `g s` | Go to Services |
| `g a` | Go to Alerts |
| `g p` | Go to Playbooks |
| `g l` | Go to Audit Logs |
| `/` or `⌘K` | Open command palette / search |
| `Escape` | Close modal, clear selection |
| `t` | Toggle theme |
| `n` | New item (context-dependent) |
| `e` | Edit selected item |
| `m` | Mute/unmute selected service |
| `r` | Refresh current view |
| `↑↓` | Navigate list items |
| `Enter` | Open selected item |

### UI/UX Guidelines
- Clean, professional design appropriate for operations tooling
- WCAG 2.1 AA accessibility compliance (verified with axe-core)
- Consistent iconography using Lucide icons
- Toast notifications for action feedback (success/error)
- Confirm destructive or impactful actions with explicit dialogs
- Tooltips include keyboard shortcuts where applicable

### Component Library Evaluation Criteria
Evaluate these options and select based on:
- Accessibility out of the box (ARIA, keyboard nav)
- Theming/customization support (CSS variables, design tokens)
- Bundle size impact
- Community activity and maintenance
- TypeScript support quality

**Options to evaluate:**
1. **shadcn/ui** - Radix primitives, Tailwind, copy-paste components (most flexible)
2. **Radix UI** - Unstyled primitives, maximum control
3. **Mantine** - Full-featured, excellent DX, good accessibility
4. **Chakra UI** - Full component library, good accessibility

## Technical Considerations

### Frontend Stack
- React 18+ with TypeScript (strict mode)
- Vite for build tooling
- React Router v6 for routing
- TanStack Query (React Query) v5 for server state
- Zustand for client state (theme, settings)
- Tailwind CSS for styling
- Geist font family (npm package available)
- Vitest + React Testing Library for unit tests
- Playwright for E2E tests
- Storybook for component documentation
- Grafana Faro for observability

### Real-Time Updates Architecture
```
┌─────────────────────────────────────────────────┐
│  Browser (React App)                            │
│  ├── WebSocket Client                           │
│  │   └── Connects to /ws                        │
│  ├── React Query Cache                          │
│  │   └── Updated on WS events                   │
│  └── Polling Fallback (30s)                     │
│       └── Used when WS unavailable              │
└─────────────────────────────────────────────────┘
         │ WebSocket
         ▼
┌─────────────────────────────────────────────────┐
│  nginx (reverse proxy)                          │
│  └── /ws → medic-api:5000/ws (upgrade)         │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│  medic-api (Flask + Flask-SocketIO)             │
│  ├── WebSocket handler                          │
│  └── Emits events on DB changes                 │
└─────────────────────────────────────────────────┘
```

### Deployment Architecture
```
┌─────────────────────────────────────────────────┐
│  nginx container (medic-ui)                     │
│  ├── /api/*     → proxy to medic-api:5000      │
│  ├── /ws        → proxy WebSocket (upgrade)    │
│  ├── /docs/*    → proxy to medic-api:5000      │
│  ├── /metrics   → proxy to medic-api:5000      │
│  └── /*         → serve static React build      │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│  medic-api container (Flask + SocketIO)         │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│  postgres container                             │
└─────────────────────────────────────────────────┘
```

### Docker Configuration
```dockerfile
# ui/Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL=/api
ARG VITE_WS_URL=/ws
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
COPY env.sh /docker-entrypoint.d/env.sh
RUN chmod +x /docker-entrypoint.d/env.sh
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Environment Variables
| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | API base URL | `/api` |
| `VITE_WS_URL` | WebSocket URL | `/ws` |
| `VITE_GRAFANA_URL` | Link to Grafana dashboard | (optional) |
| `VITE_FARO_URL` | Grafana Faro collector URL | (optional) |
| `VITE_VERSION` | App version for footer | from package.json |

### Browser Support
- Chrome (last 2 versions)
- Firefox (last 2 versions)
- Safari (last 2 versions)
- Edge (last 2 versions)

## Success Metrics

- Users can perform 95% of administrative tasks without CLI or direct API calls
- Largest Contentful Paint (LCP) < 1.5 seconds
- Time to Interactive (TTI) < 2 seconds
- Cumulative Layout Shift (CLS) < 0.1
- All critical user flows completable in under 5 clicks
- Zero WCAG 2.1 AA violations (automated testing)
- Test coverage: >80% for components and utilities
- E2E tests cover all critical paths (service CRUD, playbook execution, approvals)
- Real-time updates received within 500ms of server event
- WebSocket reconnection successful within 30 seconds
- Error rate < 0.1% of page loads (tracked via Faro)

## Open Questions

*All questions resolved:*

1. ~~Real-time updates~~ → WebSocket with polling fallback
2. ~~Component library~~ → Evaluate shadcn/ui, Radix, Mantine, Chakra
3. ~~Environment switching~~ → Separate deployments for dev/prod
4. ~~Branding~~ → Linq Brand Guidelines with Medic logo
5. ~~Playbook editing~~ → Full CRUD in UI
6. ~~Linq logo~~ → Use "The Cube" (black on light, white on dark)
7. ~~Keyboard shortcuts~~ → Comprehensive shortcuts with `?` help modal
8. ~~Grafana dashboards~~ → Configurable via `VITE_GRAFANA_URL` env var
9. ~~WebSocket backend~~ → Included as US-004
10. ~~Analytics~~ → Grafana Faro for frontend observability
