output "api_repo_url"     { value = aws_ecr_repository.api.repository_url }
output "worker_repo_url"  { value = aws_ecr_repository.worker.repository_url }
output "api_repo_name"    { value = aws_ecr_repository.api.name }
output "worker_repo_name" { value = aws_ecr_repository.worker.name }
