# AWS Provider Configuration with Default Cost Tags
provider "aws" {
  region = var.aws_region

  # Default tags applied to ALL resources
  default_tags {
    tags = {
      Project     = "msp-support-assistant"
      Owner       = "Gianluca Formica"
      Environment = var.environment
      GitHubRepo  = "https://github.com/formicag/msp-support-assistant"
      ManagedBy   = "Terraform"
    }
  }
}

# Secondary provider for resources that must be in us-east-1 (e.g., CloudFront, some global resources)
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = "msp-support-assistant"
      Owner       = "Gianluca Formica"
      Environment = var.environment
      GitHubRepo  = "https://github.com/formicag/msp-support-assistant"
      ManagedBy   = "Terraform"
    }
  }
}
