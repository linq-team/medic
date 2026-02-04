# =============================================================================
# Dev Environment Outputs
# =============================================================================

# -----------------------------------------------------------------------------
# RDS Outputs
# -----------------------------------------------------------------------------

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = module.rds.endpoint
}

output "rds_address" {
  description = "RDS PostgreSQL hostname"
  value       = module.rds.address
}

output "rds_port" {
  description = "RDS PostgreSQL port"
  value       = module.rds.port
}

output "rds_database_name" {
  description = "RDS database name"
  value       = module.rds.database_name
}

output "rds_connection_string" {
  description = "RDS connection string (without password)"
  value       = module.rds.connection_string
  sensitive   = true
}

# -----------------------------------------------------------------------------
# ElastiCache Outputs
# -----------------------------------------------------------------------------

output "elasticache_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = module.elasticache.endpoint
}

output "elasticache_connection_string" {
  description = "ElastiCache Redis connection string"
  value       = module.elasticache.connection_string
}

# -----------------------------------------------------------------------------
# Secrets Manager Outputs
# -----------------------------------------------------------------------------

output "secrets_arn" {
  description = "Secrets Manager secret ARN"
  value       = module.secrets.secret_arn
}

output "secrets_name" {
  description = "Secrets Manager secret name"
  value       = module.secrets.secret_name
}

output "iam_role_arn" {
  description = "IAM role ARN for IRSA"
  value       = module.secrets.iam_role_arn
}

# -----------------------------------------------------------------------------
# Application Outputs
# -----------------------------------------------------------------------------

output "namespace" {
  description = "Kubernetes namespace"
  value       = var.kubernetes_namespace
}

output "helm_release_name" {
  description = "Helm release name"
  value       = helm_release.medic.name
}

output "helm_release_status" {
  description = "Helm release status"
  value       = helm_release.medic.status
}

# -----------------------------------------------------------------------------
# Access URLs
# -----------------------------------------------------------------------------

output "application_url" {
  description = "Application URL (if ingress enabled)"
  value       = var.ingress_enabled ? "https://${var.ingress_host}" : null
}
