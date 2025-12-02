"""
Tool definitions for the MSP Support Agent.

These tools integrate with the Ticket API and provide capabilities for
ticket management operations.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

import boto3
import requests
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result from a tool execution."""

    success: bool
    data: Any
    error: Optional[str] = None


class TicketTools:
    """Tools for ticket management operations."""

    def __init__(self, api_endpoint: str, region: str = "us-east-1"):
        """
        Initialize ticket tools.

        Args:
            api_endpoint: The API Gateway endpoint URL
            region: AWS region
        """
        self.api_endpoint = api_endpoint.rstrip("/")
        self.region = region
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _call_api(
        self, method: str, path: str, data: Optional[dict] = None
    ) -> ToolResult:
        """Make an API call to the ticket service."""
        url = f"{self.api_endpoint}{path}"

        try:
            if method == "GET":
                response = self.session.get(url, timeout=30)
            elif method == "POST":
                response = self.session.post(url, json=data, timeout=30)
            elif method == "PATCH":
                response = self.session.patch(url, json=data, timeout=30)
            elif method == "DELETE":
                response = self.session.delete(url, timeout=30)
            else:
                return ToolResult(success=False, data=None, error=f"Unknown method: {method}")

            response.raise_for_status()
            return ToolResult(success=True, data=response.json())

        except requests.exceptions.Timeout:
            logger.error(f"API timeout: {method} {path}")
            return ToolResult(success=False, data=None, error="API request timed out")
        except requests.exceptions.HTTPError as e:
            logger.error(f"API error: {e}")
            try:
                error_data = e.response.json()
                return ToolResult(
                    success=False,
                    data=None,
                    error=error_data.get("error", str(e)),
                )
            except Exception:
                return ToolResult(success=False, data=None, error=str(e))
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return ToolResult(success=False, data=None, error=str(e))

    def create_ticket(
        self,
        title: str,
        description: str,
        priority: str = "Medium",
        category: str = "General",
        customer_id: Optional[str] = None,
    ) -> ToolResult:
        """
        Create a new support ticket.

        Args:
            title: Brief summary of the issue
            description: Detailed description
            priority: Low, Medium, High, or Critical
            category: Network, Hardware, Software, Security, or General
            customer_id: Optional customer identifier

        Returns:
            ToolResult with created ticket data
        """
        data = {
            "title": title,
            "description": description,
            "priority": priority,
            "category": category,
        }
        if customer_id:
            data["customer_id"] = customer_id

        logger.info(f"Creating ticket: {title}")
        return self._call_api("POST", "/tickets", data)

    def get_ticket(self, ticket_id: str) -> ToolResult:
        """
        Get a specific ticket by ID.

        Args:
            ticket_id: The ticket ID to retrieve

        Returns:
            ToolResult with ticket data
        """
        logger.info(f"Getting ticket: {ticket_id}")
        return self._call_api("GET", f"/tickets/{ticket_id}")

    def update_ticket(
        self,
        ticket_id: str,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        note: Optional[str] = None,
        assigned_to: Optional[str] = None,
    ) -> ToolResult:
        """
        Update an existing ticket.

        Args:
            ticket_id: The ticket ID to update
            status: New status (Open, In Progress, Resolved, Closed)
            priority: New priority
            note: Note to add to the ticket
            assigned_to: Assign to a specific person

        Returns:
            ToolResult with updated ticket data
        """
        data = {}
        if status:
            data["status"] = status
        if priority:
            data["priority"] = priority
        if note:
            data["note"] = note
        if assigned_to:
            data["assigned_to"] = assigned_to

        if not data:
            return ToolResult(success=False, data=None, error="No updates provided")

        logger.info(f"Updating ticket: {ticket_id}")
        return self._call_api("PATCH", f"/tickets/{ticket_id}", data)

    def list_tickets(
        self,
        status: Optional[str] = None,
        customer_id: Optional[str] = None,
        limit: int = 10,
    ) -> ToolResult:
        """
        List tickets with optional filters.

        Args:
            status: Filter by status
            customer_id: Filter by customer
            limit: Maximum number of tickets to return

        Returns:
            ToolResult with list of tickets
        """
        params = [f"limit={limit}"]
        if status:
            params.append(f"status={status}")
        if customer_id:
            params.append(f"customer_id={customer_id}")

        query_string = "&".join(params)
        logger.info(f"Listing tickets with params: {query_string}")
        return self._call_api("GET", f"/tickets?{query_string}")

    def delete_ticket(self, ticket_id: str) -> ToolResult:
        """
        Delete a ticket.

        Args:
            ticket_id: The ticket ID to delete

        Returns:
            ToolResult with deletion confirmation
        """
        logger.info(f"Deleting ticket: {ticket_id}")
        return self._call_api("DELETE", f"/tickets/{ticket_id}")


class KnowledgeBaseTools:
    """Tools for querying the knowledge base (RAG)."""

    def __init__(
        self,
        opensearch_endpoint: str,
        embedding_model_id: str,
        region: str = "us-east-1",
        index_name: str = "tickets-index",
    ):
        """
        Initialize knowledge base tools.

        Args:
            opensearch_endpoint: OpenSearch Serverless endpoint
            embedding_model_id: Bedrock embedding model ID
            region: AWS region
            index_name: OpenSearch index name
        """
        self.opensearch_endpoint = opensearch_endpoint
        self.embedding_model_id = embedding_model_id
        self.region = region
        self.index_name = index_name
        self.bedrock_runtime = boto3.client("bedrock-runtime", region_name=region)

    def get_embedding(self, text: str) -> list:
        """Generate embedding for text using Bedrock."""
        try:
            body = json.dumps({"inputText": text})
            response = self.bedrock_runtime.invoke_model(
                modelId=self.embedding_model_id,
                body=body,
            )
            response_body = json.loads(response["body"].read())
            return response_body.get("embedding", [])
        except ClientError as e:
            logger.error(f"Embedding error: {e}")
            return []

    def search_knowledge_base(
        self, query: str, top_k: int = 5
    ) -> ToolResult:
        """
        Search the knowledge base for relevant documents.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            ToolResult with matching documents
        """
        # Get query embedding
        embedding = self.get_embedding(query)
        if not embedding:
            return ToolResult(
                success=False,
                data=None,
                error="Failed to generate embedding",
            )

        # Note: In production, this would query OpenSearch Serverless
        # For demo, return placeholder
        logger.info(f"Searching knowledge base: {query}")
        return ToolResult(
            success=True,
            data={
                "query": query,
                "results": [],
                "message": "Knowledge base search not yet implemented",
            },
        )


# Tool schemas for agent integration
TOOL_SCHEMAS = [
    {
        "name": "create_ticket",
        "description": "Create a new support ticket in the system",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Brief summary of the issue",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of the problem",
                },
                "priority": {
                    "type": "string",
                    "enum": ["Low", "Medium", "High", "Critical"],
                    "description": "Ticket priority level",
                },
                "category": {
                    "type": "string",
                    "enum": ["Network", "Hardware", "Software", "Security", "General"],
                    "description": "Issue category",
                },
                "customer_id": {
                    "type": "string",
                    "description": "Optional customer identifier",
                },
            },
            "required": ["title", "description"],
        },
    },
    {
        "name": "get_ticket",
        "description": "Retrieve details of a specific ticket by its ID",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "The unique ticket identifier",
                },
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "update_ticket",
        "description": "Update an existing ticket's status, priority, or add notes",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "The ticket ID to update",
                },
                "status": {
                    "type": "string",
                    "enum": ["Open", "In Progress", "Resolved", "Closed"],
                    "description": "New ticket status",
                },
                "priority": {
                    "type": "string",
                    "enum": ["Low", "Medium", "High", "Critical"],
                    "description": "New priority level",
                },
                "note": {
                    "type": "string",
                    "description": "Note to add to the ticket",
                },
                "assigned_to": {
                    "type": "string",
                    "description": "Person to assign the ticket to",
                },
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "list_tickets",
        "description": "List support tickets with optional filters",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["Open", "In Progress", "Resolved", "Closed"],
                    "description": "Filter by status",
                },
                "customer_id": {
                    "type": "string",
                    "description": "Filter by customer",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of tickets to return",
                    "default": 10,
                },
            },
        },
    },
    {
        "name": "search_knowledge_base",
        "description": "Search the knowledge base for relevant information about past issues and solutions",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for finding relevant knowledge",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
]
