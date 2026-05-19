# AWS Budget — alerts before the bill gets out of hand
# Free to set up. Emails you at 50% / 80% / 100% of monthly limit.

resource "aws_sns_topic" "alerts" {
  name = "bookforge-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Actual spend budget — fires when you've already spent the money
resource "aws_budgets_budget" "monthly" {
  name         = "bookforge-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_limit)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }
}

# Forecasted spend budget — warns before you hit the limit
resource "aws_budgets_budget" "forecasted" {
  name         = "bookforge-forecasted"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_limit * 2)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
    subscriber_sns_topic_arns  = [aws_sns_topic.alerts.arn]
  }
}
