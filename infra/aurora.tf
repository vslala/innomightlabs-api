# DB Subnet Group — public subnets
resource "aws_db_subnet_group" "innomightlabs_db" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = [
    aws_subnet.public_a.id,
    aws_subnet.public_b.id,
  ]
  tags = var.tags
}

# Aurora Serverless v2 cluster
resource "aws_rds_cluster" "innomightlabs_db" {
  cluster_identifier               = "${var.project_name}-aurora-cluster"
  engine                           = "aurora-postgresql"
  engine_mode                      = "provisioned"                # v2
  engine_version                   = "15.4"
  database_name                    = var.postgres_db
  master_username                  = var.postgres_user
  master_password                  = var.postgres_password
  skip_final_snapshot              = true
  deletion_protection              = false
  iam_database_authentication_enabled = true

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 1
  }

  vpc_security_group_ids = [aws_security_group.aurora_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.innomightlabs_db.name

  # No need to expose a Data API here since we're going direct over TCP
}

# Aurora Serverless v2 instance
resource "aws_rds_cluster_instance" "innomightlabs_instance" {
  # Or use a prefix and let Terraform append a random suffix:
  identifier_prefix  = "${var.project_name}-instance-"

  cluster_identifier = aws_rds_cluster.innomightlabs_db.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.innomightlabs_db.engine
  engine_version     = aws_rds_cluster.innomightlabs_db.engine_version

  publicly_accessible = true

  tags = var.tags
}

