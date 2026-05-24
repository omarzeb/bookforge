variable "environment"             { type = string }
variable "region"                  { type = string }
variable "api_image_uri"           { type = string }
variable "instance_role_arn"       { type = string }
variable "access_role_arn"         { type = string }
variable "secrets_arn_prefix"      { type = string }
variable "ecs_cluster_arn"         { type = string }
variable "ecs_task_definition"     { type = string }
variable "ecs_subnet_ids"          { type = string; default = "" }
variable "ecs_security_group_ids"  { type = string; default = "" }
variable "s3_bucket"               { type = string }
variable "app_internal_secret"     { type = string; default = "" }
variable "custom_domain"           { type = string; default = "" }

variable "frontend_origin" { type = string; default = "" }
