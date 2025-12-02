"""
MSP Support Assistant - Strands Agents SDK Implementation

A conversational interface for the MSP Support Ticket Assistant powered by
AWS Strands Agents SDK with Amazon Nova Pro and AgentCore Memory.

This app demonstrates the FULL AgentCore + Strands pattern:
- Strands Agent with @tool decorated Python functions
- AgentCoreMemorySessionManager for short-term and long-term memory
- BedrockModel for Amazon Nova Pro integration
- Automatic memory retrieval and storage via hooks

Key Features:
- Short-term Memory: Conversation history persisted across sessions
- Long-term Memory: Extracted facts, preferences, and summaries
- Agentic RAG: retrieve_memories tool for proactive memory search
- Model-driven orchestration with tool use

Usage:
    streamlit run strands_app.py
"""

import os
import time
from datetime import datetime
from typing import Optional

import boto3
import requests
import streamlit as st
from botocore.exceptions import ClientError

# Strands Agents SDK imports
try:
    from strands import Agent
    from strands.models import BedrockModel
    STRANDS_AVAILABLE = True
except ImportError:
    STRANDS_AVAILABLE = False
    Agent = None
    BedrockModel = None

# AgentCore Memory SDK imports
try:
    from bedrock_agentcore.memory.integrations.strands.config import (
        AgentCoreMemoryConfig,
        RetrievalConfig
    )
    from bedrock_agentcore.memory.integrations.strands.session_manager import (
        AgentCoreMemorySessionManager
    )
    AGENTCORE_SDK_AVAILABLE = True
except ImportError:
    AGENTCORE_SDK_AVAILABLE = False
    AgentCoreMemoryConfig = None
    RetrievalConfig = None
    AgentCoreMemorySessionManager = None

# Import our ticket management tools
try:
    from tools import TICKET_TOOLS, list_tickets, create_ticket, get_ticket, update_ticket, get_ticket_summary
    TOOLS_AVAILABLE = True
except ImportError:
    TOOLS_AVAILABLE = False
    TICKET_TOOLS = []

# Page configuration
st.set_page_config(
    page_title="MSP Support Assistant (Strands + AgentCore)",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load AWS credentials from Streamlit secrets (for Streamlit Cloud)
_credentials_loaded = []
try:
    if hasattr(st, 'secrets') and len(st.secrets) > 0:
        for key in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AWS_DEFAULT_REGION']:
            if key in st.secrets:
                value = st.secrets[key]
                if isinstance(value, str):
                    value = value.strip().strip('"').strip("'")
                os.environ[key] = value
                _credentials_loaded.append(key)
except Exception:
    pass

# Environment configuration
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", os.environ.get("AWS_REGION", "us-east-1"))
ENVIRONMENT = os.environ.get("ENVIRONMENT", "demo")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "msp-support-assistant")

# API Gateway endpoint
API_GATEWAY_ENDPOINT = os.environ.get(
    "API_GATEWAY_ENDPOINT",
    "https://p3h9ge8d92.execute-api.us-east-1.amazonaws.com"
)

# AgentCore Memory configuration
AGENTCORE_MEMORY_ID = os.environ.get(
    "AGENTCORE_MEMORY_ID",
    "msp_support_assistant_memory-NeCST586bk"
)
DEFAULT_ACTOR_ID = os.environ.get("DEFAULT_ACTOR_ID", "demo-user")

# Model configuration - Amazon Nova Pro
MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-pro-v1:0")


def get_system_prompt() -> str:
    """Get the system prompt for the Strands Agent."""
    return """You are an intelligent MSP (Managed Service Provider) Support Assistant with access to a ticket management system and memory capabilities.

## Available Tools

You have access to these ticket management tools:
1. **list_tickets**: List all tickets or filter by status (Open, In Progress, Resolved, Closed)
2. **create_ticket**: Create a new support ticket with title, description, priority, and category
3. **get_ticket**: Get details of a specific ticket by ID
4. **update_ticket**: Update a ticket's status, priority, or add notes
5. **get_ticket_summary**: Get an overview and statistics of all tickets
6. **retrieve_memories**: Search for specific memories about the user (agentic RAG)

## Memory Capabilities

You have MEMORY capabilities powered by AWS AgentCore Memory:
- **Short-term Memory**: Your conversation history is automatically saved and restored
- **Long-term Memory**: User preferences, facts, and session summaries are extracted and remembered
- **Agentic RAG**: Use retrieve_memories to proactively search for relevant information

When users tell you their name, preferences, or other personal information:
1. Acknowledge and remember it
2. Use this information to personalize responses
3. If unsure about something you should know, use retrieve_memories to search

## Guidelines

- Use get_ticket_summary for overview/analytics requests
- Use list_tickets to show ticket lists
- Use create_ticket when users report issues
- Use get_ticket for specific ticket lookups
- Use update_ticket to modify tickets
- Use retrieve_memories to search for specific user information

Always be helpful and professional. When presenting ticket data, format it clearly.
For summaries, include:
- Total ticket count
- Breakdown by status (Open, Closed, etc.)
- Breakdown by priority
- Recent activity

Personalize your responses based on what you know about the user from memory."""


def call_ticket_api(endpoint: str, method: str = "GET", data: Optional[dict] = None) -> dict:
    """Call the Ticket API directly (fallback when tools unavailable)."""
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


def init_session_state():
    """Initialize Streamlit session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"session-{int(time.time())}"
    if "actor_id" not in st.session_state:
        st.session_state.actor_id = DEFAULT_ACTOR_ID
    if "memory_enabled" not in st.session_state:
        st.session_state.memory_enabled = True
    if "tool_executions" not in st.session_state:
        st.session_state.tool_executions = []
    if "strands_agent" not in st.session_state:
        st.session_state.strands_agent = None
    if "session_manager" not in st.session_state:
        st.session_state.session_manager = None
    if "agent_errors" not in st.session_state:
        st.session_state.agent_errors = []


def create_session_manager(actor_id: str, session_id: str):
    """Create AgentCoreMemorySessionManager for the current session.

    This provides:
    - Automatic short-term memory (conversation history)
    - Automatic long-term memory retrieval via hooks
    - Memory extraction via strategies (preferences, facts, summaries)
    """
    if not AGENTCORE_SDK_AVAILABLE:
        return None

    try:
        # Configure memory with retrieval settings for each namespace
        config = AgentCoreMemoryConfig(
            memory_id=AGENTCORE_MEMORY_ID,
            session_id=session_id,
            actor_id=actor_id,
            # Configure retrieval for long-term memory namespaces
            retrieval_config={
                f"/preferences/{actor_id}": RetrievalConfig(
                    top_k=5,
                    relevance_score=0.7
                ),
                f"/facts/{actor_id}": RetrievalConfig(
                    top_k=10,
                    relevance_score=0.6
                ),
                f"/summaries/{actor_id}": RetrievalConfig(
                    top_k=3,
                    relevance_score=0.5
                )
            }
        )

        session_manager = AgentCoreMemorySessionManager(
            agentcore_memory_config=config,
            region_name=AWS_REGION
        )

        return session_manager

    except Exception as e:
        st.session_state.agent_errors.append(f"SessionManager: {str(e)}")
        return None


def create_strands_agent(actor_id: str, session_id: str):
    """Create a Strands Agent with BedrockModel and AgentCore Memory.

    This demonstrates the full Strands + AgentCore integration:
    1. BedrockModel for Amazon Nova Pro
    2. AgentCoreMemorySessionManager for memory
    3. @tool decorated functions for ticket management
    """
    if not STRANDS_AVAILABLE:
        return None

    try:
        # Create custom boto3 session (for profile support)
        boto_session = boto3.Session(region_name=AWS_REGION)

        # Create Bedrock model with Amazon Nova Pro
        bedrock_model = BedrockModel(
            model_id=MODEL_ID,
            boto_session=boto_session,
            temperature=0.3,
            streaming=True
        )

        # Create session manager for memory integration
        session_manager = None
        if st.session_state.get("memory_enabled", True) and AGENTCORE_SDK_AVAILABLE:
            session_manager = create_session_manager(actor_id, session_id)
            st.session_state.session_manager = session_manager

        # Create the Strands Agent
        agent_kwargs = {
            "model": bedrock_model,
            "system_prompt": get_system_prompt(),
            "tools": TICKET_TOOLS if TOOLS_AVAILABLE else [],
        }

        # Add session manager if available
        if session_manager:
            agent_kwargs["session_manager"] = session_manager

        agent = Agent(**agent_kwargs)

        return agent

    except Exception as e:
        st.session_state.agent_errors.append(f"Agent creation: {str(e)}")
        return None


def get_or_create_agent():
    """Get existing agent or create a new one."""
    actor_id = st.session_state.get("actor_id", DEFAULT_ACTOR_ID)
    session_id = st.session_state.get("session_id")

    # Check if we need to recreate agent (actor changed)
    current_agent = st.session_state.get("strands_agent")
    current_actor = st.session_state.get("current_agent_actor")

    if current_agent is None or current_actor != actor_id:
        st.session_state.strands_agent = create_strands_agent(actor_id, session_id)
        st.session_state.current_agent_actor = actor_id

    return st.session_state.strands_agent


def invoke_strands_agent(prompt: str) -> str:
    """Invoke the Strands Agent with a user prompt.

    The agent will:
    1. Automatically retrieve relevant memories (via session_manager hooks)
    2. Reason about which tools to use
    3. Execute tools and synthesize response
    4. Store conversation in short-term memory
    """
    agent = get_or_create_agent()

    if agent is None:
        # Fallback message when Strands is not available
        return """**Strands Agent Not Available**

The Strands Agents SDK is not installed or configured. To enable the full agent experience:

1. Install the required packages:
```bash
pip install strands-agents strands-agents-tools bedrock-agentcore
```

2. Ensure AWS credentials are configured

In the meantime, you can use the **Direct API Access** features in the sidebar."""

    try:
        # Invoke the agent - it handles tool execution automatically
        # The session_manager hooks will:
        # - Load conversation history (short-term memory)
        # - Retrieve relevant long-term memories
        # - Store new conversation events after response
        response = agent(prompt)

        # Track tool executions from the response
        # Strands agents return AgentResult with tool_use info
        if hasattr(response, 'tool_results'):
            for tool_result in response.tool_results:
                st.session_state.tool_executions.append({
                    "tool": tool_result.get("name", "unknown"),
                    "input": tool_result.get("input", {}),
                    "timestamp": datetime.now().isoformat()
                })

        # Extract text response
        if hasattr(response, 'message'):
            return str(response.message)
        return str(response)

    except Exception as e:
        error_msg = str(e)
        st.session_state.agent_errors.append(f"Invoke: {error_msg}")
        return f"I apologize, but I encountered an error: {error_msg}"


def render_sidebar():
    """Render the sidebar with controls and information."""
    with st.sidebar:
        st.title("🧠 Strands + AgentCore")
        st.markdown("---")

        # Session info
        st.subheader("Session Info")
        st.text(f"Session: {st.session_state.session_id[:20]}...")
        st.text(f"Environment: {ENVIRONMENT}")

        st.markdown("---")

        # SDK Status
        st.subheader("SDK Status")

        if STRANDS_AVAILABLE:
            st.success("Strands SDK: Available")
        else:
            st.error("Strands SDK: Not installed")
            st.caption("pip install strands-agents")

        if AGENTCORE_SDK_AVAILABLE:
            st.success("AgentCore SDK: Available")
        else:
            st.warning("AgentCore SDK: Not installed")
            st.caption("pip install bedrock-agentcore")

        if TOOLS_AVAILABLE:
            st.success(f"Tools: {len(TICKET_TOOLS)} loaded")
        else:
            st.warning("Tools: Not loaded")

        st.success("Ticket API: Available")
        st.caption(f"API: {API_GATEWAY_ENDPOINT[:35]}...")

        st.markdown("---")

        # Memory Settings
        st.subheader("Memory Settings")

        # Actor ID input
        new_actor_id = st.text_input(
            "Your Name/ID",
            value=st.session_state.get("actor_id", DEFAULT_ACTOR_ID),
            help="Enter your name or ID for personalized memory"
        )
        if new_actor_id != st.session_state.get("actor_id"):
            st.session_state.actor_id = new_actor_id
            st.session_state.strands_agent = None  # Force agent recreation
            st.session_state.session_manager = None

        # Memory toggle
        memory_enabled = st.checkbox(
            "Enable AgentCore Memory",
            value=st.session_state.get("memory_enabled", True),
            help="Enable short-term and long-term memory via AgentCore"
        )
        if memory_enabled != st.session_state.get("memory_enabled"):
            st.session_state.memory_enabled = memory_enabled
            st.session_state.strands_agent = None  # Force recreation

        # Memory info
        if st.session_state.get("session_manager"):
            st.caption("Memory ID: " + AGENTCORE_MEMORY_ID[:30] + "...")
            st.caption("Memory strategies: preferences, facts, summaries")
        else:
            st.caption("Memory not connected")

        st.markdown("---")

        # Tool Executions
        st.subheader("Tool Executions")
        if st.session_state.tool_executions:
            for i, execution in enumerate(st.session_state.tool_executions[-5:]):
                with st.expander(f"🔧 {execution['tool']}", expanded=False):
                    st.json(execution["input"])
        else:
            st.caption("No tools executed yet")

        # Errors
        if st.session_state.agent_errors:
            with st.expander("⚠️ Agent Errors", expanded=False):
                for err in st.session_state.agent_errors[-3:]:
                    st.caption(err)

        st.markdown("---")

        # Quick Actions
        st.subheader("Quick Actions")

        if st.button("📊 Get Summary", use_container_width=True):
            st.session_state.pending_action = "Get ticket summary"

        if st.button("📋 List Tickets", use_container_width=True):
            st.session_state.pending_action = "Show all tickets"

        if st.button("🔄 Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.tool_executions = []
            st.session_state.agent_errors = []
            st.rerun()

        if st.button("🔁 Reset Agent", use_container_width=True):
            st.session_state.strands_agent = None
            st.session_state.session_manager = None
            st.session_state.session_id = f"session-{int(time.time())}"
            st.rerun()

        st.markdown("---")

        # Direct API Access
        st.subheader("Direct API Access")
        st.caption("Works without Strands SDK")

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
**Strands + AgentCore Pattern:**

1. **Strands Agent**
   - Model: Amazon Nova Pro
   - @tool decorated Python functions
   - Automatic tool orchestration

2. **AgentCore Memory**
   - Short-term: Conversation events
   - Long-term: Strategies extract:
     - User preferences
     - Semantic facts
     - Session summaries

3. **Memory Hooks**
   - ShortMemoryHook: Load/save history
   - LongTermMemoryHook: Retrieve memories

4. **Agentic RAG**
   - retrieve_memories tool
   - Proactive memory search
            """)


def render_chat():
    """Render the main chat interface."""
    st.title("🧠 MSP Support Assistant")
    st.markdown(
        "I'm your AI-powered support assistant with **Strands Agent** orchestration "
        "and **AgentCore Memory** for personalized, context-aware conversations."
    )

    # SDK status banner
    if not STRANDS_AVAILABLE:
        st.warning("Strands SDK not installed. Install with: `pip install strands-agents`")
    elif not AGENTCORE_SDK_AVAILABLE:
        st.info("AgentCore SDK not installed. Memory features limited.")

    # Example prompts
    st.markdown("**Try asking:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📊 Overview of tickets", use_container_width=True):
            st.session_state.pending_action = "Give me an overview of all tickets"
    with col2:
        if st.button("🧠 What do you remember?", use_container_width=True):
            st.session_state.pending_action = "What do you remember about me from our previous conversations?"
    with col3:
        if st.button("🆕 Create ticket", use_container_width=True):
            st.session_state.pending_action = "I need to report a VPN connection issue that started this morning"

    st.markdown("---")

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Handle pending action from buttons
    if hasattr(st.session_state, "pending_action") and st.session_state.pending_action:
        prompt = st.session_state.pending_action
        st.session_state.pending_action = None

        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking with Strands Agent..."):
                response = invoke_strands_agent(prompt)
                st.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

    # Chat input
    if prompt := st.chat_input("How can I help you today?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking with Strands Agent..."):
                response = invoke_strands_agent(prompt)
                st.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response})


def main():
    """Main application entry point."""
    init_session_state()
    render_sidebar()
    render_chat()


if __name__ == "__main__":
    main()
