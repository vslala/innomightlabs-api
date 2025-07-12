

output "api_gateway_url" {
  description = "API Gateway URL"
  value       = aws_apigatewayv2_api.innomightlabs_api.api_endpoint
}

output "bastion_ssh_command" {
  description = "SSH command to connect to bastion host"
  value       = "ssh -i ~/.ssh/bastion-ec2.pem ec2-user@${aws_eip.bastion_eip.public_ip}"
}

output "rds_endpoint" {
  description = "Aurora cluster endpoint"
  value       = aws_rds_cluster.innomightlabs_db.endpoint
}