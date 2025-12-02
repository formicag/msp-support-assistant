"""
MSP Support Assistant - AgentCore Tools Lambda Handler

This Lambda function handles MCP-compatible tool calls from the AgentCore Gateway.
Unlike the API Gateway handler, this accepts map-based parameters directly.

Tools available:
- list_tickets: List all tickets with optional filters
- create_ticket: Create a new support ticket
- get_ticket: Get a specific ticket by ID
- update_ticket: Update an existing ticket
- get_ticket_summary: Get a summary/overview of all tickets
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO")
logger = logging.getLogger()
logger.setLevel(log_level)

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")
tickets_table_name = os.environ.get("TICKETS_TABLE_NAME", "msp-support-assistant-demo-tickets")
tickets_table = dynamodb.Table(tickets_table_name)


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj) if obj % 1 else int(obj)
        return super().default(obj)


def generate_ticket_id() -> str:
    """Generate a unique ticket ID."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    unique_id = uuid.uuid4().hex[:8].upper()
    return f"TKT-{timestamp}-{unique_id}"


def get_current_timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def list_tickets(params: dict) -> dict:
    """
    List tickets with optional filters.

    Parameters:
        status (str, optional): Filter by status (Open, In Progress, Resolved, Closed)
        customer_id (str, optional): Filter by customer
        limit (int, optional): Maximum number of tickets to return (default: 50)

    Returns:
        dict with tickets list and count
    """
    logger.info(f"list_tickets called with params: {params}")

    status_filter = params.get("status")
    customer_filter = params.get("customer_id")
    limit = min(int(params.get("limit", 50)), 100)

    try:
        scan_kwargs = {"Limit": limit}
        filter_expressions = []
        expression_values = {}
        expression_names = {}

        if status_filter:
            filter_expressions.append("#status = :status")
            expression_values[":status"] = status_filter
            expression_names["#status"] = "Status"

        if customer_filter:
            filter_expressions.append("CustomerId = :customer")
            expression_values[":customer"] = customer_filter

        if filter_expressions:
            scan_kwargs["FilterExpression"] = " AND ".join(filter_expressions)
            scan_kwargs["ExpressionAttributeValues"] = expression_values
            if expression_names:
                scan_kwargs["ExpressionAttributeNames"] = expression_names

        response = tickets_table.scan(**scan_kwargs)

        return {
            "success": True,
            "tickets": response.get("Items", []),
            "count": len(response.get("Items", []))
        }
    except ClientError as e:
        logger.error(f"Failed to list tickets: {e}")
        return {"success": False, "error": str(e)}


def create_ticket(params: dict) -> dict:
    """
    Create a new support ticket.

    Parameters:
        title (str, required): Brief summary of the issue
        description (str, required): Detailed description of the problem
        priority (str, optional): Low, Medium, High, or Critical (default: Medium)
        category (str, optional): Network, Hardware, Software, Security, or General
        customer_id (str, optional): Customer identifier

    Returns:
        dict with created ticket data
    """
    logger.info(f"create_ticket called with params: {params}")

    title = params.get("title")
    description = params.get("description")

    if not title or not description:
        return {
            "success": False,
            "error": "Missing required fields: title and description are required"
        }

    ticket_id = generate_ticket_id()
    timestamp = get_current_timestamp()

    ticket = {
        "TicketId": ticket_id,
        "Title": title,
        "Description": description,
        "Status": params.get("status", "Open"),
        "Priority": params.get("priority", "Medium"),
        "CustomerId": params.get("customer_id", "default"),
        "AssignedTo": params.get("assigned_to"),
        "Category": params.get("category", "General"),
        "Tags": params.get("tags", []),
        "CreatedAt": timestamp,
        "UpdatedAt": timestamp,
        "Notes": [],
    }

    # Remove None values
    ticket = {k: v for k, v in ticket.items() if v is not None}

    try:
        tickets_table.put_item(Item=ticket)
        logger.info(f"Created ticket: {ticket_id}")
        return {
            "success": True,
            "message": "Ticket created successfully",
            "ticket": ticket
        }
    except ClientError as e:
        logger.error(f"Failed to create ticket: {e}")
        return {"success": False, "error": str(e)}


def get_ticket(params: dict) -> dict:
    """
    Get a specific ticket by ID.

    Parameters:
        ticket_id (str, required): The unique ticket identifier

    Returns:
        dict with ticket data
    """
    logger.info(f"get_ticket called with params: {params}")

    ticket_id = params.get("ticket_id") or params.get("id")

    if not ticket_id:
        return {"success": False, "error": "ticket_id is required"}

    try:
        response = tickets_table.get_item(Key={"TicketId": ticket_id})
        ticket = response.get("Item")

        if not ticket:
            return {"success": False, "error": f"Ticket {ticket_id} not found"}

        return {"success": True, "ticket": ticket}
    except ClientError as e:
        logger.error(f"Failed to get ticket: {e}")
        return {"success": False, "error": str(e)}


def update_ticket(params: dict) -> dict:
    """
    Update an existing ticket.

    Parameters:
        ticket_id (str, required): The ticket ID to update
        status (str, optional): New status (Open, In Progress, Resolved, Closed)
        priority (str, optional): New priority level
        note (str, optional): Note to add to the ticket
        assigned_to (str, optional): Person to assign the ticket to

    Returns:
        dict with updated ticket data
    """
    logger.info(f"update_ticket called with params: {params}")

    ticket_id = params.get("ticket_id") or params.get("id")

    if not ticket_id:
        return {"success": False, "error": "ticket_id is required"}

    # Allowed update fields
    allowed_fields = ["Title", "Description", "Status", "Priority", "AssignedTo", "Category", "Tags"]

    update_parts = []
    expression_values = {}
    expression_names = {}

    for field in allowed_fields:
        value = params.get(field) or params.get(field.lower())
        if value is not None:
            placeholder = f":val_{field.lower()}"
            update_parts.append(f"#{field} = {placeholder}")
            expression_values[placeholder] = value
            expression_names[f"#{field}"] = field

    # Handle notes append
    if "note" in params:
        note = {
            "text": params["note"],
            "timestamp": get_current_timestamp(),
            "author": params.get("author", "Agent"),
        }
        update_parts.append("Notes = list_append(if_not_exists(Notes, :empty_list), :new_note)")
        expression_values[":new_note"] = [note]
        expression_values[":empty_list"] = []

    if not update_parts:
        return {"success": False, "error": "No valid fields to update"}

    # Always update timestamp
    update_parts.append("#UpdatedAt = :updated_at")
    expression_values[":updated_at"] = get_current_timestamp()
    expression_names["#UpdatedAt"] = "UpdatedAt"

    update_expression = "SET " + ", ".join(update_parts)

    try:
        response = tickets_table.update_item(
            Key={"TicketId": ticket_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ExpressionAttributeNames=expression_names if expression_names else None,
            ReturnValues="ALL_NEW",
            ConditionExpression="attribute_exists(TicketId)",
        )
        logger.info(f"Updated ticket: {ticket_id}")
        return {
            "success": True,
            "message": "Ticket updated successfully",
            "ticket": response["Attributes"]
        }
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return {"success": False, "error": f"Ticket {ticket_id} not found"}
        logger.error(f"Failed to update ticket: {e}")
        return {"success": False, "error": str(e)}


def get_ticket_summary(params: dict) -> dict:
    """
    Get a summary/overview of all tickets.

    Parameters:
        None required

    Returns:
        dict with ticket statistics and overview
    """
    logger.info("get_ticket_summary called")

    try:
        # Scan all tickets
        response = tickets_table.scan()
        tickets = response.get("Items", [])

        # Calculate statistics
        total_count = len(tickets)

        # Count by status
        status_counts = {}
        priority_counts = {}
        category_counts = {}

        # Track recent tickets (last 24 hours)
        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)
        recent_tickets = []

        for ticket in tickets:
            # Status counts
            status = ticket.get("Status", "Unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

            # Priority counts
            priority = ticket.get("Priority", "Unknown")
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

            # Category counts
            category = ticket.get("Category", "Unknown")
            category_counts[category] = category_counts.get(category, 0) + 1

            # Check if recent
            created_at = ticket.get("CreatedAt", "")
            if created_at:
                try:
                    ticket_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    if ticket_time > last_24h:
                        recent_tickets.append({
                            "TicketId": ticket.get("TicketId"),
                            "Title": ticket.get("Title"),
                            "Priority": ticket.get("Priority"),
                            "Status": ticket.get("Status"),
                            "CreatedAt": created_at
                        })
                except (ValueError, TypeError):
                    pass

        return {
            "success": True,
            "summary": {
                "total_tickets": total_count,
                "by_status": status_counts,
                "by_priority": priority_counts,
                "by_category": category_counts,
                "tickets_last_24_hours": len(recent_tickets),
                "recent_tickets": recent_tickets[:5]  # Top 5 recent
            }
        }
    except ClientError as e:
        logger.error(f"Failed to get ticket summary: {e}")
        return {"success": False, "error": str(e)}


# Tool dispatcher
TOOLS = {
    "list_tickets": list_tickets,
    "create_ticket": create_ticket,
    "get_ticket": get_ticket,
    "update_ticket": update_ticket,
    "get_ticket_summary": get_ticket_summary,
}


def lambda_handler(event: dict, context: Any) -> dict:
    """
    Main Lambda handler for AgentCore Gateway tool invocations.

    The AgentCore Gateway sends tool invocations as map-based parameters,
    not as API Gateway events.

    Expected event format from Gateway:
    {
        "tool_name": "list_tickets",
        "parameters": {
            "status": "Open",
            "limit": 10
        }
    }

    Or direct parameter format:
    {
        "status": "Open",
        "limit": 10
    }
    """
    logger.info(f"Received event: {json.dumps(event, cls=DecimalEncoder)}")

    # Determine the tool to invoke
    tool_name = event.get("tool_name") or event.get("name") or event.get("action")

    # If tool_name is specified, get parameters from 'parameters' key
    if tool_name:
        params = event.get("parameters", event.get("input", {}))
    else:
        # Try to infer tool from event structure (direct invocation)
        # This handles the case where Gateway sends params directly
        params = event

        # Check if this looks like a specific tool call
        if "ticket_id" in event or "id" in event:
            if any(k in event for k in ["status", "priority", "note", "assigned_to"]):
                tool_name = "update_ticket"
            else:
                tool_name = "get_ticket"
        elif "title" in event and "description" in event:
            tool_name = "create_ticket"
        elif event.get("action") == "summary" or event.get("summary"):
            tool_name = "get_ticket_summary"
        else:
            tool_name = "list_tickets"  # Default to list

    logger.info(f"Invoking tool: {tool_name} with params: {params}")

    # Execute the tool
    if tool_name not in TOOLS:
        return {
            "success": False,
            "error": f"Unknown tool: {tool_name}. Available tools: {list(TOOLS.keys())}"
        }

    result = TOOLS[tool_name](params)

    # Ensure JSON serializable
    return json.loads(json.dumps(result, cls=DecimalEncoder))
