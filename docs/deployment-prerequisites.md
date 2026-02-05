# Deployment Prerequisites

This document describes all prerequisites for deploying Medic to an EKS cluster using the CI/CD pipeline and Terraform.

## Architecture Overview

```
                        ┌─────────────────────────────────────────────────────────────┐
                        │                     GitHub Actions                          │
                        │                                                             │
                        │  ┌──────────┐    ┌──────────────┐    ┌──────────────────┐  │
                        │  │ CI Build │───▶│ Terraform    │───▶│ CD Deploy (Helm) │  │
                        │  │ (build.  │    │ (terraform.  │    │ (cd-eks.yml)     │  │
                        │  │  yml)    │    │  yml)        │    │                  │  │
                        │  └────┬─────┘    └──────┬───────┘    └────────┬─────────┘  │
                        └───────┼──────────────────┼────────────────────┼─────────────┘
                                │                  │                    │
                 ┌──────────────┘        ┌─────────┘                   │
                 ▼                       ▼                             ▼
         ┌──────────────┐     ┌──────────────────────┐    ┌──────────────────────┐
         │ ECR          │     │ AWS (us-east-2)       │    │ EKS Cluster          │
         │ (us-east-1)  │     │                       │    │ (us-east-2)          │
         │              │     │  ┌─────────────────┐  │    │                      │
         │ medic:latest │     │  │ RDS PostgreSQL  │  │    │  ┌────────────────┐  │
         │ medic:<sha>  │     │  └─────────────────┘  │    │  │ Helm Release   │  │
         │              │     │  ┌─────────────────┐  │    │  │ (medic)        │  │
         └──────────────┘     │  │ ElastiCache     │  │    │  └────────────────┘  │
                              │  │ (Redis)         │  │    │  ┌────────────────┐  │
                              │  └─────────────────┘  │    │  │ ESO            │  │
                              │  ┌─────────────────┐  │    │  │ (from o11y-tf) │  │
                              │  │ Secrets Manager │  │    │  └────────────────┘  │
                              │  └─────────────────┘  │    │  ┌────────────────┐  │
                              │  ┌─────────────────┐  │    │  │ ALB Controller │  │
                              │  │ ACM Certificate │  │    │  │ (from o11y-tf) │  │
                              │  └─────────────────┘  │    │  └────────────────┘  │
                              └──────────────────────┘    └──────────────────────┘
```

## Multi-Region Architecture

Medic operates across two AWS regions:

| Resource | Region | Notes |
|----------|--------|-------|
| ECR (container images) | `us-east-1` | Image repository |
| EKS cluster | `us-east-2` | Application runtime |
| RDS PostgreSQL | `us-east-2` | Database |
| ElastiCache Redis | `us-east-2` | Rate limiting |
| Secrets Manager | `us-east-2` | Application secrets |
| ACM certificates | `us-east-2` | TLS termination |
| Terraform state (S3) | `us-east-2` | State backend |

## GitHub Configuration

### Secrets

These must be configured in **Settings > Secrets and variables > Actions**:

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | IAM access key for `medic-github-actions` user |
| `AWS_SECRET_ACCESS_KEY` | IAM secret key for `medic-github-actions` user |

### Variables

These must be configured in **Settings > Secrets and variables > Actions > Variables**:

| Variable | Value | Description |
|----------|-------|-------------|
| `TF_STATE_BUCKET` | `medic-terraform-state-018143940435` | S3 bucket for Terraform state |
| `TF_STATE_KEY` | `medic` | Key prefix for state files |
| `TF_STATE_DYNAMODB_TABLE` | `medic-terraform-locks` | DynamoDB table for state locking |

### GitHub Environments

Configure in **Settings > Environments**:

| Environment | Approval | Description |
|-------------|----------|-------------|
| `dev` | None | Auto-deploys on PR to main (currently skipped — dev cluster not yet provisioned) |
| `prod` | Required | Deploys on merge to main, requires manual approval |

## External Dependencies

These services are **not managed by Medic's Terraform** and must exist before deployment.

### EKS Cluster (from o11y-tf)

Medic's Terraform reads cluster information from the o11y-tf remote state:

| Environment | Remote State Bucket | Cluster |
|-------------|---------------------|---------|
| prod | `o11y-prod-terraform-state` | `o11y-prod` |
| dev | `dev-o11y-terraform-state` | Not yet provisioned |

Remote state outputs used:
- `cluster_name`, `cluster_endpoint`, `cluster_certificate_authority_data`
- `oidc_provider_arn` (for IRSA)
- `vpc_id`, `private_subnet_ids`, `node_security_group_id`

### External Secrets Operator (ESO)

ESO is deployed by o11y-tf and provides the CRDs that Medic's Terraform uses to create `ClusterSecretStore` and `ExternalSecret` resources. If ESO is missing, Terraform will fail with a clear error — see [ESO Troubleshooting](troubleshooting/eso-not-found.md).

Verify ESO is installed:

```bash
kubectl get crd externalsecrets.external-secrets.io
kubectl get pods -n external-secrets
```

### AWS Load Balancer Controller

The ALB Controller (deployed by o11y-tf) is required for Ingress resources. Medic uses `ingressClassName: alb` for AWS Application Load Balancer integration.

### Alloy / OpenTelemetry Collector

Medic sends traces and metrics to `http://alloy:4317` (OTEL gRPC endpoint). This collector must be running in the cluster.

## AWS Secrets Manager

Medic uses two secret paths per environment:

### Terraform-Managed (auto-created)

| Secret Path | Contents | Created By |
|-------------|----------|------------|
| `medic/dev/rds-credentials` | `username`, `password`, `host`, `port`, `database`, `DATABASE_URL` | Terraform (RDS module) |
| `medic/prod/rds-credentials` | Same as above | Terraform (RDS module) |

### Manually Created (must exist before first deploy)

| Secret Path | Required Keys |
|-------------|---------------|
| `medic/dev/app-secrets` | `MEDIC_SECRETS_KEY`, `MEDIC_WEBHOOK_SECRET`, `SLACK_API_TOKEN`, `SLACK_CHANNEL_ID`, `SLACK_SIGNING_SECRET`, `PAGERDUTY_ROUTING_KEY` |
| `medic/prod/app-secrets` | Same keys as above |

Create via AWS Console or CLI:

```bash
aws secretsmanager create-secret \
  --name "medic/prod/app-secrets" \
  --region us-east-2 \
  --secret-string '{
    "MEDIC_SECRETS_KEY": "<base64-encoded-32-byte-key>",
    "MEDIC_WEBHOOK_SECRET": "<random-token>",
    "SLACK_API_TOKEN": "<xoxb-...>",
    "SLACK_CHANNEL_ID": "<C...>",
    "SLACK_SIGNING_SECRET": "<signing-secret>",
    "PAGERDUTY_ROUTING_KEY": "<routing-key>"
  }'
```

## DNS and TLS (Cloudflare)

ACM certificates are created by Terraform using DNS validation. After `terraform apply`, you must add the validation CNAME records in Cloudflare:

1. Run `terraform output acm_validation_records` to get the CNAME name and value
2. Add the CNAME record in Cloudflare DNS for `linqapp.com`
3. Wait for ACM to validate the certificate (usually a few minutes)

| Environment | Domain | Certificate |
|-------------|--------|-------------|
| dev | `dev-medic.linqapp.com` | Created by Terraform ACM module |
| prod | `medic.linqapp.com` | Created by Terraform ACM module |

You also need A/CNAME records pointing the domain to the ALB created by the Ingress resource.

## Terraform State Backend

The state backend must exist before any Terraform operations:

| Resource | Value |
|----------|-------|
| S3 Bucket | `medic-terraform-state-018143940435` |
| DynamoDB Table | `medic-terraform-locks` |
| Region | `us-east-2` |
| Encryption | AES256 |

State keys per environment:
- Dev: `medic/dev/terraform.tfstate`
- Prod: `medic/prod/terraform.tfstate`

## IAM Permissions

The `medic-github-actions` IAM user requires the `MedicTerraformPolicy` with permissions for:

- **S3** — Terraform state read/write
- **DynamoDB** — Terraform state locking
- **ECR** — Image push/pull
- **RDS** — Database provisioning
- **ElastiCache** — Redis provisioning
- **Secrets Manager** — Secret creation and management
- **IAM** — IRSA role management
- **EC2** — Security groups and networking
- **EKS** — Cluster access and authentication
- **ACM** — Certificate provisioning

## First-Time Setup Checklist

1. Ensure the EKS cluster exists (via o11y-tf) with ESO and ALB Controller installed
2. Configure GitHub secrets (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
3. Configure GitHub variables (`TF_STATE_BUCKET`, `TF_STATE_KEY`, `TF_STATE_DYNAMODB_TABLE`)
4. Create GitHub environments (`dev`, `prod` with required reviewers)
5. Create `medic/{env}/app-secrets` in AWS Secrets Manager with all required keys
6. Run Terraform to provision infrastructure (`terraform apply`)
7. Add ACM validation CNAME records in Cloudflare
8. Add DNS records pointing domains to the ALB
9. Push to main to trigger CI → CD pipeline
