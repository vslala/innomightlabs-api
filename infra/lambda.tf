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

# Consolidated Lambda policy with all required permissions
resource "aws_iam_policy" "lambda_policy" {
  name        = "${var.project_name}-lambda-policy"
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
          "dsql:DbConnect",
          "dsql:DbConnectAdmin"
        ]
        Resource = aws_dsql_cluster.innomightlabs_db.arn
      }
    ]
  })

  tags = var.tags
}

# Attach consolidated policy to Lambda role
resource "aws_iam_role_policy_attachment" "lambda_policy" {
  policy_arn = aws_iam_policy.lambda_policy.arn
  role       = aws_iam_role.lambda_execution.name
}

data "aws_ecr_image" "innomightlabs_api" {
  repository_name = aws_ecr_repository.innomightlabs_api.name
  image_tag       = "latest"
}

resource "aws_lambda_function" "innomightlabs_api" {
  function_name    = "${var.project_name}-lambda"
  role             = aws_iam_role.lambda_execution.arn
  package_type     = "Image"
  image_uri        = "${aws_ecr_repository.innomightlabs_api.repository_url}:latest"
  source_code_hash = data.aws_ecr_image.innomightlabs_api.image_digest
  timeout          = 60
  memory_size      = 1024

  environment {
    variables = {
      DSQL_ENDPOINT     = aws_dsql_cluster.innomightlabs_db.arn
      POSTGRES_USER     = var.postgres_user
      POSTGRES_DB       = var.postgres_db
      STAGE             = var.stage
      REGION            = var.aws_region
    }
  }

  tags = var.tags
}
