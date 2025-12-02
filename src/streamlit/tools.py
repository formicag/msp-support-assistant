"""
MSP Support Assistant - Strands Agent Tools

Ticket management tools using Strands @tool decorator pattern.
These tools are automatically discovered by the Strands Agent and provide
natural language access to the ticket management API.

Each tool uses docstrings for LLM understanding:
- First paragraph becomes the tool description
- Args section documents parameters

Usage:
    from tools import list_tickets, create_ticket, get_ticket, update_ticket, get_ticket_summary

    agent = Agent(tools=[list_tickets, create_ticket, get_ticket, update_ticket, get_ticket_summary])
"""

import os
from typing import Optional

import requests
from strands import tool

# API Gateway endpoint - configurable via environment
API_GATEWAY_ENDPOINT = os.environ.get(
    "API_GATEWAY_ENDPOINT",
    "https://p3h9ge8d92.execute-api.us-east-1.amazonaws.com"
)


def _call_ticket_api(endpoint: str, method: str = "GET", data: Optional[dict] = None) -> dict:
    """Internal helper to call the Ticket API.

    Args:
        endpoint: API endpoint path (e.g., "/tickets")
        method: HTTP method (GET, POST, PATCH)
        data: Request body for POST/PATCH

    Returns:
        API response as dictionary
    """
    url = f"{API_GATEWAY_ENDPOINT.rstrip('/')}{endpoint}"
    headers = {"Content-Type": "application/json"}

    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=30)
        elif method == "PATCH":
            response = requests.patch(url, headers=headers, json=data, timeout=30)
        else:
            return {"error": f"Unsupported method: {method}"}

        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


@tool
def list_tickets(status: Optional[str] = None, limit: int = 10) -> dict:
    """List support tickets with optional filtering by status.

    Use this tool to show all tickets or filter by a specific status.
    Returns a list of tickets with their ID, title, status, priority, and category.

    Args:
        status: Filter tickets by status. Valid values: "Open", "In Progress", "Resolved", "Closed"
        limit: Maximum number of tickets to return (default: 10)

    Returns:
        Dictionary containing list of tickets or error message
    """
    endpoint = "/tickets"
    params = []

    if status:
        params.append(f"status={status}")
    if limit:
        params.append(f"limit={limit}")
    if params:
        endpoint += "?" + "&".join(params)

    result = _call_ticket_api(endpoint)

    if "error" in result:
        return {"success": False, "error": result["error"]}

    tickets = result.get("tickets", [])
    return {
        "success": True,
        "count": len(tickets),
        "tickets": tickets
    }


@tool
def create_ticket(
    title: str,
    description: str,
    priority: str = "Medium",
    category: str = "General"
) -> dict:
    """Create a new support ticket in the system.

    Use this tool when a user reports an issue or needs help with something.
    The tool creates a ticket and returns the ticket ID for tracking.

    Args:
        title: Brief summary of the issue (required)
        description: Detailed description of the problem (required)
        priority: Ticket priority level. Valid values: "Low", "Medium", "High", "Critical"
        category: Issue category. Valid values: "Network", "Hardware", "Software", "Security", "General"

    Returns:
        Dictionary containing the created ticket details or error message
    """
    data = {
        "title": title,
        "description": description,
        "priority": priority,
        "category": category
    }

    result = _call_ticket_api("/tickets", method="POST", data=data)

    if "error" in result:
        return {"success": False, "error": result["error"]}

    ticket = result.get("ticket", {})
    return {
        "success": True,
        "message": f"Ticket created successfully",
        "ticket_id": ticket.get("TicketId"),
        "ticket": ticket
    }


@tool
def get_ticket(ticket_id: str) -> dict:
    """Retrieve details of a specific ticket by its ID.

    Use this tool to get full information about a particular ticket,
    including its history, notes, and current status.

    Args:
        ticket_id: The unique ticket identifier (e.g., "TKT-1234567890")

    Returns:
        Dictionary containing ticket details or error message
    """
    result = _call_ticket_api(f"/tickets/{ticket_id}")

    if "error" in result:
        return {"success": False, "error": result["error"]}

    return {
        "success": True,
        "ticket": result
    }


@tool
def update_ticket(
    ticket_id: str,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    note: Optional[str] = None
) -> dict:
    """Update an existing ticket's status, priority, or add notes.

    Use this tool to modify a ticket when its status changes,
    priority needs adjustment, or to add progress notes.

    Args:
        ticket_id: The ticket ID to update (required)
        status: New ticket status. Valid values: "Open", "In Progress", "Resolved", "Closed"
        priority: New priority level. Valid values: "Low", "Medium", "High", "Critical"
        note: Note to add to the ticket history

    Returns:
        Dictionary containing updated ticket details or error message
    """
    data = {}
    if status:
        data["status"] = status
    if priority:
        data["priority"] = priority
    if note:
        data["note"] = note

    if not data:
        return {"success": False, "error": "No update fields provided"}

    result = _call_ticket_api(f"/tickets/{ticket_id}", method="PATCH", data=data)

    if "error" in result:
        return {"success": False, "error": result["error"]}

    return {
        "success": True,
        "message": f"Ticket {ticket_id} updated successfully",
        "ticket": result
    }


@tool
def get_ticket_summary() -> dict:
    """Get a summary and overview of all tickets including statistics.

    Use this tool when the user asks for an overview, analytics, or summary
    of the ticket system. Returns counts by status, priority, and category.

    Returns:
        Dictionary containing ticket statistics and summary
    """
    result = _call_ticket_api("/tickets?limit=100")

    if "error" in result:
        return {"success": False, "error": result["error"]}

    tickets = result.get("tickets", [])

    # Compute summary statistics
    summary = {
        "total_tickets": len(tickets),
        "by_status": {},
        "by_priority": {},
        "by_category": {}
    }

    for ticket in tickets:
        status = ticket.get("Status", "Unknown")
        priority = ticket.get("Priority", "Unknown")
        category = ticket.get("Category", "Unknown")

        summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
        summary["by_priority"][priority] = summary["by_priority"].get(priority, 0) + 1
        summary["by_category"][category] = summary["by_category"].get(category, 0) + 1

    return {
        "success": True,
        "summary": summary,
        "recent_tickets": tickets[:5] if tickets else []
    }


@tool
def retrieve_memories(query: str, namespace: Optional[str] = None) -> dict:
    """Search and retrieve memories related to a specific query.

    Use this tool for agentic RAG - when you need to proactively search
    for relevant memories based on the conversation context. This allows
    iterative memory exploration and cross-reference capabilities.

    This is different from automatic memory retrieval which happens on every query.
    Use this when you need to:
    - Search for specific facts about the user
    - Find relevant session summaries
    - Look up user preferences for a specific topic

    Args:
        query: The search query to find relevant memories
        namespace: Optional namespace to search in. Valid values:
                   "/preferences/{actorId}", "/facts/{actorId}", "/summaries/{actorId}"

    Returns:
        Dictionary containing matching memory records
    """
    # This tool provides agentic RAG capabilities
    # The actual implementation uses the AgentCore Memory retrieve_memories API
    # For now, return a placeholder that will be enhanced with actual memory retrieval
    return {
        "success": True,
        "message": "Memory retrieval tool - use session_manager for actual retrieval",
        "query": query,
        "namespace": namespace,
        "memories": []
    }


# Export all tools for easy import
TICKET_TOOLS = [
    list_tickets,
    create_ticket,
    get_ticket,
    update_ticket,
    get_ticket_summary,
    retrieve_memories
]
