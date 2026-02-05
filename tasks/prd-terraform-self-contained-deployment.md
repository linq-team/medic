# PRD: Medic Terraform Self-Contained Deployment Infrastructure

## Introduction

Make Medic's Terraform deployment fully self-contained by adding required Kubernetes resources (ClusterSecretStore) and AWS resources (ACM certificates, application secrets) directly in Terraform. This eliminates manual setup steps and ensures deployments work out-of-the-box with proper error handling when external dependencies (like ESO from o11y-tf) are unavailable.

Additionally, fix the region mismatch bug in CI/CD workflows and implement proper deployment triggers: PRs deploy to dev, merges to main deploy to prod.

**Note:** The AWS Load Balancer Controller is shared infrastructure deployed by o11y-tf in `kube-system`. Medic only needs to create Ingress resources that reference it.

## Goals

- Create ACM certificates for `medic.linqapp.com` (prod) and `dev-medic.linqapp.com` (dev)
- Create ClusterSecretStore resource that references ESO (deployed by o11y-tf)
- Fail fast with helpful error messages and documentation links when ESO is unavailable
- Seed application secrets in AWS Secrets Manager with initial values
- Fix region mismatch (`us-east-1` vs `us-east-2`) in GitHub Actions workflows
- Update CD pipeline: PRs → dev, merge to main → prod
- Support future dev cluster (`dev-o11y-tf`) with skip option while unavailable

## User Stories

### US-001: Fix Region Mismatch in CI/CD Workflows
**Description:** As a DevOps engineer, I want consistent AWS region configuration so that Terraform and CD workflows don't fail due to mismatched regions.

**Acceptance Criteria:**
- [ ] `terraform.yml` uses `AWS_REGION: us-east-2` (matches EKS cluster region)
- [ ] `cd-eks.yml` uses `AWS_REGION: us-east-2` consistently
- [ ] ECR image check in `cd-eks.yml` explicitly uses `us-east-1` (where ECR lives)
- [ ] All Terraform variable defaults use `us-east-2`
- [ ] Document the multi-region setup (ECR in us-east-1, EKS in us-east-2)

### US-002: Create ACM Certificates for Dev and Prod
**Description:** As a DevOps engineer, I want ACM certificates created by Terraform so that TLS is configured without manual certificate provisioning.

**Acceptance Criteria:**
- [ ] Dev environment creates certificate for `dev-medic.linqapp.com`
- [ ] Prod environment creates certificate for `medic.linqapp.com`
- [ ] Certificates use DNS validation method
- [ ] Terraform outputs validation CNAME records for manual Cloudflare setup
- [ ] Certificate ARN is automatically passed to Helm ingress configuration
- [ ] Add clear output messages showing the DNS records to add to Cloudflare

### US-003: Create ClusterSecretStore for External Secrets Operator
**Description:** As a DevOps engineer, I want a ClusterSecretStore created by Terraform so that ExternalSecret resources can fetch secrets from AWS Secrets Manager.

**Acceptance Criteria:**
- [ ] Create `kubernetes_manifest` resource for ClusterSecretStore
- [ ] ClusterSecretStore named `aws-secrets-manager` (matches Helm chart expectation)
- [ ] Configured to use AWS Secrets Manager as backend
- [ ] References the IRSA service account created by secrets module
- [ ] Region set to `us-east-2`

### US-004: Validate ESO Availability with Helpful Errors
**Description:** As a DevOps engineer, I want Terraform to fail fast with helpful error messages when ESO is not installed, so I know exactly what's missing and how to fix it.

**Acceptance Criteria:**
- [ ] Add data source to check if ESO CRDs exist in cluster
- [ ] Terraform fails with clear error if `external-secrets.io` CRDs not found
- [ ] Error message includes link to troubleshooting documentation
- [ ] Create `docs/troubleshooting/eso-not-found.md` with resolution steps
- [ ] Document that ESO is deployed by o11y-tf and is a prerequisite

### US-005: Seed Application Secrets in Secrets Manager
**Description:** As a DevOps engineer, I want initial application secrets created in Secrets Manager so that the application can start without manual secret creation.

**Acceptance Criteria:**
- [ ] Create secret `medic/{env}/app-secrets` with required structure
- [ ] Include keys: `MEDIC_SECRETS_KEY`, `MEDIC_WEBHOOK_SECRET`, `SLACK_API_TOKEN`, `SLACK_CHANNEL_ID`, `SLACK_SIGNING_SECRET`, `PAGERDUTY_ROUTING_KEY`
- [ ] Generate random values for `MEDIC_SECRETS_KEY` (32-byte base64) and `MEDIC_WEBHOOK_SECRET` using Terraform
- [ ] Populate external service tokens (Slack, PagerDuty) with actual values on first deploy
- [ ] Add `lifecycle { ignore_changes = [secret_string] }` to prevent overwrites after initial creation
- [ ] Note: `DATABASE_URL` and `REDIS_URL` are handled separately by existing RDS/ElastiCache modules

### US-006: Update CD Pipeline for PR and Merge Triggers
**Description:** As a developer, I want PRs to deploy to dev and merges to main to deploy to prod, so that I can test changes before production.

**Acceptance Criteria:**
- [ ] PRs to `main` trigger deployment to `dev` environment
- [ ] Merges/pushes to `main` trigger deployment to `prod` environment
- [ ] Dev deployment does not require approval
- [ ] Prod deployment requires GitHub Environment approval
- [ ] Update `cd-eks.yml` workflow triggers accordingly
- [ ] Add `skip_dev` input option (default: true) for manual workflow dispatch while dev cluster unavailable

### US-007: Support Future Dev Cluster Configuration
**Description:** As a DevOps engineer, I want the dev environment configured for the future `dev-o11y-tf` cluster so that it works automatically when the cluster is created.

**Acceptance Criteria:**
- [ ] Dev environment references `dev-o11y-tf` remote state
- [ ] Use same S3 bucket (`medic-terraform-state-018143940435`) with different key prefix (`dev/` vs `prod/`)
- [ ] Use same DynamoDB table (`medic-terraform-locks`) for both environments
- [ ] Terraform plan shows clear error when dev remote state is unavailable
- [ ] Document that dev will fail until `dev-o11y-tf` cluster is provisioned
- [ ] CD workflow skips dev deployment by default until cluster exists

### US-008: Create Deployment Prerequisites Documentation
**Description:** As a DevOps engineer, I want clear documentation of all deployment prerequisites so that new team members can understand the system.

**Acceptance Criteria:**
- [ ] Create `docs/deployment-prerequisites.md`
- [ ] Document GitHub secrets required: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- [ ] Document GitHub variables required: `TF_STATE_BUCKET`, `TF_STATE_KEY`, `TF_STATE_DYNAMODB_TABLE`
- [ ] Document GitHub Environments required: `dev`, `prod` (with protection rules)
- [ ] Document external dependencies: o11y-tf cluster, ESO installation, ALB Controller (shared)
- [ ] Document Cloudflare DNS setup for ACM certificate validation
- [ ] Include architecture diagram showing component relationships

### US-009: Update Ingress Host Configuration
**Description:** As a DevOps engineer, I want ingress hosts correctly configured per environment so that traffic routes to the right endpoints.

**Acceptance Criteria:**
- [ ] Dev environment uses `dev-medic.linqapp.com`
- [ ] Prod environment uses `medic.linqapp.com`
- [ ] Update `terraform/environments/dev/variables.tf` default for `ingress_host`
- [ ] Verify prod already uses correct host
- [ ] Certificate ARN automatically matched to ingress host

## Functional Requirements

- FR-1: All Terraform configurations must use `us-east-2` as the primary region (except ECR operations which use `us-east-1`)
- FR-2: ACM certificates must be created with DNS validation method and output the required CNAME records
- FR-3: ClusterSecretStore must be created after verifying ESO CRDs exist
- FR-4: Application secrets must be seeded with generated values for internal keys and actual values for external service tokens
- FR-5: CD pipeline must deploy to dev on PR (when enabled), prod on merge to main
- FR-6: All failures must include actionable error messages with documentation links
- FR-7: Both environments share the same S3 bucket and DynamoDB table with different key prefixes
- FR-8: Secret values must use `ignore_changes` lifecycle to prevent Terraform from overwriting manual updates

## Non-Goals

- No installation of AWS Load Balancer Controller (shared infrastructure from o11y-tf)
- No automatic DNS record creation in Cloudflare (manual step)
- No installation of External Secrets Operator (managed by o11y-tf)
- No creation of the dev cluster itself (managed separately)
- No automatic rotation of secrets
- No multi-region failover configuration

## Technical Considerations

### Multi-Region Architecture
- **ECR Repository:** `us-east-1` (existing, cannot change)
- **EKS Cluster:** `us-east-2` (from o11y-tf)
- **RDS/ElastiCache:** `us-east-2` (same region as EKS)
- **Secrets Manager:** `us-east-2` (same region as EKS)
- **ACM Certificates:** `us-east-2` (must match ALB region)

### Shared Infrastructure from o11y-tf
The following components are deployed by o11y-tf and shared across all apps:
- **AWS Load Balancer Controller** - `kube-system` namespace, uses `ingressClassName: alb`
- **External Secrets Operator** - Provides CRDs for ExternalSecret/ClusterSecretStore
- **Cert Manager** - TLS certificate management
- **External DNS** - Route53 DNS management
- **KEDA** - Event-driven autoscaling

Medic creates Ingress resources that reference the shared ALB Controller:
```yaml
ingressClassName: alb
annotations:
  alb.ingress.kubernetes.io/scheme: internet-facing
  alb.ingress.kubernetes.io/target-type: ip
  alb.ingress.kubernetes.io/certificate-arn: <ACM_CERT_ARN>
```

### Remote State Configuration
Both environments use the same backend resources with different prefixes:
- **S3 Bucket:** `medic-terraform-state-018143940435`
- **DynamoDB Table:** `medic-terraform-locks`
- **Dev State Key:** `medic/dev/terraform.tfstate`
- **Prod State Key:** `medic/prod/terraform.tfstate`

### o11y-tf Remote State References
- **Prod:** `o11y-prod-terraform-state` bucket, `terraform.tfstate` key, `us-east-2`
- **Dev:** TBD - `dev-o11y-tf` cluster remote state (will fail until cluster created)

### Application Secrets Structure
Secret path: `medic/{env}/app-secrets`

Keys stored:
- `MEDIC_SECRETS_KEY` - AES-256-GCM encryption key for user secrets
- `MEDIC_WEBHOOK_SECRET` - Webhook signature validation
- `SLACK_API_TOKEN` - Slack bot token
- `SLACK_CHANNEL_ID` - Default notification channel
- `SLACK_SIGNING_SECRET` - Slack request verification
- `PAGERDUTY_ROUTING_KEY` - PagerDuty Events API routing

**Status:** Secrets created in AWS Secrets Manager (prod and dev). Values managed in AWS console.

Note: `DATABASE_URL` is stored separately in `medic/{env}/rds-credentials` by the RDS module.

### Helm Chart Dependencies
```
ClusterSecretStore → ESO CRDs (from o11y-tf)
Medic Helm Release → ClusterSecretStore, ALB Controller (shared), RDS, ElastiCache
```

## Definition of Done

Per team standards, this feature is not complete until:

### Tests
- [ ] Terraform `plan` succeeds for both dev and prod configurations
- [ ] Terraform `apply` succeeds in prod environment
- [ ] ClusterSecretStore created and syncing
- [ ] ExternalSecret successfully pulls secrets from Secrets Manager
- [ ] Ingress creates ALB with valid TLS certificate

### QA
- [ ] Manual deployment to prod environment verified
- [ ] Certificate validation records documented and added to Cloudflare
- [ ] ALB DNS name resolves and serves traffic
- [ ] Secrets correctly injected into application pods

### Monitoring
- [ ] Failed deployments trigger GitHub Actions failure notifications
- [ ] Terraform state drift detection (manual periodic check)

### Telemetry
- [ ] GitHub Actions workflow duration tracked
- [ ] Deployment success/failure rate visible in GitHub Actions

### Tooling
- [ ] `terraform plan` can be run locally with proper AWS credentials
- [ ] Clear error messages for all failure scenarios

### Runbook
- [ ] `docs/deployment-prerequisites.md` created
- [ ] `docs/troubleshooting/eso-not-found.md` created
- [ ] README updated with deployment instructions
- [ ] Cloudflare DNS setup steps documented

### Handoff
- [ ] DevOps team aware of new deployment flow (PR → dev, merge → prod)
- [ ] Team informed about shared infrastructure dependencies from o11y-tf

## Success Metrics

- Terraform deployment requires zero manual AWS console steps (except Cloudflare DNS)
- New developer can deploy with only GitHub secrets/variables configured
- Deployment failures include actionable error messages with resolution steps
- Time from PR merge to production deployment < 15 minutes

## Open Questions

*All questions resolved*
