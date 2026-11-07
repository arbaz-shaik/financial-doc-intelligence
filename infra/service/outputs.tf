output "service_name" {
  value = aws_ecs_express_gateway_service.api.service_name
}

output "service_arn" {
  value = aws_ecs_express_gateway_service.api.service_arn
}

output "ingress_paths" {
  value = aws_ecs_express_gateway_service.api.ingress_paths
}

output "log_group" {
  value = aws_cloudwatch_log_group.api.name
}