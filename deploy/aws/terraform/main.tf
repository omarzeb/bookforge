# deploy/aws/terraform/main.tf
# Root module — wires all sub-modules together.
# Run: terraform init && terraform plan && terraform apply

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Uncomment after first apply to store state remotely (recommended)
  # backend "s3" {
  #   bucket = "bookforge-terraform-state-{your-account-id}"
  #   key    = "bookforge/terraform.tfstate"
  #   region = var.aws_region
  #   encrypt = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "bookforge"
      ManagedBy = "terraform"
      Env       = var.environment
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
}

# ── Modules ───────────────────────────────────────────────────────────────────

module "ecr" {
  source      = "./modules/ecr"
  environment = var.environment
}

module "iam" {
  source      = "./modules/iam"
  account_id  = local.account_id
  region      = local.region
  s3_bucket   = module.s3.bucket_arn
  environment = var.environment
}

module "secrets" {
  source               = "./modules/secrets"
  environment          = var.environment
  fernet_key           = var.fernet_key
  jwt_secret           = var.jwt_secret
  database_url         = var.database_url
  redis_url            = var.redis_url
  app_secret_key       = var.app_secret_key
}

module "s3" {
  source      = "./modules/s3"
  account_id  = local.account_id
  environment = var.environment
}

module "cloudwatch" {
  source        = "./modules/cloudwatch"
  alert_sns_arn = module.budget.alert_sns_arn
}

module "fargate_worker" {
  source                     = "./modules/fargate_worker"
  account_id                 = local.account_id
  region                     = local.region
  environment                = var.environment
  worker_image_uri           = "${module.ecr.worker_repo_url}:latest"
  task_execution_role_arn    = module.iam.fargate_execution_role_arn
  task_role_arn              = module.iam.fargate_task_role_arn
  secrets_arn_prefix         = module.secrets.secrets_arn_prefix
  s3_bucket                  = module.s3.bucket_name
}

module "app_runner" {
  source                  = "./modules/app_runner"
  environment             = var.environment
  region                  = local.region
  api_image_uri           = "${module.ecr.api_repo_url}:latest"
  instance_role_arn       = module.iam.app_runner_instance_role_arn
  access_role_arn         = module.iam.app_runner_access_role_arn
  secrets_arn_prefix      = module.secrets.secrets_arn_prefix
  ecs_cluster_arn         = module.fargate_worker.cluster_arn
  ecs_task_definition     = module.fargate_worker.task_definition_arn
  ecs_subnet_ids          = var.ecs_subnet_ids
  ecs_security_group_ids  = var.ecs_security_group_ids
  s3_bucket               = module.s3.bucket_name
  app_internal_secret     = var.app_internal_secret
  custom_domain           = var.custom_domain
}

module "budget" {
  source         = "./modules/budget"
  alert_email    = var.alert_email
  monthly_limit  = var.budget_monthly_limit
}
