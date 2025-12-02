"""
Configuration for the MSP Support Agent.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentConfig:
    """Configuration for the MSP Support Agent."""

    # AWS Configuration
    aws_region: str = field(default_factory=lambda: os.environ.get("AWS_REGION", "us-east-1"))

    # Bedrock Models
    claude_model_id: str = field(
        default_factory=lambda: os.environ.get(
            "BEDROCK_CLAUDE_MODEL", "anthropic.claude-3-sonnet-20240229-v1:0"
        )
    )
    titan_model_id: str = field(
        default_factory=lambda: os.environ.get(
            "BEDROCK_TITAN_MODEL", "amazon.titan-text-express-v1"
        )
    )
    embedding_model_id: str = field(
        default_factory=lambda: os.environ.get(
            "BEDROCK_EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0"
        )
    )

    # API Configuration
    api_gateway_endpoint: str = field(
        default_factory=lambda: os.environ.get("API_GATEWAY_ENDPOINT", "")
    )

    # OpenSearch Configuration
    opensearch_endpoint: str = field(
        default_factory=lambda: os.environ.get("OPENSEARCH_ENDPOINT", "")
    )
    opensearch_index: str = field(
        default_factory=lambda: os.environ.get("OPENSEARCH_INDEX", "tickets-index")
    )

    # S3 Vector Store
    vector_store_bucket: str = field(
        default_factory=lambda: os.environ.get("VECTOR_STORE_BUCKET", "")
    )

    # Memory Configuration
    memory_enabled: bool = field(
        default_factory=lambda: os.environ.get("MEMORY_ENABLED", "true").lower() == "true"
    )
    short_term_memory_size: int = field(
        default_factory=lambda: int(os.environ.get("SHORT_TERM_MEMORY_SIZE", "20"))
    )

    # Guardrails
    guardrail_id: Optional[str] = field(
        default_factory=lambda: os.environ.get("BEDROCK_GUARDRAIL_ID")
    )
    guardrail_version: str = field(
        default_factory=lambda: os.environ.get("BEDROCK_GUARDRAIL_VERSION", "DRAFT")
    )

    # Logging
    log_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))

    # Environment
    environment: str = field(default_factory=lambda: os.environ.get("ENVIRONMENT", "demo"))


# System prompts
SYSTEM_PROMPT = """You are an intelligent MSP (Managed Service Provider) Support Assistant.
Your role is to help users manage support tickets through natural conversation.

## Capabilities
You can help with:
1. **Creating Tickets**: When a user describes an issue, help them create a support ticket
2. **Updating Tickets**: Add notes, change status, or update ticket details
3. **Querying Tickets**: Find and display ticket information
4. **Providing Guidance**: Offer troubleshooting advice based on similar past issues

## Ticket Fields
When creating tickets, gather these details:
- **Title**: Brief summary of the issue
- **Description**: Detailed explanation of the problem
- **Priority**: Low, Medium, High, or Critical
- **Category**: Network, Hardware, Software, Security, or General
- **Customer ID**: Optional customer identifier

## Guidelines
- Be helpful, professional, and efficient
- Ask clarifying questions when needed
- Format ticket information clearly when displaying
- Use available tools to interact with the ticket system
- Reference past conversations when relevant
- Escalate to human support if needed

## Response Format
When displaying tickets, use a clear format:
```
Ticket ID: [ID]
Title: [Title]
Status: [Status]
Priority: [Priority]
Category: [Category]
Created: [Date]
Description: [Description]
```
"""

ROUTING_PROMPT = """Analyze the following user query and determine its complexity.

Query: {query}

Classify this query as:
- SIMPLE: Basic questions, status checks, or straightforward requests
- COMPLEX: Multi-step operations, detailed analysis, or nuanced responses needed

Respond with only: SIMPLE or COMPLEX"""
