terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  # Backend configuration for remote state
  # Using S3 with DynamoDB locking for team collaboration
  backend "s3" {
    bucket         = "msp-support-assistant-tfstate"
    key            = "terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "msp-support-assistant-tflock"
    encrypt        = true
  }
}
