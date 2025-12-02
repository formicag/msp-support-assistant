# MSP Support Assistant

A fully serverless AI-powered support ticket assistant powered by **AWS Strands Agents SDK**, **Amazon Nova Pro**, and **AgentCore Memory**, demonstrating the full AWS agent ecosystem for enterprise MSP (Managed Service Provider) operations.

[![CI](https://github.com/formicag/msp-support-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/formicag/msp-support-assistant/actions/workflows/ci.yml)
[![Deploy](https://github.com/formicag/msp-support-assistant/actions/workflows/deploy.yml/badge.svg)](https://github.com/formicag/msp-support-assistant/actions/workflows/deploy.yml)

**Repository**: [https://github.com/formicag/msp-support-assistant](https://github.com/formicag/msp-support-assistant)

---

## Live Demo

| Service | URL |
|---------|-----|
| **Streamlit App** | https://ut48uszr3s.us-east-1.awsapprunner.com |
| **API Gateway** | https://p3h9ge8d92.execute-api.us-east-1.amazonaws.com |

---

## Features

### Core Capabilities

- **Strands Agents SDK**: AWS open-source framework for building AI agents with model-driven orchestration
- **@tool Decorated Functions**: Python tools using Strands decorator pattern with automatic tool specs
- **AgentCoreMemorySessionManager**: Native short-term and long-term memory integration
- **Amazon Nova Pro**: Powered by Amazon's latest foundation model with BedrockModel class
- **Agentic RAG**: retrieve_memories tool for proactive memory search
- **Streamlit Frontend**: Real-time chat interface with memory and agent status
- **100% Serverless**: Lambda, App Runner, DynamoDB, OpenSearch Serverless

### AgentCore Memory System

The assistant uses AWS Bedrock AgentCore Memory for persistent context:

| Memory Type | Strategy | Description |
|-------------|----------|-------------|
| **Short-term** | Event Storage | Stores each conversation exchange as events |
| **Long-term** | User Preferences | Extracts and remembers user preferences |
| **Long-term** | Semantic Facts | Extracts factual information (names, roles, etc.) |
| **Long-term** | Session Summaries | Creates condensed summaries of sessions |

**Memory ID**: `msp_support_assistant_memory-NeCST586bk`

### Strands @tool Decorated Functions

The agent uses Strands `@tool` decorator pattern for automatic tool discovery:

```python
from strands import tool

@tool
def list_tickets(status: Optional[str] = None, limit: int = 10) -> dict:
    """List support tickets with optional filtering by status.

    Args:
        status: Filter by status (Open, In Progress, Resolved, Closed)
        limit: Maximum number of tickets to return
    """
    return _call_ticket_api(f"/tickets?status={status}&limit={limit}")
```

| Tool | Description |
|------|-------------|
| `list_tickets` | List all tickets or filter by status |
| `create_ticket` | Create a new support ticket |
| `get_ticket` | Get details of a specific ticket by ID |
| `update_ticket` | Update ticket status, priority, or add notes |
| `get_ticket_summary` | Get overview and statistics of all tickets |
| `retrieve_memories` | Agentic RAG - proactive memory search |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      MSP Support Assistant (Strands + AgentCore)            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────────────────────────────────────────┐  │
│  │  Streamlit   │───▶│           Strands Agent                          │  │
│  │  (App Runner)│    │  ┌────────────────┐  ┌─────────────────────────┐ │  │
│  └──────────────┘    │  │ BedrockModel   │  │ AgentCoreMemory         │ │  │
│         │            │  │ (Nova Pro)     │  │ SessionManager          │ │  │
│         │            │  └────────────────┘  └─────────────────────────┘ │  │
│         │            │  ┌────────────────────────────────────────────┐  │  │
│         │            │  │ @tool Decorated Functions                  │  │  │
│         │            │  │ • list_tickets  • get_ticket_summary       │  │  │
│         │            │  │ • create_ticket • retrieve_memories        │  │  │
│         │            │  │ • get_ticket    • update_ticket            │  │  │
│         │            │  └────────────────────────────────────────────┘  │  │
│         │            └──────────────────────────────────────────────────┘  │
│         │                     │                         │                   │
│         │                     ▼                         ▼                   │
│         │     ┌───────────────────────────┐  ┌──────────────────────────┐  │
│         │     │  AgentCore Memory         │  │  API Gateway (HTTP)      │  │
│         │     │  ┌─────────────────────┐  │  │  /tickets endpoints      │  │
│         │     │  │ Short-term (Events) │  │  └──────────────────────────┘  │
│         │     │  │ via Memory Hooks    │  │               │                │
│         │     │  └─────────────────────┘  │               ▼                │
│         │     │  ┌─────────────────────┐  │  ┌──────────────────────────┐  │
│         │     │  │ Long-term Strategies│  │  │  Lambda (Ticket API)     │  │
│         │     │  │ • user_preferences  │  │  └──────────────────────────┘  │
│         │     │  │ • semantic_facts    │  │               │                │
│         │     │  │ • session_summaries │  │               ▼                │
│         │     │  └─────────────────────┘  │  ┌──────────────────────────┐  │
│         │     └───────────────────────────┘  │      DynamoDB            │  │
│         │                                    │  (Tickets Table)         │  │
│         │                                    └──────────────────────────┘  │
│         │                                                                   │
│         │     Model: Amazon Nova Pro (us.amazon.nova-pro-v1:0)             │
│         │     SDK: Strands Agents + bedrock-agentcore                      │
│         │                                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Strands Agent Data Flow

1. **User Input**: User sends message via Streamlit chat interface
2. **Session Manager**: AgentCoreMemorySessionManager loads conversation history
3. **Memory Hooks**: ShortMemoryHook and LongTermMemoryHook retrieve relevant context
4. **Agent Invoke**: Strands Agent with BedrockModel reasons about which tools to use
5. **Tool Execution**: @tool decorated functions execute and return results
6. **Response**: Agent synthesizes response based on tool results
7. **Event Storage**: Session manager stores conversation as events automatically

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| **Agent Framework** | [Strands Agents SDK](https://strandsagents.com) (`strands-agents`) |
| **LLM** | Amazon Nova Pro via `BedrockModel` class |
| **Memory** | AWS Bedrock AgentCore Memory via `AgentCoreMemorySessionManager` |
| **Memory SDK** | `bedrock-agentcore` package |
| **Tools** | `@tool` decorated Python functions |
| **Frontend** | Streamlit on AWS App Runner |
| **Backend API** | AWS Lambda + API Gateway (HTTP) |
| **Database** | Amazon DynamoDB |
| **Vector Store** | OpenSearch Serverless + S3 |
| **Infrastructure** | Terraform |

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

---

## Security Model

### GitHub Actions OIDC Authentication

This project uses **OpenID Connect (OIDC)** for secure, keyless authentication from GitHub Actions to AWS. No long-lived credentials are stored.

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

---

## CI/CD Pipeline

### Workflows

#### 1. CI Pipeline (`.github/workflows/ci.yml`)

- Python Lint & Test (Black, Flake8, Pylint, Pytest)
- Terraform Validation
- Docker Build Test
- Security Scanning (Trivy, Checkov)

#### 2. Deploy Pipeline (`.github/workflows/deploy.yml`)

1. Terraform Plan → Apply
2. Build & Push Docker Images to ECR
3. Deploy Lambda Functions
4. Deploy App Runner Service

---

## Prerequisites

- AWS Account with Bedrock access enabled (including Nova Pro)
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
terraform init
terraform plan
terraform apply
```

### 4. Run Locally

```bash
cd src/streamlit
pip install -r requirements.txt

# Option A: Strands Agent with AgentCore Memory (recommended)
AWS_PROFILE=your-profile streamlit run strands_app.py --server.port 8501

# Option B: Direct Bedrock Converse API (legacy)
AWS_PROFILE=your-profile streamlit run app.py --server.port 8501
```

### 5. Access the Application

- Local: http://localhost:8501
- Production: Check `terraform output streamlit_app_url`

### 6. Verify Strands Installation

```python
# Test imports
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
print("All imports successful!")
```

---

## Project Structure

```
msp-support-assistant/
├── .github/workflows/
│   ├── ci.yml                    # CI pipeline
│   └── deploy.yml                # Deploy pipeline
├── data/
│   ├── sample_tickets.json       # Sample tickets
│   └── knowledge_base.json       # Knowledge base
├── docs/
│   └── TEST_CASES_MEMORY.md      # Memory feature test cases
├── src/
│   ├── lambda/
│   │   └── handler.py            # Ticket API Lambda
│   └── streamlit/
│       ├── strands_app.py        # Strands Agent implementation (recommended)
│       ├── tools.py              # @tool decorated ticket functions
│       ├── app.py                # Legacy Bedrock Converse API implementation
│       ├── requirements.txt      # Python dependencies
│       └── Dockerfile
├── terraform/
│   ├── agentcore_memory.tf       # AgentCore Memory resource + strategies
│   ├── api_gateway.tf            # HTTP API for ticket operations
│   ├── app_runner.tf             # Streamlit hosting
│   ├── dynamodb.tf               # Tickets table
│   ├── lambda.tf                 # Ticket API function
│   ├── iam.tf                    # IAM roles with memory permissions
│   └── ...
└── README.md
```

---

## Environment Variables

### Streamlit Application

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_REGION` | AWS region | `us-east-1` |
| `API_GATEWAY_ENDPOINT` | Ticket API endpoint | Required |
| `AGENTCORE_MEMORY_ID` | Memory resource ID | `msp_support_assistant_memory-NeCST586bk` |
| `DEFAULT_ACTOR_ID` | Default user ID for memory | `demo-user` |

### Lambda Function

| Variable | Description |
|----------|-------------|
| `TICKETS_TABLE_NAME` | DynamoDB table name |
| `LOG_LEVEL` | Logging level |

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

### AgentCore Memory APIs (via boto3)

```python
# Create event (short-term memory)
client.create_event(
    memoryId="msp_support_assistant_memory-NeCST586bk",
    actorId="user-id",
    sessionId="session-id",
    eventTimestamp="2025-12-02T21:00:00Z",
    payload=[
        {"conversational": {"role": "USER", "content": {"text": "message"}}}
    ]
)

# List memory records (long-term memory)
client.list_memory_records(
    memoryId="msp_support_assistant_memory-NeCST586bk",
    namespace="/facts/user-id"
)
```

---

## Memory Namespaces

| Namespace Pattern | Strategy | Contents |
|-------------------|----------|----------|
| `/preferences/{actorId}` | `user_preferences` | User preferences |
| `/facts/{actorId}` | `semantic_facts` | Factual information |
| `/summaries/{actorId}/{sessionId}` | `session_summaries` | Session summaries |

---

## Testing

See [docs/TEST_CASES_MEMORY.md](docs/TEST_CASES_MEMORY.md) for comprehensive test cases covering:

- Memory infrastructure
- Short-term memory (event storage)
- Long-term memory (extraction strategies)
- Memory context integration
- Error handling
- Actor ID management

---

## Cleanup

```bash
cd terraform
terraform destroy
```

---

## Cost Considerations

| Service | Pricing |
|---------|---------|
| **Lambda** | First 1M requests/month free |
| **DynamoDB** | On-demand, minimal for demo |
| **OpenSearch Serverless** | ~$0.24/hour for OCU |
| **App Runner** | ~$0.064/vCPU-hour |
| **Bedrock Nova Pro** | Per-token pricing |
| **AgentCore Memory** | Per-request pricing |

**Estimated demo cost**: $5-20/day depending on usage

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Support

- Open an issue on [GitHub](https://github.com/formicag/msp-support-assistant/issues)
- Contact: Gianluca Formica

---

*Built with AWS Strands Agents SDK, Amazon Nova Pro, AgentCore Memory, and Terraform*

---

## Strands Agents SDK Resources

- [Strands Agents Documentation](https://strandsagents.com/latest/)
- [Strands GitHub Repository](https://github.com/strands-agents/sdk-python)
- [Bedrock AgentCore SDK](https://github.com/aws/bedrock-agentcore-sdk-python)
- [AgentCore Memory Integration](https://strandsagents.com/latest/documentation/docs/community/session-managers/agentcore-memory/)
