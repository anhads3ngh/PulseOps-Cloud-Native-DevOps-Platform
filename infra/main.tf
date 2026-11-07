# PulseOps: event-driven, pay-per-use reference architecture.
# Note: AWS resources incur real charges. Teardown with terraform destroy.

resource "aws_dynamodb_table" "jobs" {
  name         = "${local.name}-jobs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  attribute { name = "pk", type = "S" }
  point_in_time_recovery { enabled = false }
  server_side_encryption { enabled = true }
  tags = local.tags
}

resource "aws_sqs_queue" "dead" {
  name                      = "${local.name}-jobs-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
  tags                      = local.tags
}

resource "aws_sqs_queue" "jobs" {
  name                       = "${local.name}-jobs"
  visibility_timeout_seconds = 180 # >= 6 × worker Lambda timeout
  message_retention_seconds  = 345600
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dead.arn
    maxReceiveCount     = 4
  })
  tags = local.tags
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.name}-api"
  retention_in_days = 7
  tags              = local.tags
}
resource "aws_cloudwatch_log_group" "worker" {
  name              = "/aws/lambda/${local.name}-worker"
  retention_in_days = 7
  tags              = local.tags
}

resource "aws_iam_role" "api" {
  name = "${local.name}-api-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = local.tags
}
resource "aws_iam_role" "worker" {
  name = "${local.name}-worker-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = local.tags
}
resource "aws_iam_role_policy_attachment" "api_logs" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
resource "aws_iam_role_policy_attachment" "worker_logs" {
  role       = aws_iam_role.worker.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
resource "aws_iam_role_policy" "api" {
  role = aws_iam_role.api.id
  name = "${local.name}-api-access"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Scan"], Resource = aws_dynamodb_table.jobs.arn },
      { Effect = "Allow", Action = ["sqs:SendMessage"], Resource = aws_sqs_queue.jobs.arn }
    ]
  })
}
resource "aws_iam_role_policy" "worker" {
  role = aws_iam_role.worker.id
  name = "${local.name}-worker-access"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:UpdateItem"], Resource = aws_dynamodb_table.jobs.arn },
      { Effect = "Allow", Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes", "sqs:ChangeMessageVisibility"], Resource = aws_sqs_queue.jobs.arn }
    ]
  })
}

resource "aws_lambda_function" "api" {
  function_name = "${local.name}-api"
  package_type  = "Image"
  image_uri     = var.image_uri
  role          = aws_iam_role.api.arn
  timeout       = 15
  memory_size   = 256
  architectures = ["x86_64"]
  image_config { command = ["pulseops.lambda_adapter.handler"] }
  environment {
    variables = {
      DYNAMO_TABLE    = aws_dynamodb_table.jobs.name
      SQS_QUEUE_URL   = aws_sqs_queue.jobs.url
      SQS_QUEUE_NAME  = aws_sqs_queue.jobs.name
      DEMO_API_KEY    = var.demo_api_key
      MAX_ATTEMPTS    = "4"
    }
  }
  lifecycle { ignore_changes = [image_uri] } # code deployed by GitHub CD via image SHA
  depends_on = [aws_iam_role_policy.api, aws_iam_role_policy_attachment.api_logs, aws_cloudwatch_log_group.api]
  tags = local.tags
}

resource "aws_lambda_function" "worker" {
  function_name = "${local.name}-worker"
  package_type  = "Image"
  image_uri     = var.image_uri
  role          = aws_iam_role.worker.arn
  timeout       = 30
  memory_size   = 256
  architectures = ["x86_64"]
  image_config { command = ["pulseops.worker.handler"] }
  environment {
    variables = {
      DYNAMO_TABLE   = aws_dynamodb_table.jobs.name
      SQS_QUEUE_NAME = aws_sqs_queue.jobs.name
      MAX_ATTEMPTS   = "4"
    }
  }
  lifecycle { ignore_changes = [image_uri] }
  depends_on = [aws_iam_role_policy.worker, aws_iam_role_policy_attachment.worker_logs, aws_cloudwatch_log_group.worker]
  tags = local.tags
}

resource "aws_lambda_event_source_mapping" "queue" {
  event_source_arn        = aws_sqs_queue.jobs.arn
  function_name           = aws_lambda_function.worker.arn
  batch_size              = 5
  function_response_types = ["ReportBatchItemFailures"]
  scaling_config { maximum_concurrency = 2 }
}

resource "aws_apigatewayv2_api" "api" {
  name          = "${local.name}-http"
  protocol_type = "HTTP"
  description   = "Synthetic publishing reliability lab"
  tags          = local.tags
}
resource "aws_apigatewayv2_integration" "api" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}
resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.api.id}"
}
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_rate_limit  = 5
    throttling_burst_limit = 10
  }
  tags = local.tags
}
resource "aws_lambda_permission" "gateway" {
  statement_id  = "AllowPulseOpsApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}

resource "aws_cloudwatch_metric_alarm" "dlq" {
  alarm_name          = "${local.name}-dead-letter-queue-not-empty"
  alarm_description   = "A delivery failed repeatedly; investigate the dead-letter queue"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  dimensions          = { QueueName = aws_sqs_queue.dead.name }
  tags                = local.tags
}
resource "aws_cloudwatch_metric_alarm" "worker_errors" {
  alarm_name          = "${local.name}-worker-invocation-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  dimensions          = { FunctionName = aws_lambda_function.worker.function_name }
  tags                = local.tags
}

resource "aws_cloudwatch_dashboard" "operations" {
  dashboard_name = "${local.name}-operations"
  dashboard_body = jsonencode({
    widgets = [
      { type = "text", x = 0, y = 0, width = 24, height = 2, properties = { markdown = "# PulseOps · Reliability Dashboard\nSimulated delivery jobs · SQS retry/DLQ · Lambda · DynamoDB" } },
      { type = "metric", x = 0, y = 2, width = 12, height = 6, properties = { view = "timeSeries", region = var.aws_region, title = "SQS pending & in-flight", stat = "Average", period = 60, metrics = [["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.jobs.name], ["AWS/SQS", "ApproximateNumberOfMessagesNotVisible", "QueueName", aws_sqs_queue.jobs.name]] } },
      { type = "metric", x = 12, y = 2, width = 12, height = 6, properties = { view = "timeSeries", region = var.aws_region, title = "DLQ messages (alarm threshold > 0)", stat = "Maximum", period = 60, metrics = [["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.dead.name]] } },
      { type = "metric", x = 0, y = 8, width = 12, height = 6, properties = { view = "timeSeries", region = var.aws_region, title = "Application deliveries, retries, terminal failures", stat = "Sum", period = 60, metrics = [["PulseOps/Delivery", "JobPublished"], ["PulseOps/Delivery", "JobRetried"], ["PulseOps/Delivery", "JobFailed"]] } },
      { type = "metric", x = 12, y = 8, width = 12, height = 6, properties = { view = "timeSeries", region = var.aws_region, title = "Lambda worker errors & duration", period = 60, metrics = [["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.worker.function_name, { stat = "Sum" }], ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.worker.function_name, { stat = "Average", yAxis = "right" }]] } }
    ]
  })
}
