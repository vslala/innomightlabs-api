output "bastion_public_ip" {
  description = "Public IP of the bastion server"
  value       = aws_instance.bastion.public_ip
}

output "bastion_ssh_command" {
  description = "SSH command to connect to bastion"
  value       = "ssh -i bastion-ec2.pem ec2-user@${aws_instance.bastion.public_ip}"
}

output "api_gateway_url" {
  description = "API Gateway URL"
  value       = aws_apigatewayv2_api.innomightlabs_api.api_endpoint
}