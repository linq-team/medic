# =============================================================================
# ElastiCache Module Outputs
# =============================================================================

output "endpoint" {
  description = "The endpoint of the ElastiCache cluster (host:port format)"
  value       = "${aws_elasticache_cluster.this.cache_nodes[0].address}:${aws_elasticache_cluster.this.cache_nodes[0].port}"
}

output "address" {
  description = "The DNS name of the cache cluster"
  value       = aws_elasticache_cluster.this.cache_nodes[0].address
}

output "port" {
  description = "The port number of the cache cluster"
  value       = aws_elasticache_cluster.this.cache_nodes[0].port
}

output "connection_string" {
  description = "Redis connection string (redis:// URL format)"
  value       = "redis://${aws_elasticache_cluster.this.cache_nodes[0].address}:${aws_elasticache_cluster.this.cache_nodes[0].port}"
}

output "cluster_id" {
  description = "The cluster identifier"
  value       = aws_elasticache_cluster.this.cluster_id
}

output "arn" {
  description = "The ARN of the ElastiCache cluster"
  value       = aws_elasticache_cluster.this.arn
}

output "security_group_id" {
  description = "The security group ID of the ElastiCache cluster"
  value       = aws_security_group.redis.id
}

output "subnet_group_name" {
  description = "The name of the ElastiCache subnet group"
  value       = aws_elasticache_subnet_group.this.name
}

output "engine_version_actual" {
  description = "The actual engine version of the ElastiCache cluster"
  value       = aws_elasticache_cluster.this.engine_version_actual
}

output "configuration_endpoint" {
  description = "The configuration endpoint (for cluster mode, same as endpoint for single node)"
  value       = aws_elasticache_cluster.this.configuration_endpoint
}
