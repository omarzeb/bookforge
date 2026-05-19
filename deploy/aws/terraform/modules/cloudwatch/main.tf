# deploy/aws/terraform/modules/cloudwatch/main.tf
#
# CloudWatch log retention — 7 days on all log groups.
# Default is NEVER EXPIRE which accumulates cost indefinitely.
# At ~$0.50/GB ingested + $0.03/GB stored, a busy app can rack up
# surprising bills. 7 days is enough to debug any incident.

locals {
  log_groups = [
    # App Runner ships API logs here automatically
    "/aws/apprunner/bookforge-api/application",
    "/aws/apprunner/bookforge-api/system",
    # Fargate worker tasks
    "/ecs/bookforge-worker",
    # EventBridge reconciliation task
    "/ecs/bookforge-reconcile",
  ]
}

resource "aws_cloudwatch_log_group" "app_logs" {
  for_each          = toset(local.log_groups)
  name              = each.value
  retention_in_days = 7    # cheapest useful retention

  tags = {
    Project     = "bookforge"
    ManagedBy   = "terraform"
  }
}

# CloudWatch Logs Insights saved query — find logs by correlation ID
# Use this when debugging a user-reported issue:
#   1. Get the X-Correlation-ID from the user
#   2. Run this query in the AWS console
resource "aws_cloudwatch_query_definition" "by_correlation_id" {
  name = "bookforge/find-by-correlation-id"

  log_group_names = local.log_groups

  query_string = <<-QUERY
    fields @timestamp, @message
    | filter @message like /CORRELATION_ID_PLACEHOLDER/
    | sort @timestamp asc
    | limit 200
  QUERY
}

# Alarm: 5xx error rate > 5% over 5 minutes → SNS email
resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  alarm_name          = "bookforge-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "5xxError"
  namespace           = "AWS/AppRunner"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "BookForge API returning too many 5xx errors"
  alarm_actions       = [var.alert_sns_arn]
  ok_actions          = [var.alert_sns_arn]

  dimensions = {
    ServiceName = "bookforge-api"
  }
}
