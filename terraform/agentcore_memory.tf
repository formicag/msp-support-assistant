# =============================================================================
# AgentCore Memory - Short-term and Long-term Memory for MSP Support Assistant
# =============================================================================

# -----------------------------------------------------------------------------
# IAM Role for AgentCore Memory Execution
# -----------------------------------------------------------------------------

resource "aws_iam_role" "agentcore_memory_execution" {
  name = "${local.name_prefix}-agentcore-memory-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "bedrock-agentcore.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(local.cost_tags, {
    Name    = "${local.name_prefix}-agentcore-memory-execution"
    Purpose = "AgentCore Memory execution role"
  })
}

# Policy for memory execution - allows Bedrock model invocation for extraction
resource "aws_iam_role_policy" "agentcore_memory_execution" {
  name = "${local.name_prefix}-agentcore-memory-policy"
  role = aws_iam_role.agentcore_memory_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:${var.aws_region}::foundation-model/*"
        ]
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# AgentCore Memory Resource
# -----------------------------------------------------------------------------

resource "aws_bedrockagentcore_memory" "msp_support" {
  name        = "msp_support_assistant_memory"
  description = "Memory for MSP Support Assistant - stores conversation context and user preferences"

  # Event expiry: How long to keep raw conversation events (short-term memory)
  # Must be between 7 and 365 days
  event_expiry_duration = 30

  # Execution role for memory extraction
  memory_execution_role_arn = aws_iam_role.agentcore_memory_execution.arn

  tags = merge(local.cost_tags, {
    Name    = "${local.name_prefix}-memory"
    Purpose = "AgentCore Memory for short-term and long-term context"
  })
}

# -----------------------------------------------------------------------------
# Memory Strategies (Long-term Memory)
# -----------------------------------------------------------------------------

# User Preference Strategy - Remembers user preferences across sessions
resource "aws_bedrockagentcore_memory_strategy" "user_preferences" {
  memory_id   = aws_bedrockagentcore_memory.msp_support.id
  name        = "user_preferences"
  description = "Extracts and stores user preferences like priority levels, categories, and communication style"

  type = "USER_PREFERENCE"

  # Namespace for organizing preference memories
  namespaces = ["/preferences/{actorId}"]

  depends_on = [aws_bedrockagentcore_memory.msp_support]
}

# Semantic Memory Strategy - Remembers facts and domain knowledge
resource "aws_bedrockagentcore_memory_strategy" "semantic" {
  memory_id   = aws_bedrockagentcore_memory.msp_support.id
  name        = "semantic_facts"
  description = "Extracts and stores factual information like user names, departments, and ticket history"

  type = "SEMANTIC"

  # Namespace for organizing semantic memories
  namespaces = ["/facts/{actorId}"]

  depends_on = [aws_bedrockagentcore_memory.msp_support]
}

# Summary Strategy - Creates session summaries
resource "aws_bedrockagentcore_memory_strategy" "summaries" {
  memory_id   = aws_bedrockagentcore_memory.msp_support.id
  name        = "session_summaries"
  description = "Creates condensed summaries of support sessions"

  type = "SUMMARIZATION"

  # Namespace for organizing summary memories
  namespaces = ["/summaries/{actorId}/{sessionId}"]

  depends_on = [aws_bedrockagentcore_memory.msp_support]
}

# -----------------------------------------------------------------------------
# IAM Permissions for Agent to Access Memory
# -----------------------------------------------------------------------------

# Add memory permissions to Lambda execution role
resource "aws_iam_role_policy" "lambda_agentcore_memory" {
  name = "${local.name_prefix}-lambda-agentcore-memory"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AgentCoreMemoryAccess"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:CreateEvent",
          "bedrock-agentcore:GetEvent",
          "bedrock-agentcore:DeleteEvent",
          "bedrock-agentcore:RetrieveMemoryRecords",
          "bedrock-agentcore:GetMemoryRecord",
          "bedrock-agentcore:ListMemoryRecords"
        ]
        Resource = [
          aws_bedrockagentcore_memory.msp_support.arn,
          "${aws_bedrockagentcore_memory.msp_support.arn}/*"
        ]
      },
      {
        Sid    = "AgentCoreMemoryRead"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:GetMemory"
        ]
        Resource = aws_bedrockagentcore_memory.msp_support.arn
      }
    ]
  })
}

# Add memory permissions to agent execution role (for direct agent access)
resource "aws_iam_role_policy" "agent_agentcore_memory" {
  name = "${local.name_prefix}-agent-agentcore-memory"
  role = aws_iam_role.agent_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AgentCoreMemoryAccess"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:CreateEvent",
          "bedrock-agentcore:GetEvent",
          "bedrock-agentcore:DeleteEvent",
          "bedrock-agentcore:RetrieveMemoryRecords",
          "bedrock-agentcore:GetMemoryRecord",
          "bedrock-agentcore:ListMemoryRecords"
        ]
        Resource = [
          aws_bedrockagentcore_memory.msp_support.arn,
          "${aws_bedrockagentcore_memory.msp_support.arn}/*"
        ]
      },
      {
        Sid    = "AgentCoreMemoryRead"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:GetMemory"
        ]
        Resource = aws_bedrockagentcore_memory.msp_support.arn
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "agentcore_memory_id" {
  description = "The ID of the AgentCore Memory resource"
  value       = aws_bedrockagentcore_memory.msp_support.id
}

output "agentcore_memory_arn" {
  description = "The ARN of the AgentCore Memory resource"
  value       = aws_bedrockagentcore_memory.msp_support.arn
}

output "agentcore_memory_strategies" {
  description = "Memory strategies configured"
  value = {
    user_preferences = "user_preferences"
    semantic_facts   = "semantic_facts"
    session_summaries = "session_summaries"
  }
}
