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