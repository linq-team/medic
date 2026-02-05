# =============================================================================
# Terraform Backend Configuration - Dev Environment
# =============================================================================
# Shared S3 backend with environment-specific key prefix.
# Both dev and prod use the same S3 bucket and DynamoDB table:
#   - Bucket:   medic-terraform-state-018143940435
#   - DynamoDB: medic-terraform-locks
#   - Dev key:  medic/dev/terraform.tfstate
#   - Prod key: medic/prod/terraform.tfstate
#
# Backend configuration values are passed via -backend-config flags in CI/CD.
# =============================================================================

terraform {
  backend "s3" {
    # These values are passed via -backend-config in GitHub Actions:
    # - bucket:         vars.TF_STATE_BUCKET  (medic-terraform-state-018143940435)
    # - key:            vars.TF_STATE_KEY/dev/terraform.tfstate  (medic/dev/terraform.tfstate)
    # - region:         env.AWS_REGION         (us-east-2)
    # - dynamodb_table: vars.TF_STATE_DYNAMODB_TABLE  (medic-terraform-locks)
    # - encrypt:        true

    # Placeholder values for terraform init without backend config
    # These are overridden by -backend-config flags
    encrypt = true
  }
}
