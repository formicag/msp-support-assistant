# =============================================================================
# IAM Roles and Policies
# =============================================================================

# -----------------------------------------------------------------------------
# GitHub OIDC Provider
# -----------------------------------------------------------------------------

resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  thumbprint_list = [var.github_oidc_thumbprint]

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-github-oidc"
  })
}

# -----------------------------------------------------------------------------
# GitHub Actions Deploy Role (OIDC)
# -----------------------------------------------------------------------------

resource "aws_iam_role" "github_actions" {
  name = "GitHubActionsDeployRole"
  path = "/"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = local.github_oidc_subject
          }
        }
      }
    ]
  })

  tags = merge(local.cost_tags, {
    Name        = "GitHubActionsDeployRole"
    Description = "IAM role for GitHub Actions CI/CD via OIDC"
  })
}

# GitHub Actions Policy - Limited permissions for deployment
resource "aws_iam_role_policy" "github_actions" {
  name = "github-actions-deploy-policy"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # ECR permissions
      {
        Sid    = "ECRPermissions"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:DescribeRepositories",
          "ecr:CreateRepository",
          "ecr:DeleteRepository",
          "ecr:TagResource"
        ]
        Resource = "*"
      },
      # Lambda permissions
      {
        Sid    = "LambdaPermissions"
        Effect = "Allow"
        Action = [
          "lambda:CreateFunction",
          "lambda:UpdateFunctionCode",
          "lambda:UpdateFunctionConfiguration",
          "lambda:GetFunction",
          "lambda:DeleteFunction",
          "lambda:PublishVersion",
          "lambda:CreateAlias",
          "lambda:UpdateAlias",
          "lambda:DeleteAlias",
          "lambda:ListVersionsByFunction",
          "lambda:GetPolicy",
          "lambda:AddPermission",
          "lambda:RemovePermission",
          "lambda:InvokeFunction",
          "lambda:TagResource",
          "lambda:ListTags"
        ]
        Resource = "arn:aws:lambda:${var.aws_region}:${local.account_id}:function:${local.name_prefix}-*"
      },
      # S3 permissions for Terraform state and artifacts
      {
        Sid    = "S3Permissions"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:GetBucketVersioning",
          "s3:CreateBucket",
          "s3:DeleteBucket",
          "s3:PutBucketVersioning",
          "s3:PutBucketEncryption",
          "s3:GetBucketEncryption",
          "s3:PutBucketPublicAccessBlock",
          "s3:GetBucketPublicAccessBlock",
          "s3:PutBucketTagging",
          "s3:GetBucketTagging"
        ]
        Resource = [
          "arn:aws:s3:::${local.name_prefix}-*",
          "arn:aws:s3:::${local.name_prefix}-*/*",
          "arn:aws:s3:::msp-support-assistant-tfstate",
          "arn:aws:s3:::msp-support-assistant-tfstate/*"
        ]
      },
      # DynamoDB permissions for Terraform state lock and app tables
      {
        Sid    = "DynamoDBPermissions"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem",
          "dynamodb:CreateTable",
          "dynamodb:DeleteTable",
          "dynamodb:DescribeTable",
          "dynamodb:UpdateTable",
          "dynamodb:TagResource",
          "dynamodb:ListTagsOfResource",
          "dynamodb:DescribeContinuousBackups",
          "dynamodb:UpdateContinuousBackups"
        ]
        Resource = [
          "arn:aws:dynamodb:${var.aws_region}:${local.account_id}:table/${local.name_prefix}-*",
          "arn:aws:dynamodb:${var.aws_region}:${local.account_id}:table/msp-support-assistant-tflock"
        ]
      },
      # Bedrock permissions
      {
        Sid    = "BedrockPermissions"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:GetFoundationModel",
          "bedrock:ListFoundationModels",
          "bedrock:CreateAgent",
          "bedrock:UpdateAgent",
          "bedrock:GetAgent",
          "bedrock:DeleteAgent",
          "bedrock:ListAgents",
          "bedrock:CreateAgentAlias",
          "bedrock:UpdateAgentAlias",
          "bedrock:GetAgentAlias",
          "bedrock:DeleteAgentAlias",
          "bedrock:PrepareAgent",
          "bedrock:CreateKnowledgeBase",
          "bedrock:UpdateKnowledgeBase",
          "bedrock:GetKnowledgeBase",
          "bedrock:DeleteKnowledgeBase",
          "bedrock:CreateGuardrail",
          "bedrock:UpdateGuardrail",
          "bedrock:GetGuardrail",
          "bedrock:DeleteGuardrail"
        ]
        Resource = "*"
      },
      # OpenSearch Serverless permissions
      {
        Sid    = "OpenSearchServerlessPermissions"
        Effect = "Allow"
        Action = [
          "aoss:CreateCollection",
          "aoss:DeleteCollection",
          "aoss:UpdateCollection",
          "aoss:BatchGetCollection",
          "aoss:ListCollections",
          "aoss:CreateSecurityPolicy",
          "aoss:UpdateSecurityPolicy",
          "aoss:GetSecurityPolicy",
          "aoss:DeleteSecurityPolicy",
          "aoss:ListSecurityPolicies",
          "aoss:CreateAccessPolicy",
          "aoss:UpdateAccessPolicy",
          "aoss:GetAccessPolicy",
          "aoss:DeleteAccessPolicy",
          "aoss:ListAccessPolicies",
          "aoss:APIAccessAll"
        ]
        Resource = "*"
      },
      # CloudWatch permissions
      {
        Sid    = "CloudWatchPermissions"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:DeleteLogGroup",
          "logs:CreateLogStream",
          "logs:DeleteLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:TagResource",
          "logs:PutRetentionPolicy"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/*/${local.name_prefix}*"
      },
      # SSM Parameter Store permissions
      {
        Sid    = "SSMPermissions"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:PutParameter",
          "ssm:DeleteParameter",
          "ssm:GetParametersByPath",
          "ssm:AddTagsToResource",
          "ssm:ListTagsForResource"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter/${var.project_name}/*"
      },
      # IAM permissions (limited for role management)
      {
        Sid    = "IAMPermissions"
        Effect = "Allow"
        Action = [
          "iam:GetRole",
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:UpdateRole",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:GetRolePolicy",
          "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies",
          "iam:TagRole",
          "iam:UntagRole",
          "iam:PassRole",
          "iam:CreateServiceLinkedRole",
          "iam:GetOpenIDConnectProvider",
          "iam:CreateOpenIDConnectProvider",
          "iam:DeleteOpenIDConnectProvider",
          "iam:TagOpenIDConnectProvider",
          "iam:ListOpenIDConnectProviders"
        ]
        Resource = [
          "arn:aws:iam::${local.account_id}:role/${local.name_prefix}-*",
          "arn:aws:iam::${local.account_id}:role/GitHubActionsDeployRole",
          "arn:aws:iam::${local.account_id}:oidc-provider/token.actions.githubusercontent.com",
          "arn:aws:iam::${local.account_id}:role/aws-service-role/*"
        ]
      },
      # API Gateway permissions
      {
        Sid    = "APIGatewayPermissions"
        Effect = "Allow"
        Action = [
          "apigateway:*"
        ]
        Resource = [
          "arn:aws:apigateway:${var.aws_region}::/apis/*",
          "arn:aws:apigateway:${var.aws_region}::/tags/*"
        ]
      },
      # App Runner permissions
      {
        Sid    = "AppRunnerPermissions"
        Effect = "Allow"
        Action = [
          "apprunner:CreateService",
          "apprunner:UpdateService",
          "apprunner:DeleteService",
          "apprunner:DescribeService",
          "apprunner:ListServices",
          "apprunner:StartDeployment",
          "apprunner:PauseService",
          "apprunner:ResumeService",
          "apprunner:TagResource",
          "apprunner:ListTagsForResource",
          "apprunner:CreateAutoScalingConfiguration",
          "apprunner:DeleteAutoScalingConfiguration",
          "apprunner:DescribeAutoScalingConfiguration"
        ]
        Resource = "*"
      },
      # STS for assuming roles
      {
        Sid    = "STSPermissions"
        Effect = "Allow"
        Action = [
          "sts:GetCallerIdentity"
        ]
        Resource = "*"
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Bedrock Agent Execution Role
# -----------------------------------------------------------------------------

resource "aws_iam_role" "agent_execution" {
  name = "${local.name_prefix}-agent-execution-role"
  path = "/"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
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
    Name = "${local.name_prefix}-agent-execution-role"
  })
}

resource "aws_iam_role_policy" "agent_execution" {
  name = "agent-execution-policy"
  role = aws_iam_role.agent_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Bedrock model invocation
      {
        Sid    = "BedrockModelInvocation"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = local.bedrock_model_arns
      },
      # Bedrock Agent and Memory operations
      {
        Sid    = "BedrockAgentOperations"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeAgent",
          "bedrock:Retrieve",
          "bedrock:RetrieveAndGenerate",
          "bedrock:GetAgentMemory",
          "bedrock:DeleteAgentMemory"
        ]
        Resource = "*"
      },
      # S3 access for vector store
      {
        Sid    = "S3VectorStoreAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.vector_store.arn,
          "${aws_s3_bucket.vector_store.arn}/*"
        ]
      },
      # OpenSearch Serverless access
      {
        Sid    = "OpenSearchAccess"
        Effect = "Allow"
        Action = [
          "aoss:APIAccessAll"
        ]
        Resource = aws_opensearchserverless_collection.knowledge_base.arn
      },
      # CloudWatch Logs
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/bedrock/${local.name_prefix}*"
      },
      # SSM Parameter Store (read-only)
      {
        Sid    = "SSMParameterRead"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter/${var.project_name}/*"
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Lambda Execution Role
# -----------------------------------------------------------------------------

resource "aws_iam_role" "lambda_execution" {
  name = "${local.name_prefix}-lambda-execution-role"
  path = "/"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-lambda-execution-role"
  })
}

resource "aws_iam_role_policy" "lambda_execution" {
  name = "lambda-execution-policy"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # DynamoDB access for tickets table
      {
        Sid    = "DynamoDBAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.tickets.arn,
          "${aws_dynamodb_table.tickets.arn}/index/*"
        ]
      },
      # CloudWatch Logs
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/lambda/${local.name_prefix}-*"
      },
      # SSM Parameter Store (read-only)
      {
        Sid    = "SSMParameterRead"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter/${var.project_name}/*"
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# App Runner Instance Role
# -----------------------------------------------------------------------------

resource "aws_iam_role" "app_runner_instance" {
  name = "${local.name_prefix}-app-runner-instance-role"
  path = "/"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "tasks.apprunner.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-app-runner-instance-role"
  })
}

resource "aws_iam_role_policy" "app_runner_instance" {
  name = "app-runner-instance-policy"
  role = aws_iam_role.app_runner_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Bedrock Agent invocation
      {
        Sid    = "BedrockInvoke"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeAgent",
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "*"
      },
      # SSM Parameter Store
      {
        Sid    = "SSMParameterRead"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter/${var.project_name}/*"
      },
      # CloudWatch Logs
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/apprunner/${local.name_prefix}*"
      }
    ]
  })
}

# App Runner ECR Access Role
resource "aws_iam_role" "app_runner_ecr_access" {
  name = "${local.name_prefix}-app-runner-ecr-access-role"
  path = "/"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "build.apprunner.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-app-runner-ecr-access-role"
  })
}

resource "aws_iam_role_policy_attachment" "app_runner_ecr_access" {
  role       = aws_iam_role.app_runner_ecr_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}
