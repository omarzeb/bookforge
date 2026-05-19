# deploy/aws/terraform/outputs.tf

output "app_runner_url" {
  description = "Public URL of the BookForge API (and frontend via Caddy if self-hosted)"
  value       = "https://${module.app_runner.service_url}"
}

output "api_ecr_repo" {
  description = "ECR repository URL for the API image"
  value       = module.ecr.api_repo_url
}

output "worker_ecr_repo" {
  description = "ECR repository URL for the worker image"
  value       = module.ecr.worker_repo_url
}

output "s3_bucket" {
  description = "S3 bucket name for compiled books"
  value       = module.s3.bucket_name
}

output "ecs_cluster" {
  description = "ECS cluster name for Fargate worker tasks"
  value       = module.fargate_worker.cluster_name
}

output "ecs_task_definition" {
  description = "ECS task definition ARN for the worker"
  value       = module.fargate_worker.task_definition_arn
}
