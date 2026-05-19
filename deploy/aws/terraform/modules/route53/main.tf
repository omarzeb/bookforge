# Optional — only create if custom_domain is set
# Provisions: hosted zone + ACM certificate + App Runner custom domain

resource "aws_route53_zone" "main" {
  count = var.domain != "" ? 1 : 0
  name  = var.domain
}

resource "aws_acm_certificate" "main" {
  count             = var.domain != "" ? 1 : 0
  domain_name       = var.domain
  validation_method = "DNS"

  subject_alternative_names = ["*.${var.domain}"]

  lifecycle { create_before_destroy = true }
}
