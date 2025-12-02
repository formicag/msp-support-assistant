# =============================================================================
# Amazon Bedrock AgentCore Gateway
# =============================================================================
# This creates an AgentCore Gateway that exposes Lambda functions as MCP tools.
# The Gateway provides a unified MCP endpoint for AI agents to discover and
# invoke tools securely.

# -----------------------------------------------------------------------------
# AgentCore Gateway IAM Role
# -----------------------------------------------------------------------------
# This role is assumed by the AgentCore Gateway to invoke Lambda functions
# and access other AWS resources on behalf of the agent.

resource "aws_iam_role" "agentcore_gateway" {
  name = "${local.name_prefix}-agentcore-gateway-role"
  path = "/"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "bedrock-agentcore.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
          }
        }
      }
    ]
  })

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-agentcore-gateway-role"
  })
}

resource "aws_iam_role_policy" "agentcore_gateway" {
  name = "agentcore-gateway-policy"
  role = aws_iam_role.agentcore_gateway.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Lambda invocation for tool targets
      {
        Sid    = "LambdaInvoke"
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          aws_lambda_function.ticket_api.arn,
          "${aws_lambda_function.ticket_api.arn}:*",
          aws_lambda_function.agentcore_tools.arn,
          "${aws_lambda_function.agentcore_tools.arn}:*"
        ]
      },
      # CloudWatch Logs for Gateway
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/bedrock-agentcore/${local.name_prefix}*"
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# AgentCore Tools Lambda Function
# -----------------------------------------------------------------------------
# This Lambda function handles MCP-compatible tool calls from the Gateway.
# It accepts map-based parameters (not API Gateway events).

resource "aws_lambda_function" "agentcore_tools" {
  function_name = "${local.name_prefix}-agentcore-tools"
  role          = aws_iam_role.lambda_execution.arn
  handler       = "agentcore_handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 512

  filename         = data.archive_file.agentcore_tools_lambda.output_path
  source_code_hash = data.archive_file.agentcore_tools_lambda.output_base64sha256

  environment {
    variables = {
      TICKETS_TABLE_NAME = aws_dynamodb_table.tickets.name
      ENVIRONMENT        = var.environment
      LOG_LEVEL          = "INFO"
    }
  }

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-agentcore-tools"
  })
}

# Package Lambda code
data "archive_file" "agentcore_tools_lambda" {
  type        = "zip"
  source_file = "${path.module}/../src/lambda/agentcore_handler.py"
  output_path = "${path.module}/.terraform/agentcore_tools_lambda.zip"
}

# Lambda permission for AgentCore Gateway to invoke
resource "aws_lambda_permission" "agentcore_gateway_invoke" {
  statement_id  = "AllowAgentCoreGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.agentcore_tools.function_name
  principal     = "bedrock-agentcore.amazonaws.com"
  source_arn    = "arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:gateway/*"
}

# CloudWatch Log Group for AgentCore Tools Lambda
resource "aws_cloudwatch_log_group" "agentcore_tools" {
  name              = "/aws/lambda/${aws_lambda_function.agentcore_tools.function_name}"
  retention_in_days = 14

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-agentcore-tools-logs"
  })
}

# -----------------------------------------------------------------------------
# SSM Parameters for AgentCore Gateway Configuration
# -----------------------------------------------------------------------------

resource "aws_ssm_parameter" "agentcore_gateway_role_arn" {
  name  = "/${var.project_name}/${var.environment}/agentcore-gateway-role-arn"
  type  = "String"
  value = aws_iam_role.agentcore_gateway.arn

  tags = local.cost_tags
}

resource "aws_ssm_parameter" "agentcore_tools_lambda_arn" {
  name  = "/${var.project_name}/${var.environment}/agentcore-tools-lambda-arn"
  type  = "String"
  value = aws_lambda_function.agentcore_tools.arn

  tags = local.cost_tags
}

# -----------------------------------------------------------------------------
# Outputs for AgentCore Gateway
# -----------------------------------------------------------------------------

output "agentcore_gateway_role_arn" {
  description = "IAM Role ARN for AgentCore Gateway"
  value       = aws_iam_role.agentcore_gateway.arn
}

output "agentcore_tools_lambda_arn" {
  description = "Lambda ARN for AgentCore Tools"
  value       = aws_lambda_function.agentcore_tools.arn
}

output "agentcore_tools_lambda_name" {
  description = "Lambda function name for AgentCore Tools"
  value       = aws_lambda_function.agentcore_tools.function_name
}
