

output "api_gateway_url" {
  description = "API Gateway URL"
  value       = aws_apigatewayv2_api.innomightlabs_api.api_endpoint
}

output "dsql_endpoint" {
  description = "Aurora DSQL cluster ARN"
  value       = aws_dsql_cluster.innomightlabs_db.arn
}

output "aurora_serverless_endpoint" {
  description = "Aurora Serverless cluster endpoint"
  value       = aws_rds_cluster.aurora_serverless.endpoint
}

output "simple_lambda_function_name" {
  description = "Simple Lambda function name"
  value       = module.api_lambda.simple_lambda_function_name
}

output "bastion_public_ip" {
  description = "Bastion host public IP address"
  value       = aws_eip.bastion.public_ip
}