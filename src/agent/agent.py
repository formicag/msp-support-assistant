"""
MSP Support Agent - Main Agent Implementation

This module implements the core agent logic using a pattern compatible
with the Strands SDK and AWS Bedrock AgentCore.
"""

import json
import logging
from typing import Any, Generator, Optional

import boto3
from botocore.exceptions import ClientError

from .config import AgentConfig, SYSTEM_PROMPT
from .memory import MemoryManager
from .router import ModelRouter
from .tools import TicketTools, KnowledgeBaseTools, TOOL_SCHEMAS, ToolResult

logger = logging.getLogger(__name__)


class MSPSupportAgent:
    """
    MSP Support Agent powered by Bedrock and Strands patterns.

    This agent provides:
    - Natural language support ticket management
    - Dynamic model routing (Claude/Titan)
    - Short-term and long-term memory
    - RAG with knowledge base integration
    - Tool use for ticket operations
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize the MSP Support Agent.

        Args:
            config: Agent configuration (uses defaults if not provided)
        """
        self.config = config or AgentConfig()

        # Initialize AWS clients
        self.bedrock_runtime = boto3.client(
            "bedrock-runtime", region_name=self.config.aws_region
        )

        # Initialize components
        self.memory = MemoryManager(
            max_short_term_messages=self.config.short_term_memory_size,
            region=self.config.aws_region,
            memory_enabled=self.config.memory_enabled,
        )

        self.router = ModelRouter(
            claude_model_id=self.config.claude_model_id,
            titan_model_id=self.config.titan_model_id,
            region=self.config.aws_region,
        )

        self.ticket_tools = TicketTools(
            api_endpoint=self.config.api_gateway_endpoint,
            region=self.config.aws_region,
        )

        self.kb_tools = KnowledgeBaseTools(
            opensearch_endpoint=self.config.opensearch_endpoint,
            embedding_model_id=self.config.embedding_model_id,
            region=self.config.aws_region,
            index_name=self.config.opensearch_index,
        )

        # Session state
        self.session_id: Optional[str] = None

        logger.info(f"MSPSupportAgent initialized (environment: {self.config.environment})")

    def start_session(self, session_id: str, user_id: Optional[str] = None) -> None:
        """
        Start a new conversation session.

        Args:
            session_id: Unique session identifier
            user_id: Optional user identifier
        """
        self.session_id = session_id
        self.memory.set_session(session_id)
        if user_id:
            self.memory.short_term.set_metadata("user_id", user_id)
        logger.info(f"Session started: {session_id}")

    def end_session(self, generate_summary: bool = True) -> Optional[str]:
        """
        End the current session.

        Args:
            generate_summary: Whether to generate and store a session summary

        Returns:
            Session summary if generated
        """
        summary = None
        if generate_summary and len(self.memory.short_term.messages) > 2:
            summary = self._generate_session_summary()
            if summary:
                user_id = self.memory.short_term.get_metadata("user_id")
                self.memory.save_session_summary(summary, user_id)

        self.memory.clear_session()
        self.session_id = None
        logger.info("Session ended")
        return summary

    def _generate_session_summary(self) -> Optional[str]:
        """Generate a summary of the current session."""
        context = self.memory.short_term.get_context_string()
        if not context:
            return None

        prompt = f"""Summarize this support conversation in 2-3 sentences,
focusing on the main issue and resolution (if any):

{context}

Summary:"""

        try:
            # Use Titan for summarization (cost-effective)
            body = json.dumps(
                {
                    "inputText": prompt,
                    "textGenerationConfig": {
                        "maxTokenCount": 200,
                        "temperature": 0.3,
                    },
                }
            )

            response = self.bedrock_runtime.invoke_model(
                modelId=self.config.titan_model_id,
                body=body,
            )

            response_body = json.loads(response["body"].read())
            return response_body.get("results", [{}])[0].get("outputText", "").strip()

        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return None

    def _execute_tool(self, tool_name: str, tool_input: dict) -> ToolResult:
        """
        Execute a tool based on its name and input.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Tool input parameters

        Returns:
            ToolResult with execution result
        """
        logger.info(f"Executing tool: {tool_name}")

        try:
            if tool_name == "create_ticket":
                return self.ticket_tools.create_ticket(**tool_input)
            elif tool_name == "get_ticket":
                return self.ticket_tools.get_ticket(**tool_input)
            elif tool_name == "update_ticket":
                return self.ticket_tools.update_ticket(**tool_input)
            elif tool_name == "list_tickets":
                return self.ticket_tools.list_tickets(**tool_input)
            elif tool_name == "search_knowledge_base":
                return self.kb_tools.search_knowledge_base(**tool_input)
            else:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Unknown tool: {tool_name}",
                )
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return ToolResult(success=False, data=None, error=str(e))

    def _invoke_model(
        self,
        messages: list[dict],
        model_id: str,
        tools: Optional[list[dict]] = None,
    ) -> dict:
        """
        Invoke a Bedrock model.

        Args:
            messages: Conversation messages
            model_id: Model ID to use
            tools: Optional tool definitions

        Returns:
            Model response
        """
        # Build request body based on model type
        if "anthropic" in model_id.lower():
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2048,
                "system": SYSTEM_PROMPT,
                "messages": messages,
            }
            if tools:
                body["tools"] = tools

            # Add guardrails if configured
            if self.config.guardrail_id:
                body["amazon-bedrock-guardrailConfig"] = {
                    "guardrailIdentifier": self.config.guardrail_id,
                    "guardrailVersion": self.config.guardrail_version,
                }

        else:  # Titan or other models
            # Flatten messages to text prompt
            prompt_parts = [SYSTEM_PROMPT]
            for msg in messages:
                role = "User" if msg["role"] == "user" else "Assistant"
                content = msg["content"]
                if isinstance(content, list):
                    content = content[0].get("text", "")
                prompt_parts.append(f"{role}: {content}")

            body = {
                "inputText": "\n".join(prompt_parts) + "\nAssistant:",
                "textGenerationConfig": {
                    "maxTokenCount": 2048,
                    "temperature": 0.7,
                    "topP": 0.9,
                },
            }

        try:
            response = self.bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps(body),
            )

            response_body = json.loads(response["body"].read())

            # Parse response based on model
            if "anthropic" in model_id.lower():
                return response_body
            else:
                # Titan response format
                output_text = (
                    response_body.get("results", [{}])[0].get("outputText", "")
                )
                return {
                    "content": [{"type": "text", "text": output_text}],
                    "stop_reason": "end_turn",
                }

        except ClientError as e:
            logger.error(f"Model invocation error: {e}")
            raise

    def process_message(
        self,
        user_message: str,
        force_model: Optional[str] = None,
    ) -> str:
        """
        Process a user message and generate a response.

        Args:
            user_message: The user's input message
            force_model: Force a specific model ("claude" or "titan")

        Returns:
            Agent's response
        """
        # Add to memory
        self.memory.add_user_message(user_message)

        # Get conversation context
        context = self.memory.get_conversation_context()

        # Route to appropriate model
        model_id = self.router.get_model(
            user_message,
            context_length=len(context),
            force_model=force_model,
        )

        # Format messages for model
        messages = []
        for msg in context:
            messages.append(
                {
                    "role": msg["role"],
                    "content": [{"type": "text", "text": msg["content"]}],
                }
            )

        # Use tools only with Claude
        tools = TOOL_SCHEMAS if "claude" in model_id.lower() else None

        try:
            # Initial model call
            response = self._invoke_model(messages, model_id, tools)

            # Handle tool use (Claude only)
            while response.get("stop_reason") == "tool_use":
                tool_results = []

                for content_block in response.get("content", []):
                    if content_block.get("type") == "tool_use":
                        tool_name = content_block.get("name")
                        tool_input = content_block.get("input", {})
                        tool_use_id = content_block.get("id")

                        # Execute the tool
                        result = self._execute_tool(tool_name, tool_input)

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": json.dumps(
                                    {
                                        "success": result.success,
                                        "data": result.data,
                                        "error": result.error,
                                    }
                                ),
                            }
                        )

                # Add assistant response and tool results to messages
                messages.append({"role": "assistant", "content": response["content"]})
                messages.append({"role": "user", "content": tool_results})

                # Continue conversation
                response = self._invoke_model(messages, model_id, tools)

            # Extract final text response
            final_response = ""
            for content_block in response.get("content", []):
                if content_block.get("type") == "text":
                    final_response += content_block.get("text", "")

            # Add to memory
            self.memory.add_assistant_message(final_response)

            return final_response

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            error_response = f"I apologize, but I encountered an error: {str(e)}"
            self.memory.add_assistant_message(error_response)
            return error_response

    def process_message_stream(
        self,
        user_message: str,
        force_model: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """
        Process a user message with streaming response.

        Args:
            user_message: The user's input message
            force_model: Force a specific model

        Yields:
            Response chunks as they become available
        """
        # For streaming, we use Claude which supports streaming
        self.memory.add_user_message(user_message)
        context = self.memory.get_conversation_context()

        model_id = self.config.claude_model_id  # Always use Claude for streaming

        messages = []
        for msg in context:
            messages.append(
                {
                    "role": msg["role"],
                    "content": [{"type": "text", "text": msg["content"]}],
                }
            )

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "system": SYSTEM_PROMPT,
            "messages": messages,
        }

        try:
            response = self.bedrock_runtime.invoke_model_with_response_stream(
                modelId=model_id,
                body=json.dumps(body),
            )

            full_response = ""
            for event in response.get("body", []):
                chunk = json.loads(event.get("chunk", {}).get("bytes", b"{}"))
                if chunk.get("type") == "content_block_delta":
                    delta = chunk.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        full_response += text
                        yield text

            self.memory.add_assistant_message(full_response)

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            error_msg = f"Error: {str(e)}"
            self.memory.add_assistant_message(error_msg)
            yield error_msg

    def get_stats(self) -> dict:
        """Get agent statistics."""
        return {
            "session_id": self.session_id,
            "message_count": len(self.memory.short_term.messages),
            "routing_stats": self.router.get_routing_stats(),
            "environment": self.config.environment,
        }
