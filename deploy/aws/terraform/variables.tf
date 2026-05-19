# deploy/aws/terraform/variables.tf

variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (production / staging)"
  type        = string
  default     = "production"
}

variable "alert_email" {
  description = "Email address for budget alerts and CloudWatch alarms"
  type        = string
}

variable "budget_monthly_limit" {
  description = "Monthly spend cap in USD before alerts fire"
  type        = number
  default     = 25
}

# ── Secrets (never commit real values — use terraform.tfvars or env vars) ─────
variable "fernet_key" {
  description = "Fernet key for encrypting OpenRouter API keys at rest"
  type        = string
  sensitive   = true
}

variable "jwt_secret" {
  description = "JWT signing secret"
  type        = string
  sensitive   = true
}

variable "database_url" {
  description = "Neon PostgreSQL async connection string"
  type        = string
  sensitive   = true
}

variable "redis_url" {
  description = "Upstash Redis connection URL"
  type        = string
  sensitive   = true
}

variable "app_secret_key" {
  description = "FastAPI application secret key"
  type        = string
  sensitive   = true
}

variable "app_internal_secret" {
  description = "Shared secret for EventBridge → /internal/reconcile endpoint"
  type        = string
  sensitive   = true
  default     = ""
}

# ── Network ───────────────────────────────────────────────────────────────────
variable "ecs_subnet_ids" {
  description = "Subnet IDs for Fargate tasks (comma-separated string)"
  type        = string
  default     = ""
}

variable "ecs_security_group_ids" {
  description = "Security group IDs for Fargate tasks (comma-separated string)"
  type        = string
  default     = ""
}

# ── Optional ──────────────────────────────────────────────────────────────────
variable "custom_domain" {
  description = "Custom domain for App Runner (leave empty to use auto-generated URL)"
  type        = string
  default     = ""
}
