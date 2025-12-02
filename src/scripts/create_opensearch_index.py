#!/usr/bin/env python3
"""
Create OpenSearch Serverless Index for Vector Search

This script creates the vector index in OpenSearch Serverless
with the appropriate mapping for RAG functionality.
"""

import argparse
import json
import logging
import os
import sys
from typing import Optional

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class OpenSearchIndexManager:
    """Manages OpenSearch Serverless index operations."""

    def __init__(
        self,
        endpoint: str,
        region: str = "us-east-1",
        index_name: str = "tickets-index",
        embedding_dimension: int = 1024,
    ):
        """
        Initialize the index manager.

        Args:
            endpoint: OpenSearch Serverless collection endpoint
            region: AWS region
            index_name: Name of the index to create
            embedding_dimension: Dimension of embedding vectors
        """
        self.endpoint = endpoint.rstrip("/")
        if not self.endpoint.startswith("https://"):
            self.endpoint = f"https://{self.endpoint}"

        self.region = region
        self.index_name = index_name
        self.embedding_dimension = embedding_dimension

        # Get credentials for signing
        session = boto3.Session()
        self.credentials = session.get_credentials()
        self.service = "aoss"  # OpenSearch Serverless

    def _sign_request(self, method: str, url: str, body: Optional[dict] = None) -> dict:
        """Sign a request with SigV4."""
        headers = {"Content-Type": "application/json"}
        body_str = json.dumps(body) if body else ""

        request = AWSRequest(
            method=method,
            url=url,
            data=body_str,
            headers=headers,
        )

        SigV4Auth(self.credentials, self.service, self.region).add_auth(request)
        return dict(request.headers)

    def _make_request(
        self,
        method: str,
        path: str,
        body: Optional[dict] = None,
    ) -> requests.Response:
        """Make a signed request to OpenSearch."""
        url = f"{self.endpoint}/{path}"
        headers = self._sign_request(method, url, body)

        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=body)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=body)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")

        return response

    def check_index_exists(self) -> bool:
        """Check if the index already exists."""
        try:
            response = self._make_request("GET", self.index_name)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error checking index: {e}")
            return False

    def create_index(self) -> bool:
        """
        Create the vector index with appropriate mapping.

        Returns:
            True if index was created successfully
        """
        # Index mapping for vector search
        mapping = {
            "settings": {
                "index": {
                    "knn": True,
                    "knn.algo_param.ef_search": 512,
                }
            },
            "mappings": {
                "properties": {
                    "id": {
                        "type": "keyword"
                    },
                    "title": {
                        "type": "text",
                        "analyzer": "standard"
                    },
                    "content": {
                        "type": "text",
                        "analyzer": "standard"
                    },
                    "category": {
                        "type": "keyword"
                    },
                    "tags": {
                        "type": "keyword"
                    },
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": self.embedding_dimension,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "nmslib",
                            "parameters": {
                                "ef_construction": 512,
                                "m": 16
                            }
                        }
                    },
                    "metadata": {
                        "type": "object",
                        "enabled": True
                    },
                    "created_at": {
                        "type": "date"
                    }
                }
            }
        }

        try:
            if self.check_index_exists():
                logger.info(f"Index {self.index_name} already exists")
                return True

            response = self._make_request("PUT", self.index_name, mapping)

            if response.status_code in [200, 201]:
                logger.info(f"Successfully created index: {self.index_name}")
                return True
            else:
                logger.error(f"Failed to create index: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error creating index: {e}")
            return False

    def delete_index(self) -> bool:
        """Delete the index."""
        try:
            response = self._make_request("DELETE", self.index_name)

            if response.status_code in [200, 404]:
                logger.info(f"Index {self.index_name} deleted or did not exist")
                return True
            else:
                logger.error(f"Failed to delete index: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error deleting index: {e}")
            return False

    def get_index_info(self) -> Optional[dict]:
        """Get information about the index."""
        try:
            response = self._make_request("GET", self.index_name)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get index info: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error getting index info: {e}")
            return None


def main():
    parser = argparse.ArgumentParser(
        description="Manage OpenSearch Serverless index for vector search"
    )
    parser.add_argument(
        "--endpoint",
        required=True,
        help="OpenSearch Serverless collection endpoint",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="AWS region",
    )
    parser.add_argument(
        "--index-name",
        default="tickets-index",
        help="Name of the index",
    )
    parser.add_argument(
        "--dimension",
        type=int,
        default=1024,
        help="Embedding vector dimension (1024 for Titan v2)",
    )
    parser.add_argument(
        "--action",
        choices=["create", "delete", "info"],
        default="create",
        help="Action to perform",
    )

    args = parser.parse_args()

    manager = OpenSearchIndexManager(
        endpoint=args.endpoint,
        region=args.region,
        index_name=args.index_name,
        embedding_dimension=args.dimension,
    )

    if args.action == "create":
        success = manager.create_index()
        sys.exit(0 if success else 1)

    elif args.action == "delete":
        success = manager.delete_index()
        sys.exit(0 if success else 1)

    elif args.action == "info":
        info = manager.get_index_info()
        if info:
            print(json.dumps(info, indent=2))
            sys.exit(0)
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
