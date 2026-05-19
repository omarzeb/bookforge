# ECS Fargate cluster + task definition for the one-shot worker
# No ECS Service — tasks are launched on-demand by the API via boto3.run_task()

resource "aws_ecs_cluster" "bookforge" {
  name = "bookforge"

  setting {
    name  = "containerInsights"
    value = "disabled"   # costs $0.35/GB — disable for portfolio scale
  }
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/bookforge-worker"
  retention_in_days = 7
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "bookforge-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"    # 0.5 vCPU
  memory                   = "1024"   # 1 GB
  execution_role_arn       = var.task_execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([{
    name  = "bookforge-worker"
    image = var.worker_image_uri

    # Entry point — API overrides command with ["--job-id", "<id>"]
    command = ["--help"]

    environment = [
      { name = "APP_ENV",         value = "production" },
      { name = "STORAGE_BACKEND", value = "s3" },
      { name = "S3_BUCKET",       value = var.s3_bucket },
      { name = "AWS_REGION",      value = var.region },
    ]

    secrets = [
      { name = "DATABASE_URL",   valueFrom = "${var.secrets_arn_prefix}/database_url" },
      { name = "REDIS_URL",      valueFrom = "${var.secrets_arn_prefix}/redis_url" },
      { name = "FERNET_KEY",     valueFrom = "${var.secrets_arn_prefix}/fernet_key" },
      { name = "JWT_SECRET",     valueFrom = "${var.secrets_arn_prefix}/jwt_secret" },
      { name = "APP_SECRET_KEY", valueFrom = "${var.secrets_arn_prefix}/app_secret_key" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.worker.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "worker"
      }
    }

    essential = true
  }])
}

# EventBridge rule — hourly reconciliation of stuck jobs
resource "aws_cloudwatch_event_rule" "reconcile" {
  name                = "bookforge-reconcile"
  description         = "Trigger stuck job reconciliation every hour"
  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "reconcile_api" {
  rule      = aws_cloudwatch_event_rule.reconcile.name
  target_id = "bookforge-reconcile-api"
  arn       = var.api_service_arn

  http_target {
    header_parameters = {
      "X-Internal-Secret" = var.app_internal_secret
    }
    path_parameter_values = []
    query_string_parameters = {
      timeout_minutes = "30"
    }
  }
}
