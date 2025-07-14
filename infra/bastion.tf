# Bastion Host for Aurora Serverless RDS Access

# Security Group for Bastion Host
resource "aws_security_group" "bastion" {
  name_prefix = "${var.project_name}-bastion-"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-bastion-sg"
  })
}

# Allow bastion to access Aurora
resource "aws_security_group_rule" "aurora_from_bastion" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.bastion.id
  security_group_id        = aws_security_group.aurora.id
}

# Elastic IP for Bastion
resource "aws_eip" "bastion" {
  domain = "vpc"
  tags = merge(var.tags, {
    Name = "${var.project_name}-bastion-eip"
  })
}

# Latest Amazon Linux 2 AMI
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]
  
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

# Bastion Host EC2
resource "aws_instance" "bastion" {
  ami                         = data.aws_ami.amazon_linux.id
  instance_type               = "t3.micro"
  key_name                    = "bastion-ec2"
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.bastion.id]
  iam_instance_profile        = aws_iam_instance_profile.bastion_profile.name
  user_data_replace_on_change = true
  
  user_data = base64encode(<<-EOF
    #!/bin/bash
    yum update -y
    
    # Install PostgreSQL 14 client and jq
    amazon-linux-extras install postgresql14 -y
    yum install -y jq
    
    # Export database variables
    cat >> /home/ec2-user/.bashrc << 'EOL'
    export RDS_ENDPOINT="${aws_rds_cluster.aurora_serverless.endpoint}"
    export DB_NAME="${var.postgres_db}"
    export DB_USER="${var.postgres_user}"
    export AWS_DEFAULT_REGION="${var.aws_region}"
    
    # Alias for IAM-based RDS connection
    alias rds-connect="PGPASSWORD=\$(aws rds generate-db-auth-token --hostname \$RDS_ENDPOINT --port 5432 --username \$DB_USER --region \$AWS_DEFAULT_REGION) psql -h \$RDS_ENDPOINT -U \$DB_USER -d \$DB_NAME"
    
    # Alias to get master password from secrets manager
    alias get-rds-password="aws secretsmanager get-secret-value --secret-id ${aws_rds_cluster.aurora_serverless.master_user_secret[0].secret_arn} --query SecretString --output text | jq -r .password"
    EOL
    
    # Apply to current session
    source /home/ec2-user/.bashrc
  EOF
  )



  tags = merge(var.tags, {
    Name = "${var.project_name}-bastion"
  })
}

# Associate Elastic IP
resource "aws_eip_association" "bastion" {
  instance_id   = aws_instance.bastion.id
  allocation_id = aws_eip.bastion.id
}

# IAM role for bastion to access RDS and Secrets Manager
resource "aws_iam_role" "bastion_role" {
  name = "${var.project_name}-bastion-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "bastion_policy" {
  name = "${var.project_name}-bastion-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "rds:DescribeDBClusters",
          "rds-db:connect"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_rds_cluster.aurora_serverless.master_user_secret[0].secret_arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "bastion_policy" {
  policy_arn = aws_iam_policy.bastion_policy.arn
  role       = aws_iam_role.bastion_role.name
}

resource "aws_iam_instance_profile" "bastion_profile" {
  name = "${var.project_name}-bastion-profile"
  role = aws_iam_role.bastion_role.name
}