# =============================================================================
# Terraform Outputs
# =============================================================================

# -----------------------------------------------------------------------------
# General Information
# -----------------------------------------------------------------------------

output "aws_account_id" {
  description = "AWS Account ID"
  value       = local.account_id
}

output "aws_region" {
  description = "AWS Region"
  value       = var.aws_region
}

output "environment" {
  description = "Environment name"
  value       = var.environment
}

# -----------------------------------------------------------------------------
# GitHub OIDC
# -----------------------------------------------------------------------------

output "github_actions_role_arn" {
  description = "ARN of the GitHub Actions IAM role for OIDC authentication"
  value       = aws_iam_role.github_actions.arn
}

output "github_oidc_provider_arn" {
  description = "ARN of the GitHub OIDC provider"
  value       = aws_iam_openid_connect_provider.github.arn
}

# -----------------------------------------------------------------------------
# S3 Buckets
# -----------------------------------------------------------------------------

output "vector_store_bucket_name" {
  description = "Name of the S3 bucket for vector store"
  value       = aws_s3_bucket.vector_store.id
}

output "vector_store_bucket_arn" {
  description = "ARN of the S3 bucket for vector store"
  value       = aws_s3_bucket.vector_store.arn
}

output "artifacts_bucket_name" {
  description = "Name of the S3 bucket for artifacts"
  value       = aws_s3_bucket.artifacts.id
}

# -----------------------------------------------------------------------------
# DynamoDB
# -----------------------------------------------------------------------------

output "tickets_table_name" {
  description = "Name of the DynamoDB tickets table"
  value       = aws_dynamodb_table.tickets.name
}

output "tickets_table_arn" {
  description = "ARN of the DynamoDB tickets table"
  value       = aws_dynamodb_table.tickets.arn
}

# -----------------------------------------------------------------------------
# OpenSearch Serverless
# -----------------------------------------------------------------------------

output "opensearch_collection_endpoint" {
  description = "OpenSearch Serverless collection endpoint"
  value       = aws_opensearchserverless_collection.knowledge_base.collection_endpoint
}

output "opensearch_collection_arn" {
  description = "OpenSearch Serverless collection ARN"
  value       = aws_opensearchserverless_collection.knowledge_base.arn
}

# -----------------------------------------------------------------------------
# Lambda
# -----------------------------------------------------------------------------

output "ticket_api_lambda_arn" {
  description = "ARN of the ticket API Lambda function"
  value       = aws_lambda_function.ticket_api.arn
}

output "ticket_api_lambda_name" {
  description = "Name of the ticket API Lambda function"
  value       = aws_lambda_function.ticket_api.function_name
}

# -----------------------------------------------------------------------------
# API Gateway
# -----------------------------------------------------------------------------

output "api_gateway_endpoint" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "api_gateway_id" {
  description = "API Gateway ID"
  value       = aws_apigatewayv2_api.ticket_api.id
}

# -----------------------------------------------------------------------------
# ECR
# -----------------------------------------------------------------------------

output "ecr_repository_url" {
  description = "ECR repository URL for Streamlit image"
  value       = aws_ecr_repository.streamlit.repository_url
}

output "ecr_repository_name" {
  description = "ECR repository name"
  value       = aws_ecr_repository.streamlit.name
}

# -----------------------------------------------------------------------------
# App Runner
# -----------------------------------------------------------------------------

output "streamlit_app_url" {
  description = "Streamlit App Runner service URL"
  value       = aws_apprunner_service.streamlit.service_url
}

output "streamlit_app_arn" {
  description = "Streamlit App Runner service ARN"
  value       = aws_apprunner_service.streamlit.arn
}

# -----------------------------------------------------------------------------
# IAM Roles
# -----------------------------------------------------------------------------

output "agent_execution_role_arn" {
  description = "ARN of the Bedrock Agent execution role"
  value       = aws_iam_role.agent_execution.arn
}

output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda_execution.arn
}

output "app_runner_role_arn" {
  description = "ARN of the App Runner instance role"
  value       = aws_iam_role.app_runner_instance.arn
}

# -----------------------------------------------------------------------------
# SSM Parameters (for application configuration)
# -----------------------------------------------------------------------------

output "ssm_parameter_prefix" {
  description = "SSM Parameter Store prefix for this project"
  value       = "/${var.project_name}/${var.environment}"
}
