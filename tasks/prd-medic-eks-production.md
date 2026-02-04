# PRD: Medic EKS Production Deployment

## Git Workflow

1. Pull down latest `main` branch before starting work
2. Create a feature branch from `main`: `git checkout -b feature/medic-eks-production`
3. Each user story should have a corresponding Linear ticket created before implementation
4. Commit messages must reference the Linear ticket: `feat: [SRE-XXX] - Description`
5. All commits should be co-authored with Claude

## Linear Tickets

Before starting implementation:
1. Create a Linear project or initiative for "Medic EKS Production Deployment"
2. Create individual tickets for each user story (US-001 through US-028)
3. Use the ticket ID in commit messages and PR descriptions
4. Link related tickets using Linear's "blocked by" relationships for dependencies

## Introduction

Deploy Medic to Amazon EKS with production-grade security, observability, and reliability. This PRD addresses critical security vulnerabilities identified in PR #2 review, implements proper Kubernetes infrastructure, and establishes CI/CD pipelines for automated deployments.

The deployment targets a Dev environment initially (with Production flag for future promotion), uses AWS Secrets Manager with External Secrets Operator for secret management, and is sized for small-scale usage (1-2 replicas, <100 monitored services).

## Goals

- Fix all critical security vulnerabilities before production deployment
- Deploy Medic API and Worker to EKS with proper separation of concerns
- Implement distributed rate limiting via Redis
- Establish observability stack (metrics, logs, traces)
- Create CI/CD pipeline with environment-based deployment flags
- Achieve 99.9% uptime SLA capability

## User Stories

---

### Phase 1: Security Hardening (Blockers)

These must be completed before any production deployment.

---

### US-001: Fix SSRF vulnerability in webhook steps
**Description:** As a security engineer, I need webhook URLs validated to prevent Server-Side Request Forgery attacks against internal services.

**Acceptance Criteria:**
- [ ] Create `Medic/Core/url_validator.py` module with `validate_url()` function
- [ ] Block private IP ranges: 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16
- [ ] Block localhost, internal hostnames, and cloud metadata endpoints (169.254.169.254)
- [ ] Only allow http/https schemes
- [ ] DNS resolution check to catch DNS rebinding (resolve hostname, validate IP)
- [ ] Integrate into `playbook_engine.py` `execute_webhook_step()` function
- [ ] Integrate into `webhook_delivery.py` `_send_request()` function
- [ ] Add `MEDIC_ALLOWED_WEBHOOK_HOSTS` env var for explicit allowlist (optional)
- [ ] Return 400 error with "Invalid webhook URL" message (no internal details)
- [ ] Add 15+ unit tests covering all blocked ranges and edge cases
- [ ] Typecheck/lint passes

---

### US-002: Fix timing attack in API key verification
**Description:** As a security engineer, I need API key verification to be constant-time to prevent timing-based key enumeration attacks.

**Acceptance Criteria:**
- [ ] Modify `_get_api_key_from_db()` in `auth_middleware.py` to iterate ALL keys before returning
- [ ] Store matched key in variable, continue loop, return after complete iteration
- [ ] Add comment explaining timing attack mitigation
- [ ] Consider adding database index optimization for future (document as follow-up)
- [ ] Add unit test verifying all keys are checked even when match found early
- [ ] Typecheck/lint passes

---

### US-003: Fix script execution environment variable leak
**Description:** As a security engineer, I need script execution to use an allowlist of environment variables to prevent secrets from leaking to playbook scripts.

**Acceptance Criteria:**
- [ ] Create `ALLOWED_SCRIPT_ENV_VARS` constant: `["PATH", "HOME", "USER", "LANG", "LC_ALL", "TZ"]`
- [ ] Modify `execute_script_step()` in `playbook_engine.py` to filter `os.environ`
- [ ] Only pass allowlisted vars plus explicit `MEDIC_*` context vars
- [ ] Add `MEDIC_ADDITIONAL_SCRIPT_ENV_VARS` config for extending allowlist
- [ ] Document security model in code comments
- [ ] Add unit test verifying sensitive vars (MEDIC_SECRETS_KEY, DATABASE_URL) are NOT passed
- [ ] Typecheck/lint passes

---

### US-004: Add rate limiting to all endpoints
**Description:** As a security engineer, I need all endpoints rate limited to prevent abuse and DoS attacks.

**Acceptance Criteria:**
- [ ] Remove `/metrics` and `/docs` from `RATE_LIMIT_BYPASS_PREFIXES`
- [ ] Add separate higher limits for health endpoints: 1000 req/min
- [ ] Add configurable limits for `/metrics`: 100 req/min (for Prometheus scraping)
- [ ] Add configurable limits for `/docs`: 60 req/min
- [ ] Update unit tests to verify no endpoints bypass rate limiting
- [ ] Typecheck/lint passes

---

### Phase 2: Code Quality Improvements

---

### US-005: Extract shared datetime utilities
**Description:** As a developer, I need a single source of truth for datetime helpers to eliminate code duplication across 6 files.

**Acceptance Criteria:**
- [ ] Create `Medic/Core/utils/__init__.py` (empty)
- [ ] Create `Medic/Core/utils/datetime_helpers.py` with:
  - `TIMEZONE` constant (America/Chicago)
  - `now()` function returning timezone-aware datetime
  - `parse_datetime()` function handling multiple formats
- [ ] Replace `_now()` in: `playbook_engine.py`, `audit_log.py`, `slack_approval.py`, `secrets.py`, `circuit_breaker.py`, `job_runs.py`
- [ ] Replace `_parse_datetime()` where duplicated
- [ ] Delete all duplicate implementations
- [ ] All existing tests continue to pass
- [ ] Typecheck/lint passes

---

### US-006: Split playbook_engine.py into modules
**Description:** As a developer, I need the 2,672-line playbook_engine.py split into focused modules for maintainability.

**Acceptance Criteria:**
- [ ] Create `Medic/Core/playbook/` package directory
- [ ] Create `Medic/Core/playbook/__init__.py` re-exporting public API
- [ ] Create `Medic/Core/playbook/models.py` - dataclasses (PlaybookExecution, StepResult, etc.)
- [ ] Create `Medic/Core/playbook/db.py` - all database operations
- [ ] Create `Medic/Core/playbook/engine.py` - PlaybookExecutionEngine class
- [ ] Create `Medic/Core/playbook/executors/__init__.py`
- [ ] Create `Medic/Core/playbook/executors/webhook.py` - execute_webhook_step
- [ ] Create `Medic/Core/playbook/executors/script.py` - execute_script_step
- [ ] Create `Medic/Core/playbook/executors/condition.py` - execute_condition_step
- [ ] Create `Medic/Core/playbook/executors/wait.py` - execute_wait_step
- [ ] Update imports in all files that use playbook_engine
- [ ] Keep `playbook_engine.py` as facade re-exporting for backwards compatibility
- [ ] All 108 existing playbook_engine tests pass
- [ ] Typecheck/lint passes

---

### Phase 3: Redis Rate Limiter Implementation

---

### US-007: Implement RedisRateLimiter
**Description:** As an operator, I need distributed rate limiting via Redis so limits work correctly across multiple API replicas.

**Acceptance Criteria:**
- [ ] Implement `RedisRateLimiter` class in `rate_limiter.py` (replace NotImplementedError)
- [ ] Use Redis MULTI/EXEC for atomic increment and expiry
- [ ] Implement sliding window algorithm matching InMemoryRateLimiter behavior
- [ ] Add `REDIS_URL` environment variable for connection string
- [ ] Add connection pooling with configurable pool size
- [ ] Add graceful fallback to InMemoryRateLimiter if Redis unavailable
- [ ] Log warning when falling back to in-memory
- [ ] Add health check for Redis connection
- [ ] Add 20+ unit tests with Redis mocking
- [ ] Add integration test with real Redis (use testcontainers or skip if unavailable)
- [ ] Typecheck/lint passes

---

### US-008: Add rate limiter factory with auto-selection
**Description:** As an operator, I need the rate limiter to automatically select Redis or in-memory based on configuration.

**Acceptance Criteria:**
- [ ] Create `get_rate_limiter()` factory function
- [ ] If `REDIS_URL` is set, return RedisRateLimiter
- [ ] If `REDIS_URL` is not set, return InMemoryRateLimiter with warning log
- [ ] Cache limiter instance (singleton pattern)
- [ ] Update `rate_limit_middleware.py` to use factory
- [ ] Add `MEDIC_RATE_LIMITER_TYPE` env var override: `redis`, `memory`, `auto` (default)
- [ ] Typecheck/lint passes

---

### Phase 4: Docker & Container Setup

---

### US-009: Create production Dockerfile
**Description:** As a DevOps engineer, I need a production-optimized Docker image for Medic.

**Acceptance Criteria:**
- [ ] Create `Dockerfile` in repository root
- [ ] Use multi-stage build (builder + runtime)
- [ ] Base image: `python:3.11-slim-bookworm`
- [ ] Install only production dependencies (not dev)
- [ ] Run as non-root user (uid 1000)
- [ ] Set `PYTHONUNBUFFERED=1` and `PYTHONDONTWRITEBYTECODE=1`
- [ ] Expose port 8080
- [ ] Health check: `CMD curl -f http://localhost:8080/health || exit 1`
- [ ] Labels: maintainer, version, description
- [ ] .dockerignore excludes: .git, tests/, __pycache__, *.pyc, .env
- [ ] Image builds successfully
- [ ] Image size < 500MB

---

### US-010: Create Docker Compose for local development
**Description:** As a developer, I need Docker Compose to run Medic with all dependencies locally.

**Acceptance Criteria:**
- [ ] Create `docker-compose.yml` in repository root
- [ ] Services: medic-api, medic-worker, postgres, redis
- [ ] PostgreSQL 15 with persistent volume
- [ ] Redis 7 with persistent volume
- [ ] Environment variables from `.env.example`
- [ ] Health checks for all services
- [ ] API depends_on postgres and redis with health conditions
- [ ] Expose API on port 8080
- [ ] Create `.env.example` with all required variables (no real secrets)
- [ ] `docker-compose up` starts all services successfully

---

### Phase 5: Kubernetes Manifests

---

### US-011: Create Kubernetes namespace and base configuration
**Description:** As a DevOps engineer, I need Kubernetes namespace and common resources for Medic deployment.

**Acceptance Criteria:**
- [ ] Create `k8s/` directory in repository root
- [ ] Create `k8s/base/` for Kustomize base
- [ ] Create `k8s/base/namespace.yaml` - `medic` namespace with labels
- [ ] Create `k8s/base/kustomization.yaml` referencing all base resources
- [ ] Create `k8s/overlays/dev/` for dev environment
- [ ] Create `k8s/overlays/prod/` for production environment (placeholder)
- [ ] Add resource quotas for namespace (CPU: 4 cores, Memory: 8Gi for dev)
- [ ] Add network policy allowing only ingress from ALB and inter-pod communication
- [ ] `kubectl apply -k k8s/overlays/dev` succeeds (dry-run)

---

### US-012: Create API Deployment manifest
**Description:** As a DevOps engineer, I need a Kubernetes Deployment for the Medic API service.

**Acceptance Criteria:**
- [ ] Create `k8s/base/api-deployment.yaml`
- [ ] Deployment name: `medic-api`
- [ ] Replicas: 2 (configurable via overlay)
- [ ] Container resources: requests (256Mi/250m), limits (512Mi/500m)
- [ ] Liveness probe: /health/live, initialDelaySeconds: 10
- [ ] Readiness probe: /health/ready, initialDelaySeconds: 5
- [ ] Environment variables from ConfigMap and Secrets
- [ ] Pod anti-affinity for spreading across nodes
- [ ] Service account with minimal permissions
- [ ] Security context: runAsNonRoot, readOnlyRootFilesystem, drop ALL capabilities
- [ ] `kubectl apply` succeeds (dry-run)

---

### US-013: Create Worker Deployment manifest
**Description:** As a DevOps engineer, I need a separate Kubernetes Deployment for the Medic Worker (monitor + playbook execution).

**Acceptance Criteria:**
- [ ] Create `k8s/base/worker-deployment.yaml`
- [ ] Deployment name: `medic-worker`
- [ ] Replicas: 1 (single worker to avoid duplicate alerts)
- [ ] Container command override to run worker process
- [ ] Container resources: requests (256Mi/250m), limits (1Gi/1000m)
- [ ] Liveness probe: process check or /health endpoint
- [ ] Environment variables from ConfigMap and Secrets
- [ ] Security context matching API deployment
- [ ] Pod disruption budget: minAvailable: 1
- [ ] `kubectl apply` succeeds (dry-run)

---

### US-014: Create Service and Ingress manifests
**Description:** As a DevOps engineer, I need Kubernetes Service and Ingress for external access to Medic API.

**Acceptance Criteria:**
- [ ] Create `k8s/base/api-service.yaml` - ClusterIP service on port 80 -> 8080
- [ ] Create `k8s/base/ingress.yaml` - ALB Ingress Controller annotations
- [ ] Ingress annotations for: SSL redirect, health check path, target type IP
- [ ] TLS configuration with ACM certificate ARN (via overlay)
- [ ] Host-based routing: `medic.dev.example.com` (configurable)
- [ ] Path-based routing: `/` -> medic-api service
- [ ] Dev overlay sets dev hostname
- [ ] Prod overlay sets prod hostname and certificate
- [ ] `kubectl apply` succeeds (dry-run)

---

### US-015: Create ConfigMap and ExternalSecret manifests
**Description:** As a DevOps engineer, I need ConfigMap for non-sensitive config and ExternalSecret for AWS Secrets Manager integration.

**Acceptance Criteria:**
- [ ] Create `k8s/base/configmap.yaml` with non-sensitive config:
  - MEDIC_LOG_LEVEL
  - MEDIC_TIMEZONE
  - MEDIC_RATE_LIMIT_REQUESTS
  - MEDIC_RATE_LIMIT_WINDOW
- [ ] Create `k8s/base/external-secret.yaml` using External Secrets Operator
- [ ] ExternalSecret references AWS Secrets Manager path: `medic/dev/secrets`
- [ ] Maps secrets to K8s secret keys: DATABASE_URL, REDIS_URL, MEDIC_SECRETS_KEY, SLACK_API_TOKEN
- [ ] Create SecretStore resource for AWS provider
- [ ] Dev overlay uses dev secret path
- [ ] Prod overlay uses prod secret path
- [ ] Document required AWS Secrets Manager structure in README

---

### US-016: Create Horizontal Pod Autoscaler
**Description:** As a DevOps engineer, I need HPA to automatically scale API pods based on load.

**Acceptance Criteria:**
- [ ] Create `k8s/base/api-hpa.yaml`
- [ ] Target: medic-api deployment
- [ ] Min replicas: 2, Max replicas: 10
- [ ] Scale on CPU utilization > 70%
- [ ] Scale on memory utilization > 80%
- [ ] Behavior: scale up fast (15s), scale down slow (300s)
- [ ] Dev overlay: min 1, max 3
- [ ] Prod overlay: min 2, max 10
- [ ] `kubectl apply` succeeds (dry-run)

---

### Phase 6: Observability

---

### US-017: Configure structured JSON logging
**Description:** As an operator, I need structured JSON logs for CloudWatch Logs Insights queries.

**Acceptance Criteria:**
- [ ] Create `Medic/Core/logging_config.py` module
- [ ] Configure Python logging with JSON formatter
- [ ] Include fields: timestamp, level, logger, message, service, environment
- [ ] Include request context: request_id, api_key_id (if available)
- [ ] Include error context: exception type, traceback (for errors)
- [ ] Add `MEDIC_LOG_FORMAT` env var: `json` (default) or `text` (for local dev)
- [ ] Replace `logger.log(level=20, msg=...)` pattern with standard methods
- [ ] Update at least 10 key log statements to use structured format
- [ ] Typecheck/lint passes

---

### US-018: Create Prometheus ServiceMonitor
**Description:** As an operator, I need Prometheus to scrape Medic metrics for monitoring.

**Acceptance Criteria:**
- [ ] Create `k8s/base/servicemonitor.yaml` for Prometheus Operator
- [ ] Target medic-api service on /metrics endpoint
- [ ] Scrape interval: 30s
- [ ] Add metric relabeling for environment and service labels
- [ ] Verify existing metrics exposed: auth_failures, rate_limit_hits, playbook_executions
- [ ] Add `medic_info` metric with version label
- [ ] Document available metrics in README

---

### US-019: Create Grafana dashboard
**Description:** As an operator, I need a Grafana dashboard to visualize Medic health and performance.

**Acceptance Criteria:**
- [ ] Create `k8s/base/grafana-dashboard.yaml` as ConfigMap
- [ ] Dashboard panels:
  - Request rate (by endpoint, status code)
  - Error rate (4xx, 5xx)
  - Latency percentiles (p50, p95, p99)
  - Auth failures by reason
  - Rate limit hits
  - Playbook executions (started, completed, failed)
  - Webhook delivery success rate
  - Active alerts count
- [ ] Variables: environment, time range
- [ ] Alerts: Error rate > 5%, Latency p99 > 2s
- [ ] Export as JSON, embed in ConfigMap
- [ ] Dashboard loads successfully in Grafana

---

### Phase 7: CI/CD Pipeline

---

### US-020: Create GitHub Actions workflow for Docker build
**Description:** As a DevOps engineer, I need automated Docker image builds on push to main.

**Acceptance Criteria:**
- [ ] Create `.github/workflows/build.yml`
- [ ] Trigger on: push to main, pull request to main, manual dispatch
- [ ] Jobs: lint, test, build
- [ ] Lint job: ruff check, mypy
- [ ] Test job: pytest with coverage report
- [ ] Build job: docker build, tag with git SHA and `latest`
- [ ] Upload test coverage as artifact
- [ ] Cache pip dependencies between runs
- [ ] Cache Docker layers between runs
- [ ] Workflow completes in < 10 minutes

---

### US-021: Create GitHub Actions workflow for ECR push
**Description:** As a DevOps engineer, I need Docker images pushed to Amazon ECR on successful builds.

**Acceptance Criteria:**
- [ ] Extend `.github/workflows/build.yml` with deploy job
- [ ] Deploy job runs only on push to main (not PRs)
- [ ] Configure AWS credentials via OIDC (not access keys)
- [ ] Login to ECR using aws-actions/amazon-ecr-login
- [ ] Push image with tags: git SHA, `latest`, semver if tagged release
- [ ] ECR repository: `medic/api`
- [ ] Image scanning enabled on push
- [ ] Document required AWS IAM role and GitHub secrets

---

### US-022: Create GitHub Actions workflow for EKS deployment
**Description:** As a DevOps engineer, I need automated deployment to EKS with environment control.

**Acceptance Criteria:**
- [ ] Create `.github/workflows/deploy.yml`
- [ ] Trigger on: workflow_dispatch with environment input (dev/prod)
- [ ] Trigger on: successful build workflow completion (dev only, auto)
- [ ] Input: `environment` (dev/prod), `image_tag` (default: latest)
- [ ] Configure AWS credentials via OIDC
- [ ] Install kubectl and configure kubeconfig for EKS
- [ ] Run: `kubectl apply -k k8s/overlays/$ENVIRONMENT`
- [ ] Wait for rollout: `kubectl rollout status deployment/medic-api`
- [ ] Run smoke test: curl health endpoint
- [ ] Slack notification on success/failure
- [ ] Production requires manual approval (GitHub environment protection)
- [ ] Document required GitHub environments and secrets

---

### Phase 8: Database & Infrastructure

---

### US-023: Create Terraform module for RDS PostgreSQL
**Description:** As a DevOps engineer, I need Terraform to provision RDS PostgreSQL for Medic.

**Acceptance Criteria:**
- [ ] Create `terraform/` directory in repository root
- [ ] Create `terraform/modules/rds/` module
- [ ] Create `terraform/modules/rds/main.tf` with aws_db_instance resource
- [ ] Create `terraform/modules/rds/variables.tf` with configurable inputs
- [ ] Create `terraform/modules/rds/outputs.tf` exposing endpoint and credentials
- [ ] PostgreSQL version 15, instance class variable (default: db.t3.micro)
- [ ] Multi-AZ configurable (default: false for dev)
- [ ] Security group allowing inbound 5432 from EKS node security group
- [ ] Subnet group using existing VPC private subnets
- [ ] Parameter group with shared_buffers, max_connections tuned for instance size
- [ ] Automated backups: 7 days retention, preferred window
- [ ] Storage: 20GB gp3, autoscaling enabled up to 100GB
- [ ] Output connection string to AWS Secrets Manager (via aws_secretsmanager_secret_version)
- [ ] `terraform plan` succeeds

---

### US-024: Create Terraform module for ElastiCache Redis
**Description:** As a DevOps engineer, I need Terraform to provision ElastiCache Redis for rate limiting.

**Acceptance Criteria:**
- [ ] Create `terraform/modules/elasticache/` module
- [ ] Create `terraform/modules/elasticache/main.tf` with aws_elasticache_cluster resource
- [ ] Create `terraform/modules/elasticache/variables.tf` with configurable inputs
- [ ] Create `terraform/modules/elasticache/outputs.tf` exposing endpoint
- [ ] Redis 7.x, node type variable (default: cache.t3.micro)
- [ ] Single node (cluster mode disabled)
- [ ] Security group allowing inbound 6379 from EKS node security group
- [ ] Subnet group using existing VPC private subnets
- [ ] No persistence/snapshots (ephemeral rate limit data)
- [ ] Output connection string to AWS Secrets Manager
- [ ] `terraform plan` succeeds

---

### US-025: Create Terraform module for AWS Secrets Manager
**Description:** As a DevOps engineer, I need Terraform to manage Secrets Manager secrets for Medic.

**Acceptance Criteria:**
- [ ] Create `terraform/modules/secrets/` module
- [ ] Create secret: `medic/${var.environment}/secrets`
- [ ] Secret rotation: disabled (manual rotation for now)
- [ ] IAM policy allowing EKS service account to read secrets
- [ ] Output: secret ARN, IAM policy ARN
- [ ] Document manual steps for populating secret values
- [ ] `terraform plan` succeeds

---

### US-026: Create Terraform root module for Medic infrastructure
**Description:** As a DevOps engineer, I need a root Terraform module composing all Medic AWS resources.

**Acceptance Criteria:**
- [ ] Create `terraform/environments/dev/` directory
- [ ] Create `terraform/environments/dev/main.tf` calling modules
- [ ] Create `terraform/environments/dev/variables.tf` with environment-specific values
- [ ] Create `terraform/environments/dev/backend.tf` for S3 state backend
- [ ] Create `terraform/environments/dev/terraform.tfvars` (gitignored, with example)
- [ ] Create `terraform/environments/prod/` directory (placeholder, similar structure)
- [ ] Data sources for existing VPC and EKS cluster
- [ ] Pass EKS node security group to RDS and ElastiCache modules
- [ ] Output all endpoints and ARNs
- [ ] Create `terraform/.gitignore` (*.tfstate, *.tfvars, .terraform/)
- [ ] Create `terraform/README.md` with usage instructions
- [ ] `terraform init && terraform plan` succeeds

---

### US-027: Create IAM role for External Secrets Operator
**Description:** As a DevOps engineer, I need an IAM role that External Secrets Operator can assume to read Secrets Manager.

**Acceptance Criteria:**
- [ ] Add to `terraform/modules/secrets/` or create dedicated IAM module
- [ ] Create IAM role with trust policy for EKS OIDC provider
- [ ] Attach policy allowing secretsmanager:GetSecretValue on medic secrets
- [ ] Attach policy allowing secretsmanager:DescribeSecret on medic secrets
- [ ] Output: role ARN for Kubernetes ServiceAccount annotation
- [ ] Document ServiceAccount annotation in K8s manifests
- [ ] `terraform plan` succeeds

---

### US-028: Create database migration job
**Description:** As a DevOps engineer, I need a Kubernetes Job to run database migrations before deployments.

**Acceptance Criteria:**
- [ ] Create `k8s/base/migration-job.yaml`
- [ ] Job runs migrations from `migrations/` directory
- [ ] Use init container or pre-deploy hook pattern
- [ ] Job has ttlSecondsAfterFinished: 3600 (cleanup after 1 hour)
- [ ] Job uses same secrets as API deployment
- [ ] Backoff limit: 3
- [ ] Create migration runner script: `scripts/run-migrations.sh`
- [ ] Document migration workflow in README

---

## Functional Requirements

### Security
- FR-1: All outbound HTTP requests must validate URLs against SSRF blocklist
- FR-2: API key verification must be constant-time (iterate all keys)
- FR-3: Script execution must only receive allowlisted environment variables
- FR-4: All API endpoints must be rate limited (no exceptions)
- FR-5: Secrets must be stored in AWS Secrets Manager, not in Git or ConfigMaps

### Infrastructure
- FR-6: API and Worker must run as separate Kubernetes Deployments
- FR-7: API must support horizontal scaling via HPA
- FR-8: Worker must run as single replica to prevent duplicate alerts
- FR-9: All pods must run as non-root with read-only filesystem
- FR-10: Database connections must use connection pooling

### Observability
- FR-11: All logs must be structured JSON with request context
- FR-12: Prometheus metrics must be exposed at /metrics endpoint
- FR-13: Health check endpoints must verify database and Redis connectivity

### CI/CD
- FR-14: Docker images must be built and pushed on every merge to main
- FR-15: Dev deployment must be automatic on successful build
- FR-16: Production deployment must require manual approval
- FR-17: All deployments must include rollout status verification

## Non-Goals (Out of Scope)

- Multi-region deployment or disaster recovery setup
- Service mesh (Istio/Linkerd) integration
- GitOps tooling (ArgoCD/Flux) - using kubectl apply directly
- Custom Helm chart - using Kustomize for simplicity
- EKS cluster provisioning (cluster already exists)
- VPC/networking provisioning (using existing VPC)
- Log aggregation beyond CloudWatch (no ELK/Loki setup)
- Distributed tracing (OpenTelemetry) - future enhancement
- Blue/green or canary deployment strategies
- Cost optimization (reserved instances, spot nodes)
- Compliance certifications (SOC2, HIPAA)

## Technical Considerations

### Dependencies
- External Secrets Operator must be installed in EKS cluster
- AWS Load Balancer Controller must be installed for ALB Ingress
- Prometheus Operator must be installed for ServiceMonitor
- Grafana must be available for dashboard import

### Existing Infrastructure (Already Provisioned)
- EKS cluster exists and is configured
- VPC with public/private subnets exists
- EKS node security group exists (for RDS/Redis ingress rules)
- EKS OIDC provider configured (for IRSA)

### Terraform State
- S3 backend for state storage
- DynamoDB for state locking
- Separate state files per environment (dev/prod)

### Database
- PostgreSQL 15 on RDS (not Aurora for cost reasons)
- Connection pooling via PgBouncer or SQLAlchemy pool
- Migrations run as Kubernetes Job before deployment

### Networking
- ALB terminates TLS with ACM certificate
- Internal traffic within cluster is unencrypted (acceptable for now)
- Network policies restrict pod-to-pod communication
- RDS and ElastiCache in private subnets, accessible only from EKS nodes

### Backwards Compatibility
- `playbook_engine.py` kept as facade after refactor
- All existing imports continue to work
- API contract unchanged

## Success Metrics

- Zero critical/high security vulnerabilities in deployment
- API p99 latency < 500ms under normal load
- 99.9% uptime (measured weekly)
- Deployment from merge to running in dev < 15 minutes
- All security fixes verified by re-running security review

## Open Questions

1. Should we implement database connection pooling via PgBouncer sidecar or rely on SQLAlchemy pool?
2. What is the ACM certificate ARN for TLS termination? (needed for prod overlay)
3. Should the worker have its own /health endpoint or rely on process liveness?
4. Do we need PodDisruptionBudget for the API during node maintenance?
5. Should we add resource requests/limits for init containers (migrations)?

## Appendix: Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | Yes | PostgreSQL connection string |
| REDIS_URL | Yes | Redis connection string |
| MEDIC_SECRETS_KEY | Yes | AES-256 key for secrets encryption |
| SLACK_API_TOKEN | Yes | Slack Bot token for notifications |
| SLACK_SIGNING_SECRET | Yes | Slack webhook signature verification |
| MEDIC_LOG_LEVEL | No | Logging level (default: INFO) |
| MEDIC_LOG_FORMAT | No | Log format: json/text (default: json) |
| MEDIC_RATE_LIMITER_TYPE | No | Rate limiter: redis/memory/auto (default: auto) |
| MEDIC_ALLOWED_WEBHOOK_HOSTS | No | Comma-separated allowlist for webhook URLs |
| MEDIC_WEBHOOK_SECRET | Yes | Secret for webhook trigger authentication |
| AWS_REGION | No | AWS region (default: us-east-1) |

## Appendix: AWS Secrets Manager Structure

```json
{
  "DATABASE_URL": "postgresql://user:pass@host:5432/medic",
  "REDIS_URL": "redis://host:6379/0",
  "MEDIC_SECRETS_KEY": "base64-encoded-32-byte-key",
  "SLACK_API_TOKEN": "xoxb-...",
  "SLACK_SIGNING_SECRET": "...",
  "MEDIC_WEBHOOK_SECRET": "..."
}
```

Secret paths:
- Dev: `medic/dev/secrets`
- Prod: `medic/prod/secrets`

## Appendix: Terraform Variables

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| environment | string | Environment name | `dev` |
| aws_region | string | AWS region | `us-east-1` |
| vpc_id | string | Existing VPC ID | `vpc-abc123` |
| private_subnet_ids | list(string) | Private subnet IDs for RDS/Redis | `["subnet-a", "subnet-b"]` |
| eks_cluster_name | string | Existing EKS cluster name | `my-eks-cluster` |
| eks_node_security_group_id | string | EKS node SG for ingress rules | `sg-xyz789` |
| eks_oidc_provider_arn | string | EKS OIDC provider for IRSA | `arn:aws:iam::...` |
| rds_instance_class | string | RDS instance size | `db.t3.micro` |
| rds_multi_az | bool | Enable Multi-AZ | `false` |
| redis_node_type | string | ElastiCache node size | `cache.t3.micro` |

## Appendix: Terraform Module Structure

```
terraform/
├── modules/
│   ├── rds/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── elasticache/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── secrets/
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── environments/
│   ├── dev/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   ├── backend.tf
│   │   └── terraform.tfvars.example
│   └── prod/
│       └── (same structure)
├── .gitignore
└── README.md
```
