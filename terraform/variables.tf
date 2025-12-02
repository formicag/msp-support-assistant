# =============================================================================
# Project Configuration Variables
# =============================================================================

variable "project_name" {
  description = "Name of the project, used for resource naming"
  type        = string
  default     = "msp-support-assistant"
}

variable "environment" {
  description = "Environment name (demo, dev, staging, prod)"
  type        = string
  default     = "demo"

  validation {
    condition     = contains(["demo", "dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: demo, dev, staging, prod."
  }
}

variable "aws_region" {
  description = "AWS region for resource deployment"
  type        = string
  default     = "us-east-1"
}

# =============================================================================
# Cost Tags (applied via default_tags but also available for explicit use)
# =============================================================================

variable "cost_tags" {
  description = "Cost allocation tags for all AWS resources"
  type        = map(string)
  default = {
    Project     = "msp-support-assistant"
    Owner       = "Gianluca Formica"
    Environment = "demo"
    GitHubRepo  = "https://github.com/formicag/msp-support-assistant"
  }
}

# =============================================================================
# GitHub OIDC Configuration
# =============================================================================

variable "github_org" {
  description = "GitHub organization or username"
  type        = string
  default     = "formicag"
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "msp-support-assistant"
}

variable "github_oidc_thumbprint" {
  description = "GitHub OIDC provider thumbprint"
  type        = string
  default     = "6938fd4d98bab03faadb97b34396831e3780aea1"
}

# =============================================================================
# Bedrock Configuration
# =============================================================================

variable "bedrock_claude_model_id" {
  description = "Anthropic Claude model ID for complex queries"
  type        = string
  default     = "anthropic.claude-3-sonnet-20240229-v1:0"
}

variable "bedrock_titan_model_id" {
  description = "Amazon Titan model ID for simple queries"
  type        = string
  default     = "amazon.titan-text-express-v1"
}

variable "bedrock_embedding_model_id" {
  description = "Amazon Titan Embeddings model ID"
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
}

# =============================================================================
# OpenSearch Serverless Configuration
# =============================================================================

variable "opensearch_collection_name" {
  description = "Name for the OpenSearch Serverless collection"
  type        = string
  default     = "msp-knowledge-base"
}

variable "opensearch_index_name" {
  description = "Name for the OpenSearch vector index"
  type        = string
  default     = "tickets-index"
}

variable "embedding_dimension" {
  description = "Dimension of the embedding vectors"
  type        = number
  default     = 1024 # Titan Embeddings v2 dimension
}

# =============================================================================
# DynamoDB Configuration
# =============================================================================

variable "dynamodb_billing_mode" {
  description = "DynamoDB billing mode (PAY_PER_REQUEST or PROVISIONED)"
  type        = string
  default     = "PAY_PER_REQUEST"
}

# =============================================================================
# App Runner Configuration
# =============================================================================

variable "streamlit_cpu" {
  description = "CPU units for Streamlit App Runner service"
  type        = string
  default     = "1024" # 1 vCPU
}

variable "streamlit_memory" {
  description = "Memory for Streamlit App Runner service"
  type        = string
  default     = "2048" # 2 GB
}

variable "streamlit_port" {
  description = "Port for Streamlit application"
  type        = number
  default     = 8501
}

# =============================================================================
# Lambda Configuration
# =============================================================================

variable "lambda_runtime" {
  description = "Lambda runtime for ticket API"
  type        = string
  default     = "python3.11"
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 30
}

variable "lambda_memory_size" {
  description = "Lambda memory size in MB"
  type        = number
  default     = 256
}
