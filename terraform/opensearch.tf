# =============================================================================
# OpenSearch Serverless
# =============================================================================

# -----------------------------------------------------------------------------
# Security Policies
# -----------------------------------------------------------------------------

# Encryption policy - required before collection creation
resource "aws_opensearchserverless_security_policy" "encryption" {
  name = "msp-kb-encryption" # Max 32 chars
  type = "encryption"

  policy = jsonencode({
    Rules = [
      {
        ResourceType = "collection"
        Resource = [
          "collection/${var.opensearch_collection_name}"
        ]
      }
    ]
    AWSOwnedKey = true
  })
}

# Network policy - allow public access (for demo; restrict in production)
resource "aws_opensearchserverless_security_policy" "network" {
  name = "msp-kb-network" # Max 32 chars
  type = "network"

  policy = jsonencode([
    {
      Description = "Public access for demo"
      Rules = [
        {
          ResourceType = "collection"
          Resource = [
            "collection/${var.opensearch_collection_name}"
          ]
        },
        {
          ResourceType = "dashboard"
          Resource = [
            "collection/${var.opensearch_collection_name}"
          ]
        }
      ]
      AllowFromPublic = true
    }
  ])
}

# -----------------------------------------------------------------------------
# Access Policy
# -----------------------------------------------------------------------------

resource "aws_opensearchserverless_access_policy" "data_access" {
  name = "msp-kb-data-access" # Max 32 chars
  type = "data"

  policy = jsonencode([
    {
      Description = "Access for agent and GitHub Actions"
      Rules = [
        {
          ResourceType = "collection"
          Resource = [
            "collection/${var.opensearch_collection_name}"
          ]
          Permission = [
            "aoss:CreateCollectionItems",
            "aoss:DeleteCollectionItems",
            "aoss:UpdateCollectionItems",
            "aoss:DescribeCollectionItems"
          ]
        },
        {
          ResourceType = "index"
          Resource = [
            "index/${var.opensearch_collection_name}/*"
          ]
          Permission = [
            "aoss:CreateIndex",
            "aoss:DeleteIndex",
            "aoss:UpdateIndex",
            "aoss:DescribeIndex",
            "aoss:ReadDocument",
            "aoss:WriteDocument"
          ]
        }
      ]
      Principal = [
        aws_iam_role.agent_execution.arn,
        aws_iam_role.github_actions.arn,
        aws_iam_role.lambda_execution.arn,
        "arn:aws:iam::${local.account_id}:root"
      ]
    }
  ])
}

# -----------------------------------------------------------------------------
# Collection (Vector Search)
# -----------------------------------------------------------------------------

resource "aws_opensearchserverless_collection" "knowledge_base" {
  name        = var.opensearch_collection_name
  type        = "VECTORSEARCH"
  description = "Vector search collection for MSP Support Assistant knowledge base"

  depends_on = [
    aws_opensearchserverless_security_policy.encryption,
    aws_opensearchserverless_security_policy.network,
    aws_opensearchserverless_access_policy.data_access
  ]

  tags = merge(local.cost_tags, {
    Name    = var.opensearch_collection_name
    Purpose = "RAG knowledge base for support tickets"
  })
}

# -----------------------------------------------------------------------------
# Note: Index creation is done via script after collection is ready
# The index mapping should include:
# - id: keyword
# - embedding: knn_vector with dimension 1024 (Titan v2)
# - text: text
# - metadata: object
# -----------------------------------------------------------------------------
