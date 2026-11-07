# Our own log group, with retention, so logs don't pile up and cost money forever
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/findoc-api-${var.environment}"
  retention_in_days = 7
}