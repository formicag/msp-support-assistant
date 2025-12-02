"""
Unit tests for the MSP Support Agent.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "agent"))


class TestModelRouter:
    """Tests for the model router."""

    def test_classifies_simple_query(self):
        from router import ModelRouter, QueryComplexity

        router = ModelRouter()

        result = router.classify_query("What is the status of ticket 123?")

        assert result == QueryComplexity.SIMPLE

    def test_classifies_complex_query(self):
        from router import ModelRouter, QueryComplexity

        router = ModelRouter()

        result = router.classify_query(
            "Can you analyze the root cause of the recurring VPN issues "
            "and provide a detailed troubleshooting plan?"
        )

        assert result == QueryComplexity.COMPLEX

    def test_routes_to_claude_for_complex(self):
        from router import ModelRouter

        router = ModelRouter(
            claude_model_id="claude-test",
            titan_model_id="titan-test"
        )

        model = router.get_model("Explain in detail how the authentication works")

        assert model == "claude-test"

    def test_routes_to_titan_for_simple(self):
        from router import ModelRouter

        router = ModelRouter(
            claude_model_id="claude-test",
            titan_model_id="titan-test"
        )

        model = router.get_model("List open tickets")

        assert model == "titan-test"

    def test_force_model_override(self):
        from router import ModelRouter

        router = ModelRouter(
            claude_model_id="claude-test",
            titan_model_id="titan-test"
        )

        model = router.get_model("Simple query", force_model="claude")

        assert model == "claude-test"


class TestShortTermMemory:
    """Tests for short-term memory."""

    def test_adds_messages(self):
        from memory import ShortTermMemory

        stm = ShortTermMemory(max_messages=10)

        stm.add_message("user", "Hello")
        stm.add_message("assistant", "Hi there!")

        assert len(stm.messages) == 2

    def test_respects_max_messages(self):
        from memory import ShortTermMemory

        stm = ShortTermMemory(max_messages=3)

        for i in range(5):
            stm.add_message("user", f"Message {i}")

        assert len(stm.messages) == 3
        assert stm.messages[0].content == "Message 2"

    def test_get_context_returns_formatted_messages(self):
        from memory import ShortTermMemory

        stm = ShortTermMemory()
        stm.add_message("user", "Hello")
        stm.add_message("assistant", "Hi!")

        context = stm.get_context()

        assert len(context) == 2
        assert context[0]["role"] == "user"
        assert context[1]["role"] == "assistant"


class TestLongTermMemory:
    """Tests for long-term memory."""

    def test_stores_locally_when_bedrock_unavailable(self):
        from memory import LongTermMemory

        ltm = LongTermMemory(enabled=False)

        result = ltm.store("key1", "value1", namespace="facts")

        assert result is True
        assert "facts" in ltm._local_store
        assert len(ltm._local_store["facts"]) == 1

    def test_retrieves_from_local_store(self):
        from memory import LongTermMemory

        ltm = LongTermMemory(enabled=False)
        ltm.store("key1", "VPN troubleshooting guide", namespace="facts")

        results = ltm.retrieve("VPN")

        assert len(results) == 1
        assert "VPN" in results[0].value


class TestMemoryManager:
    """Tests for the unified memory manager."""

    def test_manages_session(self):
        from memory import MemoryManager

        manager = MemoryManager(memory_enabled=False)

        manager.set_session("session-123")

        assert manager.session_id == "session-123"

    def test_adds_messages_to_short_term(self):
        from memory import MemoryManager

        manager = MemoryManager(memory_enabled=False)

        manager.add_user_message("Hello")
        manager.add_assistant_message("Hi there!")

        context = manager.get_conversation_context()

        assert len(context) == 2


class TestToolResult:
    """Tests for tool results."""

    def test_success_result(self):
        from tools import ToolResult

        result = ToolResult(success=True, data={"id": "123"})

        assert result.success is True
        assert result.data["id"] == "123"
        assert result.error is None

    def test_error_result(self):
        from tools import ToolResult

        result = ToolResult(success=False, data=None, error="Something went wrong")

        assert result.success is False
        assert result.error == "Something went wrong"


class TestToolSchemas:
    """Tests for tool schema definitions."""

    def test_schemas_are_valid(self):
        from tools import TOOL_SCHEMAS

        assert len(TOOL_SCHEMAS) > 0

        for schema in TOOL_SCHEMAS:
            assert "name" in schema
            assert "description" in schema
            assert "input_schema" in schema

    def test_create_ticket_schema_has_required_fields(self):
        from tools import TOOL_SCHEMAS

        create_schema = next(s for s in TOOL_SCHEMAS if s["name"] == "create_ticket")

        assert "title" in create_schema["input_schema"]["properties"]
        assert "description" in create_schema["input_schema"]["properties"]
        assert "title" in create_schema["input_schema"]["required"]
