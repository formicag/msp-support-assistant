"""
MSP Support Assistant - Streamlit Frontend

A conversational interface for the MSP Support Ticket Assistant powered by
AWS Bedrock AgentCore with Strands SDK.
"""

import os

import requests
import streamlit as st
from typing import Optional

# Page configuration
st.set_page_config(
    page_title="MSP Support Assistant",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Environment configuration
API_GATEWAY_ENDPOINT = os.environ.get("API_GATEWAY_ENDPOINT", "https://p3h9ge8d92.execute-api.us-east-1.amazonaws.com")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "demo")


def init_session_state():
    """Initialize Streamlit session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "tickets" not in st.session_state:
        st.session_state.tickets = []


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


def create_ticket(title: str, description: str, priority: str = "Medium", category: str = "General") -> dict:
    """Create a ticket via API."""
    data = {
        "title": title,
        "description": description,
        "priority": priority,
        "category": category,
    }
    return call_ticket_api("POST", "/tickets", data)


def list_tickets(status: Optional[str] = None, limit: int = 10) -> dict:
    """List tickets with optional filters."""
    endpoint = f"/tickets?limit={limit}"
    if status:
        endpoint += f"&status={status}"
    return call_ticket_api("GET", endpoint)


def render_sidebar():
    """Render the sidebar with controls and information."""
    with st.sidebar:
        st.title("🎫 MSP Support")
        st.markdown("---")

        st.subheader("Session Info")
        st.text(f"Environment: {ENVIRONMENT}")

        st.markdown("---")

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

        if st.button("📋 List All Tickets", use_container_width=True):
            with st.spinner("Fetching tickets..."):
                result = list_tickets()
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.session_state.tickets = result.get("tickets", [])
                    if st.session_state.tickets:
                        st.success(f"Found {len(st.session_state.tickets)} tickets")
                    else:
                        st.info("No tickets found")

        st.markdown("---")

        if st.session_state.tickets:
            st.subheader("Recent Tickets")
            for ticket in st.session_state.tickets[:5]:
                with st.expander(f"🎫 {ticket.get('TicketId', 'N/A')[:15]}..."):
                    st.write(f"**Title:** {ticket.get('Title', 'N/A')}")
                    st.write(f"**Status:** {ticket.get('Status', 'N/A')}")
                    st.write(f"**Priority:** {ticket.get('Priority', 'N/A')}")

        st.markdown("---")
        with st.expander("🔧 Debug Info"):
            st.text(f"API: {API_GATEWAY_ENDPOINT or 'Not set'}")


def render_main():
    """Render the main content area."""
    st.title("🎫 MSP Support Assistant")
    st.markdown(
        "Create and manage support tickets for your MSP operations."
    )

    st.markdown("---")

    # Ticket Creation Form
    st.subheader("📝 Create New Ticket")

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
                    result = create_ticket(title, description, priority, category)
                    if "error" in result:
                        st.error(f"Failed to create ticket: {result['error']}")
                    else:
                        ticket = result.get("ticket", {})
                        st.success(f"Ticket created! ID: {ticket.get('TicketId', 'N/A')}")

    # Display tickets table
    st.markdown("---")
    st.subheader("📋 Tickets")

    if st.session_state.tickets:
        for ticket in st.session_state.tickets:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                with col1:
                    st.write(f"**{ticket.get('Title', 'N/A')}**")
                with col2:
                    st.write(ticket.get('TicketId', 'N/A')[:20])
                with col3:
                    status = ticket.get('Status', 'N/A')
                    if status == "Open":
                        st.write("🟢 Open")
                    elif status == "In Progress":
                        st.write("🟡 In Progress")
                    elif status == "Resolved":
                        st.write("🟣 Resolved")
                    else:
                        st.write(status)
                with col4:
                    priority = ticket.get('Priority', 'N/A')
                    if priority == "Critical":
                        st.write("🔴 Critical")
                    elif priority == "High":
                        st.write("🟠 High")
                    elif priority == "Medium":
                        st.write("🟡 Medium")
                    else:
                        st.write("🟢 Low")
                st.markdown("---")
    else:
        st.info("Click 'List All Tickets' in the sidebar to load tickets.")


def main():
    """Main application entry point."""
    init_session_state()
    render_sidebar()
    render_main()


if __name__ == "__main__":
    main()
