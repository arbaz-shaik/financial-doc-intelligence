output "repository_url" {
  description = "ECR repository URL; the service appends :<git-sha>"
  value       = aws_ecr_repository.api.repository_url
}

output "execution_role_arn" {
  description = "Role ECS uses to start the task (pull image, logs, read secret)"
  value       = aws_iam_role.execution.arn
}

output "task_role_arn" {
  description = "Role the app's code uses (read-only on chunks/)"
  value       = aws_iam_role.task.arn
}

output "infrastructure_role_arn" {
  description = "Role Express Mode uses to build the ALB, target groups and security groups"
  value       = aws_iam_role.infrastructure.arn
}

output "groq_param_arn" {
  description = "ARN of the Groq API key parameter (the value itself is never in Terraform)"
  value       = local.groq_param_arn
}

output "bucket_name" {
  description = "S3 bucket holding the chunks"
  value       = aws_s3_bucket.chunks.id
}