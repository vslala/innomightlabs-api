# Secrets Manager for Aurora credentials
resource "aws_secretsmanager_secret" "aurora_credentials" {
  name        = "${var.project_name}-aurora-postgres-credentials"
  description = "Aurora database credentials"
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "aurora_credentials" {
  secret_id = aws_secretsmanager_secret.aurora_credentials.id
  secret_string = jsonencode({
    username = aws_rds_cluster.innomightlabs_db.master_username
    password = var.postgres_password
    host     = aws_rds_cluster.innomightlabs_db.endpoint
    port     = 5432
    dbname   = aws_rds_cluster.innomightlabs_db.database_name
  })
}