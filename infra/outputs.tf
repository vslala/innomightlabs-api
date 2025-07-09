

output "api_gateway_url" {
  description = "API Gateway URL"
  value       = aws_apigatewayv2_api.innomightlabs_api.api_endpoint
}