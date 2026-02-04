# =============================================================================
# Terraform Backend Configuration
# =============================================================================
# Uses S3 for state storage and DynamoDB for state locking.
# Backend configuration values are passed via -backend-config flags in CI/CD.
# =============================================================================

terraform {
  backend "s3" {
    # These values are passed via -backend-config in GitHub Actions:
    # - bucket: S3 bucket name (from vars.TF_STATE_BUCKET)
    # - key: State file path (from vars.TF_STATE_KEY/dev/terraform.tfstate)
    # - region: AWS region (from vars.AWS_REGION)
    # - dynamodb_table: DynamoDB table for locking (from vars.TF_STATE_DYNAMODB_TABLE)
    # - encrypt: true

    # Placeholder values for terraform init without backend config
    # These are overridden by -backend-config flags
    encrypt = true
  }
}
