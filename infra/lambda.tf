# Lambda Function
resource "aws_lambda_function" "innomightlabs_api" {
  function_name = "${var.project_name}-lambda"
  role          = aws_iam_role.lambda_execution.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.innomightlabs_api.repository_url}:latest"
  timeout       = 60
  memory_size   = 1024

  vpc_config {
    subnet_ids         = [aws_subnet.private_a.id, aws_subnet.private_b.id]
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      POSTGRES_HOST     = aws_rds_cluster.innomightlabs_db.endpoint
      POSTGRES_PORT     = "5432"
      POSTGRES_DB       = aws_rds_cluster.innomightlabs_db.database_name
      POSTGRES_USER     = aws_rds_cluster.innomightlabs_db.master_username
      POSTGRES_PASSWORD = var.postgres_password
      GOOGLE_API_KEY    = var.google_api_key
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_cloudwatch_log_group.lambda_logs,
  ]

  tags = var.tags
}

# CloudWatch Log Group - AWS creates this automatically, so we import or ignore
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.project_name}-lambda"
  retention_in_days = 7
  tags              = var.tags

  lifecycle {
    prevent_destroy = true
  }
}

