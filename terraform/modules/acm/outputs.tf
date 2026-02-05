# =============================================================================
# ACM Module Outputs
# =============================================================================

output "certificate_arn" {
  description = "The ARN of the ACM certificate"
  value       = aws_acm_certificate.this.arn
}

output "domain_validation_options" {
  description = "Domain validation options for the ACM certificate (use to create DNS records)"
  value       = aws_acm_certificate.this.domain_validation_options
}

output "domain_name" {
  description = "The domain name of the certificate"
  value       = aws_acm_certificate.this.domain_name
}

# -----------------------------------------------------------------------------
# Cloudflare DNS Setup Helper
# -----------------------------------------------------------------------------
# These outputs provide the CNAME record details needed for Cloudflare DNS
# to complete ACM certificate validation.
# -----------------------------------------------------------------------------

output "validation_cname_name" {
  description = "The CNAME record name to add in Cloudflare for certificate validation"
  value       = one([for dvo in aws_acm_certificate.this.domain_validation_options : dvo.resource_record_name if dvo.resource_record_type == "CNAME"])
}

output "validation_cname_value" {
  description = "The CNAME record value to add in Cloudflare for certificate validation"
  value       = one([for dvo in aws_acm_certificate.this.domain_validation_options : dvo.resource_record_value if dvo.resource_record_type == "CNAME"])
}
