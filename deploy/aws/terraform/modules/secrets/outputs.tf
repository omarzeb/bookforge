output "secrets_arn_prefix" {
  value = "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:bookforge"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

output "secret_arns" {
  value = { for k, v in aws_secretsmanager_secret.secrets : k => v.arn }
}
