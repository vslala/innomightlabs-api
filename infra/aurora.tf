# Aurora DSQL Cluster - Serverless with built-in IAM authentication
# Note: DSQL doesn't require database creation - connect directly to cluster
resource "aws_dsql_cluster" "innomightlabs_db" {
  deletion_protection_enabled = false

  tags = var.tags
}

# VPC for Aurora Serverless
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(var.tags, {
    Name = "${var.project_name}-vpc"
  })
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(var.tags, {
    Name = "${var.project_name}-igw"
  })
}

# Public Subnet for NAT Gateway
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true

  tags = merge(var.tags, {
    Name = "${var.project_name}-public-subnet"
  })
}

# Private Subnet for Aurora and Lambda
resource "aws_subnet" "private" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = data.aws_availability_zones.available.names[0]

  tags = merge(var.tags, {
    Name = "${var.project_name}-private-subnet"
  })
}

# Second private subnet for Aurora (required for DB subnet group)
resource "aws_subnet" "private_2" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.3.0/24"
  availability_zone = data.aws_availability_zones.available.names[1]

  tags = merge(var.tags, {
    Name = "${var.project_name}-private-subnet-2"
  })
}

# Elastic IP for NAT Gateway
resource "aws_eip" "nat" {
  domain = "vpc"

  tags = merge(var.tags, {
    Name = "${var.project_name}-nat-eip"
  })
}

# NAT Gateway
resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public.id

  tags = merge(var.tags, {
    Name = "${var.project_name}-nat-gateway"
  })

  depends_on = [aws_internet_gateway.main]
}

# Route Table for Public Subnet
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-public-rt"
  })
}

# Route Table for Private Subnet
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-private-rt"
  })
}

# Route Table Associations
resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  subnet_id      = aws_subnet.private.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_2" {
  subnet_id      = aws_subnet.private_2.id
  route_table_id = aws_route_table.private.id
}

# Security Group for Aurora
resource "aws_security_group" "aurora" {
  name_prefix = "${var.project_name}-aurora-"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-aurora-sg"
  })
}

# Security Group for Lambda
resource "aws_security_group" "lambda" {
  name_prefix = "${var.project_name}-lambda-"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-lambda-sg"
  })
}

# DB Subnet Group
resource "aws_db_subnet_group" "aurora" {
  name       = "${var.project_name}-aurora-subnet-group"
  subnet_ids = [aws_subnet.private.id, aws_subnet.private_2.id]

  tags = merge(var.tags, {
    Name = "${var.project_name}-aurora-subnet-group"
  })
}

# Aurora Serverless v2 Cluster
resource "aws_rds_cluster" "aurora_serverless" {
  cluster_identifier     = "${var.project_name}-aurora-serverless"
  engine                 = "aurora-postgresql"
  engine_mode            = "provisioned"
  engine_version         = "15.10"
  database_name          = var.postgres_db
  master_username        = var.postgres_user
  manage_master_user_password = true
  
  db_subnet_group_name   = aws_db_subnet_group.aurora.name
  vpc_security_group_ids = [aws_security_group.aurora.id]
  
  serverlessv2_scaling_configuration {
    max_capacity = 1
    min_capacity = 0.5
  }
  
  iam_database_authentication_enabled = true
  skip_final_snapshot                 = true
  deletion_protection                 = false

  tags = var.tags
}

# Aurora Serverless v2 Instance
resource "aws_rds_cluster_instance" "aurora_serverless" {
  cluster_identifier = aws_rds_cluster.aurora_serverless.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.aurora_serverless.engine
  engine_version     = aws_rds_cluster.aurora_serverless.engine_version

  tags = var.tags
}

# Data source for availability zones
data "aws_availability_zones" "available" {
  state = "available"
}

# Force delete Lambda ENIs on destroy
resource "null_resource" "lambda_eni_cleanup" {
  triggers = {
    vpc_id = aws_vpc.main.id
  }

  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
      sleep 30
      aws ec2 describe-network-interfaces --filters "Name=vpc-id,Values=${self.triggers.vpc_id}" "Name=status,Values=available" --query 'NetworkInterfaces[].NetworkInterfaceId' --output text | tr '\t' '\n' | xargs -I {} aws ec2 delete-network-interface --network-interface-id {} || true
    EOT
  }
}