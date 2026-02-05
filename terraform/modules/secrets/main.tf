# =============================================================================
# Medic Secrets Manager and IAM Module
# =============================================================================
# Creates:
#   - Secrets Manager secret for application secrets
#   - Data source for manually-created app-secrets
#   - IAM role with trust policy for EKS OIDC (IRSA)
#   - IAM policy allowing secretsmanager:GetSecretValue, DescribeSecret
# =============================================================================

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

# -----------------------------------------------------------------------------
# Secrets Manager Secret
# -----------------------------------------------------------------------------
resource "aws_secretsmanager_secret" "this" {
  name        = "medic/${var.environment}/secrets"
  description = "Application secrets for Medic ${var.environment} environment"

  # Recovery window (days to wait before permanent deletion)
  recovery_window_in_days = var.recovery_window_in_days

  # KMS encryption (uses AWS managed key if not specified)
  kms_key_id = var.kms_key_id

  tags = merge(var.tags, {
    Name        = "medic-${var.environment}-secrets"
    Environment = var.environment
  })
}

# Initial secret version with placeholder values
# Note: Actual secrets should be populated manually or via CI/CD
resource "aws_secretsmanager_secret_version" "this" {
  count = var.create_initial_version ? 1 : 0

  secret_id = aws_secretsmanager_secret.this.id
  secret_string = jsonencode({
    DATABASE_URL      = "postgresql://user:password@host:5432/medic"
    MEDIC_SECRETS_KEY = "change-me-in-production"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# -----------------------------------------------------------------------------
# App Secrets (manually created in AWS)
# -----------------------------------------------------------------------------
# References the existing medic/{env}/app-secrets secret that was created
# manually. This secret contains application-specific secrets such as
# MEDIC_SECRETS_KEY, MEDIC_WEBHOOK_SECRET, Slack tokens, and PagerDuty keys.
#
# Terraform only reads this secret (data source) — it does NOT manage the
# secret values. The IAM policy below grants read access to both the
# Terraform-managed secret and this manually-created app-secrets secret.
# -----------------------------------------------------------------------------

data "aws_secretsmanager_secret" "app_secrets" {
  name = "medic/${var.environment}/app-secrets"
}

# -----------------------------------------------------------------------------
# IAM Role for IRSA (IAM Roles for Service Accounts)
# -----------------------------------------------------------------------------
# This role can be assumed by the Kubernetes service account via OIDC
# -----------------------------------------------------------------------------
resource "aws_iam_role" "this" {
  name        = "medic-${var.environment}-secrets-role"
  description = "IAM role for Medic ${var.environment} to access Secrets Manager via IRSA"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.eks_oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(var.eks_oidc_provider_arn, "/^arn:aws:iam::[0-9]+:oidc-provider\\//", "")}:sub" = "system:serviceaccount:${var.eks_namespace}:${var.service_account_name}"
            "${replace(var.eks_oidc_provider_arn, "/^arn:aws:iam::[0-9]+:oidc-provider\\//", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "medic-${var.environment}-secrets-role"
    Environment = var.environment
  })
}

# -----------------------------------------------------------------------------
# IAM Policy for Secrets Manager Access
# -----------------------------------------------------------------------------
resource "aws_iam_policy" "secrets_access" {
  name        = "medic-${var.environment}-secrets-policy"
  description = "Policy allowing Medic to read secrets from Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GetSecretValue"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.this.arn,
          "${aws_secretsmanager_secret.this.arn}:*",
          # App secrets (manually created, referenced via data source)
          data.aws_secretsmanager_secret.app_secrets.arn,
          "${data.aws_secretsmanager_secret.app_secrets.arn}:*"
        ]
      },
      {
        Sid    = "ListSecrets"
        Effect = "Allow"
        Action = [
          "secretsmanager:ListSecrets"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "secretsmanager:ResourceTag/Environment" = var.environment
          }
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "medic-${var.environment}-secrets-policy"
    Environment = var.environment
  })
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "secrets_access" {
  role       = aws_iam_role.this.name
  policy_arn = aws_iam_policy.secrets_access.arn
}

# -----------------------------------------------------------------------------
# Optional: KMS Policy for Secret Decryption
# -----------------------------------------------------------------------------
# Only created if a custom KMS key is provided
# -----------------------------------------------------------------------------
resource "aws_iam_policy" "kms_decrypt" {
  count = var.kms_key_id != null ? 1 : 0

  name        = "medic-${var.environment}-kms-decrypt-policy"
  description = "Policy allowing Medic to decrypt secrets using KMS"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "KMSDecrypt"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = [var.kms_key_id]
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "medic-${var.environment}-kms-decrypt-policy"
    Environment = var.environment
  })
}

resource "aws_iam_role_policy_attachment" "kms_decrypt" {
  count = var.kms_key_id != null ? 1 : 0

  role       = aws_iam_role.this.name
  policy_arn = aws_iam_policy.kms_decrypt[0].arn
}
