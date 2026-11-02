# Each IAM resource type has its own import ID format.

# Role: the role name
import {
  to = aws_iam_role.execution
  id = "findoc-ecs-execution-role"
}

# Managed policy attachment: "role-name/policy-arn"
import {
  to = aws_iam_role_policy_attachment.execution_managed
  id = "findoc-ecs-execution-role/arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Inline policy: "role-name:policy-name"
import {
  to = aws_iam_role_policy.execution_ssm
  id = "findoc-ecs-execution-role:read-findoc-params"
}

import {
  to = aws_iam_role.task
  id = "findoc-ecs-task-role"
}

import {
  to = aws_iam_role_policy.task_s3
  id = "findoc-ecs-task-role:read-chunks"
}
