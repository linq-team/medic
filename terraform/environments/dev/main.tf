# =============================================================================
# Medic Dev Environment - Root Module
# =============================================================================
# Provisions AWS infrastructure and deploys Medic via Helm:
#   - RDS PostgreSQL database (with credentials in Secrets Manager)
#   - ElastiCache Redis cluster
#   - Secrets Manager and IAM for ESO/IRSA
#   - Medic Helm chart via helm_release
#
# Infrastructure dependencies (VPC, EKS, subnets) are fetched from dev-o11y-tf
# remote state to stay in sync with the dev platform.
#
# NOTE: This environment will fail until dev-o11y-tf is provisioned. The remote
# state data source will error when the dev cluster state does not exist.
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.25"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

# -----------------------------------------------------------------------------
# Providers
# -----------------------------------------------------------------------------

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "medic"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Helm provider uses EKS cluster authentication from o11y remote state
provider "helm" {
  kubernetes {
    host                   = local.eks_endpoint
    cluster_ca_certificate = base64decode(local.eks_ca_cert)
    token                  = data.aws_eks_cluster_auth.this.token
  }
}

provider "kubernetes" {
  host                   = local.eks_endpoint
  cluster_ca_certificate = base64decode(local.eks_ca_cert)
  token                  = data.aws_eks_cluster_auth.this.token
}

# -----------------------------------------------------------------------------
# Remote State - dev-o11y-tf (dev platform infrastructure)
# -----------------------------------------------------------------------------
# Fetches VPC, EKS, subnets, and security group info from dev-o11y-tf state.
# This ensures medic-dev stays in sync with dev platform infrastructure.
#
# Will fail until dev-o11y-tf cluster is provisioned and has state in S3.
# -----------------------------------------------------------------------------

data "terraform_remote_state" "o11y" {
  backend = "s3"

  config = {
    bucket = var.o11y_state_bucket
    key    = var.o11y_state_key
    region = var.o11y_state_region
  }
}

# Local values derived from o11y remote state
locals {
  # EKS cluster info
  eks_cluster_name  = data.terraform_remote_state.o11y.outputs.cluster_name
  eks_endpoint      = data.terraform_remote_state.o11y.outputs.cluster_endpoint
  eks_ca_cert       = data.terraform_remote_state.o11y.outputs.cluster_certificate_authority_data
  oidc_provider_arn = data.terraform_remote_state.o11y.outputs.oidc_provider_arn

  # Network info
  vpc_id                 = data.terraform_remote_state.o11y.outputs.vpc_id
  private_subnet_ids     = data.terraform_remote_state.o11y.outputs.private_subnet_ids
  node_security_group_id = data.terraform_remote_state.o11y.outputs.node_security_group_id
}

# EKS auth token (requires cluster name from remote state)
data "aws_eks_cluster_auth" "this" {
  name = local.eks_cluster_name
}

# -----------------------------------------------------------------------------
# RDS Credentials in Secrets Manager
# -----------------------------------------------------------------------------
# Generate secure credentials and store them in Secrets Manager.
# The application retrieves credentials via External Secrets Operator (ESO).
# -----------------------------------------------------------------------------

resource "random_password" "rds_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret" "rds_credentials" {
  name        = "medic/${var.environment}/rds-credentials"
  description = "RDS credentials for Medic ${var.environment}"

  recovery_window_in_days = var.environment == "prod" ? 30 : 7

  tags = merge(var.tags, {
    Name = "medic-${var.environment}-rds-credentials"
  })
}

resource "aws_secretsmanager_secret_version" "rds_credentials" {
  secret_id = aws_secretsmanager_secret.rds_credentials.id
  secret_string = jsonencode({
    username = var.rds_master_username
    password = random_password.rds_password.result
    host     = module.rds.address
    port     = 5432
    database = var.rds_database_name
    # Full connection string for convenience
    DATABASE_URL = "postgresql://${var.rds_master_username}:${random_password.rds_password.result}@${module.rds.endpoint}/${var.rds_database_name}"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# -----------------------------------------------------------------------------
# RDS PostgreSQL Module
# -----------------------------------------------------------------------------

module "rds" {
  source = "../../modules/rds"

  identifier            = "medic-${var.environment}"
  vpc_id                = local.vpc_id
  subnet_ids            = local.private_subnet_ids
  eks_security_group_id = local.node_security_group_id

  # Instance configuration
  instance_class = var.rds_instance_class
  engine_version = var.rds_engine_version
  database_name  = var.rds_database_name
  multi_az       = var.rds_multi_az

  # Credentials from Secrets Manager
  master_username = var.rds_master_username
  master_password = random_password.rds_password.result

  # Storage
  allocated_storage     = var.rds_allocated_storage
  max_allocated_storage = var.rds_max_allocated_storage

  # Backup
  backup_retention_period = var.rds_backup_retention_period
  skip_final_snapshot     = var.environment == "dev" ? true : false

  # Monitoring
  performance_insights_enabled = var.rds_performance_insights_enabled

  # Lifecycle
  deletion_protection = var.environment == "prod" ? true : false

  tags = var.tags
}

# -----------------------------------------------------------------------------
# ElastiCache Redis Module
# -----------------------------------------------------------------------------

module "elasticache" {
  source = "../../modules/elasticache"

  cluster_id            = "medic-${var.environment}"
  vpc_id                = local.vpc_id
  subnet_ids            = local.private_subnet_ids
  eks_security_group_id = local.node_security_group_id

  # Instance configuration
  node_type      = var.elasticache_node_type
  engine_version = var.elasticache_engine_version

  # Snapshot (disabled by default for rate limit data)
  snapshot_retention_limit = 0

  tags = var.tags
}

# -----------------------------------------------------------------------------
# Secrets Manager and IAM Module (for application secrets)
# -----------------------------------------------------------------------------

module "secrets" {
  source = "../../modules/secrets"

  environment           = var.environment
  eks_oidc_provider_arn = local.oidc_provider_arn
  eks_namespace         = var.kubernetes_namespace
  service_account_name  = var.service_account_name

  # Don't create initial version - secrets managed externally
  create_initial_version = false

  tags = var.tags
}

# -----------------------------------------------------------------------------
# Kubernetes Namespace
# -----------------------------------------------------------------------------

resource "kubernetes_namespace" "medic" {
  count = var.create_namespace ? 1 : 0

  metadata {
    name = var.kubernetes_namespace

    labels = {
      name        = var.kubernetes_namespace
      environment = var.environment
      managed-by  = "terraform"
    }
  }
}

# -----------------------------------------------------------------------------
# Helm Release - Medic Application
# -----------------------------------------------------------------------------

resource "helm_release" "medic" {
  name      = "medic"
  namespace = var.kubernetes_namespace
  chart     = var.helm_chart_path
  version   = var.helm_chart_version

  create_namespace = false # Use kubernetes_namespace resource above

  # Wait for resources to be ready
  wait          = true
  wait_for_jobs = true
  timeout       = 600

  # Atomic install - rollback on failure
  atomic = true

  # Values from variables
  values = [
    yamlencode({
      global = {
        environment = var.environment
      }

      image = {
        repository = var.image_repository
        tag        = var.image_tag
        pullPolicy = var.image_pull_policy
      }

      api = {
        replicaCount = var.api_replica_count
        resources    = var.api_resources
      }

      worker = {
        replicaCount = var.worker_replica_count
        resources    = var.worker_resources
      }

      ingress = {
        enabled = var.ingress_enabled
        host    = var.ingress_host
        tls = {
          enabled        = var.ingress_tls_enabled
          certificateArn = var.ingress_certificate_arn
        }
      }

      serviceAccount = {
        create = true
        name   = var.service_account_name
        annotations = {
          "eks.amazonaws.com/role-arn" = module.secrets.iam_role_arn
        }
      }

      # ExternalSecret for ESO integration - includes RDS credentials
      externalSecret = {
        enabled        = true
        secretStoreRef = var.external_secret_store_ref
        secretPath     = module.secrets.secret_name
        # Also fetch RDS credentials
        additionalSecrets = [
          {
            secretPath = aws_secretsmanager_secret.rds_credentials.name
            property   = "DATABASE_URL"
          }
        ]
      }

      # Disable direct secret creation (using ESO)
      secret = {
        create = false
      }

      # Application configuration (non-sensitive)
      config = {
        PORT                        = "8080"
        LOG_LEVEL                   = var.log_level
        REDIS_URL                   = module.elasticache.connection_string
        MEDIC_RATE_LIMITER_TYPE     = "redis"
        OTEL_EXPORTER_OTLP_ENDPOINT = var.otel_endpoint
        OTEL_SERVICE_NAME           = "medic"
        MEDIC_ENVIRONMENT           = var.environment
      }

      # Metrics and monitoring
      metrics = {
        serviceMonitor = {
          enabled = var.service_monitor_enabled
        }
      }

      # Grafana dashboard
      grafana = {
        dashboard = {
          enabled = var.grafana_dashboard_enabled
        }
      }

      # Migrations
      migrations = {
        enabled = var.migrations_enabled
      }
    })
  ]

  depends_on = [
    module.rds,
    module.elasticache,
    module.secrets,
    kubernetes_namespace.medic,
    aws_secretsmanager_secret_version.rds_credentials
  ]
}
