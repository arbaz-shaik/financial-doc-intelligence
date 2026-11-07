resource "random_id" "suffix" {
  byte_length = 3 # 6 hex characters, e.g. "a1b2c3"
}

resource "aws_ecs_express_gateway_service" "api" {
  service_name = "findoc-api-${random_id.suffix.hex}"

  execution_role_arn      = local.f.execution_role_arn
  infrastructure_role_arn = local.f.infrastructure_role_arn
  task_role_arn           = local.f.task_role_arn

  health_check_path = "/health"
  cpu               = "1024" # 1 vCPU
  memory            = "3072" # 3 GB

  wait_for_steady_state = true

  scaling_target = [{
    auto_scaling_metric       = "AVERAGE_CPU"
    auto_scaling_target_value = 60
    min_task_count            = 1
    max_task_count            = 1
  }]

  primary_container {
    image          = "${local.f.repository_url}:${var.image_tag}"
    container_port = 8000

    aws_logs_configuration = [{
      log_group         = aws_cloudwatch_log_group.api.name
      log_stream_prefix = "ecs"
    }]

    environment {
      name  = "STORAGE_MODE"
      value = "s3"
    }
    environment {
      name  = "S3_BUCKET"
      value = local.f.bucket_name
    }
    environment {
      name  = "CHROMA_MODE"
      value = "local"
    }
    environment {
      name  = "CHROMA_PATH"
      value = "/tmp/chroma"
    }
    environment {
      name  = "INDEX_ON_STARTUP"
      value = "true"
    }
    environment {
      name  = "HF_HUB_OFFLINE"
      value = "1"
    }

    # Only the ARN passes through Terraform; ECS fetches the value at container start
    secret {
      name       = "GROQ_API_KEY"
      value_from = local.f.groq_param_arn
    }
  }

  timeouts {
    create = "20m"
    update = "20m"
    delete = "20m"
  }
}