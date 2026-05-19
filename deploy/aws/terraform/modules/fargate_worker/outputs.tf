output "cluster_arn"         { value = aws_ecs_cluster.bookforge.arn }
output "cluster_name"        { value = aws_ecs_cluster.bookforge.name }
output "task_definition_arn" { value = aws_ecs_task_definition.worker.arn }
