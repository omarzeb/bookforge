variable "account_id"  { type = string }
variable "region"      { type = string }
variable "s3_bucket"   { type = string }
variable "environment" { type = string }

variable "github_repo" {
  description = "GitHub repo in org/repo format e.g. myuser/book-forge"
  type        = string
  default     = "YOUR_USERNAME/book-forge"
}
