# Lambda Execution Role
resource "aws_iam_role" "lambda_execution" {
  name = "${var.project_name}-lambda-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# Basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.lambda_execution.name
}

# VPC execution policy for Lambda
resource "aws_iam_role_policy_attachment" "lambda_vpc_execution" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
  role       = aws_iam_role.lambda_execution.name
}

# Bedrock access policy for Lambda
resource "aws_iam_policy" "lambda_bedrock_access" {
  name        = "${var.project_name}-lambda-bedrock-access"
  description = "Policy for Lambda to access Bedrock"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "*"
      }
    ]
  })

  tags = var.tags
}

# Attach Bedrock policy to Lambda role
resource "aws_iam_role_policy_attachment" "lambda_bedrock" {
  policy_arn = aws_iam_policy.lambda_bedrock_access.arn
  role       = aws_iam_role.lambda_execution.name
}

# Secrets Manager access policy for Lambda
resource "aws_iam_policy" "lambda_secrets_access" {
  name        = "${var.project_name}-lambda-secrets-access"
  description = "Policy for Lambda to access Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_secretsmanager_secret.aurora_credentials.arn
      }
    ]
  })

  tags = var.tags
}

# Attach Secrets Manager policy to Lambda role
resource "aws_iam_role_policy_attachment" "lambda_secrets" {
  policy_arn = aws_iam_policy.lambda_secrets_access.arn
  role       = aws_iam_role.lambda_execution.name
}

# RDS IAM authentication policy for Lambda
resource "aws_iam_policy" "lambda_rds_connect" {
  name        = "${var.project_name}-lambda-rds-connect"
  description = "Policy for Lambda to connect to RDS using IAM authentication"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "rds-db:connect"
        ]
        Resource = "arn:aws:rds-db:${var.aws_region}:*:dbuser:${aws_rds_cluster.innomightlabs_db.cluster_identifier}/${var.postgres_user}"
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "lambda_rds_connect" {
  policy_arn = aws_iam_policy.lambda_rds_connect.arn
  role       = aws_iam_role.lambda_execution.name
}

# GitHub OIDC Provider
resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com",
  ]

  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd"
  ]

  tags = var.tags
}

# IAM Role for GitHub Actions
resource "aws_iam_role" "github_actions" {
  name = "${var.project_name}-github-actions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_repository}:*"
          }
        }
      }
    ]
  })

  tags = var.tags
}

# IAM Policy for GitHub Actions Terraform deployment
resource "aws_iam_policy" "github_actions_access" {
  name        = "${var.project_name}-github-actions-access"
  description = "Policy for GitHub Actions to deploy infrastructure via Terraform"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::innomightlabs-api-terraform-state",
          "arn:aws:s3:::innomightlabs-api-terraform-state/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:*",
          "lambda:*",
          "apigateway:*",
          "logs:*",
          "ec2:*",
          "rds:*",
          "secretsmanager:*"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:*"
        ]
        Resource = [
          "arn:aws:iam::*:role/${var.project_name}-*",
          "arn:aws:iam::*:policy/${var.project_name}-*",
          "arn:aws:iam::*:instance-profile/${var.project_name}-*",
          "arn:aws:iam::*:oidc-provider/token.actions.githubusercontent.com"
        ]
      }
    ]
  })

  tags = var.tags
}

# Attach policy to GitHub Actions role
resource "aws_iam_role_policy_attachment" "github_actions_access" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions_access.arn
}