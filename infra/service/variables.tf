variable "aws_region" {
  type    = string
  default = "eu-north-1"
}

variable "environment" {
  type    = string
  default = "dev"
}

# No default on purpose: you must choose which image (git commit SHA) to deploy
variable "image_tag" {
  type        = string
  description = "ECR image tag to deploy, e.g. a git commit SHA"
}