# =============================================================================
# SSM Parameter Store for Configuration
# =============================================================================

# -----------------------------------------------------------------------------
# Application Configuration Parameters
# -----------------------------------------------------------------------------

resource "aws_ssm_parameter" "api_gateway_endpoint" {
  name        = "/${var.project_name}/${var.environment}/api-gateway-endpoint"
  description = "API Gateway endpoint URL"
  type        = "String"
  value       = aws_apigatewayv2_stage.default.invoke_url

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-api-gateway-endpoint"
  })
}

resource "aws_ssm_parameter" "opensearch_endpoint" {
  name        = "/${var.project_name}/${var.environment}/opensearch-endpoint"
  description = "OpenSearch Serverless collection endpoint"
  type        = "String"
  value       = aws_opensearchserverless_collection.knowledge_base.collection_endpoint

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-opensearch-endpoint"
  })
}

resource "aws_ssm_parameter" "vector_store_bucket" {
  name        = "/${var.project_name}/${var.environment}/vector-store-bucket"
  description = "S3 bucket for vector store"
  type        = "String"
  value       = aws_s3_bucket.vector_store.id

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-vector-store-bucket"
  })
}

resource "aws_ssm_parameter" "tickets_table_name" {
  name        = "/${var.project_name}/${var.environment}/tickets-table-name"
  description = "DynamoDB tickets table name"
  type        = "String"
  value       = aws_dynamodb_table.tickets.name

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-tickets-table-name"
  })
}

resource "aws_ssm_parameter" "bedrock_claude_model" {
  name        = "/${var.project_name}/${var.environment}/bedrock-claude-model"
  description = "Bedrock Claude model ID"
  type        = "String"
  value       = var.bedrock_claude_model_id

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-bedrock-claude-model"
  })
}

resource "aws_ssm_parameter" "bedrock_titan_model" {
  name        = "/${var.project_name}/${var.environment}/bedrock-titan-model"
  description = "Bedrock Titan model ID"
  type        = "String"
  value       = var.bedrock_titan_model_id

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-bedrock-titan-model"
  })
}

resource "aws_ssm_parameter" "bedrock_embedding_model" {
  name        = "/${var.project_name}/${var.environment}/bedrock-embedding-model"
  description = "Bedrock embedding model ID"
  type        = "String"
  value       = var.bedrock_embedding_model_id

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-bedrock-embedding-model"
  })
}

resource "aws_ssm_parameter" "ecr_streamlit_repo" {
  name        = "/${var.project_name}/${var.environment}/ecr-streamlit-repo"
  description = "ECR repository URL for Streamlit"
  type        = "String"
  value       = aws_ecr_repository.streamlit.repository_url

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-ecr-streamlit-repo"
  })
}
