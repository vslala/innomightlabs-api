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

  # <-- No vpc_config here!

  environment {
    variables = {
      POSTGRES_HOST     = aws_rds_cluster.innomightlabs_db.endpoint
      POSTGRES_PORT     = aws_rds_cluster.innomightlabs_db.port
      POSTGRES_USER     = var.postgres_user
      POSTGRES_PASSWORD = var.postgres_password
      POSTGRES_DB       = var.postgres_db
    }
  }

  tags = var.tags
}
