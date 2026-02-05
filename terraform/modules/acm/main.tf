# =============================================================================
# Medic ACM Certificate Module
# =============================================================================
# Creates an ACM certificate with DNS validation for TLS termination.
# After applying, add the CNAME record from the outputs to Cloudflare DNS
# to complete certificate validation.
# =============================================================================

# -----------------------------------------------------------------------------
# ACM Certificate
# -----------------------------------------------------------------------------
# Uses DNS validation - requires adding a CNAME record to Cloudflare
# -----------------------------------------------------------------------------
resource "aws_acm_certificate" "this" {
  domain_name       = var.domain_name
  validation_method = "DNS"

  tags = merge(var.tags, {
    Name = var.domain_name
  })

  lifecycle {
    create_before_destroy = true
  }
}
