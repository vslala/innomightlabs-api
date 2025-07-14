# Lambda Execution Role
resource "aws_iam_role" "lambda_execution" {
  name = "${var.api_lambda_variables.project_name}-lambda-execution-role"

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

  tags = var.api_lambda_variables.tags
}

# Consolidated Lambda policy with all required permissions
resource "aws_iam_policy" "lambda_policy" {
  name        = "${var.api_lambda_variables.project_name}-lambda-policy"
  description = "Consolidated policy for Lambda with all required permissions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "dsql:DbConnect"
        ]
        Resource = var.api_lambda_variables.dsql_cluster_arn
      },
      {
        Effect = "Allow"
        Action = [
          "rds-db:connect"
        ]
        Resource = "arn:aws:rds-db:${var.api_lambda_variables.aws_region}:${var.api_lambda_variables.caller_identity_account_id}:dbuser:${var.api_lambda_variables.aurora_cluster_identifier}/${var.api_lambda_variables.postgres_user}"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = var.api_lambda_variables.rds_secret_arn
      }
    ]
  })

  tags = var.api_lambda_variables.tags
}

# Attach consolidated policy to Lambda role
resource "aws_iam_role_policy_attachment" "lambda_policy" {
  policy_arn = aws_iam_policy.lambda_policy.arn
  role       = aws_iam_role.lambda_execution.name
}

data "aws_ecr_image" "innomightlabs_api" {
  repository_name = var.api_lambda_variables.ecr_repository_name
  image_tag       = "latest"
}

resource "aws_lambda_function" "innomightlabs_api" {
  function_name    = "${var.api_lambda_variables.project_name}-lambda"
  role             = aws_iam_role.lambda_execution.arn
  package_type     = "Image"
  image_uri        = "${var.api_lambda_variables.ecr_repository_url}:latest"
  source_code_hash = data.aws_ecr_image.innomightlabs_api.image_digest
  timeout          = 60
  memory_size      = 1024

  vpc_config {
    subnet_ids         = [var.api_lambda_variables.private_subnet_id]
    security_group_ids = [var.api_lambda_variables.lambda_security_group_id]
  }

  environment {
    variables = {
      DSQL_ENDPOINT     = var.api_lambda_variables.dsql_cluster_arn
      RDS_ENDPOINT      = var.api_lambda_variables.aurora_serverless_endpoint
      RDS_SECRET_ARN    = var.api_lambda_variables.rds_secret_arn
      DB_TYPE           = "rds"
      POSTGRES_USER     = var.api_lambda_variables.postgres_user
      POSTGRES_DB       = var.api_lambda_variables.postgres_db
      STAGE             = var.api_lambda_variables.stage
      REGION            = var.api_lambda_variables.aws_region
    }
  }

  tags = var.api_lambda_variables.tags
}