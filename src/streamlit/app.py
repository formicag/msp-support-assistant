"""
MSP Support Assistant - Streamlit Frontend

A conversational interface for the MSP Support Ticket Assistant powered by
AWS Bedrock AgentCore with Strands SDK.
"""

import json
import os
import time
from datetime import datetime
from typing import Optional

import boto3
import requests
import streamlit as st
from botocore.exceptions import ClientError

# Page configuration
st.set_page_config(
    page_title="MSP Support Assistant",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Environment configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
API_GATEWAY_ENDPOINT = os.environ.get("API_GATEWAY_ENDPOINT", "")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "demo")


def get_bedrock_client():
    """Get or create Bedrock runtime client (lazy initialization)."""
    if "bedrock_client" not in st.session_state:
        try:
            st.session_state.bedrock_client = boto3.client(
                "bedrock-runtime", region_name=AWS_REGION
            )
        except Exception as e:
            st.error(f"Failed to initialize Bedrock client: {e}")
            return None
    return st.session_state.bedrock_client


def init_session_state():
    """Initialize Streamlit session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"session-{int(time.time())}"
    if "tickets" not in st.session_state:
        st.session_state.tickets = []


def get_system_prompt() -> str:
    """Get the system prompt for the agent."""
    return """You are an intelligent MSP (Managed Service Provider) Support Assistant.
Your role is to help users manage support tickets through natural conversation.

You can help with:
1. **Creating Tickets**: When a user describes an issue, help them create a support ticket
2. **Updating Tickets**: Add notes, change status, or update ticket details
3. **Querying Tickets**: Find and display ticket information
4. **Providing Guidance**: Offer troubleshooting advice based on similar past issues

When creating tickets, gather these details:
- Title (brief summary)
- Description (detailed explanation)
- Priority (Low, Medium, High, Critical)
- Category (Network, Hardware, Software, Security, General)

Always be helpful, professional, and efficient. If you need more information, ask clarifying questions.
Format ticket information clearly when displaying it."""


def invoke_bedrock_model(prompt: str, model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0") -> str:
    """Invoke Bedrock model for response generation."""
    try:
        bedrock_client = get_bedrock_client()
        if bedrock_client is None:
            return "I apologize, but the AI service is not available at the moment. Please try again later."

        # Build conversation history
        messages = []
        for msg in st.session_state.messages[-10:]:  # Last 10 messages for context
            messages.append({
                "role": msg["role"],
                "content": [{"type": "text", "text": msg["content"]}]
            })

        # Add current message
        messages.append({
            "role": "user",
            "content": [{"type": "text", "text": prompt}]
        })

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "system": get_system_prompt(),
            "messages": messages,
        }

        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
        )

        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"]

    except ClientError as e:
        error_msg = f"Error invoking Bedrock: {e.response['Error']['Message']}"
        st.error(error_msg)
        return f"I apologize, but I encountered an error: {error_msg}"
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return f"I apologize, but I encountered an unexpected error. Please try again."


def call_ticket_api(method: str, endpoint: str, data: Optional[dict] = None) -> dict:
    """Call the Ticket API."""
    if not API_GATEWAY_ENDPOINT:
        return {"error": "API Gateway endpoint not configured"}

    url = f"{API_GATEWAY_ENDPOINT.rstrip('/')}{endpoint}"
    headers = {"Content-Type": "application/json"}

    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=30)
        elif method == "PATCH":
            response = requests.patch(url, headers=headers, json=data, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, timeout=30)
        else:
            return {"error": f"Unsupported method: {method}"}

        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def create_ticket_from_conversation(title: str, description: str, priority: str = "Medium", category: str = "General") -> dict:
    """Create a ticket via API."""
    data = {
        "title": title,
        "description": description,
        "priority": priority,
        "category": category,
    }
    return call_ticket_api("POST", "/tickets", data)


def get_ticket(ticket_id: str) -> dict:
    """Get ticket by ID."""
    return call_ticket_api("GET", f"/tickets/{ticket_id}")


def list_tickets(status: Optional[str] = None, limit: int = 10) -> dict:
    """List tickets with optional filters."""
    endpoint = f"/tickets?limit={limit}"
    if status:
        endpoint += f"&status={status}"
    return call_ticket_api("GET", endpoint)


def update_ticket(ticket_id: str, updates: dict) -> dict:
    """Update a ticket."""
    return call_ticket_api("PATCH", f"/tickets/{ticket_id}", updates)


def render_sidebar():
    """Render the sidebar with controls and information."""
    with st.sidebar:
        st.title("🎫 MSP Support")
        st.markdown("---")

        # Session info
        st.subheader("Session Info")
        st.text(f"Session: {st.session_state.session_id[:20]}...")
        st.text(f"Environment: {ENVIRONMENT}")

        st.markdown("---")

        # Quick actions
        st.subheader("Quick Actions")

        if st.button("📋 List Open Tickets", use_container_width=True):
            with st.spinner("Fetching tickets..."):
                result = list_tickets(status="Open")
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.session_state.tickets = result.get("tickets", [])
                    if st.session_state.tickets:
                        st.success(f"Found {len(st.session_state.tickets)} open tickets")
                    else:
                        st.info("No open tickets found")

        if st.button("🔄 Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

        st.markdown("---")

        # Recent tickets display
        if st.session_state.tickets:
            st.subheader("Recent Tickets")
            for ticket in st.session_state.tickets[:5]:
                with st.expander(f"🎫 {ticket.get('TicketId', 'N/A')[:15]}..."):
                    st.write(f"**Title:** {ticket.get('Title', 'N/A')}")
                    st.write(f"**Status:** {ticket.get('Status', 'N/A')}")
                    st.write(f"**Priority:** {ticket.get('Priority', 'N/A')}")

        st.markdown("---")

        # Model info
        st.subheader("Model Configuration")
        st.caption("Claude 3 Sonnet for complex queries")
        st.caption("Titan for simple questions")

        st.markdown("---")

        # Debug panel (collapsible)
        with st.expander("🔧 Debug Info"):
            st.text(f"API Endpoint: {API_GATEWAY_ENDPOINT or 'Not set'}")
            st.text(f"Region: {AWS_REGION}")
            st.text(f"Messages: {len(st.session_state.messages)}")


def render_chat():
    """Render the main chat interface."""
    st.title("🎫 MSP Support Assistant")
    st.markdown(
        "I'm your AI-powered support assistant. I can help you create, update, "
        "and manage support tickets through natural conversation."
    )

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("How can I help you today?"):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = invoke_bedrock_model(prompt)
                st.markdown(response)

        # Add assistant message
        st.session_state.messages.append({"role": "assistant", "content": response})


def render_ticket_form():
    """Render quick ticket creation form."""
    st.markdown("---")
    with st.expander("📝 Quick Ticket Form", expanded=False):
        with st.form("ticket_form"):
            col1, col2 = st.columns(2)

            with col1:
                title = st.text_input("Title", placeholder="Brief summary of the issue")
                priority = st.selectbox("Priority", ["Low", "Medium", "High", "Critical"])

            with col2:
                category = st.selectbox(
                    "Category",
                    ["General", "Network", "Hardware", "Software", "Security"],
                )

            description = st.text_area(
                "Description",
                placeholder="Detailed description of the issue...",
                height=100,
            )

            submitted = st.form_submit_button("Create Ticket", use_container_width=True)

            if submitted:
                if not title or not description:
                    st.error("Title and description are required")
                else:
                    with st.spinner("Creating ticket..."):
                        result = create_ticket_from_conversation(
                            title, description, priority, category
                        )
                        if "error" in result:
                            st.error(f"Failed to create ticket: {result['error']}")
                        else:
                            ticket = result.get("ticket", {})
                            st.success(
                                f"Ticket created successfully! ID: {ticket.get('TicketId', 'N/A')}"
                            )
                            # Add to chat
                            msg = f"I've created ticket **{ticket.get('TicketId')}** for you:\n- **Title:** {title}\n- **Priority:** {priority}\n- **Category:** {category}"
                            st.session_state.messages.append(
                                {"role": "assistant", "content": msg}
                            )


def main():
    """Main application entry point."""
    init_session_state()
    render_sidebar()
    render_chat()
    render_ticket_form()


if __name__ == "__main__":
    main()
