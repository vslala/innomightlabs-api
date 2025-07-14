# API Gateway
resource "aws_apigatewayv2_api" "innomightlabs_api" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"
  
  cors_configuration {
    allow_origins     = ["*"]
    allow_methods     = ["*"]
    allow_headers     = ["*"]
  }
  
  tags = var.tags
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id           = aws_apigatewayv2_api.innomightlabs_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = module.api_lambda.innomightlabs_api_lambda_invoke_arn
}

resource "aws_apigatewayv2_route" "proxy" {
  api_id    = aws_apigatewayv2_api.innomightlabs_api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.innomightlabs_api.id
  name        = "$default"
  auto_deploy = true
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = module.api_lambda.innomightlabs_api_lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.innomightlabs_api.execution_arn}/*/*"
}