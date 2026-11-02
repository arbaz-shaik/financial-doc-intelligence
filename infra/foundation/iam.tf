# Who am I? Used to build ARNs without hardcoding the account ID.
# This only reads your identity - it never reads secrets.
data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id

  # The Groq parameter is NOT managed by Terraform (its value must never enter state).
  # We only build its ARN as a string, for permissions and (in the service stack) the secret.
  groq_param_arn = "arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter/findoc/GROQ_API_KEY"

  # Trust policy shared by both roles: only ECS tasks may assume them.
  ecs_tasks_trust = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# ---------- Task execution role: used by ECS to START the container ----------

resource "aws_iam_role" "execution" {
  name               = "findoc-ecs-execution-role"
  assume_role_policy = local.ecs_tasks_trust
}

# AWS-managed policy: pull from ECR + write CloudWatch logs
resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Inline policy: read only the /findoc/ parameters (to inject GROQ_API_KEY)
resource "aws_iam_role_policy" "execution_ssm" {
  name = "read-findoc-params"
  role = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "ReadFindocParams"
      Effect   = "Allow"
      Action   = "ssm:GetParameters"
      Resource = "arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter/findoc/*"
    }]
  })
}

# ---------- Task role: used by the APP's code while running ----------

resource "aws_iam_role" "task" {
  name               = "findoc-ecs-task-role"
  assume_role_policy = local.ecs_tasks_trust
}

# Inline policy: read-only on chunks/ in the bucket (no write, no delete)
resource "aws_iam_role_policy" "task_s3" {
  name = "read-chunks"
  role = aws_iam_role.task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "ListChunksPrefix"
        Effect    = "Allow"
        Action    = "s3:ListBucket"
        Resource  = aws_s3_bucket.chunks.arn
        Condition = { StringLike = { "s3:prefix" = ["chunks", "chunks/*"] } }
      },
      {
        Sid      = "ReadChunks"
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.chunks.arn}/chunks/*"
      }
    ]
  })
}
# ---------- Infrastructure role: used by Express Mode to BUILD the ALB, target groups, SGs ----------

resource "aws_iam_role" "infrastructure" {
  name = "findoc-ecs-infrastructure-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        # Confused-deputy protection: only ECS acting for THIS account's resources
        StringEquals = { "aws:SourceAccount" = local.account_id }
        ArnEquals    = { "aws:SourceArn" = "arn:aws:ecs:${var.aws_region}:${local.account_id}:*" }
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "infrastructure_managed" {
  role       = aws_iam_role.infrastructure.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices"
}