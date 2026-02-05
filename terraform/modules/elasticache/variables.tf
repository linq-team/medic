# =============================================================================
# ElastiCache Module Variables
# =============================================================================

# -----------------------------------------------------------------------------
# Required Variables
# -----------------------------------------------------------------------------

variable "cluster_id" {
  description = "The name of the ElastiCache cluster"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where ElastiCache will be deployed"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for the ElastiCache subnet group (should be private subnets)"
  type        = list(string)
}

variable "eks_security_group_id" {
  description = "Security group ID of EKS nodes (allows inbound Redis access)"
  type        = string
}

# -----------------------------------------------------------------------------
# Optional Variables - Instance Configuration
# -----------------------------------------------------------------------------

variable "node_type" {
  description = "The compute and memory capacity of the nodes"
  type        = string
  default     = "cache.t3.micro"
}

variable "engine_version" {
  description = "The version number of the cache engine (Redis)"
  type        = string
  default     = "7.1"
}

variable "parameter_group_name" {
  description = "Name of the parameter group to associate with this cluster"
  type        = string
  default     = "default.redis7"
}

# -----------------------------------------------------------------------------
# Optional Variables - Snapshot Configuration
# -----------------------------------------------------------------------------

variable "snapshot_retention_limit" {
  description = "Number of days for which ElastiCache will retain automatic snapshots (0 to disable)"
  type        = number
  default     = 0 # No snapshots for ephemeral rate limit data
}

variable "snapshot_window" {
  description = "Daily time range during which automated snapshots are created"
  type        = string
  default     = "03:00-04:00"
}

# -----------------------------------------------------------------------------
# Optional Variables - Maintenance
# -----------------------------------------------------------------------------

variable "maintenance_window" {
  description = "Weekly time range for system maintenance"
  type        = string
  default     = "Mon:04:00-Mon:05:00"
}

variable "auto_minor_version_upgrade" {
  description = "Indicates that minor engine upgrades will be applied automatically"
  type        = bool
  default     = true
}

variable "apply_immediately" {
  description = "Specifies whether any modifications are applied immediately, or during the next maintenance window"
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# Optional Variables - Notifications
# -----------------------------------------------------------------------------

variable "notification_topic_arn" {
  description = "ARN of an SNS topic to send ElastiCache notifications to"
  type        = string
  default     = null
}

# -----------------------------------------------------------------------------
# Optional Variables - Tags
# -----------------------------------------------------------------------------

variable "tags" {
  description = "A mapping of tags to assign to all resources"
  type        = map(string)
  default     = {}
}
