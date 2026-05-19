variable "alert_sns_arn" {
  description = "SNS topic ARN for CloudWatch alarms (created in budget module)"
  type        = string
  default     = ""
}
