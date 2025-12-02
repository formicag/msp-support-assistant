# =============================================================================
# Amazon Cognito User Pool for AgentCore Gateway Authentication
# =============================================================================
# This provides JWT authentication for the AgentCore Gateway.
# Uses M2M (machine-to-machine) client credentials flow for Streamlit app.

# -----------------------------------------------------------------------------
# Cognito User Pool
# -----------------------------------------------------------------------------

resource "aws_cognito_user_pool" "agentcore_gateway" {
  name = "${local.name_prefix}-agentcore-gateway-pool"

  # Password policy (required even for M2M)
  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
    require_uppercase = true
  }

  # Account recovery
  account_recovery_setting {
    recovery_mechanism {
      name     = "admin_only"
      priority = 1
    }
  }

  # MFA disabled for M2M clients
  mfa_configuration = "OFF"

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-agentcore-gateway-pool"
  })
}

# -----------------------------------------------------------------------------
# Cognito User Pool Domain
# -----------------------------------------------------------------------------

resource "aws_cognito_user_pool_domain" "agentcore_gateway" {
  domain       = "${local.name_prefix}-agentcore-${random_id.suffix.hex}"
  user_pool_id = aws_cognito_user_pool.agentcore_gateway.id
}

# Random suffix for unique domain name
resource "random_id" "suffix" {
  byte_length = 4
}

# -----------------------------------------------------------------------------
# Resource Server (defines scopes for API access)
# -----------------------------------------------------------------------------

resource "aws_cognito_resource_server" "agentcore_gateway" {
  identifier   = "agentcore-gateway"
  name         = "AgentCore Gateway API"
  user_pool_id = aws_cognito_user_pool.agentcore_gateway.id

  scope {
    scope_name        = "tools"
    scope_description = "Access to AgentCore Gateway tools"
  }

  scope {
    scope_name        = "invoke"
    scope_description = "Invoke tools via Gateway"
  }
}

# -----------------------------------------------------------------------------
# M2M Client (for Streamlit application)
# -----------------------------------------------------------------------------

resource "aws_cognito_user_pool_client" "agentcore_m2m" {
  name         = "${local.name_prefix}-agentcore-m2m-client"
  user_pool_id = aws_cognito_user_pool.agentcore_gateway.id

  # M2M client configuration
  generate_secret = true

  # OAuth2 settings for client credentials flow
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes = [
    "${aws_cognito_resource_server.agentcore_gateway.identifier}/tools",
    "${aws_cognito_resource_server.agentcore_gateway.identifier}/invoke"
  ]

  # Token validity
  access_token_validity  = 1  # 1 hour
  id_token_validity      = 1  # 1 hour
  refresh_token_validity = 30 # 30 days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # Prevent user existence errors
  prevent_user_existence_errors = "ENABLED"

  # Explicit auth flows
  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]

  depends_on = [aws_cognito_resource_server.agentcore_gateway]
}

# -----------------------------------------------------------------------------
# Outputs for Cognito
# -----------------------------------------------------------------------------

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = aws_cognito_user_pool.agentcore_gateway.id
}

output "cognito_user_pool_arn" {
  description = "Cognito User Pool ARN"
  value       = aws_cognito_user_pool.agentcore_gateway.arn
}

output "cognito_client_id" {
  description = "Cognito M2M Client ID"
  value       = aws_cognito_user_pool_client.agentcore_m2m.id
}

output "cognito_client_secret" {
  description = "Cognito M2M Client Secret"
  value       = aws_cognito_user_pool_client.agentcore_m2m.client_secret
  sensitive   = true
}

output "cognito_domain" {
  description = "Cognito User Pool Domain"
  value       = "https://${aws_cognito_user_pool_domain.agentcore_gateway.domain}.auth.${var.aws_region}.amazoncognito.com"
}

output "cognito_token_endpoint" {
  description = "Cognito Token Endpoint for M2M authentication"
  value       = "https://${aws_cognito_user_pool_domain.agentcore_gateway.domain}.auth.${var.aws_region}.amazoncognito.com/oauth2/token"
}

output "cognito_discovery_url" {
  description = "Cognito OIDC Discovery URL for Gateway JWT validation"
  value       = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.agentcore_gateway.id}/.well-known/openid-configuration"
}
