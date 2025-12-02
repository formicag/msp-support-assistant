# MSP Support Assistant

A fully serverless AI-powered support ticket assistant powered by **AWS Bedrock AgentCore**, demonstrating advanced agent capabilities for enterprise MSP (Managed Service Provider) operations.

[![CI](https://github.com/formicag/msp-support-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/formicag/msp-support-assistant/actions/workflows/ci.yml)
[![Deploy](https://github.com/formicag/msp-support-assistant/actions/workflows/deploy.yml/badge.svg)](https://github.com/formicag/msp-support-assistant/actions/workflows/deploy.yml)

**Repository**: [https://github.com/formicag/msp-support-assistant](https://github.com/formicag/msp-support-assistant)

---

## Features

- **Natural Language Ticket Management**: Create, update, and query support tickets through conversational AI
- **Dynamic Model Routing**: Intelligent routing between Claude (complex queries) and Titan (simple queries)
- **Dual RAG Architecture**: OpenSearch Serverless + S3 Vectors for hot/cold knowledge retrieval
- **Memory System**: Short-term (conversation) and long-term (persistent) memory
- **Bedrock Guardrails**: Content safety and compliance enforcement
- **Strands SDK Pattern**: Modular agent architecture with tool integration
- **Streamlit Frontend**: Real-time chat interface with streaming responses
- **100% Serverless**: Lambda, App Runner, DynamoDB, OpenSearch Serverless

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MSP Support Assistant                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────────────────┐  │
│  │  Streamlit   │───▶│  API Gateway     │───▶│  Lambda (Ticket API)     │  │
│  │  (App Runner)│    │  (HTTP API)      │    │                          │  │
│  └──────────────┘    └──────────────────┘    └──────────────────────────┘  │
│         │                                              │                     │
│         ▼                                              ▼                     │
│  ┌──────────────────────────────────────┐    ┌──────────────────────────┐  │
│  │      Amazon Bedrock AgentCore        │    │      DynamoDB            │  │
│  │  ┌─────────┐  ┌─────────┐           │    │  (Tickets Table)         │  │
│  │  │ Claude  │  │  Titan  │           │    └──────────────────────────┘  │
│  │  │(Complex)│  │(Simple) │           │                                   │
│  │  └─────────┘  └─────────┘           │                                   │
│  │       ▲             ▲                │                                   │
│  │       └──────┬──────┘                │                                   │
│  │              │                       │                                   │
│  │    ┌─────────────────┐              │    ┌──────────────────────────┐  │
│  │    │  Model Router   │              │    │  OpenSearch Serverless   │  │
│  │    └─────────────────┘              │    │  (Vector Search - Hot)   │  │
│  │                                      │    └──────────────────────────┘  │
│  │  ┌───────────────────────────────┐  │                                   │
│  │  │  AgentCore Memory (STM/LTM)   │  │    ┌──────────────────────────┐  │
│  │  └───────────────────────────────┘  │    │  S3 Vector Store         │  │
│  │                                      │    │  (Cold Knowledge)        │  │
│  │  ┌───────────────────────────────┐  │    └──────────────────────────┘  │
│  │  │  Bedrock Guardrails           │  │                                   │
│  │  └───────────────────────────────┘  │                                   │
│  └──────────────────────────────────────┘                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Cost Tags

All AWS resources are tagged for cost allocation and tracking:

| Tag Key | Value | Description |
|---------|-------|-------------|
| `Project` | `msp-support-assistant` | Project identifier |
| `Owner` | `Gianluca Formica` | Project owner |
| `Environment` | `demo` / `staging` / `prod` | Deployment environment |
| `GitHubRepo` | `https://github.com/formicag/msp-support-assistant` | Source repository |
| `ManagedBy` | `Terraform` | Infrastructure management tool |

Tags are applied via:
- **Default tags** in the AWS provider (automatic for most resources)
- **Explicit tags** on resources that don't inherit defaults (IAM roles, OpenSearch policies)

---

## Security Model

### GitHub Actions OIDC Authentication

This project uses **OpenID Connect (OIDC)** for secure, keyless authentication from GitHub Actions to AWS. No long-lived credentials are stored.

#### How It Works

1. GitHub Actions requests an OIDC token from GitHub's identity provider
2. The token is exchanged with AWS STS for temporary credentials
3. AWS validates the token against the configured trust policy
4. Temporary credentials are issued for the deployment session

#### IAM Role: `GitHubActionsDeployRole`

```hcl
# Trust policy allows GitHub OIDC provider
{
  "Effect": "Allow",
  "Principal": {
    "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
  },
  "Action": "sts:AssumeRoleWithWebIdentity",
  "Condition": {
    "StringEquals": {
      "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
    },
    "StringLike": {
      "token.actions.githubusercontent.com:sub": "repo:formicag/msp-support-assistant:*"
    }
  }
}
```

#### Permissions (Least Privilege)

The GitHub Actions role has limited permissions for:
- ECR (push/pull images)
- Lambda (deploy functions)
- S3 (Terraform state and artifacts)
- DynamoDB (tables and state lock)
- Bedrock (agent management)
- OpenSearch Serverless (collection management)
- CloudWatch (logging)
- SSM (parameter store)
- API Gateway (API management)
- App Runner (service deployment)
- IAM (limited role management for this project only)

---

## CI/CD Pipeline

### Workflows

#### 1. CI Pipeline (`.github/workflows/ci.yml`)

Runs on all pushes and pull requests:

- **Python Lint & Test**
  - Black formatting check
  - Flake8 linting
  - Pylint static analysis
  - Pytest with coverage

- **Terraform Validation**
  - Format check (`terraform fmt`)
  - Syntax validation (`terraform validate`)

- **Docker Build Test**
  - Build Streamlit image without pushing

- **Security Scanning**
  - Trivy vulnerability scanner
  - Checkov IaC security scanner

#### 2. Deploy Pipeline (`.github/workflows/deploy.yml`)

Runs on merge to main or manual trigger:

1. **Terraform Plan**: Preview infrastructure changes
2. **Terraform Apply**: Deploy infrastructure (requires approval)
3. **Build & Push Images**: Push to ECR
4. **Deploy Lambda**: Update function code
5. **Deploy App Runner**: Trigger new deployment
6. **Verify Deployment**: Health checks and summary

### GitHub Secrets Required

| Secret | Description |
|--------|-------------|
| `AWS_ACCOUNT_ID` | AWS account ID (e.g., `010819240034`) |

### Environment Protection

- Production deployments require manual approval
- Concurrent deployments are prevented

---

## Prerequisites

- AWS Account with Bedrock access enabled
- Terraform >= 1.5.0
- Python >= 3.11
- Docker
- AWS CLI configured with appropriate credentials

---

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/formicag/msp-support-assistant.git
cd msp-support-assistant
```

### 2. Configure Terraform Backend

Create an S3 bucket and DynamoDB table for Terraform state:

```bash
# Create state bucket
aws s3 mb s3://msp-support-assistant-tfstate --region us-east-1

# Create lock table
aws dynamodb create-table \
  --table-name msp-support-assistant-tflock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### 3. Deploy Infrastructure

```bash
cd terraform

# Copy and customize variables
cp terraform.tfvars.example terraform.tfvars

# Initialize Terraform
terraform init \
  -backend-config="bucket=msp-support-assistant-tfstate" \
  -backend-config="key=terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=msp-support-assistant-tflock"

# Plan and apply
terraform plan
terraform apply
```

### 4. Load Sample Data

```bash
# Install dependencies
pip install -r src/scripts/requirements.txt

# Load sample tickets and create embeddings
python src/scripts/ingest_data.py \
  --region us-east-1 \
  --tickets-table msp-support-assistant-demo-tickets
```

### 5. Build and Deploy Streamlit

```bash
# Get ECR repository URL from Terraform output
ECR_REPO=$(terraform output -raw ecr_repository_url)

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_REPO

# Build and push
cd ../src/streamlit
docker build -t $ECR_REPO:latest .
docker push $ECR_REPO:latest
```

### 6. Access the Application

Get the App Runner URL:

```bash
cd ../../terraform
terraform output streamlit_app_url
```

---

## Project Structure

```
msp-support-assistant/
├── .github/
│   └── workflows/
│       ├── ci.yml              # CI pipeline (lint, test, validate)
│       └── deploy.yml          # Deploy pipeline (Terraform + app deploy)
├── data/
│   ├── sample_tickets.json     # Sample support tickets
│   └── knowledge_base.json     # Knowledge base articles
├── docs/
│   └── architecture.md         # Detailed architecture documentation
├── src/
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── agent.py            # Main agent implementation
│   │   ├── config.py           # Configuration and prompts
│   │   ├── memory.py           # Memory management (STM/LTM)
│   │   ├── router.py           # Dynamic model routing
│   │   ├── tools.py            # Tool definitions and handlers
│   │   └── requirements.txt
│   ├── lambda/
│   │   ├── handler.py          # Ticket API Lambda handler
│   │   └── requirements.txt
│   ├── scripts/
│   │   ├── ingest_data.py      # Data ingestion script
│   │   ├── create_opensearch_index.py
│   │   └── requirements.txt
│   └── streamlit/
│       ├── app.py              # Streamlit application
│       ├── Dockerfile
│       ├── requirements.txt
│       └── .streamlit/
│           └── config.toml
├── terraform/
│   ├── api_gateway.tf          # API Gateway resources
│   ├── app_runner.tf           # App Runner service
│   ├── dynamodb.tf             # DynamoDB tables
│   ├── ecr.tf                  # ECR repositories
│   ├── iam.tf                  # IAM roles and policies
│   ├── lambda.tf               # Lambda function
│   ├── locals.tf               # Local values
│   ├── opensearch.tf           # OpenSearch Serverless
│   ├── outputs.tf              # Terraform outputs
│   ├── providers.tf            # AWS provider with default tags
│   ├── s3.tf                   # S3 buckets
│   ├── ssm.tf                  # SSM Parameter Store
│   ├── terraform.tfvars.example
│   ├── variables.tf            # Input variables
│   └── versions.tf             # Provider versions
└── README.md
```

---

## Environment Variables

### Streamlit Application

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_REGION` | AWS region | `us-east-1` |
| `API_GATEWAY_ENDPOINT` | Ticket API endpoint | Required |
| `ENVIRONMENT` | Environment name | `demo` |
| `SSM_PARAMETER_PREFIX` | SSM parameter prefix | `/msp-support-assistant/demo` |

### Lambda Function

| Variable | Description | Default |
|----------|-------------|---------|
| `TICKETS_TABLE_NAME` | DynamoDB table name | Required |
| `SESSIONS_TABLE_NAME` | Sessions table name | Required |
| `ENVIRONMENT` | Environment name | `demo` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Agent Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `BEDROCK_CLAUDE_MODEL` | Claude model ID | `anthropic.claude-3-sonnet-20240229-v1:0` |
| `BEDROCK_TITAN_MODEL` | Titan model ID | `amazon.titan-text-express-v1` |
| `BEDROCK_EMBEDDING_MODEL` | Embedding model | `amazon.titan-embed-text-v2:0` |
| `MEMORY_ENABLED` | Enable long-term memory | `true` |

---

## API Reference

### Ticket API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/tickets` | Create a new ticket |
| `GET` | `/tickets` | List all tickets |
| `GET` | `/tickets/{ticketId}` | Get ticket by ID |
| `PATCH` | `/tickets/{ticketId}` | Update ticket |
| `DELETE` | `/tickets/{ticketId}` | Delete ticket |
| `GET` | `/health` | Health check |

### Request/Response Examples

**Create Ticket**
```json
POST /tickets
{
  "title": "VPN Connection Issues",
  "description": "Users reporting intermittent VPN disconnections",
  "priority": "High",
  "category": "Network"
}
```

**Response**
```json
{
  "message": "Ticket created successfully",
  "ticket": {
    "TicketId": "TKT-20241202-A1B2C3D4",
    "Title": "VPN Connection Issues",
    "Status": "Open",
    "Priority": "High",
    "Category": "Network",
    "CreatedAt": "2024-12-02T10:30:00Z"
  }
}
```

---

## Cleanup

To destroy all resources:

```bash
cd terraform
terraform destroy
```

Don't forget to:
- Delete the S3 state bucket
- Delete the DynamoDB lock table
- Remove any orphaned CloudWatch log groups

---

## Cost Considerations

This demo uses primarily serverless services with pay-per-use pricing:

- **Lambda**: First 1M requests/month free
- **DynamoDB**: On-demand pricing, minimal for demo
- **OpenSearch Serverless**: ~$0.24/hour for OCU (minimum 2)
- **App Runner**: ~$0.064/vCPU-hour when running
- **Bedrock**: Per-token pricing varies by model
- **S3**: Minimal storage costs

**Estimated demo cost**: $5-20/day depending on usage

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest tests/`
5. Submit a pull request

---

## Support

For issues and questions:
- Open an issue on [GitHub](https://github.com/formicag/msp-support-assistant/issues)
- Contact: Gianluca Formica

---

*Built with AWS Bedrock AgentCore, Strands SDK, and Terraform*
