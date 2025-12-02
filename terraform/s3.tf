# =============================================================================
# S3 Buckets
# =============================================================================

# Random suffix for bucket names to ensure uniqueness
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# -----------------------------------------------------------------------------
# Vector Store Bucket (for S3 Vector Store / long-term knowledge)
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "vector_store" {
  bucket = "${local.name_prefix}-vector-store-${random_id.bucket_suffix.hex}"

  tags = merge(local.cost_tags, {
    Name    = "${local.name_prefix}-vector-store"
    Purpose = "S3 Vector Store for RAG knowledge base"
  })
}

resource "aws_s3_bucket_versioning" "vector_store" {
  bucket = aws_s3_bucket.vector_store.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "vector_store" {
  bucket = aws_s3_bucket.vector_store.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "vector_store" {
  bucket = aws_s3_bucket.vector_store.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "vector_store" {
  bucket = aws_s3_bucket.vector_store.id

  rule {
    id     = "cleanup-old-versions"
    status = "Enabled"

    filter {}  # Required: empty filter applies to all objects

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# -----------------------------------------------------------------------------
# Artifacts Bucket (for Lambda code, documents, etc.)
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "artifacts" {
  bucket = "${local.name_prefix}-artifacts-${random_id.bucket_suffix.hex}"

  tags = merge(local.cost_tags, {
    Name    = "${local.name_prefix}-artifacts"
    Purpose = "Deployment artifacts and documents"
  })
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "cleanup-old-versions"
    status = "Enabled"

    filter {}  # Required: empty filter applies to all objects

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    filter {}  # Required: empty filter applies to all objects

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
  }
}
