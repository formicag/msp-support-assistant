"""
MSP Support Assistant - Ticket API Lambda Handler

This Lambda function handles CRUD operations for support tickets.
It integrates with DynamoDB for persistent storage.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
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


def create_response(status_code: int, body: dict) -> dict:
    """Create a standardized API response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Api-Key",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }


def generate_ticket_id() -> str:
    """Generate a unique ticket ID."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    unique_id = uuid.uuid4().hex[:8].upper()
    return f"TKT-{timestamp}-{unique_id}"


def get_current_timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def create_ticket(event: dict) -> dict:
    """Create a new support ticket."""
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return create_response(400, {"error": "Invalid JSON in request body"})

    # Validate required fields
    required_fields = ["title", "description"]
    missing_fields = [f for f in required_fields if not body.get(f)]
    if missing_fields:
        return create_response(
            400, {"error": f"Missing required fields: {', '.join(missing_fields)}"}
        )

    # Generate ticket data
    ticket_id = generate_ticket_id()
    timestamp = get_current_timestamp()

    ticket = {
        "TicketId": ticket_id,
        "Title": body["title"],
        "Description": body["description"],
        "Status": body.get("status", "Open"),
        "Priority": body.get("priority", "Medium"),
        "CustomerId": body.get("customer_id", "default"),
        "AssignedTo": body.get("assigned_to"),
        "Category": body.get("category", "General"),
        "Tags": body.get("tags", []),
        "CreatedAt": timestamp,
        "UpdatedAt": timestamp,
        "Notes": [],
    }

    # Remove None values
    ticket = {k: v for k, v in ticket.items() if v is not None}

    try:
        tickets_table.put_item(Item=ticket)
        logger.info(f"Created ticket: {ticket_id}")
        return create_response(201, {"message": "Ticket created successfully", "ticket": ticket})
    except ClientError as e:
        logger.error(f"Failed to create ticket: {e}")
        return create_response(500, {"error": "Failed to create ticket"})


def get_ticket(event: dict) -> dict:
    """Get a specific ticket by ID."""
    path_params = event.get("pathParameters", {}) or {}
    ticket_id = path_params.get("ticketId")

    if not ticket_id:
        return create_response(400, {"error": "Ticket ID is required"})

    try:
        response = tickets_table.get_item(Key={"TicketId": ticket_id})
        ticket = response.get("Item")

        if not ticket:
            return create_response(404, {"error": f"Ticket {ticket_id} not found"})

        return create_response(200, {"ticket": ticket})
    except ClientError as e:
        logger.error(f"Failed to get ticket: {e}")
        return create_response(500, {"error": "Failed to retrieve ticket"})


def update_ticket(event: dict) -> dict:
    """Update an existing ticket."""
    path_params = event.get("pathParameters", {}) or {}
    ticket_id = path_params.get("ticketId")

    if not ticket_id:
        return create_response(400, {"error": "Ticket ID is required"})

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return create_response(400, {"error": "Invalid JSON in request body"})

    # Allowed update fields
    allowed_fields = [
        "Title",
        "Description",
        "Status",
        "Priority",
        "AssignedTo",
        "Category",
        "Tags",
    ]

    # Build update expression
    update_parts = []
    expression_values = {}
    expression_names = {}

    for field in allowed_fields:
        # Handle case-insensitive field names from input
        value = body.get(field) or body.get(field.lower())
        if value is not None:
            placeholder = f":val_{field.lower()}"
            update_parts.append(f"#{field} = {placeholder}")
            expression_values[placeholder] = value
            expression_names[f"#{field}"] = field

    # Handle notes append (special case)
    if "note" in body:
        note = {
            "text": body["note"],
            "timestamp": get_current_timestamp(),
            "author": body.get("author", "System"),
        }
        update_parts.append("Notes = list_append(if_not_exists(Notes, :empty_list), :new_note)")
        expression_values[":new_note"] = [note]
        expression_values[":empty_list"] = []

    if not update_parts:
        return create_response(400, {"error": "No valid fields to update"})

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
        return create_response(
            200, {"message": "Ticket updated successfully", "ticket": response["Attributes"]}
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return create_response(404, {"error": f"Ticket {ticket_id} not found"})
        logger.error(f"Failed to update ticket: {e}")
        return create_response(500, {"error": "Failed to update ticket"})


def delete_ticket(event: dict) -> dict:
    """Delete a ticket."""
    path_params = event.get("pathParameters", {}) or {}
    ticket_id = path_params.get("ticketId")

    if not ticket_id:
        return create_response(400, {"error": "Ticket ID is required"})

    try:
        tickets_table.delete_item(
            Key={"TicketId": ticket_id},
            ConditionExpression="attribute_exists(TicketId)",
        )
        logger.info(f"Deleted ticket: {ticket_id}")
        return create_response(200, {"message": f"Ticket {ticket_id} deleted successfully"})
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return create_response(404, {"error": f"Ticket {ticket_id} not found"})
        logger.error(f"Failed to delete ticket: {e}")
        return create_response(500, {"error": "Failed to delete ticket"})


def list_tickets(event: dict) -> dict:
    """List all tickets with optional filtering."""
    query_params = event.get("queryStringParameters", {}) or {}

    # Pagination
    limit = min(int(query_params.get("limit", 50)), 100)
    last_key = query_params.get("lastKey")

    # Filters
    status_filter = query_params.get("status")
    customer_filter = query_params.get("customer_id")

    try:
        scan_kwargs = {"Limit": limit}

        if last_key:
            scan_kwargs["ExclusiveStartKey"] = {"TicketId": last_key}

        # Apply filters if provided
        filter_expressions = []
        expression_values = {}

        if status_filter:
            filter_expressions.append("#status = :status")
            expression_values[":status"] = status_filter

        if customer_filter:
            filter_expressions.append("CustomerId = :customer")
            expression_values[":customer"] = customer_filter

        if filter_expressions:
            scan_kwargs["FilterExpression"] = " AND ".join(filter_expressions)
            scan_kwargs["ExpressionAttributeValues"] = expression_values
            if status_filter:
                scan_kwargs["ExpressionAttributeNames"] = {"#status": "Status"}

        response = tickets_table.scan(**scan_kwargs)

        result = {
            "tickets": response.get("Items", []),
            "count": len(response.get("Items", [])),
        }

        if "LastEvaluatedKey" in response:
            result["lastKey"] = response["LastEvaluatedKey"]["TicketId"]

        return create_response(200, result)
    except ClientError as e:
        logger.error(f"Failed to list tickets: {e}")
        return create_response(500, {"error": "Failed to list tickets"})


def health_check(event: dict) -> dict:
    """Health check endpoint."""
    return create_response(
        200,
        {
            "status": "healthy",
            "service": "msp-support-assistant-ticket-api",
            "timestamp": get_current_timestamp(),
        },
    )


def lambda_handler(event: dict, context: Any) -> dict:
    """Main Lambda handler - routes requests to appropriate handlers."""
    logger.info(f"Received event: {json.dumps(event)}")

    # Get HTTP method and path
    http_method = event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("rawPath", "")

    # Route request
    if path == "/health" and http_method == "GET":
        return health_check(event)
    elif path == "/tickets" and http_method == "POST":
        return create_ticket(event)
    elif path == "/tickets" and http_method == "GET":
        return list_tickets(event)
    elif path.startswith("/tickets/") and http_method == "GET":
        return get_ticket(event)
    elif path.startswith("/tickets/") and http_method in ["PATCH", "PUT"]:
        return update_ticket(event)
    elif path.startswith("/tickets/") and http_method == "DELETE":
        return delete_ticket(event)
    else:
        return create_response(404, {"error": f"Route not found: {http_method} {path}"})
