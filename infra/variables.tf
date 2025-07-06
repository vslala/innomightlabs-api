variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "innomightlabs-api"
}

variable "ecr_repository_name" {
  description = "Name of the ECR repository"
  type        = string
  default     = "innomightlabs-api"
}

variable "github_repository" {
  description = "GitHub repository in the format owner/repo"
  type        = string
  default     = "vslala/innomightlabs-api"
}

variable "tags" {
  description = "Common tags to be applied to all resources"
  type        = map(string)
  default = {
    Project     = "innomightlabs-api"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}

# Aurora DSQL Environment Variables
variable "postgres_db" {
  description = "Database name for Aurora DSQL"
  type        = string
  default     = "innomightlabs"
}

variable "postgres_user" {
  description = "Database username for Aurora DSQL (IAM-based)"
  type        = string
  default     = "iam_db_user"
}

# Legacy variable kept for CI/CD compatibility
variable "postgres_password" {
  description = "Not used with Aurora DSQL (IAM authentication)"
  type        = string
  sensitive   = true
  default     = "unused"
}

variable "google_api_key" {
  description = "Google API key"
  type        = string
  sensitive   = true
}

variable "stage" {
  description = "Stage of the deployment (e.g., dev, staging, prod)"
  type        = string
  default     = "dev"
}
