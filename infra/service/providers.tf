provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "findoc"
      Environment = var.environment
      ManagedBy   = "terraform"
      Stack       = "service"
    }
  }
}