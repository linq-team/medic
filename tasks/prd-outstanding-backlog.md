# PRD: Outstanding Backlog & PR #10 Remediation

## Overview

This PRD captures all remaining unimplemented work from the SRE backlog, organized into actionable work streams. It also includes remediation items identified during the PR #10 code review for the Terraform self-contained deployment feature.

## Work Streams

### 1. PR #10 Remediation (Terraform/CD Pipeline Fixes)

Issues found during code review of PR #10 (`feature/terraform-self-contained-deployment`). These should be addressed before the next production deployment.

#### 1.1 Fix Dev Deploy ECR Image Availability

**Priority:** High
**Problem:** The CD pipeline triggers on `pull_request` for dev, but CI only pushes images to ECR on `push` to main. Dev deployments will find no ECR image and fail silently. Currently masked by `skip_dev=true` default.
**Solution:** Either:
- (A) Push images to ECR on PR builds with a PR-specific tag (e.g., `pr-<number>`), or
- (B) Have dev deployments use the `latest` tag from main, or
- (C) Add a pre-check step that verifies the image exists before attempting deploy and provides a clear skip message

**Files:** `.github/workflows/build.yml`, `.github/workflows/cd-eks.yml`
**Tests:** Verify dev deployment either succeeds with correct image or skips with clear message

#### 1.2 Remove Dead `ingress_certificate_arn` Variable

**Priority:** Medium
**Problem:** Both environments still declare the `ingress_certificate_arn` variable, but it is no longer referenced in `main.tf` (replaced by `module.acm.certificate_arn`). Dead code.
**Solution:** Remove the variable from both `terraform/environments/dev/variables.tf` and `terraform/environments/prod/variables.tf`.
**Files:** `terraform/environments/dev/variables.tf`, `terraform/environments/prod/variables.tf`
**Tests:** `terraform validate` and `terraform plan` pass after removal

#### 1.3 Fix `values.yaml` Secrets Manager Path Defaults

**Priority:** Medium
**Problem:** Helm `values.yaml` defaults reference `medic/production/...` paths using "production" instead of "prod". Standalone Helm installs with defaults would get incorrect Secrets Manager paths. While Terraform overrides these per environment, the defaults should be correct.
**Solution:** Update `values.yaml` defaults to use `medic/prod/app-secrets` and `medic/prod/rds-credentials` (or make them empty with a comment that Terraform sets these).
**Files:** `helm/medic/values.yaml`
**Tests:** `helm lint` passes; verify Terraform still overrides correctly

#### 1.4 Reduce Dev/Prod Terraform Code Duplication

**Priority:** Low
**Problem:** `terraform/environments/dev/main.tf` and `terraform/environments/prod/main.tf` are ~70% identical. DRY violation.
**Solution:** Extract shared configuration into a reusable Terraform module (e.g., `terraform/modules/medic-environment/`) that both environments call with env-specific variables. Keep environment directories as thin wrappers.
**Files:** `terraform/modules/medic-environment/` (new), `terraform/environments/dev/main.tf`, `terraform/environments/prod/main.tf`
**Tests:** `terraform plan` produces identical resources before and after refactor for both environments

#### 1.5 Clarify CD Pipeline Concurrency Group

**Priority:** Low
**Problem:** The concurrency group expression in `cd-eks.yml` uses a ternary to dynamically select environment, which is non-obvious to readers.
**Solution:** Add an inline comment explaining the logic, or refactor to use a named job output for the environment name.
**Files:** `.github/workflows/cd-eks.yml`
**Tests:** YAML lint passes; verify concurrent deployments to same environment are still blocked

#### 1.6 Fix notify-failure Job Dependency Chain

**Priority:** Medium
**Problem:** The `notify-failure` job may not trigger correctly when upstream jobs are skipped (e.g., `deploy-dev` is skipped). GitHub Actions `needs` with `if: failure()` does not trigger when dependencies are skipped.
**Solution:** Update the `notify-failure` job condition to `if: always() && (needs.deploy-dev.result == 'failure' || needs.deploy-prod.result == 'failure')` or similar pattern that accounts for skipped jobs.
**Files:** `.github/workflows/cd-eks.yml`
**Tests:** Verify notification fires on actual failures; verify it does NOT fire when jobs are merely skipped

---

### 2. Siren Project - Operational Readiness (SRE-1 through SRE-6)

These tickets belong to the **Siren** project and address operational readiness gaps. They are cross-cutting concerns that apply to the Siren incident management system.

#### 2.1 Complete Test Coverage (SRE-1)

**Priority:** High
**Linear:** [SRE-1](https://linear.app/linq/issue/SRE-1)
**Scope:**
- Fix existing tests to pass reliably (remove soft-fail from CI)
- Add integration tests for Slack event/command handlers, PagerDuty, Linear, Bedrock AI
- Add E2E tests for full incident lifecycle
- Set up 80%+ coverage threshold

#### 2.2 Manual Test Plan & QA Signoff (SRE-2)

**Priority:** High
**Linear:** [SRE-2](https://linear.app/linq/issue/SRE-2)
**Scope:**
- Document manual test plan for all incident flows
- Document edge cases (concurrent updates, large volumes, network failures)
- Define QA signoff process

#### 2.3 Production Alerting Rules (SRE-3)

**Priority:** Urgent
**Linear:** [SRE-3](https://linear.app/linq/issue/SRE-3)
**Scope:**
- Implement Prometheus alerting rules for availability, error rates, latency SLOs
- Configure alert routing (Critical -> PagerDuty, Warning -> Slack)
- Create runbook links in annotations

#### 2.4 Operational Runbook (SRE-4)

**Priority:** High
**Linear:** [SRE-4](https://linear.app/linq/issue/SRE-4)
**Scope:**
- Create operational runbook for on-call engineers
- Create support team documentation
- Link runbooks from monitoring alerts

#### 2.5 Ownership & Handoff (SRE-5)

**Priority:** Medium
**Linear:** [SRE-5](https://linear.app/linq/issue/SRE-5)
**Scope:**
- Document ownership (CODEOWNERS)
- Create handoff checklist template
- Set up release notification process

#### 2.6 Debugging & Admin Tooling (SRE-6)

**Priority:** Medium
**Linear:** [SRE-6](https://linear.app/linq/issue/SRE-6)
**Scope:**
- Admin API endpoints for bulk operations
- Pre-built Loki/Grafana queries for debugging
- Connection testing tools (Slack, PagerDuty, DB, Redis)

---

### 3. Medic v2 UI - Remaining Features

#### 3.1 WebSocket Real-Time Updates (SRE-62, SRE-63)

**Priority:** High
**Linear:** [SRE-62](https://linear.app/linq/issue/SRE-62), [SRE-63](https://linear.app/linq/issue/SRE-63)
**Scope:**
- Backend: Flask-SocketIO WebSocket endpoint with event emission
- Frontend: WebSocket client with reconnection, fallback to polling
- Real-time cache updates via React Query invalidation
- Connection status indicator in UI header

#### 3.2 Keyboard Shortcuts (SRE-65)

**Priority:** Medium
**Linear:** [SRE-65](https://linear.app/linq/issue/SRE-65)
**Scope:**
- Global shortcuts (`?` help, `g d/s/a/p/l` navigation, `/` search, `t` theme)
- Context shortcuts on Services page (`n` new, `m` mute, `e` edit)
- Shortcuts respect input focus; help modal on `?`

#### 3.3 Playbook Management UI (SRE-75, SRE-76, SRE-77)

**Priority:** High
**Linear:** [SRE-75](https://linear.app/linq/issue/SRE-75), [SRE-76](https://linear.app/linq/issue/SRE-76), [SRE-77](https://linear.app/linq/issue/SRE-77)
**Scope:**
- Playbook creation form with step builder (drag-and-drop)
- Step types: Webhook, Wait, Condition, Script
- Playbook detail view with execution history and live logs
- Approval workflow with real-time pending badge via WebSocket
- Depends on WebSocket infrastructure (SRE-62/63)

#### 3.4 Audit Log Detail View (SRE-79)

**Priority:** Medium
**Linear:** [SRE-79](https://linear.app/linq/issue/SRE-79)
**Scope:**
- Full detail view with before/after JSON diff
- Syntax-highlighted changes
- Navigation between log entries

#### 3.5 Health Check & Metrics Page (SRE-80)

**Priority:** Medium
**Linear:** [SRE-80](https://linear.app/linq/issue/SRE-80)
**Scope:**
- System health indicators (API, DB, Worker, WebSocket)
- Key metrics display (total services, active alerts, heartbeats/hour)
- Link to external Grafana dashboards

#### 3.6 Responsive Design & Accessibility (SRE-83)

**Priority:** High
**Linear:** [SRE-83](https://linear.app/linq/issue/SRE-83)
**Scope:**
- Responsive layout for mobile/tablet/desktop
- WCAG 2.1 AA compliance
- Keyboard accessibility, ARIA labels, screen reader testing
- axe-core audit with 0 violations

#### 3.7 Frontend Observability with Grafana Faro (SRE-84)

**Priority:** High
**Linear:** [SRE-84](https://linear.app/linq/issue/SRE-84)
**Scope:**
- Grafana Faro Web SDK integration
- JS error capture with stack traces
- Web Vitals (LCP, FID, CLS) reporting
- Source maps upload for symbolication

---

### 4. Medic Agent for Remote Execution (SRE-21)

**Priority:** High
**Linear:** [SRE-21](https://linear.app/linq/issue/SRE-21)
**Milestone:** Phase 3: Auto-Remediation

**Scope:**
- Lightweight Rust agent binary (<5MB, <5MB idle memory)
- Connects to Medic server, authenticates via API key
- Executes pre-approved scripts from allowlist only
- Reports execution status; agent heartbeat monitored by Medic
- Prometheus metrics: script executions, skips, duration, connection status
- Structured JSON logging, optional OpenTelemetry tracing
- Platform support: Linux (x86_64, arm64), macOS (Intel, Apple Silicon)
- Package distribution: Homebrew, APT, YUM/DNF
- Systemd/launchd service files included

---

### 5. Python 3.14 Handoff (SRE-133)

**Priority:** Medium
**Linear:** [SRE-133](https://linear.app/linq/issue/SRE-133)
**Scope:**
- Clear ownership assigned for post-deployment support
- Ops team notified and briefed on rollback procedure
- Post-deployment monitoring owner identified
- Schedule post-deployment review meeting

---

### 6. Dev Cluster Provisioning (SRE-134 through SRE-146)

These tickets belong to the **o11y** project and provision the development EKS cluster (`dev-o11y-tf`). This cluster is a prerequisite for the Medic dev deployment path (see 1.1 above).

**Linear:** [SRE-134](https://linear.app/linq/issue/SRE-134) (parent)

| Ticket | Title | Priority | Depends On |
|--------|-------|----------|------------|
| SRE-135 | Create Terraform dev environment structure | High | - |
| SRE-136 | Configure dev EKS cluster | High | SRE-135 |
| SRE-137 | Configure dev node groups (static) | High | SRE-136 |
| SRE-138 | Configure Karpenter for dev with aggressive spot | High | SRE-137 |
| SRE-139 | Deploy infrastructure Helm releases for dev | Medium | SRE-138 |
| SRE-140 | Deploy observability Helm releases for dev | Medium | SRE-139 |
| SRE-141 | Configure Alloy dual-write to dev and prod backends | High | SRE-140 |
| SRE-142 | Configure dev RDS for Grafana | Medium | SRE-135 |
| SRE-143 | Configure dev secrets in AWS Secrets Manager | Medium | SRE-142, SRE-139 |
| SRE-144 | Configure dev DNS and certificates | Medium | SRE-139, SRE-140 |
| SRE-145 | Configure Alertmanager for Slack notifications | Medium | SRE-140 |
| SRE-146 | Create dev deployment documentation | Low | All above |

**Estimated Cost:** ~$200-300/month (aggressive spot, minimal resources)

---

## Implementation Order

### Phase 1: PR #10 Remediation & Quick Wins
1. Remove dead `ingress_certificate_arn` variable (1.2)
2. Fix `values.yaml` Secrets Manager path defaults (1.3)
3. Fix notify-failure job condition (1.6)
4. Clarify concurrency group comment (1.5)

### Phase 2: Dev Cluster & Pipeline
1. Dev cluster provisioning (Section 6 - o11y project)
2. Fix dev deploy ECR image availability (1.1) - after dev cluster exists
3. Reduce dev/prod Terraform duplication (1.4)

### Phase 3: Siren Operational Readiness
1. Production alerting rules (SRE-3) - Urgent
2. Test coverage (SRE-1)
3. Manual test plan (SRE-2)
4. Operational runbook (SRE-4)
5. Ownership & handoff (SRE-5)
6. Admin tooling (SRE-6)

### Phase 4: Medic v2 UI Features
1. WebSocket backend + frontend (SRE-62, SRE-63) - blocks playbook features
2. Playbook management (SRE-75, SRE-76, SRE-77)
3. Keyboard shortcuts (SRE-65)
4. Audit log detail (SRE-79)
5. Health check page (SRE-80)
6. Responsive design & accessibility (SRE-83)
7. Grafana Faro observability (SRE-84)

### Phase 5: Advanced Features
1. Medic Agent for remote execution (SRE-21)
2. Python 3.14 handoff (SRE-133)

## Principles

- **Test everything testable**: All new code must have unit tests; integration tests for external service interactions; E2E tests for critical user flows
- **DRY**: Extract shared patterns into reusable modules/components; avoid copy-paste between environments
- **No hardcoding**: Use environment variables, Terraform variables, or Helm values for all configurable values; no magic strings
- **Incremental delivery**: Each work item should be independently deployable and reviewable

## Linked Tickets

| Category | Tickets |
|----------|---------|
| PR #10 Remediation | (new - to be created) |
| Siren Readiness | SRE-1, SRE-2, SRE-3, SRE-4, SRE-5, SRE-6 |
| Medic v2 UI | SRE-62, SRE-63, SRE-65, SRE-75, SRE-76, SRE-77, SRE-79, SRE-80, SRE-83, SRE-84 |
| Medic Agent | SRE-21 |
| Python 3.14 Handoff | SRE-133 |
| Dev Cluster | SRE-134, SRE-135, SRE-136, SRE-137, SRE-138, SRE-139, SRE-140, SRE-141, SRE-142, SRE-143, SRE-144, SRE-145, SRE-146 |
