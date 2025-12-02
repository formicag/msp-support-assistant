"""
MSP Support Assistant - AgentCore Streamlit Frontend

A conversational interface for the MSP Support Ticket Assistant powered by
AWS Bedrock with Amazon Nova Pro.

This app demonstrates the AgentCore best practice pattern:
- User sends natural language request
- Amazon Nova Pro processes the request with tool use
- Agent calls tools via API Gateway
- Agent returns summarized response

Usage:
    streamlit run app.py
"""

import json
import os
import time
from typing import Optional

import boto3
import requests
import streamlit as st
from botocore.exceptions import ClientError

# Page configuration
st.set_page_config(
    page_title="MSP Support Assistant (AgentCore)",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load AWS credentials from Streamlit secrets (for Streamlit Cloud)
# This sets environment variables that boto3 will use
if hasattr(st, 'secrets'):
    for key in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AWS_DEFAULT_REGION']:
        if key in st.secrets:
            os.environ[key] = st.secrets[key]

# Environment configuration
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", os.environ.get("AWS_REGION", "us-east-1"))
ENVIRONMENT = os.environ.get("ENVIRONMENT", "demo")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "msp-support-assistant")

# AgentCore Gateway configuration (loaded from SSM or environment)
MCP_ENDPOINT = os.environ.get("MCP_ENDPOINT", "")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")
COGNITO_CLIENT_SECRET = os.environ.get("COGNITO_CLIENT_SECRET", "")
COGNITO_TOKEN_ENDPOINT = os.environ.get("COGNITO_TOKEN_ENDPOINT", "")

# API Gateway endpoint (fallback for direct API access)
API_GATEWAY_ENDPOINT = os.environ.get(
    "API_GATEWAY_ENDPOINT",
    "https://p3h9ge8d92.execute-api.us-east-1.amazonaws.com"
)


def load_config_from_ssm():
    """Load AgentCore Gateway configuration from SSM Parameter Store.

    Returns empty config if AWS credentials are not available (e.g., Streamlit Cloud).
    """
    # Skip SSM if we detect we're on Streamlit Cloud without credentials
    # or if environment variables are already set
    if MCP_ENDPOINT or COGNITO_CLIENT_ID:
        return {
            "mcp_endpoint": MCP_ENDPOINT,
            "cognito_client_id": COGNITO_CLIENT_ID,
        }

    try:
        ssm = boto3.client("ssm", region_name=AWS_REGION)

        config = {}
        params = [
            ("agentcore-mcp-endpoint", "mcp_endpoint"),
            ("cognito-client-id", "cognito_client_id"),
            ("cognito-discovery-url", "cognito_discovery_url"),
        ]

        for param_name, config_key in params:
            try:
                response = ssm.get_parameter(
                    Name=f"/{PROJECT_NAME}/{ENVIRONMENT}/{param_name}"
                )
                config[config_key] = response["Parameter"]["Value"]
            except ClientError:
                pass

        return config
    except Exception:
        # No AWS credentials available - this is fine for Streamlit Cloud
        # The app will work with direct API calls
        return {}


def get_bedrock_client():
    """Get or create Bedrock runtime client (lazy initialization)."""
    if "bedrock_client" not in st.session_state:
        st.session_state.bedrock_client = None
        try:
            client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
            # Test if credentials are available by checking caller identity
            sts = boto3.client("sts", region_name=AWS_REGION)
            sts.get_caller_identity()
            st.session_state.bedrock_client = client
        except Exception:
            # No AWS credentials - Bedrock won't work, but API calls will
            st.session_state.bedrock_client = None
    return st.session_state.bedrock_client


def init_session_state():
    """Initialize Streamlit session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"session-{int(time.time())}"
    if "config" not in st.session_state:
        st.session_state.config = load_config_from_ssm()
    if "tool_results" not in st.session_state:
        st.session_state.tool_results = []


def get_cognito_token() -> Optional[str]:
    """Get access token from Cognito using client credentials flow."""
    if not COGNITO_TOKEN_ENDPOINT or not COGNITO_CLIENT_ID or not COGNITO_CLIENT_SECRET:
        return None

    try:
        response = requests.post(
            COGNITO_TOKEN_ENDPOINT,
            data={
                "grant_type": "client_credentials",
                "client_id": COGNITO_CLIENT_ID,
                "client_secret": COGNITO_CLIENT_SECRET,
                "scope": "agentcore-gateway/tools agentcore-gateway/invoke"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10
        )
        response.raise_for_status()
        return response.json().get("access_token")
    except Exception as e:
        st.warning(f"Failed to get Cognito token: {e}")
        return None


def get_system_prompt() -> str:
    """Get the system prompt for the agent."""
    return """You are an intelligent MSP (Managed Service Provider) Support Assistant with access to a ticket management system.

You have access to the following tools:
1. **list_tickets**: List all tickets or filter by status (Open, In Progress, Resolved, Closed)
2. **create_ticket**: Create a new support ticket with title, description, priority, and category
3. **get_ticket**: Get details of a specific ticket by ID
4. **update_ticket**: Update a ticket's status, priority, or add notes
5. **get_ticket_summary**: Get an overview and statistics of all tickets

When users ask about tickets:
- Use get_ticket_summary for overview/analytics requests
- Use list_tickets to show ticket lists
- Use create_ticket when users report issues
- Use get_ticket for specific ticket lookups
- Use update_ticket to modify tickets

Always be helpful and professional. When presenting ticket data, format it clearly.
For summaries, include:
- Total ticket count
- Breakdown by status (Open, Closed, etc.)
- Breakdown by priority
- Recent activity (tickets in last 24 hours)

If you can't access the tools, explain what you would do and suggest the user check the AgentCore Gateway configuration."""


def call_ticket_api(endpoint: str, method: str = "GET", data: Optional[dict] = None) -> dict:
    """Call the Ticket API directly (fallback when AgentCore not available)."""
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


# Tool definitions for Bedrock Converse API (Amazon Nova Pro)
TOOLS = [
    {
        "toolSpec": {
            "name": "list_tickets",
            "description": "List support tickets with optional filters. Use this to show all tickets or filter by status.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["Open", "In Progress", "Resolved", "Closed"],
                            "description": "Filter tickets by status"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of tickets to return"
                        }
                    }
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "create_ticket",
            "description": "Create a new support ticket in the system. Use when a user reports an issue.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Brief summary of the issue"
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed description of the problem"
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["Low", "Medium", "High", "Critical"],
                            "description": "Ticket priority level"
                        },
                        "category": {
                            "type": "string",
                            "enum": ["Network", "Hardware", "Software", "Security", "General"],
                            "description": "Issue category"
                        }
                    },
                    "required": ["title", "description"]
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "get_ticket",
            "description": "Retrieve details of a specific ticket by its ID.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "ticket_id": {
                            "type": "string",
                            "description": "The unique ticket identifier"
                        }
                    },
                    "required": ["ticket_id"]
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "update_ticket",
            "description": "Update an existing ticket's status, priority, or add notes.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "ticket_id": {
                            "type": "string",
                            "description": "The ticket ID to update"
                        },
                        "status": {
                            "type": "string",
                            "enum": ["Open", "In Progress", "Resolved", "Closed"],
                            "description": "New ticket status"
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["Low", "Medium", "High", "Critical"],
                            "description": "New priority level"
                        },
                        "note": {
                            "type": "string",
                            "description": "Note to add to the ticket"
                        }
                    },
                    "required": ["ticket_id"]
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "get_ticket_summary",
            "description": "Get a summary and overview of all tickets including counts by status, priority, and recent activity.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {}
                }
            }
        }
    }
]


def execute_tool(tool_name: str, tool_input: dict) -> dict:
    """Execute a tool call via the API Gateway."""
    if tool_name == "list_tickets":
        endpoint = "/tickets"
        params = []
        if tool_input.get("status"):
            params.append(f"status={tool_input['status']}")
        if tool_input.get("limit"):
            params.append(f"limit={tool_input['limit']}")
        if params:
            endpoint += "?" + "&".join(params)
        return call_ticket_api(endpoint)

    elif tool_name == "create_ticket":
        return call_ticket_api("/tickets", method="POST", data=tool_input)

    elif tool_name == "get_ticket":
        ticket_id = tool_input.get("ticket_id")
        return call_ticket_api(f"/tickets/{ticket_id}")

    elif tool_name == "update_ticket":
        ticket_id = tool_input.pop("ticket_id", None)
        if not ticket_id:
            return {"error": "ticket_id is required"}
        return call_ticket_api(f"/tickets/{ticket_id}", method="PATCH", data=tool_input)

    elif tool_name == "get_ticket_summary":
        # Get all tickets and compute summary
        result = call_ticket_api("/tickets?limit=100")
        if "error" in result:
            return result

        tickets = result.get("tickets", [])
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

        return {"success": True, "summary": summary, "tickets": tickets}

    else:
        return {"error": f"Unknown tool: {tool_name}"}


def invoke_agent(prompt: str, model_id: str = "us.amazon.nova-pro-v1:0") -> str:
    """Invoke the agent with tool use capability using Bedrock Converse API."""
    try:
        bedrock_client = get_bedrock_client()
        if bedrock_client is None:
            # No AWS credentials - show helpful message with setup instructions
            return """**AWS Credentials Required**

To enable the AI agent, you need to configure AWS credentials in Streamlit Cloud:

1. Go to **Settings > Secrets** in your Streamlit Cloud app
2. Add the following secrets in TOML format:

```toml
AWS_ACCESS_KEY_ID = "your-access-key"
AWS_SECRET_ACCESS_KEY = "your-secret-key"
AWS_SESSION_TOKEN = "your-session-token"
AWS_DEFAULT_REGION = "us-east-1"
```

In the meantime, you can still:
- Use the **Quick Ticket Form** in the sidebar to create tickets
- Click **List Tickets** to view existing tickets via the API

The ticket API works without AWS credentials since it uses the public API Gateway endpoint."""

        # Build conversation history for Converse API
        messages = []
        for msg in st.session_state.messages[-10:]:
            messages.append({
                "role": msg["role"],
                "content": [{"text": msg["content"]}]
            })

        # Add current message
        messages.append({
            "role": "user",
            "content": [{"text": prompt}]
        })

        # First call with tools using Converse API
        response = bedrock_client.converse(
            modelId=model_id,
            messages=messages,
            system=[{"text": get_system_prompt()}],
            toolConfig={"tools": TOOLS},
            inferenceConfig={"maxTokens": 4096}
        )

        # Handle tool use loop
        while response.get("stopReason") == "tool_use":
            tool_results = []
            assistant_content = response["output"]["message"]["content"]

            # Process each tool use block
            for content_block in assistant_content:
                if "toolUse" in content_block:
                    tool_use = content_block["toolUse"]
                    tool_name = tool_use["name"]
                    tool_input = tool_use.get("input", {})
                    tool_use_id = tool_use["toolUseId"]

                    # Show tool execution in sidebar
                    st.session_state.tool_results.append({
                        "tool": tool_name,
                        "input": tool_input
                    })

                    # Execute the tool
                    result = execute_tool(tool_name, tool_input)

                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tool_use_id,
                            "content": [{"json": result}]
                        }
                    })

            # Add assistant response and tool results to messages
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

            # Continue conversation
            response = bedrock_client.converse(
                modelId=model_id,
                messages=messages,
                system=[{"text": get_system_prompt()}],
                toolConfig={"tools": TOOLS},
                inferenceConfig={"maxTokens": 4096}
            )

        # Extract final text response
        final_response = ""
        for content_block in response.get("output", {}).get("message", {}).get("content", []):
            if "text" in content_block:
                final_response += content_block["text"]

        # Clean up any thinking tags that Nova sometimes includes
        if "<thinking>" in final_response:
            # Remove thinking tags content
            import re
            final_response = re.sub(r'<thinking>.*?</thinking>\s*', '', final_response, flags=re.DOTALL)

        return final_response.strip()

    except ClientError as e:
        error_msg = f"Error invoking Bedrock: {e.response['Error']['Message']}"
        st.error(error_msg)
        return f"I apologize, but I encountered an error: {error_msg}"
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return f"I apologize, but I encountered an unexpected error: {str(e)}"


def render_sidebar():
    """Render the sidebar with controls and information."""
    with st.sidebar:
        st.title("🤖 AgentCore Demo")
        st.markdown("---")

        # Session info
        st.subheader("Session Info")
        st.text(f"Session: {st.session_state.session_id[:20]}...")
        st.text(f"Environment: {ENVIRONMENT}")

        st.markdown("---")

        # AgentCore status
        st.subheader("Status")

        # Check Bedrock availability
        bedrock_available = get_bedrock_client() is not None
        if bedrock_available:
            st.success("AI Agent: Available")
        else:
            st.warning("AI Agent: No credentials")
            st.caption("Configure AWS secrets to enable")

        st.success("Ticket API: Available")
        st.caption(f"API: {API_GATEWAY_ENDPOINT[:35]}...")

        st.markdown("---")

        # Tool execution log
        st.subheader("Tool Executions")
        if st.session_state.tool_results:
            for i, result in enumerate(st.session_state.tool_results[-5:]):
                with st.expander(f"🔧 {result['tool']}", expanded=False):
                    st.json(result["input"])
        else:
            st.caption("No tools executed yet")

        st.markdown("---")

        # Quick actions
        st.subheader("Quick Actions")

        if st.button("📊 Get Summary", use_container_width=True):
            st.session_state.pending_action = "Get ticket summary"

        if st.button("📋 List Tickets", use_container_width=True):
            st.session_state.pending_action = "Show all tickets"

        if st.button("🔄 Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.tool_results = []
            st.rerun()

        st.markdown("---")

        # Direct API access (works without Bedrock)
        st.subheader("Direct API Access")
        st.caption("Works without AWS credentials")

        if st.button("📋 View Tickets (API)", use_container_width=True):
            with st.spinner("Fetching tickets..."):
                result = call_ticket_api("/tickets?limit=10")
                if "error" not in result:
                    tickets = result.get("tickets", [])
                    if tickets:
                        for t in tickets[:5]:
                            st.markdown(f"**{t.get('TicketId', 'N/A')[:20]}**")
                            st.caption(f"{t.get('Title', 'N/A')} - {t.get('Status', 'N/A')}")
                    else:
                        st.info("No tickets found")
                else:
                    st.error(result["error"])

        # Quick ticket form
        with st.expander("➕ Create Ticket"):
            with st.form("quick_ticket"):
                title = st.text_input("Title")
                description = st.text_area("Description", height=80)
                priority = st.selectbox("Priority", ["Low", "Medium", "High", "Critical"])
                category = st.selectbox("Category", ["General", "Network", "Hardware", "Software", "Security"])

                if st.form_submit_button("Create", use_container_width=True):
                    if title and description:
                        result = call_ticket_api("/tickets", "POST", {
                            "title": title,
                            "description": description,
                            "priority": priority,
                            "category": category
                        })
                        if "error" not in result:
                            ticket = result.get("ticket", {})
                            st.success(f"Created: {ticket.get('TicketId', 'OK')}")
                        else:
                            st.error(result["error"])
                    else:
                        st.warning("Title and description required")

        st.markdown("---")

        # Architecture info
        with st.expander("ℹ️ Architecture"):
            st.markdown("""
            **AgentCore Pattern:**
            1. User sends message
            2. Amazon Nova Pro analyzes request
            3. Nova Pro calls tools via API
            4. Nova Pro summarizes response

            **Tools Available:**
            - `list_tickets`
            - `create_ticket`
            - `get_ticket`
            - `update_ticket`
            - `get_ticket_summary`
            """)


def render_chat():
    """Render the main chat interface."""
    st.title("🤖 MSP Support Assistant")
    st.markdown(
        "I'm your AI-powered support assistant with access to the ticket management system. "
        "Ask me about tickets, request summaries, or describe issues to create new tickets."
    )

    # Example prompts
    st.markdown("**Try asking:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📊 Overview of tickets", use_container_width=True):
            st.session_state.pending_action = "Give me an overview of all tickets"
    with col2:
        if st.button("📋 Show open tickets", use_container_width=True):
            st.session_state.pending_action = "Show me all open tickets"
    with col3:
        if st.button("🆕 Create ticket", use_container_width=True):
            st.session_state.pending_action = "I need to report a VPN connection issue"

    st.markdown("---")

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Handle pending action from buttons
    if hasattr(st.session_state, "pending_action") and st.session_state.pending_action:
        prompt = st.session_state.pending_action
        st.session_state.pending_action = None

        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = invoke_agent(prompt)
                st.markdown(response)

        # Add assistant message
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

    # Chat input
    if prompt := st.chat_input("How can I help you today?"):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = invoke_agent(prompt)
                st.markdown(response)

        # Add assistant message
        st.session_state.messages.append({"role": "assistant", "content": response})


def main():
    """Main application entry point."""
    init_session_state()
    render_sidebar()
    render_chat()


if __name__ == "__main__":
    main()
