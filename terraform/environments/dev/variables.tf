# =============================================================================
# Dev Environment Variables
# =============================================================================

# -----------------------------------------------------------------------------
# AWS Configuration
# -----------------------------------------------------------------------------

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

# -----------------------------------------------------------------------------
# Network Configuration
# -----------------------------------------------------------------------------

variable "vpc_id" {
  description = "VPC ID where resources will be deployed"
  type        = string
}

variable "eks_cluster_name" {
  description = "Name of the existing EKS cluster"
  type        = string
}

variable "eks_node_security_group_id" {
  description = "Security group ID of EKS nodes (for database access)"
  type        = string
}

# -----------------------------------------------------------------------------
# RDS Configuration
# -----------------------------------------------------------------------------

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "rds_engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "15"
}

variable "rds_database_name" {
  description = "Name of the database to create"
  type        = string
  default     = "medic"
}

variable "rds_master_username" {
  description = "Master username for RDS"
  type        = string
  sensitive   = true
}

variable "rds_master_password" {
  description = "Master password for RDS"
  type        = string
  sensitive   = true
}

variable "rds_allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 20
}

variable "rds_max_allocated_storage" {
  description = "Maximum allocated storage in GB for autoscaling"
  type        = number
  default     = 100
}

variable "rds_multi_az" {
  description = "Enable Multi-AZ deployment"
  type        = bool
  default     = false
}

variable "rds_backup_retention_period" {
  description = "Backup retention period in days"
  type        = number
  default     = 7
}

variable "rds_performance_insights_enabled" {
  description = "Enable Performance Insights"
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# ElastiCache Configuration
# -----------------------------------------------------------------------------

variable "elasticache_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "elasticache_engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.1"
}

# -----------------------------------------------------------------------------
# Kubernetes Configuration
# -----------------------------------------------------------------------------

variable "kubernetes_namespace" {
  description = "Kubernetes namespace for Medic"
  type        = string
  default     = "medic"
}

variable "create_namespace" {
  description = "Create Kubernetes namespace"
  type        = bool
  default     = true
}

variable "service_account_name" {
  description = "Name of the Kubernetes service account"
  type        = string
  default     = "medic"
}

# -----------------------------------------------------------------------------
# Helm Chart Configuration
# -----------------------------------------------------------------------------

variable "helm_chart_path" {
  description = "Path to the Helm chart (relative or absolute)"
  type        = string
  default     = "../../../helm/medic"
}

variable "helm_chart_version" {
  description = "Version of the Helm chart (null for local charts)"
  type        = string
  default     = null
}

# -----------------------------------------------------------------------------
# Application Configuration
# -----------------------------------------------------------------------------

variable "image_repository" {
  description = "Docker image repository"
  type        = string
}

variable "image_tag" {
  description = "Docker image tag"
  type        = string
  default     = "latest"
}

variable "image_pull_policy" {
  description = "Image pull policy"
  type        = string
  default     = "IfNotPresent"
}

variable "api_replica_count" {
  description = "Number of API replicas"
  type        = number
  default     = 2
}

variable "api_resources" {
  description = "API resource requests and limits"
  type = object({
    requests = object({
      cpu    = string
      memory = string
    })
    limits = object({
      cpu    = string
      memory = string
    })
  })
  default = {
    requests = {
      cpu    = "100m"
      memory = "256Mi"
    }
    limits = {
      cpu    = "500m"
      memory = "512Mi"
    }
  }
}

variable "worker_replica_count" {
  description = "Number of worker replicas"
  type        = number
  default     = 1
}

variable "worker_resources" {
  description = "Worker resource requests and limits"
  type = object({
    requests = object({
      cpu    = string
      memory = string
    })
    limits = object({
      cpu    = string
      memory = string
    })
  })
  default = {
    requests = {
      cpu    = "50m"
      memory = "128Mi"
    }
    limits = {
      cpu    = "200m"
      memory = "256Mi"
    }
  }
}

# -----------------------------------------------------------------------------
# Ingress Configuration
# -----------------------------------------------------------------------------

variable "ingress_enabled" {
  description = "Enable ingress"
  type        = bool
  default     = true
}

variable "ingress_host" {
  description = "Ingress hostname"
  type        = string
}

variable "ingress_tls_enabled" {
  description = "Enable TLS on ingress"
  type        = bool
  default     = true
}

variable "ingress_certificate_arn" {
  description = "ARN of ACM certificate for TLS"
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# Observability Configuration
# -----------------------------------------------------------------------------

variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"
}

variable "otel_endpoint" {
  description = "OpenTelemetry collector endpoint"
  type        = string
  default     = "http://alloy:4317"
}

variable "service_monitor_enabled" {
  description = "Enable ServiceMonitor for Prometheus"
  type        = bool
  default     = true
}

variable "grafana_dashboard_enabled" {
  description = "Enable Grafana dashboard ConfigMap"
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# External Secrets Configuration
# -----------------------------------------------------------------------------

variable "external_secret_store_ref" {
  description = "Name of the ClusterSecretStore for External Secrets Operator"
  type        = string
  default     = "aws-secrets-manager"
}

# -----------------------------------------------------------------------------
# Migration Configuration
# -----------------------------------------------------------------------------

variable "migrations_enabled" {
  description = "Enable database migrations Helm hook"
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# Tags
# -----------------------------------------------------------------------------

variable "tags" {
  description = "Additional tags for all resources"
  type        = map(string)
  default     = {}
}
