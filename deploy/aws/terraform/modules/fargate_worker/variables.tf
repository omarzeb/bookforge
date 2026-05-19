variable "account_id"              { type = string }
variable "region"                  { type = string }
variable "environment"             { type = string }
variable "worker_image_uri"        { type = string }
variable "task_execution_role_arn" { type = string }
variable "task_role_arn"           { type = string }
variable "secrets_arn_prefix"      { type = string }
variable "s3_bucket"               { type = string }
variable "api_service_arn"         { type = string; default = "" }
variable "app_internal_secret"     { type = string; default = "" }
