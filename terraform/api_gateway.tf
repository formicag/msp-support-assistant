# =============================================================================
# API Gateway (HTTP API)
# =============================================================================

# -----------------------------------------------------------------------------
# HTTP API
# -----------------------------------------------------------------------------

resource "aws_apigatewayv2_api" "ticket_api" {
  name          = "${local.name_prefix}-ticket-api"
  description   = "HTTP API for MSP Support Ticket operations"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins     = ["*"]
    allow_methods     = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allow_headers     = ["Content-Type", "Authorization", "X-Api-Key"]
    expose_headers    = ["X-Request-Id"]
    max_age           = 300
    allow_credentials = false
  }

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-ticket-api"
  })
}

# -----------------------------------------------------------------------------
# Lambda Integration
# -----------------------------------------------------------------------------

resource "aws_apigatewayv2_integration" "ticket_api" {
  api_id                 = aws_apigatewayv2_api.ticket_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.ticket_api.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------

# Create ticket
resource "aws_apigatewayv2_route" "create_ticket" {
  api_id    = aws_apigatewayv2_api.ticket_api.id
  route_key = "POST /tickets"
  target    = "integrations/${aws_apigatewayv2_integration.ticket_api.id}"
}

# Get ticket by ID
resource "aws_apigatewayv2_route" "get_ticket" {
  api_id    = aws_apigatewayv2_api.ticket_api.id
  route_key = "GET /tickets/{ticketId}"
  target    = "integrations/${aws_apigatewayv2_integration.ticket_api.id}"
}

# Update ticket
resource "aws_apigatewayv2_route" "update_ticket" {
  api_id    = aws_apigatewayv2_api.ticket_api.id
  route_key = "PATCH /tickets/{ticketId}"
  target    = "integrations/${aws_apigatewayv2_integration.ticket_api.id}"
}

# List tickets
resource "aws_apigatewayv2_route" "list_tickets" {
  api_id    = aws_apigatewayv2_api.ticket_api.id
  route_key = "GET /tickets"
  target    = "integrations/${aws_apigatewayv2_integration.ticket_api.id}"
}

# Delete ticket
resource "aws_apigatewayv2_route" "delete_ticket" {
  api_id    = aws_apigatewayv2_api.ticket_api.id
  route_key = "DELETE /tickets/{ticketId}"
  target    = "integrations/${aws_apigatewayv2_integration.ticket_api.id}"
}

# Health check
resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.ticket_api.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.ticket_api.id}"
}

# -----------------------------------------------------------------------------
# Stage
# -----------------------------------------------------------------------------

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.ticket_api.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId         = "$context.requestId"
      ip                = "$context.identity.sourceIp"
      requestTime       = "$context.requestTime"
      httpMethod        = "$context.httpMethod"
      routeKey          = "$context.routeKey"
      status            = "$context.status"
      protocol          = "$context.protocol"
      responseLength    = "$context.responseLength"
      integrationError  = "$context.integrationErrorMessage"
      integrationStatus = "$context.integrationStatus"
    })
  }

  default_route_settings {
    throttling_burst_limit = 100
    throttling_rate_limit  = 50
  }

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-api-default-stage"
  })
}

# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${local.name_prefix}-ticket-api"
  retention_in_days = 30

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-api-gateway-logs"
  })
}
