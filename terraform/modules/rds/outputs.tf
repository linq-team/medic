# =============================================================================
# RDS Module Outputs
# =============================================================================

output "endpoint" {
  description = "The connection endpoint for the RDS instance"
  value       = aws_db_instance.this.endpoint
}

output "address" {
  description = "The hostname of the RDS instance"
  value       = aws_db_instance.this.address
}

output "port" {
  description = "The port the RDS instance is listening on"
  value       = aws_db_instance.this.port
}

output "database_name" {
  description = "The name of the database"
  value       = aws_db_instance.this.db_name
}

output "username" {
  description = "The master username for the database"
  value       = aws_db_instance.this.username
  sensitive   = true
}

output "connection_string" {
  description = "PostgreSQL connection string (without password)"
  value       = "postgresql://${aws_db_instance.this.username}@${aws_db_instance.this.endpoint}/${aws_db_instance.this.db_name}"
  sensitive   = true
}

output "connection_string_with_password" {
  description = "PostgreSQL connection string (with password placeholder)"
  value       = "postgresql://${aws_db_instance.this.username}:PASSWORD@${aws_db_instance.this.endpoint}/${aws_db_instance.this.db_name}"
  sensitive   = true
}

output "arn" {
  description = "The ARN of the RDS instance"
  value       = aws_db_instance.this.arn
}

output "id" {
  description = "The identifier of the RDS instance"
  value       = aws_db_instance.this.id
}

output "security_group_id" {
  description = "The security group ID of the RDS instance"
  value       = aws_security_group.rds.id
}

output "subnet_group_name" {
  description = "The name of the DB subnet group"
  value       = aws_db_subnet_group.this.name
}

output "availability_zone" {
  description = "The availability zone of the RDS instance"
  value       = aws_db_instance.this.availability_zone
}

output "multi_az" {
  description = "Whether the RDS instance is multi-AZ"
  value       = aws_db_instance.this.multi_az
}

output "engine_version_actual" {
  description = "The actual engine version of the RDS instance"
  value       = aws_db_instance.this.engine_version_actual
}
