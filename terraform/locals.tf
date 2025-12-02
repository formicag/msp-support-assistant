# =============================================================================
# Local Values
# =============================================================================

locals {
  # Common naming prefix
  name_prefix = "${var.project_name}-${var.environment}"

  # Cost tags for resources that don't inherit default_tags (like IAM)
  cost_tags = {
    Project     = "msp-support-assistant"
    Owner       = "Gianluca Formica"
    Environment = var.environment
    GitHubRepo  = "https://github.com/formicag/msp-support-assistant"
    ManagedBy   = "Terraform"
  }

  # AWS Account ID
  account_id = data.aws_caller_identity.current.account_id

  # GitHub OIDC subject claim patterns
  github_oidc_subject      = "repo:${var.github_org}/${var.github_repo}:*"
  github_oidc_subject_main = "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main"
  github_oidc_subject_pr   = "repo:${var.github_org}/${var.github_repo}:pull_request"

  # Resource ARNs
  bedrock_model_arns = [
    "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_claude_model_id}",
    "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_titan_model_id}",
    "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_embedding_model_id}",
  ]
}

# =============================================================================
# Data Sources
# =============================================================================

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_partition" "current" {}
