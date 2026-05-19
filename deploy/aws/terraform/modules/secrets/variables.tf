variable "environment"   { type = string }
variable "fernet_key"    { type = string; sensitive = true }
variable "jwt_secret"    { type = string; sensitive = true }
variable "database_url"  { type = string; sensitive = true }
variable "redis_url"     { type = string; sensitive = true }
variable "app_secret_key"{ type = string; sensitive = true }

variable "app_internal_secret" { type = string; sensitive = true; default = "" }
