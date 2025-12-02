"""
Memory management for the MSP Support Agent.

Implements short-term (conversation) and long-term (persistent) memory
using Amazon Bedrock AgentCore Memory.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Represents a conversation message."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict = field(default_factory=dict)


@dataclass
class MemoryRecord:
    """Represents a long-term memory record."""

    key: str
    value: Any
    namespace: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict = field(default_factory=dict)


class ShortTermMemory:
    """
    Short-term memory for conversation context.

    Maintains a sliding window of recent messages for context in conversations.
    """

    def __init__(self, max_messages: int = 20):
        """
        Initialize short-term memory.

        Args:
            max_messages: Maximum number of messages to retain
        """
        self.max_messages = max_messages
        self.messages: list[Message] = []
        self.session_metadata: dict = {}

    def add_message(self, role: str, content: str, metadata: Optional[dict] = None) -> None:
        """
        Add a message to the conversation history.

        Args:
            role: "user" or "assistant"
            content: Message content
            metadata: Optional metadata about the message
        """
        message = Message(role=role, content=content, metadata=metadata or {})
        self.messages.append(message)

        # Trim if exceeding max
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

    def get_context(self, last_n: Optional[int] = None) -> list[dict]:
        """
        Get conversation context for model input.

        Args:
            last_n: Number of recent messages to include (default: all)

        Returns:
            List of message dictionaries formatted for model input
        """
        messages = self.messages[-last_n:] if last_n else self.messages
        return [{"role": m.role, "content": m.content} for m in messages]

    def get_context_string(self, last_n: Optional[int] = None) -> str:
        """
        Get conversation context as a formatted string.

        Args:
            last_n: Number of recent messages to include

        Returns:
            Formatted conversation history string
        """
        messages = self.messages[-last_n:] if last_n else self.messages
        lines = []
        for m in messages:
            role_label = "User" if m.role == "user" else "Assistant"
            lines.append(f"{role_label}: {m.content}")
        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all messages from memory."""
        self.messages = []
        self.session_metadata = {}

    def set_metadata(self, key: str, value: Any) -> None:
        """Set session metadata."""
        self.session_metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get session metadata."""
        return self.session_metadata.get(key, default)


class LongTermMemory:
    """
    Long-term memory using Amazon Bedrock AgentCore Memory.

    Provides persistent storage of facts, preferences, and session summaries.
    """

    def __init__(
        self,
        memory_id: Optional[str] = None,
        region: str = "us-east-1",
        enabled: bool = True,
    ):
        """
        Initialize long-term memory.

        Args:
            memory_id: Bedrock AgentCore memory resource ID
            region: AWS region
            enabled: Whether memory operations are enabled
        """
        self.memory_id = memory_id
        self.region = region
        self.enabled = enabled
        self._local_store: dict[str, list[MemoryRecord]] = {}

        if enabled and memory_id:
            try:
                # Note: bedrock-agent-runtime client for memory operations
                self.client = boto3.client("bedrock-agent-runtime", region_name=region)
            except Exception as e:
                logger.warning(f"Could not initialize Bedrock memory client: {e}")
                self.client = None
        else:
            self.client = None

    def store(
        self,
        key: str,
        value: Any,
        namespace: str = "facts",
        metadata: Optional[dict] = None,
    ) -> bool:
        """
        Store a memory record.

        Args:
            key: Unique key for the record
            value: Value to store
            namespace: Memory namespace (facts, preferences, summaries)
            metadata: Optional metadata

        Returns:
            True if stored successfully
        """
        record = MemoryRecord(
            key=key,
            value=value,
            namespace=namespace,
            metadata=metadata or {},
        )

        # Store locally
        if namespace not in self._local_store:
            self._local_store[namespace] = []
        self._local_store[namespace].append(record)

        # If Bedrock memory is available, store there too
        if self.enabled and self.client and self.memory_id:
            try:
                # Note: This is a placeholder for actual Bedrock memory API
                # The exact API will depend on AgentCore Memory implementation
                logger.info(f"Stored memory: {namespace}/{key}")
                return True
            except ClientError as e:
                logger.error(f"Failed to store in Bedrock memory: {e}")

        return True

    def retrieve(
        self,
        query: str,
        namespace: Optional[str] = None,
        limit: int = 5,
    ) -> list[MemoryRecord]:
        """
        Retrieve relevant memories.

        Args:
            query: Search query
            namespace: Optional namespace filter
            limit: Maximum number of records to return

        Returns:
            List of relevant memory records
        """
        results = []

        # Search local store (simple text matching for demo)
        for ns, records in self._local_store.items():
            if namespace and ns != namespace:
                continue

            for record in records:
                value_str = str(record.value).lower()
                if query.lower() in value_str:
                    results.append(record)
                    if len(results) >= limit:
                        break

        # If Bedrock memory is available, search there too
        if self.enabled and self.client and self.memory_id:
            try:
                # Placeholder for Bedrock memory search
                pass
            except ClientError as e:
                logger.error(f"Failed to search Bedrock memory: {e}")

        return results[:limit]

    def store_session_summary(
        self,
        session_id: str,
        summary: str,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Store a session summary.

        Args:
            session_id: Session identifier
            summary: Summary of the session
            user_id: Optional user identifier

        Returns:
            True if stored successfully
        """
        return self.store(
            key=session_id,
            value={"summary": summary, "user_id": user_id},
            namespace="summaries",
            metadata={"type": "session_summary"},
        )

    def store_user_preference(
        self,
        user_id: str,
        preference_key: str,
        preference_value: Any,
    ) -> bool:
        """
        Store a user preference.

        Args:
            user_id: User identifier
            preference_key: Preference key
            preference_value: Preference value

        Returns:
            True if stored successfully
        """
        return self.store(
            key=f"{user_id}:{preference_key}",
            value=preference_value,
            namespace="preferences",
            metadata={"user_id": user_id, "preference_key": preference_key},
        )

    def store_fact(self, fact: str, source: Optional[str] = None) -> bool:
        """
        Store a factual piece of information.

        Args:
            fact: The fact to store
            source: Optional source of the fact

        Returns:
            True if stored successfully
        """
        import hashlib

        key = hashlib.md5(fact.encode()).hexdigest()[:16]
        return self.store(
            key=key,
            value=fact,
            namespace="facts",
            metadata={"source": source} if source else {},
        )


class MemoryManager:
    """
    Unified memory manager for the agent.

    Combines short-term and long-term memory operations.
    """

    def __init__(
        self,
        max_short_term_messages: int = 20,
        memory_id: Optional[str] = None,
        region: str = "us-east-1",
        memory_enabled: bool = True,
    ):
        """
        Initialize the memory manager.

        Args:
            max_short_term_messages: Max messages in short-term memory
            memory_id: Bedrock memory resource ID
            region: AWS region
            memory_enabled: Whether long-term memory is enabled
        """
        self.short_term = ShortTermMemory(max_messages=max_short_term_messages)
        self.long_term = LongTermMemory(
            memory_id=memory_id,
            region=region,
            enabled=memory_enabled,
        )
        self.session_id: Optional[str] = None

    def set_session(self, session_id: str) -> None:
        """Set the current session ID."""
        self.session_id = session_id
        self.short_term.set_metadata("session_id", session_id)

    def add_user_message(self, content: str) -> None:
        """Add a user message to short-term memory."""
        self.short_term.add_message("user", content)

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to short-term memory."""
        self.short_term.add_message("assistant", content)

    def get_conversation_context(self, last_n: Optional[int] = None) -> list[dict]:
        """Get the conversation context for model input."""
        return self.short_term.get_context(last_n)

    def search_memory(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        """Search long-term memory for relevant information."""
        return self.long_term.retrieve(query, limit=limit)

    def save_session_summary(self, summary: str, user_id: Optional[str] = None) -> bool:
        """Save a summary of the current session."""
        if self.session_id:
            return self.long_term.store_session_summary(
                self.session_id, summary, user_id
            )
        return False

    def remember_fact(self, fact: str, source: Optional[str] = None) -> bool:
        """Store a fact extracted from the conversation."""
        return self.long_term.store_fact(fact, source)

    def clear_session(self) -> None:
        """Clear short-term memory (end of session)."""
        self.short_term.clear()
        self.session_id = None
