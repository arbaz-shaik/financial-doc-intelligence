terraform {
  required_version = ">= 1.16, < 2.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.23"
    }
    # Short random suffix for the service name (ECS keeps deleted names reserved)
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}