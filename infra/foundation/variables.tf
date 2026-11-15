variable "aws_region" {
  type    = string
  default = "eu-north-1"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "bucket_name" {
  type    = string
  default = "financial-doc-intel-arbaz-2026"
}
variable "github_repo" {
  type    = string
  default = "arbaz-shaik@114905361/financial-doc-intelligence@1181171485" # owner@id/repo@id, as GitHub sends it in the OIDC sub
}