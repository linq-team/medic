# =============================================================================
# Medic Dev Environment - Root Module
# =============================================================================
# Provisions AWS infrastructure and deploys Medic via Helm:
#   - RDS PostgreSQL database
#   - ElastiCache Redis cluster
#   - Secrets Manager and IAM for ESO/IRSA
#   - Medic Helm chart via helm_release
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

# Helm provider uses EKS cluster authentication
provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.this.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)
    token                  = data.aws_eks_cluster_auth.this.token
  }
}

provider "kubernetes" {
  host                   = data.aws_eks_cluster.this.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.this.token
}

# -----------------------------------------------------------------------------
# Data Sources - Existing Infrastructure
# -----------------------------------------------------------------------------

# Existing VPC
data "aws_vpc" "this" {
  id = var.vpc_id
}

# Private subnets for databases
data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [var.vpc_id]
  }

  tags = {
    Tier = "private"
  }
}

# Existing EKS cluster
data "aws_eks_cluster" "this" {
  name = var.eks_cluster_name
}

data "aws_eks_cluster_auth" "this" {
  name = var.eks_cluster_name
}

# EKS node security group (for database access rules)
data "aws_security_group" "eks_nodes" {
  id = var.eks_node_security_group_id
}

# EKS OIDC provider for IRSA
data "aws_iam_openid_connect_provider" "eks" {
  url = data.aws_eks_cluster.this.identity[0].oidc[0].issuer
}

# -----------------------------------------------------------------------------
# RDS PostgreSQL Module
# -----------------------------------------------------------------------------

module "rds" {
  source = "../../modules/rds"

  identifier            = "medic-${var.environment}"
  vpc_id                = var.vpc_id
  subnet_ids            = data.aws_subnets.private.ids
  eks_security_group_id = var.eks_node_security_group_id

  # Instance configuration
  instance_class = var.rds_instance_class
  engine_version = var.rds_engine_version
  database_name  = var.rds_database_name
  multi_az       = var.rds_multi_az

  # Credentials (should be stored securely)
  master_username = var.rds_master_username
  master_password = var.rds_master_password

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
  vpc_id                = var.vpc_id
  subnet_ids            = data.aws_subnets.private.ids
  eks_security_group_id = var.eks_node_security_group_id

  # Instance configuration
  node_type      = var.elasticache_node_type
  engine_version = var.elasticache_engine_version

  # Snapshot (disabled by default for rate limit data)
  snapshot_retention_limit = 0

  tags = var.tags
}

# -----------------------------------------------------------------------------
# Secrets Manager and IAM Module
# -----------------------------------------------------------------------------

module "secrets" {
  source = "../../modules/secrets"

  environment           = var.environment
  eks_oidc_provider_arn = data.aws_iam_openid_connect_provider.eks.arn
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
  name       = "medic"
  namespace  = var.kubernetes_namespace
  chart      = var.helm_chart_path
  version    = var.helm_chart_version

  create_namespace = false  # Use kubernetes_namespace resource above

  # Wait for resources to be ready
  wait             = true
  wait_for_jobs    = true
  timeout          = 600

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

      # ExternalSecret for ESO integration
      externalSecret = {
        enabled        = true
        secretStoreRef = var.external_secret_store_ref
        secretPath     = module.secrets.secret_name
      }

      # Disable direct secret creation (using ESO)
      secret = {
        create = false
      }

      # Database configuration
      config = {
        PORT      = "8080"
        LOG_LEVEL = var.log_level
        REDIS_URL = module.elasticache.connection_string
        MEDIC_RATE_LIMITER_TYPE = "redis"
        OTEL_EXPORTER_OTLP_ENDPOINT = var.otel_endpoint
        OTEL_SERVICE_NAME = "medic"
        MEDIC_ENVIRONMENT = var.environment
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

  # Database URL passed as sensitive value
  set_sensitive {
    name  = "config.DATABASE_URL"
    value = "postgresql://${var.rds_master_username}:${var.rds_master_password}@${module.rds.endpoint}/${module.rds.database_name}"
  }

  depends_on = [
    module.rds,
    module.elasticache,
    module.secrets,
    kubernetes_namespace.medic
  ]
}
