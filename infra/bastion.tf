# Bastion Host Security Group
resource "aws_security_group" "bastion_sg" {
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

# Elastic IP for Bastion Host
resource "aws_eip" "bastion_eip" {
  domain = "vpc"
  tags = merge(var.tags, {
    Name = "${var.project_name}-bastion-eip"
  })
}

# Bastion Host
resource "aws_instance" "bastion" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = "t3.micro"
  key_name              = "bastion-ec2"
  vpc_security_group_ids = [aws_security_group.bastion_sg.id]
  subnet_id             = aws_subnet.public_a.id

  user_data = <<-EOF
    #!/bin/bash
    sudo yum update -y
    sudo amazon-linux-extras enable postgresql14
    sudo yum clean metadata
    sudo yum install -y postgresql
    
    # Set environment variables for database connection
    echo 'export DB_HOST=${aws_rds_cluster.innomightlabs_db.endpoint}' >> /home/ec2-user/.bashrc
    echo 'export DB_PORT=${aws_rds_cluster.innomightlabs_db.port}' >> /home/ec2-user/.bashrc
    echo 'export DB_MASTER_USER=${var.postgres_user}' >> /home/ec2-user/.bashrc
    echo 'export DB_NAME=${var.postgres_db}' >> /home/ec2-user/.bashrc
    echo 'export PGPASSWORD="${var.postgres_password}"' >> /home/ec2-user/.bashrc
  EOF

  tags = merge(var.tags, {
    Name = "${var.project_name}-bastion"
  })
}

# Associate Elastic IP with Bastion Host
resource "aws_eip_association" "bastion_eip_assoc" {
  instance_id   = aws_instance.bastion.id
  allocation_id = aws_eip.bastion_eip.id
}

# Data source for Amazon Linux AMI
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}