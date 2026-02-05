# =============================================================================
# Secrets Module Outputs
# =============================================================================

# -----------------------------------------------------------------------------
# Secret Outputs
# -----------------------------------------------------------------------------

output "secret_arn" {
  description = "ARN of the Secrets Manager secret"
  value       = aws_secretsmanager_secret.this.arn
}

output "secret_id" {
  description = "ID of the Secrets Manager secret"
  value       = aws_secretsmanager_secret.this.id
}

output "secret_name" {
  description = "Name of the Secrets Manager secret"
  value       = aws_secretsmanager_secret.this.name
}

# -----------------------------------------------------------------------------
# App Secrets Outputs (manually created)
# -----------------------------------------------------------------------------

output "app_secrets_arn" {
  description = "ARN of the manually-created app-secrets in Secrets Manager"
  value       = data.aws_secretsmanager_secret.app_secrets.arn
}

output "app_secrets_name" {
  description = "Name of the manually-created app-secrets in Secrets Manager"
  value       = data.aws_secretsmanager_secret.app_secrets.name
}

# -----------------------------------------------------------------------------
# IAM Role Outputs
# -----------------------------------------------------------------------------

output "iam_role_arn" {
  description = "ARN of the IAM role for IRSA (use this for ServiceAccount annotation)"
  value       = aws_iam_role.this.arn
}

output "iam_role_name" {
  description = "Name of the IAM role"
  value       = aws_iam_role.this.name
}

output "iam_role_unique_id" {
  description = "Unique identifier of the IAM role"
  value       = aws_iam_role.this.unique_id
}

# -----------------------------------------------------------------------------
# IAM Policy Outputs
# -----------------------------------------------------------------------------

output "secrets_policy_arn" {
  description = "ARN of the IAM policy for Secrets Manager access"
  value       = aws_iam_policy.secrets_access.arn
}

output "kms_policy_arn" {
  description = "ARN of the IAM policy for KMS decryption (null if no custom KMS key)"
  value       = var.kms_key_id != null ? aws_iam_policy.kms_decrypt[0].arn : null
}

# -----------------------------------------------------------------------------
# Service Account Annotation
# -----------------------------------------------------------------------------

output "service_account_annotation" {
  description = "Annotation to add to Kubernetes ServiceAccount for IRSA"
  value = {
    "eks.amazonaws.com/role-arn" = aws_iam_role.this.arn
  }
}
