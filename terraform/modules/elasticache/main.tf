# =============================================================================
# Medic ElastiCache Redis Module
# =============================================================================
# Creates an ElastiCache Redis cluster with:
#   - Security group allowing access from EKS nodes only
#   - Subnet group for private deployment
#   - Single node configuration (no cluster mode)
#   - No snapshots (ephemeral rate limit data)
# =============================================================================

# -----------------------------------------------------------------------------
# Security Group for ElastiCache
# -----------------------------------------------------------------------------
# Only allows inbound Redis traffic from EKS node security group
# -----------------------------------------------------------------------------
resource "aws_security_group" "redis" {
  name        = "${var.cluster_id}-redis-sg"
  description = "Security group for Medic ElastiCache Redis"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${var.cluster_id}-redis-sg"
  })
}

resource "aws_security_group_rule" "redis_ingress_eks" {
  type                     = "ingress"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  source_security_group_id = var.eks_security_group_id
  security_group_id        = aws_security_group.redis.id
  description              = "Allow Redis from EKS nodes"
}

resource "aws_security_group_rule" "redis_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.redis.id
  description       = "Allow all outbound traffic"
}

# -----------------------------------------------------------------------------
# ElastiCache Subnet Group
# -----------------------------------------------------------------------------
# Places Redis in private subnets
# -----------------------------------------------------------------------------
resource "aws_elasticache_subnet_group" "this" {
  name        = "${var.cluster_id}-subnet-group"
  description = "Subnet group for Medic ElastiCache Redis"
  subnet_ids  = var.subnet_ids

  tags = merge(var.tags, {
    Name = "${var.cluster_id}-subnet-group"
  })
}

# -----------------------------------------------------------------------------
# ElastiCache Redis Cluster
# -----------------------------------------------------------------------------
# Single node Redis cluster for rate limiting (no persistence needed)
# -----------------------------------------------------------------------------
resource "aws_elasticache_cluster" "this" {
  cluster_id = var.cluster_id

  # Engine configuration
  engine               = "redis"
  engine_version       = var.engine_version
  node_type            = var.node_type
  num_cache_nodes      = 1 # Single node (no cluster mode)
  port                 = 6379
  parameter_group_name = var.parameter_group_name

  # Network configuration
  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = [aws_security_group.redis.id]

  # Snapshot configuration (disabled for ephemeral rate limit data)
  snapshot_retention_limit = var.snapshot_retention_limit
  snapshot_window          = var.snapshot_retention_limit > 0 ? var.snapshot_window : null

  # Maintenance
  maintenance_window         = var.maintenance_window
  auto_minor_version_upgrade = var.auto_minor_version_upgrade
  apply_immediately          = var.apply_immediately

  # Notifications
  notification_topic_arn = var.notification_topic_arn

  tags = merge(var.tags, {
    Name = var.cluster_id
  })
}
