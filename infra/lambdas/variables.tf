variable "api_lambda_variables" {
  description = "Variables passed from parent module for lambda configurations"
  type = object({
    project_name                = string
    aws_region                  = string
    postgres_user              = string
    postgres_db                = string
    stage                      = string
    tags                       = map(string)
    dsql_cluster_arn           = string
    ecr_repository_name        = string
    ecr_repository_url         = string
    aurora_serverless_endpoint = string
    aurora_cluster_identifier  = string
    rds_secret_arn            = string
    private_subnet_id          = string
    lambda_security_group_id   = string
    caller_identity_account_id = string
  })
}