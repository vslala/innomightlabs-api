# Lambda modules with passed variables
module "api_lambda" {
  source = "./lambdas"
  
  # Pass all required variables to lambda modules
  api_lambda_variables = {
    project_name                = var.project_name
    aws_region                  = var.aws_region
    postgres_user              = var.postgres_user
    postgres_db                = var.postgres_db
    google_api_key             = var.google_api_key
    stage                      = var.stage
    tags                       = var.tags
    dsql_cluster_arn           = aws_dsql_cluster.innomightlabs_db.arn
    ecr_repository_name        = aws_ecr_repository.innomightlabs_api.name
    ecr_repository_url         = aws_ecr_repository.innomightlabs_api.repository_url
    aurora_serverless_endpoint = aws_rds_cluster.aurora_serverless.endpoint
    aurora_cluster_identifier  = aws_rds_cluster.aurora_serverless.cluster_identifier
    rds_secret_arn            = aws_rds_cluster.aurora_serverless.master_user_secret[0].secret_arn
    private_subnet_id          = aws_subnet.private.id
    lambda_security_group_id   = aws_security_group.lambda.id
    caller_identity_account_id = data.aws_caller_identity.current.account_id
  }
}