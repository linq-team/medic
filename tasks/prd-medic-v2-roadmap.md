# PRD: Medic v2 — Self-Healing Heartbeat Monitoring

## Definition of Done

> **This is the baseline. A feature isn't "done" until all of this is true.**

- [ ] **Tests** — Unit, integration, end-to-end. Passing tests are table stakes.
- [ ] **QA** — Manual test plan completed. Edge cases checked. QA signoff.
- [ ] **Monitoring** — Alerts are set. It's dashboarded. We know if it breaks before a user tells us.
- [ ] **Telemetry** — Usage and performance is tracked. We know what's working and what isn't.
- [ ] **Tooling** — Internal and customer-facing tools exist. If it's hard to debug or use, it's not done.
- [ ] **Runbook** — Docs for how it works and how to talk about it exist. Support and Sales know what it is.
- [ ] **Handoff** — Clear ownership. Ops, Sales, CS — they all know what changed and what to do with it.

---

## Introduction

Medic is a dead man's switch / heartbeat monitoring service that allows services, workers, and jobs to report their health status. When heartbeats stop arriving, Medic alerts the appropriate teams.

**This PRD outlines Medic v2** — a comprehensive upgrade that:
1. Closes feature gaps with competitors (healthchecks.io, Cronitor, Dead Man's Snitch)
2. Introduces **auto-remediation and playbook execution** — a unique feature for self-hosted monitoring
3. Supports both human-approved and fully autonomous remediation workflows
4. Provides a simple admin dashboard for configuration and monitoring

---

## Goals

- Provide API authentication and rate limiting for production-grade security
- Add webhook support for custom integrations beyond Slack/PagerDuty
- Implement maintenance windows to prevent alert fatigue during planned outages
- Track job duration and support start/complete signals for richer monitoring
- **Enable playbook-based auto-remediation** that can restart services, run scripts, or trigger external systems without human intervention
- Support human-in-the-loop approval workflows for sensitive remediations
- Provide a simple admin dashboard for service management and playbook configuration

---

## Phases Overview

| Phase | Focus | Key Deliverables |
|-------|-------|------------------|
| **Phase 1** | Foundation | API auth, webhooks, rate limiting, flexible routing, working hours |
| **Phase 2** | Enhanced Monitoring | Maintenance windows, duration tracking, start/complete signals |
| **Phase 3** | Auto-Remediation | Playbooks, Rust agent, webhook triggers, approval workflows |
| **Admin Dashboard** | UI | Service list, teams, alerts, mute controls, API keys, playbook editor |

---

## Linear Tickets

### Phase 1: Foundation
| ID | Title | Priority |
|----|-------|----------|
| SRE-7 | API Key Authentication | High |
| SRE-8 | Rate Limiting | High |
| SRE-9 | Webhook Notifications | High |
| SRE-10 | Flexible Alert Routing | Medium |
| SRE-11 | Team-Based Routing | Medium |
| SRE-12 | Working Hours / Alert Schedules | Medium |

### Phase 2: Enhanced Monitoring
| ID | Title | Priority |
|----|-------|----------|
| SRE-14 | Maintenance Windows | High |
| SRE-15 | Start/Complete Signals | High |
| SRE-16 | Duration Tracking & Alerts | Medium |
| SRE-17 | Grace Periods & Flexible Schedules | Medium |

### Phase 3: Auto-Remediation
| ID | Title | Priority |
|----|-------|----------|
| SRE-18 | Playbook Definition | High |
| SRE-19 | Webhook-Based Remediation | High |
| SRE-20 | Built-in Script Execution | High |
| SRE-21 | Medic Agent for Remote Execution | High |
| SRE-22 | Approval Workflows | Medium |
| SRE-23 | Playbook Execution Engine | High |
| SRE-24 | Remediation Audit Log | Medium |
| SRE-25 | API/Webhook Triggered Remediation | High |

### Admin Dashboard
| ID | Title | Priority |
|----|-------|----------|
| SRE-13 | Admin Dashboard | Low |

---

## Phase 1: Foundation

### SRE-7: API Key Authentication
**Description:** Secure the Medic API with API keys so that only authorized services can send heartbeats and manage configurations.

**Key Requirements:**
- API keys with name, scopes (read/write/admin), optional expiration
- Keys stored hashed (bcrypt/argon2)
- All endpoints except `/health/*` require authentication
- Prometheus metrics for auth failures

---

### SRE-8: Rate Limiting
**Description:** Rate limiting on the API to prevent misbehaving clients from overwhelming the system.

**Key Requirements:**
- Configurable limits per API key (default: 100 req/min heartbeats, 20 req/min management)
- Standard rate limit headers (`X-RateLimit-*`)
- Redis or in-memory backend

---

### SRE-9: Webhook Notifications
**Description:** Configure webhook URLs for alert notifications to integrate with any system.

**Key Requirements:**
- Per-service or global webhook configuration
- Custom headers support
- Retry with exponential backoff (1s, 5s, 30s)
- Delivery status tracking

---

### SRE-10: Flexible Alert Routing
**Description:** Route alerts to multiple destinations based on service configuration.

**Key Requirements:**
- Multiple notification targets per service (Slack, PagerDuty, webhooks)
- "Notify all" vs "notify until success" modes
- Conditional routing based on priority
- PagerDuty handles escalation policies (not Medic)

---

### SRE-11: Team-Based Routing
**Description:** Route alerts to different Slack channels based on service team.

**Key Requirements:**
- Teams with associated Slack channel IDs
- Services reference team by name
- Fallback to default channel

---

### SRE-12: Working Hours / Alert Schedules
**Description:** Define working hours per service for different routing during business hours vs off-hours.

**Key Requirements:**
- Schedule definition (e.g., Mon-Fri 9am-6pm)
- Different routing for "during hours" vs "after hours"
- Proper IANA timezone support (not abbreviations like CST)
- Correct DST transition handling
- Leap year support
- Holiday calendar support (optional)

---

## Phase 2: Enhanced Monitoring

### SRE-14: Maintenance Windows
**Description:** Schedule maintenance windows to suppress alerts during expected downtime.

**Key Requirements:**
- One-time or recurring windows (cron expression)
- Affected services or "all"
- Proper timezone/DST/leap year handling
- Notifications on window start/end

---

### SRE-15: Start/Complete Signals
**Description:** Signal job start and completion for duration tracking and hung job detection.

**Key Requirements:**
- New statuses: `STARTED`, `COMPLETED`, `FAILED`
- Optional `run_id` to correlate events
- Alert on exceeded `max_duration`
- Alert on STARTED without COMPLETED

---

### SRE-16: Duration Tracking & Alerts
**Description:** Track job duration and alert on threshold violations.

**Key Requirements:**
- Historical duration data (last 100 runs)
- Statistics API (avg, p50, p95, p99)
- Grafana dashboard integration

---

### SRE-17: Grace Periods & Flexible Schedules
**Description:** Configure grace periods and flexible schedules to reduce false alerts.

**Key Requirements:**
- `grace_period_seconds` configuration
- Cron expressions for expected schedule
- "At least N heartbeats per hour" mode
- Proper DST handling for cron (skipped/repeated hours)

---

## Phase 3: Auto-Remediation

### SRE-18: Playbook Definition
**Description:** Define playbooks in YAML specifying remediation steps.

**Key Requirements:**
- Steps: `webhook`, `script`, `wait`, `condition`
- Trigger conditions (service pattern, consecutive failures)
- Approval settings (`none`, `required`, `timeout:Xm`)
- Stored in database, versionable

**Example:**
```yaml
name: restart-worker
description: Restart the worker service and verify recovery
trigger:
  service_pattern: "worker-*"
  consecutive_failures: 3
approval: none
steps:
  - name: restart-service
    type: webhook
    url: "https://internal-api/restart"
    method: POST
    body:
      service: "${SERVICE_NAME}"
  - name: wait-for-recovery
    type: wait
    duration: 30s
  - name: verify-heartbeat
    type: condition
    check: heartbeat_received
    timeout: 60s
    on_failure: escalate
```

---

### SRE-19: Webhook-Based Remediation
**Description:** Playbooks trigger external webhooks for integration with Rundeck, AWS SSM, Kubernetes, etc.

**Key Requirements:**
- Variable substitution (`${SERVICE_NAME}`, `${ALERT_ID}`, etc.)
- Configurable success conditions
- Secrets encrypted at rest

---

### SRE-20: Built-in Script Execution
**Description:** Execute predefined scripts for simple remediations without external systems.

**Key Requirements:**
- Pre-registered scripts only (no arbitrary execution)
- Sandboxed execution with resource limits
- Output captured and logged

---

### SRE-21: Medic Agent for Remote Execution
**Description:** Lightweight agent for executing remediation on managed hosts.

**Key Requirements:**
- **Written in Rust** (not Go) for minimal resource usage
- Idle memory < 5MB, binary < 5MB
- No garbage collector
- Linux (x86_64, arm64) and macOS (Intel, Apple Silicon)
- Package managers: Homebrew, APT, YUM/DNF

**Observability:**
- `medic_agent_script_executions_total{script, status}`
- `medic_agent_script_skipped_total{script, reason}` — for unregistered scripts
- Structured JSON logging with skip reasons
- Skipped scripts reported to Medic server for alerting

---

### SRE-22: Approval Workflows
**Description:** Require human approval for sensitive playbooks.

**Key Requirements:**
- Slack interactive buttons (Accept/Decline)
- PagerDuty deep link to Admin Portal approval page
- Admin Portal shows full context before decision
- Audit log of all approvals/rejections

---

### SRE-23: Playbook Execution Engine
**Description:** Reliable playbook execution with state persistence.

**Key Requirements:**
- State machine: pending_approval, running, waiting, completed, failed, cancelled
- Survives Medic restart
- Circuit breaker for runaway executions
- Prometheus metrics

---

### SRE-24: Remediation Audit Log
**Description:** Complete log of all remediation actions for compliance.

**Key Requirements:**
- All executions, webhooks, scripts, approvals logged
- Queryable and exportable (JSON, CSV)
- Configurable retention (default 90 days)

---

### SRE-25: API/Webhook Triggered Remediation
**Description:** Trigger playbooks via API, webhook, or MCP — not just heartbeat failures.

**Use Cases:**
- External monitoring triggers playbook
- ChatOps: `/restart worker-1` via MCP
- Manual intervention from Admin Dashboard
- CI/CD pipeline triggers smoke test

**Key Requirements:**
- `POST /v2/playbooks/{id}/execute` endpoint
- Webhook endpoint for external systems
- MCP tool: `execute_playbook`
- Rate limiting on trigger endpoints

---

## Admin Dashboard

### SRE-13: Admin Dashboard
**Description:** Simple web dashboard for managing Medic configuration.

**Features:**
- Service list with status and last heartbeat
- Teams management with Slack channel mappings
- Alert history with filtering
- Mute controls with reason and duration
- API key management (create, rotate, revoke)
- Playbook builder/editor

---

## Non-Goals (Out of Scope)

- **AI-assisted remediation** — Future consideration; v2 focuses on deterministic playbooks
- **Cloud sync / SaaS features** — Medic v2 is fully self-hosted
- **Full APM/tracing** — Medic monitors heartbeats, not distributed traces
- **Log aggregation** — Integrate with existing log systems, don't replace them
- **Replacing PagerDuty/Opsgenie** — Medic complements incident management; PagerDuty owns escalation

---

## Technical Considerations

### Database
- PostgreSQL remains primary store
- Add Redis for rate limiting and playbook execution state (optional, falls back to Postgres)
- Migration path for existing installations

### Agent Architecture
- **Rust** chosen over Go for minimal resource footprint (no GC, smaller binary)
- Communication via HTTPS long polling
- Agent-to-server authentication via API key
- Only pre-registered scripts can execute

### Time Handling
- All times stored in UTC internally
- IANA timezone names required (e.g., `America/Chicago`, not `CST`)
- Proper DST transition handling
- Leap year support for date-based schedules

### Security
- API keys hashed with bcrypt/argon2
- Secrets for playbooks encrypted at rest (AES-256-GCM)
- Agent commands restricted to pre-registered scripts
- Approval workflow prevents accidental autonomous actions

### Backwards Compatibility
- All v1 API endpoints continue working
- API versioning: `/v1/` (current), `/v2/` (new features)
- Gradual migration path documented

---

## Success Metrics

- **API Security:** 0 unauthenticated requests to protected endpoints
- **Alert Accuracy:** <5% false positive rate with maintenance windows and grace periods
- **Remediation Coverage:** 50% of alerts have associated playbooks within 6 months
- **MTTR Reduction:** 30% reduction in mean time to recovery for services with playbooks
- **Agent Efficiency:** <5MB memory usage on deployed agents

---

## Open Questions

1. Should playbook definitions be stored in Git (GitOps) or database? Or both with sync?
2. What's the agent update/upgrade strategy? Auto-update or manual?
3. Should we support OPA (Open Policy Agent) for fine-grained authorization?
4. Integration with Terraform/Pulumi for infrastructure-as-code remediation?
5. How do we handle playbook versioning when a playbook changes mid-execution?
