# Aurora Serverless v2 Cluster
resource "aws_rds_cluster" "innomightlabs_db" {
  cluster_identifier     = "${var.project_name}-aurora-cluster"
  engine                 = "aurora-postgresql"
  engine_mode           = "provisioned"
  engine_version        = "15.4"
  database_name         = var.postgres_db
  master_username       = var.postgres_user
  master_password       = var.postgres_password
  skip_final_snapshot   = true
  deletion_protection   = false

  serverlessv2_scaling_configuration {
    max_capacity = 1
    min_capacity = 0.5
  }

  db_subnet_group_name   = aws_db_subnet_group.innomightlabs_db.name
  vpc_security_group_ids = [aws_security_group.aurora.id]

  tags = var.tags
}

# Aurora Serverless v2 Instance
resource "aws_rds_cluster_instance" "innomightlabs_db" {
  identifier         = "${var.project_name}-aurora-instance"
  cluster_identifier = aws_rds_cluster.innomightlabs_db.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.innomightlabs_db.engine
  engine_version     = aws_rds_cluster.innomightlabs_db.engine_version

  tags = var.tags
}

# DB Subnet Group
resource "aws_db_subnet_group" "innomightlabs_db" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]

  tags = var.tags
}