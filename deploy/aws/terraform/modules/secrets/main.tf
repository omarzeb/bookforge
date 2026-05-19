# Secrets Manager entries — all secrets live under the bookforge/ prefix
# The App Runner instance role and Fargate task role both have read access to this prefix

locals {
  secrets = {
    fernet_key     = var.fernet_key
    jwt_secret     = var.jwt_secret
    database_url   = var.database_url
    redis_url      = var.redis_url
    app_secret_key = var.app_secret_key
  }
}

resource "aws_secretsmanager_secret" "secrets" {
  for_each                = local.secrets
  name                    = "bookforge/${each.key}"
  recovery_window_in_days = 0   # immediate deletion — no 30-day hold for dev
}

resource "aws_secretsmanager_secret_version" "secrets" {
  for_each      = local.secrets
  secret_id     = aws_secretsmanager_secret.secrets[each.key].id
  secret_string = each.value
}
