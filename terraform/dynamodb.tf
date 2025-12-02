# =============================================================================
# DynamoDB Tables
# =============================================================================

# -----------------------------------------------------------------------------
# Tickets Table
# -----------------------------------------------------------------------------

resource "aws_dynamodb_table" "tickets" {
  name         = "${local.name_prefix}-tickets"
  billing_mode = var.dynamodb_billing_mode
  hash_key     = "TicketId"

  attribute {
    name = "TicketId"
    type = "S"
  }

  attribute {
    name = "CustomerId"
    type = "S"
  }

  attribute {
    name = "Status"
    type = "S"
  }

  attribute {
    name = "CreatedAt"
    type = "S"
  }

  # GSI for querying tickets by customer
  global_secondary_index {
    name            = "CustomerIndex"
    hash_key        = "CustomerId"
    range_key       = "CreatedAt"
    projection_type = "ALL"
  }

  # GSI for querying tickets by status
  global_secondary_index {
    name            = "StatusIndex"
    hash_key        = "Status"
    range_key       = "CreatedAt"
    projection_type = "ALL"
  }

  # Enable point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }

  # TTL for automatic cleanup (optional, disabled by default)
  ttl {
    attribute_name = "ExpiresAt"
    enabled        = false
  }

  tags = merge(local.cost_tags, {
    Name    = "${local.name_prefix}-tickets"
    Purpose = "Support ticket storage"
  })
}

# -----------------------------------------------------------------------------
# Sessions Table (for agent memory/conversation tracking)
# -----------------------------------------------------------------------------

resource "aws_dynamodb_table" "sessions" {
  name         = "${local.name_prefix}-sessions"
  billing_mode = var.dynamodb_billing_mode
  hash_key     = "SessionId"

  attribute {
    name = "SessionId"
    type = "S"
  }

  attribute {
    name = "UserId"
    type = "S"
  }

  # GSI for querying sessions by user
  global_secondary_index {
    name            = "UserIndex"
    hash_key        = "UserId"
    projection_type = "ALL"
  }

  # Enable TTL for session expiration
  ttl {
    attribute_name = "ExpiresAt"
    enabled        = true
  }

  # Enable point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }

  tags = merge(local.cost_tags, {
    Name    = "${local.name_prefix}-sessions"
    Purpose = "Agent session and conversation tracking"
  })
}
