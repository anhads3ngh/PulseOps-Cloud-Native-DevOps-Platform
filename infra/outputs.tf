output "dashboard_url" {
  value       = aws_apigatewayv2_api.api.api_endpoint
  description = "Public demo endpoint. Mutating requests require X-Demo-Key."
}
output "cloudwatch_dashboard" {
  value = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.operations.dashboard_name}"
}
output "deploy_role_arn" {
  value = aws_iam_role.github_deploy.arn
}
output "ecr_repository_uri" {
  value = data.aws_ecr_repository.image.repository_url
}
output "dlq_name" {
  value = aws_sqs_queue.dead.name
}
