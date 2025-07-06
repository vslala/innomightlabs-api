# Infrastructure

This directory contains Terraform configuration for the InnomightLabs API infrastructure.

## Resources Created

- **ECR Repository**: For storing Docker images
- **IAM Role**: For GitHub Actions to access AWS resources
- **OIDC Provider**: For GitHub Actions authentication

## Setup

1. **Initialize Terraform**:
   ```bash
   cd infra
   terraform init
   ```

2. **Plan the deployment**:
   ```bash
   terraform plan
   ```

3. **Apply the configuration**:
   ```bash
   terraform apply
   ```

4. **Configure GitHub Secrets**:
   After applying, add the GitHub Actions role ARN to your repository secrets:
   - Go to your GitHub repository settings
   - Navigate to Secrets and variables > Actions
   - Add a new secret named `AWS_ROLE_ARN` with the value from terraform output

## Usage

The infrastructure supports:
- Automatic Docker image builds on push to main branch
- ECR repository with lifecycle policies to manage image retention
- Secure GitHub Actions authentication via OIDC

## Customization

Update `variables.tf` to customize:
- AWS region
- Repository names
- GitHub repository path
- Tags