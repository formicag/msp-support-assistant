"""
Unit tests for the Lambda ticket API handler.
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "lambda"))


class TestCreateResponse:
    """Tests for the create_response function."""

    def test_creates_valid_response(self):
        from handler import create_response

        response = create_response(200, {"message": "success"})

        assert response["statusCode"] == 200
        assert "Content-Type" in response["headers"]
        assert json.loads(response["body"]) == {"message": "success"}

    def test_includes_cors_headers(self):
        from handler import create_response

        response = create_response(200, {})

        assert response["headers"]["Access-Control-Allow-Origin"] == "*"
        assert "GET" in response["headers"]["Access-Control-Allow-Methods"]


class TestGenerateTicketId:
    """Tests for ticket ID generation."""

    def test_generates_valid_format(self):
        from handler import generate_ticket_id

        ticket_id = generate_ticket_id()

        assert ticket_id.startswith("TKT-")
        assert len(ticket_id) == 21  # TKT-YYYYMMDD-XXXXXXXX


class TestHealthCheck:
    """Tests for the health check endpoint."""

    def test_returns_healthy_status(self):
        from handler import health_check

        response = health_check({})
        body = json.loads(response["body"])

        assert response["statusCode"] == 200
        assert body["status"] == "healthy"
        assert "timestamp" in body


class TestCreateTicket:
    """Tests for ticket creation."""

    @patch("handler.tickets_table")
    def test_creates_ticket_with_required_fields(self, mock_table):
        from handler import create_ticket

        mock_table.put_item = MagicMock()

        event = {
            "body": json.dumps({
                "title": "Test Ticket",
                "description": "Test description"
            })
        }

        response = create_ticket(event)
        body = json.loads(response["body"])

        assert response["statusCode"] == 201
        assert "ticket" in body
        assert body["ticket"]["Title"] == "Test Ticket"
        mock_table.put_item.assert_called_once()

    def test_returns_error_for_missing_fields(self):
        from handler import create_ticket

        event = {"body": json.dumps({"title": "Only title"})}

        response = create_ticket(event)
        body = json.loads(response["body"])

        assert response["statusCode"] == 400
        assert "error" in body
        assert "description" in body["error"]

    def test_returns_error_for_invalid_json(self):
        from handler import create_ticket

        event = {"body": "not valid json"}

        response = create_ticket(event)

        assert response["statusCode"] == 400


class TestGetTicket:
    """Tests for retrieving tickets."""

    @patch("handler.tickets_table")
    def test_returns_ticket_when_found(self, mock_table):
        from handler import get_ticket

        mock_table.get_item = MagicMock(return_value={
            "Item": {
                "TicketId": "TKT-123",
                "Title": "Test Ticket"
            }
        })

        event = {"pathParameters": {"ticketId": "TKT-123"}}

        response = get_ticket(event)
        body = json.loads(response["body"])

        assert response["statusCode"] == 200
        assert body["ticket"]["TicketId"] == "TKT-123"

    @patch("handler.tickets_table")
    def test_returns_404_when_not_found(self, mock_table):
        from handler import get_ticket

        mock_table.get_item = MagicMock(return_value={})

        event = {"pathParameters": {"ticketId": "TKT-NOTFOUND"}}

        response = get_ticket(event)

        assert response["statusCode"] == 404


class TestListTickets:
    """Tests for listing tickets."""

    @patch("handler.tickets_table")
    def test_returns_empty_list_when_no_tickets(self, mock_table):
        from handler import list_tickets

        mock_table.scan = MagicMock(return_value={"Items": []})

        event = {"queryStringParameters": None}

        response = list_tickets(event)
        body = json.loads(response["body"])

        assert response["statusCode"] == 200
        assert body["tickets"] == []
        assert body["count"] == 0


class TestLambdaHandler:
    """Tests for the main Lambda handler routing."""

    @patch("handler.health_check")
    def test_routes_health_check(self, mock_health):
        from handler import lambda_handler

        mock_health.return_value = {"statusCode": 200, "body": "{}"}

        event = {
            "rawPath": "/health",
            "requestContext": {"http": {"method": "GET"}}
        }

        lambda_handler(event, None)

        mock_health.assert_called_once()

    def test_returns_404_for_unknown_route(self):
        from handler import lambda_handler

        event = {
            "rawPath": "/unknown",
            "requestContext": {"http": {"method": "GET"}}
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 404
