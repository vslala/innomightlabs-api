

output "api_gateway_url" {
  description = "API Gateway URL"
  value       = aws_apigatewayv2_api.innomightlabs_api.api_endpoint
}

output "dsql_endpoint" {
  description = "Aurora DSQL cluster ARN"
  value       = aws_dsql_cluster.innomightlabs_db.arn
}