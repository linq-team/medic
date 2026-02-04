# =============================================================================
# RDS Module Variables
# =============================================================================

# -----------------------------------------------------------------------------
# Required Variables
# -----------------------------------------------------------------------------

variable "identifier" {
  description = "The name of the RDS instance"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where RDS will be deployed"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for the DB subnet group (should be private subnets)"
  type        = list(string)
}

variable "eks_security_group_id" {
  description = "Security group ID of EKS nodes (allows inbound PostgreSQL access)"
  type        = string
}

variable "master_username" {
  description = "Username for the master DB user"
  type        = string
  sensitive   = true
}

variable "master_password" {
  description = "Password for the master DB user"
  type        = string
  sensitive   = true
}

# -----------------------------------------------------------------------------
# Optional Variables - Instance Configuration
# -----------------------------------------------------------------------------

variable "instance_class" {
  description = "The instance type of the RDS instance"
  type        = string
  default     = "db.t3.micro"
}

variable "engine_version" {
  description = "The engine version to use for PostgreSQL"
  type        = string
  default     = "15"
}

variable "parameter_group_name" {
  description = "Name of the DB parameter group to associate"
  type        = string
  default     = null
}

variable "database_name" {
  description = "The name of the database to create when the instance is created"
  type        = string
  default     = "medic"
}

variable "multi_az" {
  description = "Specifies if the RDS instance is multi-AZ"
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# Optional Variables - Storage Configuration
# -----------------------------------------------------------------------------

variable "allocated_storage" {
  description = "The allocated storage in gigabytes"
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "The upper limit to which Amazon RDS can automatically scale the storage"
  type        = number
  default     = 100
}

variable "kms_key_id" {
  description = "The ARN for the KMS encryption key (uses AWS managed key if not specified)"
  type        = string
  default     = null
}

# -----------------------------------------------------------------------------
# Optional Variables - Backup Configuration
# -----------------------------------------------------------------------------

variable "backup_retention_period" {
  description = "The days to retain backups for"
  type        = number
  default     = 7
}

variable "backup_window" {
  description = "The daily time range during which automated backups are created"
  type        = string
  default     = "03:00-04:00"
}

variable "maintenance_window" {
  description = "The window to perform maintenance in"
  type        = string
  default     = "Mon:04:00-Mon:05:00"
}

variable "skip_final_snapshot" {
  description = "Determines whether a final DB snapshot is created before the instance is deleted"
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# Optional Variables - Monitoring
# -----------------------------------------------------------------------------

variable "performance_insights_enabled" {
  description = "Specifies whether Performance Insights are enabled"
  type        = bool
  default     = false
}

variable "monitoring_interval" {
  description = "The interval, in seconds, between points when Enhanced Monitoring metrics are collected (0 to disable)"
  type        = number
  default     = 0
}

variable "monitoring_role_arn" {
  description = "The ARN for the IAM role that permits RDS to send enhanced monitoring metrics to CloudWatch Logs"
  type        = string
  default     = null
}

variable "enabled_cloudwatch_logs_exports" {
  description = "List of log types to enable for exporting to CloudWatch logs"
  type        = list(string)
  default     = ["postgresql", "upgrade"]
}

# -----------------------------------------------------------------------------
# Optional Variables - Lifecycle
# -----------------------------------------------------------------------------

variable "auto_minor_version_upgrade" {
  description = "Indicates that minor engine upgrades will be applied automatically"
  type        = bool
  default     = true
}

variable "apply_immediately" {
  description = "Specifies whether any database modifications are applied immediately"
  type        = bool
  default     = false
}

variable "deletion_protection" {
  description = "If the DB instance should have deletion protection enabled"
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# Optional Variables - Tags
# -----------------------------------------------------------------------------

variable "tags" {
  description = "A mapping of tags to assign to all resources"
  type        = map(string)
  default     = {}
}
