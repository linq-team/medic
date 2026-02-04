# =============================================================================
# Secrets Module Variables
# =============================================================================

# -----------------------------------------------------------------------------
# Required Variables
# -----------------------------------------------------------------------------

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
}

variable "eks_oidc_provider_arn" {
  description = "ARN of the EKS OIDC provider for IRSA"
  type        = string
}

variable "eks_namespace" {
  description = "Kubernetes namespace where Medic will be deployed"
  type        = string
}

# -----------------------------------------------------------------------------
# Optional Variables - Service Account
# -----------------------------------------------------------------------------

variable "service_account_name" {
  description = "Name of the Kubernetes service account that will assume the IAM role"
  type        = string
  default     = "medic"
}

# -----------------------------------------------------------------------------
# Optional Variables - Secret Configuration
# -----------------------------------------------------------------------------

variable "recovery_window_in_days" {
  description = "Number of days to wait before permanently deleting a secret (0 for immediate deletion)"
  type        = number
  default     = 7
}

variable "kms_key_id" {
  description = "ARN of the KMS key to use for secret encryption (uses AWS managed key if not specified)"
  type        = string
  default     = null
}

variable "create_initial_version" {
  description = "Whether to create an initial version of the secret with placeholder values"
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# Optional Variables - Tags
# -----------------------------------------------------------------------------

variable "tags" {
  description = "A mapping of tags to assign to all resources"
  type        = map(string)
  default     = {}
}
