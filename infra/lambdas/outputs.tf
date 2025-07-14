output "innomightlabs_api_lambda_function_name" {
  description = "Main API Lambda function name"
  value       = aws_lambda_function.innomightlabs_api.function_name
}

output "innomightlabs_api_lambda_invoke_arn" {
  description = "Main API Lambda invoke ARN"
  value       = aws_lambda_function.innomightlabs_api.invoke_arn
}

output "simple_lambda_function_name" {
  description = "Simple Lambda function name"
  value       = aws_lambda_function.simple_lambda.function_name
}