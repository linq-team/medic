# Medic Terraform Infrastructure

This directory contains Terraform configurations for deploying Medic to AWS EKS.

## Architecture

The Terraform configuration provisions:

- **RDS PostgreSQL** - Application database with automated backups
- **ElastiCache Redis** - Distributed rate limiting cache
- **Secrets Manager** - Application secrets storage
- **IAM Roles** - IRSA (IAM Roles for Service Accounts) for secure AWS access
- **Helm Release** - Medic application deployment via helm_release

## Directory Structure

```
terraform/
├── modules/                    # Reusable Terraform modules
│   ├── rds/                   # RDS PostgreSQL module
│   ├── elasticache/           # ElastiCache Redis module
│   └── secrets/               # Secrets Manager + IAM module
├── environments/
│   ├── dev/                   # Development environment
│   │   ├── main.tf            # Root module calling all modules + helm_release
│   │   ├── variables.tf       # Input variables
│   │   ├── outputs.tf         # Output values
│   │   ├── backend.tf         # S3 backend configuration
│   │   └── terraform.tfvars.example
│   └── prod/                  # Production environment
│       └── ...                # Same structure as dev
└── README.md                  # This file
```

## Prerequisites

1. **AWS CLI** configured with appropriate credentials
2. **Terraform** >= 1.5.0
3. **kubectl** configured for your EKS cluster
4. **Helm** >= 3.0
5. Existing **EKS cluster** with:
   - OIDC provider configured (for IRSA)
   - Node security group accessible
   - Private subnets tagged with `Tier = private`
6. S3 bucket and DynamoDB table for Terraform state (see below)

## State Backend Setup

Before running Terraform, create the state backend resources:

```bash
# Create S3 bucket for state
aws s3api create-bucket \
  --bucket medic-terraform-state \
  --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket medic-terraform-state \
  --versioning-configuration Status=Enabled

# Create DynamoDB table for locking
aws dynamodb create-table \
  --table-name medic-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

## Usage

### Local Development

1. Copy the example variables file:

```bash
cd terraform/environments/dev
cp terraform.tfvars.example terraform.tfvars
```

2. Edit `terraform.tfvars` with your values:

```hcl
vpc_id                     = "vpc-xxxxxxxxx"
eks_cluster_name           = "your-cluster"
eks_node_security_group_id = "sg-xxxxxxxxx"
image_repository           = "your-ecr-repo"
ingress_host              = "medic.example.com"
rds_master_username       = "medic_admin"
rds_master_password       = "secure-password"
```

3. Initialize and apply:

```bash
# Initialize with backend config
terraform init \
  -backend-config="bucket=medic-terraform-state" \
  -backend-config="key=medic/dev/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=medic-terraform-locks"

# Plan
terraform plan -out=tfplan

# Apply
terraform apply tfplan
```

### CI/CD (GitHub Actions)

The GitHub Actions workflow (`.github/workflows/terraform.yml`) automates:

1. **On Pull Request**: Runs `terraform plan` and comments results on PR
2. **On Push to main**: Runs `terraform apply` with approval for production

Required GitHub repository variables:
- `AWS_ROLE_ARN` - IAM role for OIDC authentication
- `AWS_REGION` - AWS region
- `TF_STATE_BUCKET` - S3 bucket for state
- `TF_STATE_KEY` - State key prefix
- `TF_STATE_DYNAMODB_TABLE` - DynamoDB table for locking

Required GitHub environments:
- `dev` - Auto-approve deployments
- `prod` - Requires manual approval

## Module Documentation

### RDS Module

Creates an RDS PostgreSQL instance with:
- Security group allowing EKS node access only
- DB subnet group in private subnets
- Automated backups (configurable retention)
- Storage autoscaling
- Optional Multi-AZ

**Key outputs:**
- `endpoint` - Connection endpoint (host:port)
- `connection_string` - PostgreSQL URL (without password)

### ElastiCache Module

Creates an ElastiCache Redis cluster with:
- Single node (no cluster mode)
- Security group allowing EKS node access only
- Subnet group in private subnets
- No snapshots (ephemeral data)

**Key outputs:**
- `connection_string` - Redis URL (redis://host:port)

### Secrets Module

Creates Secrets Manager secret and IAM resources for IRSA:
- Secret at path `medic/{environment}/secrets`
- IAM role with OIDC trust policy
- IAM policy for secretsmanager:GetSecretValue

**Key outputs:**
- `secret_arn` - Secret ARN for ESO reference
- `iam_role_arn` - Role ARN for ServiceAccount annotation

## Environment Differences

| Setting | Dev | Prod |
|---------|-----|------|
| RDS Multi-AZ | false | true |
| RDS Backup Retention | 7 days | 30 days |
| RDS Deletion Protection | false | true |
| Performance Insights | false | true |
| Skip Final Snapshot | true | false |
| API Autoscaling | disabled | enabled |
| Worker PDB | disabled | enabled |
| Secret Recovery Window | 7 days | 30 days |

## Secrets Management

Application secrets should be stored in AWS Secrets Manager and accessed via External Secrets Operator (ESO):

1. Store secrets in Secrets Manager:

```bash
aws secretsmanager put-secret-value \
  --secret-id medic/dev/secrets \
  --secret-string '{"DATABASE_URL": "...", "MEDIC_SECRETS_KEY": "..."}'
```

2. ESO syncs secrets to Kubernetes:
   - ExternalSecret resource references the Secrets Manager secret
   - ServiceAccount uses IRSA to access Secrets Manager
   - Secrets are synced to Kubernetes Secret

## Troubleshooting

### Terraform State Lock

If you get a state lock error:

```bash
terraform force-unlock LOCK_ID
```

### Helm Release Stuck

If Helm release is stuck:

```bash
helm list -n medic
helm uninstall medic -n medic
terraform apply
```

### EKS Authentication

If you get EKS authentication errors:

```bash
aws eks update-kubeconfig --name YOUR_CLUSTER_NAME
```
