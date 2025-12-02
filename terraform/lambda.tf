# =============================================================================
# Lambda Function for Ticket API
# =============================================================================

# -----------------------------------------------------------------------------
# Lambda Function
# -----------------------------------------------------------------------------

data "archive_file" "ticket_api" {
  type        = "zip"
  source_dir  = "${path.module}/../src/lambda"
  output_path = "${path.module}/.build/ticket_api.zip"
}

resource "aws_lambda_function" "ticket_api" {
  function_name = "${local.name_prefix}-ticket-api"
  description   = "API handler for support ticket operations"

  filename         = data.archive_file.ticket_api.output_path
  source_code_hash = data.archive_file.ticket_api.output_base64sha256

  runtime     = var.lambda_runtime
  handler     = "handler.lambda_handler"
  timeout     = var.lambda_timeout
  memory_size = var.lambda_memory_size

  role = aws_iam_role.lambda_execution.arn

  environment {
    variables = {
      TICKETS_TABLE_NAME  = aws_dynamodb_table.tickets.name
      SESSIONS_TABLE_NAME = aws_dynamodb_table.sessions.name
      ENVIRONMENT         = var.environment
      LOG_LEVEL           = "INFO"
    }
  }

  tracing_config {
    mode = "Active"
  }

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-ticket-api"
  })
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "ticket_api" {
  name              = "/aws/lambda/${aws_lambda_function.ticket_api.function_name}"
  retention_in_days = 30

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-ticket-api-logs"
  })
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ticket_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.ticket_api.execution_arn}/*/*"
}
