# App Runner — runs the FastAPI backend
# Auto-scales 1-3 instances, health check on /ready
# Secrets injected from Secrets Manager at startup

resource "aws_apprunner_service" "api" {
  service_name = "bookforge-api"

  source_configuration {
    image_repository {
      image_configuration {
        port = "8080"

        runtime_environment_variables = {
          APP_ENV             = var.environment
          STORAGE_BACKEND     = "s3"
          S3_BUCKET           = var.s3_bucket
          AWS_REGION          = var.region
          ECS_CLUSTER         = var.ecs_cluster_arn
          ECS_TASK_DEFINITION = var.ecs_task_definition
          ECS_SUBNET_IDS      = var.ecs_subnet_ids
          ECS_SECURITY_GROUP_IDS = var.ecs_security_group_ids
          APP_INTERNAL_SECRET = var.app_internal_secret
        }

        runtime_environment_secrets = {
          DATABASE_URL   = "${var.secrets_arn_prefix}/database_url"
          REDIS_URL      = "${var.secrets_arn_prefix}/redis_url"
          FERNET_KEY     = "${var.secrets_arn_prefix}/fernet_key"
          JWT_SECRET     = "${var.secrets_arn_prefix}/jwt_secret"
          APP_SECRET_KEY = "${var.secrets_arn_prefix}/app_secret_key"
        }
      }

      image_identifier      = var.api_image_uri
      image_repository_type = "ECR"
    }

    authentication_configuration {
      access_role_arn = var.access_role_arn
    }

    auto_deployments_enabled = true
  }

  instance_configuration {
    cpu               = "1024"   # 1 vCPU
    memory            = "2048"   # 2 GB
    instance_role_arn = var.instance_role_arn
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/ready"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 3
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.api.arn
}

resource "aws_apprunner_auto_scaling_configuration_version" "api" {
  auto_scaling_configuration_name = "bookforge-api"

  min_size = 1
  max_size = 3   # cost cap: 3 × $0.064/vCPU-hr + 3 × $0.007/GB-hr ≈ $0.23/hr max

  tags = { Name = "bookforge-api" }
}

# Custom domain — only created if custom_domain variable is set
resource "aws_apprunner_custom_domain_association" "api" {
  count       = var.custom_domain != "" ? 1 : 0
  service_arn = aws_apprunner_service.api.arn
  domain_name = var.custom_domain
}
