# MSP Support Assistant - Architecture Documentation

## Overview

The MSP Support Assistant is a serverless AI-powered application that demonstrates enterprise-grade agent capabilities using AWS Bedrock AgentCore. This document provides detailed technical documentation of the system architecture.

---

## System Components

### 1. Frontend Layer

#### Streamlit Application (App Runner)

- **Technology**: Python Streamlit
- **Hosting**: AWS App Runner (serverless container)
- **Features**:
  - Real-time chat interface
  - Streaming responses from Bedrock
  - Quick ticket creation form
  - Session management
  - Debug panel for development

**Configuration**:
```python
# Environment variables
AWS_REGION = "us-east-1"
API_GATEWAY_ENDPOINT = "https://xxx.execute-api.us-east-1.amazonaws.com"
ENVIRONMENT = "demo"
```

### 2. API Layer

#### HTTP API Gateway

- **Type**: AWS API Gateway v2 (HTTP API)
- **Authentication**: API Key / Cognito (configurable)
- **Endpoints**:
  - `POST /tickets` - Create ticket
  - `GET /tickets` - List tickets
  - `GET /tickets/{ticketId}` - Get ticket
  - `PATCH /tickets/{ticketId}` - Update ticket
  - `DELETE /tickets/{ticketId}` - Delete ticket
  - `GET /health` - Health check

### 3. Compute Layer

#### Lambda Function (Ticket API)

- **Runtime**: Python 3.11
- **Memory**: 256 MB
- **Timeout**: 30 seconds
- **Handler**: `handler.lambda_handler`

**Responsibilities**:
- CRUD operations on tickets
- Input validation
- DynamoDB interactions
- Response formatting

### 4. Data Layer

#### DynamoDB Tables

**Tickets Table**:
```
Primary Key: TicketId (String)
GSI: CustomerIndex (CustomerId, CreatedAt)
GSI: StatusIndex (Status, CreatedAt)
```

| Attribute | Type | Description |
|-----------|------|-------------|
| TicketId | String | Unique ticket identifier |
| Title | String | Brief summary |
| Description | String | Detailed description |
| Status | String | Open, In Progress, Resolved, Closed |
| Priority | String | Low, Medium, High, Critical |
| Category | String | Network, Hardware, Software, Security, General |
| CustomerId | String | Customer identifier |
| CreatedAt | String | ISO timestamp |
| UpdatedAt | String | ISO timestamp |
| Notes | List | Array of note objects |

**Sessions Table**:
```
Primary Key: SessionId (String)
GSI: UserIndex (UserId)
TTL: ExpiresAt
```

### 5. AI/ML Layer

#### Amazon Bedrock AgentCore

**Models Used**:
- **Claude 3 Sonnet**: Complex queries, multi-step reasoning, tool use
- **Titan Text Express**: Simple queries, status checks
- **Titan Embeddings v2**: Vector embeddings (1024 dimensions)

**Model Routing Logic**:
```python
# Simple patterns → Titan
SIMPLE_PATTERNS = [
    r"^what.*status",
    r"^show.*ticket",
    r"^list.*tickets?",
    # ...
]

# Complex patterns → Claude
COMPLEX_PATTERNS = [
    r"explain.*in detail",
    r"troubleshoot",
    r"analyze",
    # ...
]
```

### 6. Knowledge Layer

#### OpenSearch Serverless (Hot Data)

- **Type**: Vector search collection
- **Use Case**: Recent/frequently accessed knowledge
- **Index Mapping**:

```json
{
  "properties": {
    "embedding": {
      "type": "knn_vector",
      "dimension": 1024,
      "method": {
        "name": "hnsw",
        "space_type": "cosinesimil"
      }
    },
    "title": { "type": "text" },
    "content": { "type": "text" },
    "category": { "type": "keyword" },
    "tags": { "type": "keyword" }
  }
}
```

#### S3 Vector Store (Cold Data)

- **Use Case**: Archived knowledge, large document collections
- **Format**: JSON with embeddings
- **Cost**: ~90% cheaper than traditional vector DBs

### 7. Memory System

#### Short-Term Memory (STM)

- **Implementation**: In-memory sliding window
- **Retention**: Last 20 messages per session
- **Purpose**: Conversation context

#### Long-Term Memory (LTM)

- **Implementation**: Bedrock AgentCore Memory
- **Strategies**:
  - Session Summarization
  - User Preferences
  - Fact Extraction

**Memory Namespaces**:
```
/summaries/{actorId}/{sessionId}
/preferences/{actorId}
/facts/{actorId}
```

---

## Data Flow

### Ticket Creation Flow

```
1. User → Streamlit UI: "Create a ticket for VPN issue"
2. Streamlit → Bedrock: Invoke model with message
3. Bedrock → Model Router: Classify query complexity
4. Model Router → Claude: Complex query (ticket creation)
5. Claude → Tool Execution: create_ticket tool
6. Tool → API Gateway: POST /tickets
7. API Gateway → Lambda: Handle request
8. Lambda → DynamoDB: PutItem
9. Response flows back through chain
10. Streamlit UI: Display confirmation
```

### RAG Query Flow

```
1. User → Agent: "How do I fix VPN MTU issues?"
2. Agent → Embeddings API: Generate query embedding
3. Agent → OpenSearch: Vector similarity search
4. Agent → S3 Vectors: Additional context search
5. Agent → Merge Results: Combine and rank
6. Agent → Claude: Generate answer with context
7. Agent → User: Response with citations
```

---

## Security Architecture

### IAM Roles

| Role | Purpose | Key Permissions |
|------|---------|-----------------|
| GitHubActionsDeployRole | CI/CD deployment | ECR, Lambda, S3, DynamoDB, Bedrock |
| Agent Execution Role | Bedrock agent runtime | Bedrock, S3, OpenSearch, Logs |
| Lambda Execution Role | Ticket API | DynamoDB, Logs, SSM |
| App Runner Instance Role | Streamlit app | Bedrock, SSM, Logs |
| App Runner ECR Access Role | Pull images | ECR (managed policy) |

### Network Security

- All traffic over HTTPS
- API Gateway with throttling
- OpenSearch with SigV4 authentication
- S3 with bucket policies
- VPC optional for enhanced isolation

### Data Encryption

| Resource | Encryption |
|----------|------------|
| DynamoDB | AWS owned key |
| S3 | SSE-KMS |
| OpenSearch | AWS owned key |
| API Gateway | TLS 1.2+ |
| App Runner | TLS 1.2+ |

---

## Scalability

### Auto-Scaling Configuration

**Lambda**:
- Concurrent executions: 1000 (soft limit)
- Reserved concurrency: Configurable

**App Runner**:
- Min instances: 1
- Max instances: 5
- Max concurrency: 100 requests/instance

**DynamoDB**:
- Billing mode: PAY_PER_REQUEST
- Auto-scaling: Automatic

**OpenSearch Serverless**:
- OCU-based scaling
- Automatic capacity management

---

## Monitoring & Observability

### CloudWatch Integration

- Lambda function logs
- API Gateway access logs
- App Runner application logs
- Bedrock invocation traces

### Key Metrics

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| API Latency (P99) | API Gateway | > 3000ms |
| Lambda Errors | Lambda | > 5% |
| DynamoDB Throttles | DynamoDB | Any |
| Model Invocation Errors | Bedrock | > 1% |

---

## Cost Optimization

### Strategies Implemented

1. **Model Routing**: Use cheaper Titan for simple queries
2. **On-Demand DynamoDB**: Pay only for actual usage
3. **App Runner Min Size**: 1 instance when idle
4. **S3 Vectors**: 90% cheaper than traditional vector DBs
5. **Lambda Right-Sizing**: 256MB optimized for workload

### Cost Breakdown (Estimated)

| Service | Daily Cost (Demo) |
|---------|-------------------|
| OpenSearch Serverless | $11.52 (2 OCU) |
| App Runner | $1.54 (1 vCPU) |
| Lambda | < $0.10 |
| DynamoDB | < $0.10 |
| Bedrock (100 queries) | ~$2.00 |
| S3 | < $0.10 |
| **Total** | **~$15-20/day** |

---

## Deployment Architecture

### GitHub Actions Pipeline

```yaml
Trigger: Push to main / Manual dispatch
         ↓
    ┌────────────────────────────────────────┐
    │           CI Checks (Parallel)          │
    │  ┌──────────┐ ┌──────────┐ ┌──────────┐│
    │  │  Lint    │ │  Test    │ │ Security ││
    │  └──────────┘ └──────────┘ └──────────┘│
    └────────────────────────────────────────┘
                     ↓
    ┌────────────────────────────────────────┐
    │           Terraform Plan                │
    │      (OIDC → AWS Credentials)           │
    └────────────────────────────────────────┘
                     ↓
    ┌────────────────────────────────────────┐
    │     Manual Approval (Production)        │
    └────────────────────────────────────────┘
                     ↓
    ┌────────────────────────────────────────┐
    │           Terraform Apply               │
    └────────────────────────────────────────┘
                     ↓
    ┌────────────────────────────────────────┐
    │     Build & Deploy (Parallel)           │
    │  ┌──────────┐ ┌──────────┐ ┌──────────┐│
    │  │  ECR     │ │  Lambda  │ │App Runner││
    │  └──────────┘ └──────────┘ └──────────┘│
    └────────────────────────────────────────┘
                     ↓
    ┌────────────────────────────────────────┐
    │           Health Checks                 │
    └────────────────────────────────────────┘
```

---

## Future Enhancements

1. **Multi-tenant Support**: Per-customer isolation
2. **Bedrock Agents**: Full AgentCore integration
3. **Real-time Updates**: WebSocket for live ticket updates
4. **Email Integration**: Automatic ticket from email
5. **Slack/Teams Bot**: Chat platform integration
6. **Analytics Dashboard**: Ticket trends and insights
7. **SLA Monitoring**: Automatic escalation rules

---

## References

- [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Strands Agents SDK](https://github.com/strands-agents/strands-agents-sdk)
- [OpenSearch Serverless](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless.html)
- [S3 Vector Store](https://aws.amazon.com/s3/features/s3-vectors/)
