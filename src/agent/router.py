"""
Dynamic model routing for the MSP Support Agent.

Routes queries to appropriate LLMs (Claude vs Titan) based on
complexity and requirements.
"""

import json
import logging
import re
from enum import Enum
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class QueryComplexity(Enum):
    """Query complexity levels."""

    SIMPLE = "simple"
    COMPLEX = "complex"


class ModelRouter:
    """
    Routes queries to appropriate LLMs based on complexity.

    Uses heuristics and optionally an LLM classifier to determine
    which model is best suited for each query.
    """

    # Patterns indicating complex queries
    COMPLEX_PATTERNS = [
        r"explain.*in detail",
        r"analyze",
        r"compare",
        r"summarize.*all",
        r"what.*differences?",
        r"why.*happened",
        r"how.*work",
        r"troubleshoot",
        r"debug",
        r"investigate",
        r"review.*history",
        r"multiple.*issues",
        r"complex",
        r"detailed.*report",
    ]

    # Patterns indicating simple queries
    SIMPLE_PATTERNS = [
        r"^what.*status",
        r"^show.*ticket",
        r"^list.*tickets?",
        r"^create.*ticket",
        r"^update.*status",
        r"^close.*ticket",
        r"^get.*ticket",
        r"^find.*ticket",
        r"^how many",
        r"^is.*open",
        r"^yes$",
        r"^no$",
        r"^ok$",
        r"^thanks?",
    ]

    def __init__(
        self,
        claude_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        titan_model_id: str = "amazon.titan-text-express-v1",
        region: str = "us-east-1",
        use_llm_routing: bool = False,
    ):
        """
        Initialize the model router.

        Args:
            claude_model_id: Anthropic Claude model ID for complex queries
            titan_model_id: Amazon Titan model ID for simple queries
            region: AWS region
            use_llm_routing: Whether to use LLM for routing decisions
        """
        self.claude_model_id = claude_model_id
        self.titan_model_id = titan_model_id
        self.region = region
        self.use_llm_routing = use_llm_routing

        self.bedrock_runtime = boto3.client("bedrock-runtime", region_name=region)

        # Compile patterns
        self._complex_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.COMPLEX_PATTERNS
        ]
        self._simple_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.SIMPLE_PATTERNS
        ]

        # Usage statistics
        self.routing_stats = {"claude": 0, "titan": 0}

    def classify_query(self, query: str, context_length: int = 0) -> QueryComplexity:
        """
        Classify query complexity using heuristics.

        Args:
            query: The user query
            context_length: Length of conversation context

        Returns:
            QueryComplexity (SIMPLE or COMPLEX)
        """
        query_lower = query.lower().strip()

        # Check simple patterns first
        for pattern in self._simple_patterns:
            if pattern.search(query_lower):
                return QueryComplexity.SIMPLE

        # Check complex patterns
        for pattern in self._complex_patterns:
            if pattern.search(query_lower):
                return QueryComplexity.COMPLEX

        # Heuristics based on query characteristics
        word_count = len(query.split())

        # Very short queries are typically simple
        if word_count <= 5:
            return QueryComplexity.SIMPLE

        # Long queries or those with lots of context are complex
        if word_count > 50 or context_length > 10:
            return QueryComplexity.COMPLEX

        # Questions with specific keywords
        if any(
            word in query_lower
            for word in ["why", "how", "explain", "analyze", "troubleshoot"]
        ):
            return QueryComplexity.COMPLEX

        # Default to simple for efficiency
        return QueryComplexity.SIMPLE

    def classify_with_llm(self, query: str) -> QueryComplexity:
        """
        Use an LLM to classify query complexity.

        This is more accurate but adds latency and cost.

        Args:
            query: The user query

        Returns:
            QueryComplexity
        """
        try:
            prompt = f"""Classify this support query as SIMPLE or COMPLEX:

Query: {query}

SIMPLE means: status checks, basic lookups, simple ticket operations
COMPLEX means: requires analysis, detailed explanation, troubleshooting

Respond with only one word: SIMPLE or COMPLEX"""

            # Use Titan for classification (cheaper)
            body = json.dumps(
                {
                    "inputText": prompt,
                    "textGenerationConfig": {
                        "maxTokenCount": 10,
                        "temperature": 0,
                    },
                }
            )

            response = self.bedrock_runtime.invoke_model(
                modelId=self.titan_model_id,
                body=body,
            )

            response_body = json.loads(response["body"].read())
            result = response_body.get("results", [{}])[0].get("outputText", "").strip()

            if "COMPLEX" in result.upper():
                return QueryComplexity.COMPLEX
            return QueryComplexity.SIMPLE

        except ClientError as e:
            logger.warning(f"LLM classification failed: {e}, using heuristic")
            return self.classify_query(query)

    def get_model(
        self,
        query: str,
        context_length: int = 0,
        force_model: Optional[str] = None,
    ) -> str:
        """
        Get the appropriate model ID for a query.

        Args:
            query: The user query
            context_length: Number of messages in conversation
            force_model: Force a specific model ("claude" or "titan")

        Returns:
            Model ID to use
        """
        # Allow forcing a specific model
        if force_model:
            if force_model.lower() == "claude":
                self.routing_stats["claude"] += 1
                return self.claude_model_id
            elif force_model.lower() == "titan":
                self.routing_stats["titan"] += 1
                return self.titan_model_id

        # Classify query
        if self.use_llm_routing:
            complexity = self.classify_with_llm(query)
        else:
            complexity = self.classify_query(query, context_length)

        # Route based on complexity
        if complexity == QueryComplexity.COMPLEX:
            self.routing_stats["claude"] += 1
            logger.info(f"Routing to Claude (complex query)")
            return self.claude_model_id
        else:
            self.routing_stats["titan"] += 1
            logger.info(f"Routing to Titan (simple query)")
            return self.titan_model_id

    def get_routing_stats(self) -> dict:
        """Get routing statistics."""
        total = self.routing_stats["claude"] + self.routing_stats["titan"]
        if total == 0:
            return {"claude": 0, "titan": 0, "claude_pct": 0, "titan_pct": 0}

        return {
            "claude": self.routing_stats["claude"],
            "titan": self.routing_stats["titan"],
            "claude_pct": round(self.routing_stats["claude"] / total * 100, 1),
            "titan_pct": round(self.routing_stats["titan"] / total * 100, 1),
        }

    def reset_stats(self) -> None:
        """Reset routing statistics."""
        self.routing_stats = {"claude": 0, "titan": 0}
