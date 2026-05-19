output "nameservers" {
  value = length(aws_route53_zone.main) > 0 ? aws_route53_zone.main[0].name_servers : []
}
