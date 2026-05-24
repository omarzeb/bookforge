output "app_runner_instance_role_arn" { value = aws_iam_role.app_runner_instance.arn }
output "app_runner_access_role_arn"   { value = aws_iam_role.app_runner_access.arn }
output "fargate_execution_role_arn"   { value = aws_iam_role.fargate_execution.arn }
output "fargate_task_role_arn"        { value = aws_iam_role.fargate_task.arn }

output "github_deploy_role_arn" {
  description = "Set this as AWS_DEPLOY_ROLE_ARN in GitHub repo secrets"
  value       = aws_iam_role.github_deploy.arn
}
