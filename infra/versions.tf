terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

provider "aws" { region = var.aws_region }

variable "aws_region" {
  type        = string
  description = "AWS deployment region"
  default     = "ca-central-1"
}
variable "image_uri" {
  type        = string
  description = "Pushed ECR image URI INCLUDING a digest or tag for first Terraform deploy"
}
variable "demo_api_key" {
  type        = string
  sensitive   = true
  description = "Demo write key; stored in Terraform state and Lambda environment. Never commit it."
  validation {
    condition     = length(var.demo_api_key) >= 20
    error_message = "Choose a random demo API key of at least 20 characters."
  }
}
variable "github_repository" {
  type        = string
  description = "Exact owner/repository (e.g. alice/pulseops), used to restrict deploy OIDC trust to main"
  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "Enter a GitHub owner/repository slug."
  }
}
variable "ecr_repository_name" {
  type    = string
  default = "pulseops-delivery"
}

locals {
  name = "pulseops"
  tags = { Project = "PulseOps", ManagedBy = "Terraform", Environment = "portfolio-demo" }
}

data "aws_caller_identity" "current" {}
data "aws_ecr_repository" "image" { name = var.ecr_repository_name }
