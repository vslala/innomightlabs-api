terraform {
  required_providers {
    postgresql = {
      source  = "cyrilgdn/postgresql"
      version = "1.16.0"
    }
  }
}

# Connect to Aurora cluster using master credentials
provider "postgresql" {
  host            = aws_rds_cluster.innomightlabs_db.endpoint
  port            = aws_rds_cluster.innomightlabs_db.port
  database        = var.postgres_db
  username        = var.postgres_user
  password        = var.postgres_password
  sslmode         = "require"
}

# Create IAM-enabled database user
resource "postgresql_role" "iam_db_user" {
  name  = "iam_db_user"
  login = true
}

# Grant rds_iam role for IAM authentication
resource "postgresql_grant" "allow_iam" {
  role_name   = postgresql_role.iam_db_user.name
  object_type = "role"
  object_name = "rds_iam"
  privileges  = ["MEMBER"]
}