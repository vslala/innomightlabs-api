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

# Lambda Environment Variables
variable "postgres_host" {
  description = "PostgreSQL host"
  type        = string
  default     = "localhost"
}

variable "postgres_port" {
  description = "PostgreSQL port"
  type        = string
  default     = "5432"
}

variable "postgres_db" {
  description = "PostgreSQL database name"
  type        = string
  default     = "innomightlabs"
}

variable "postgres_user" {
  description = "PostgreSQL username"
  type        = string
  default     = "iam_db_user"
}

variable "postgres_password" {
  description = "PostgreSQL password"
  type        = string
  sensitive   = true
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
