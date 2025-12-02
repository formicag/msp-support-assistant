#!/usr/bin/env python3
"""
Data Ingestion Script for MSP Support Assistant

This script loads sample data into DynamoDB and creates embeddings
for the OpenSearch vector index.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DataIngester:
    """Handles data ingestion for the MSP Support Assistant."""

    def __init__(
        self,
        region: str = "us-east-1",
        tickets_table: Optional[str] = None,
        opensearch_endpoint: Optional[str] = None,
        vector_bucket: Optional[str] = None,
        embedding_model: str = "amazon.titan-embed-text-v2:0",
    ):
        """
        Initialize the data ingester.

        Args:
            region: AWS region
            tickets_table: DynamoDB table name for tickets
            opensearch_endpoint: OpenSearch Serverless endpoint
            vector_bucket: S3 bucket for vector storage
            embedding_model: Bedrock embedding model ID
        """
        self.region = region
        self.tickets_table = tickets_table or os.environ.get(
            "TICKETS_TABLE", "msp-support-assistant-demo-tickets"
        )
        self.opensearch_endpoint = opensearch_endpoint or os.environ.get(
            "OPENSEARCH_ENDPOINT", ""
        )
        self.vector_bucket = vector_bucket or os.environ.get(
            "VECTOR_STORE_BUCKET", ""
        )
        self.embedding_model = embedding_model

        # Initialize AWS clients
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.bedrock_runtime = boto3.client("bedrock-runtime", region_name=region)
        self.s3 = boto3.client("s3", region_name=region)

        # OpenSearch client (using requests with SigV4)
        self._opensearch_session = None

    def get_embedding(self, text: str) -> list:
        """Generate embedding using Bedrock."""
        try:
            body = json.dumps({"inputText": text})
            response = self.bedrock_runtime.invoke_model(
                modelId=self.embedding_model,
                body=body,
            )
            response_body = json.loads(response["body"].read())
            return response_body.get("embedding", [])
        except ClientError as e:
            logger.error(f"Failed to generate embedding: {e}")
            return []

    def load_sample_tickets(self, file_path: str) -> int:
        """
        Load sample tickets into DynamoDB.

        Args:
            file_path: Path to sample_tickets.json

        Returns:
            Number of tickets loaded
        """
        logger.info(f"Loading tickets from {file_path}")

        try:
            with open(file_path, "r") as f:
                tickets = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            return 0

        table = self.dynamodb.Table(self.tickets_table)
        count = 0
        timestamp = datetime.now(timezone.utc).isoformat()

        for ticket in tickets:
            try:
                item = {
                    "TicketId": ticket["id"],
                    "Title": ticket["title"],
                    "Description": ticket["description"],
                    "Category": ticket["category"],
                    "Priority": ticket["priority"],
                    "Status": ticket["status"],
                    "Tags": ticket.get("tags", []),
                    "CreatedAt": timestamp,
                    "UpdatedAt": timestamp,
                    "CustomerId": "sample-customer",
                }

                if ticket.get("resolution"):
                    item["Resolution"] = ticket["resolution"]
                    item["Notes"] = [{
                        "text": ticket["resolution"],
                        "timestamp": timestamp,
                        "author": "System"
                    }]

                table.put_item(Item=item)
                count += 1
                logger.info(f"Loaded ticket: {ticket['id']}")

            except ClientError as e:
                logger.error(f"Failed to load ticket {ticket['id']}: {e}")

        logger.info(f"Successfully loaded {count} tickets")
        return count

    def create_knowledge_embeddings(self, file_path: str) -> int:
        """
        Create embeddings for knowledge base articles.

        Args:
            file_path: Path to knowledge_base.json

        Returns:
            Number of embeddings created
        """
        logger.info(f"Creating embeddings from {file_path}")

        try:
            with open(file_path, "r") as f:
                articles = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            return 0

        count = 0
        embeddings_data = []

        for article in articles:
            # Combine title and content for embedding
            text = f"{article['title']}\n\n{article['content']}"
            embedding = self.get_embedding(text)

            if embedding:
                embedding_record = {
                    "id": article["id"],
                    "title": article["title"],
                    "category": article["category"],
                    "content": article["content"],
                    "tags": article.get("tags", []),
                    "embedding": embedding,
                }
                embeddings_data.append(embedding_record)
                count += 1
                logger.info(f"Created embedding for: {article['id']}")
            else:
                logger.warning(f"Failed to create embedding for: {article['id']}")

        # Save embeddings to S3 (for S3 Vector Store)
        if self.vector_bucket and embeddings_data:
            try:
                self.s3.put_object(
                    Bucket=self.vector_bucket,
                    Key="knowledge-base/embeddings.json",
                    Body=json.dumps(embeddings_data),
                    ContentType="application/json",
                )
                logger.info(f"Saved embeddings to s3://{self.vector_bucket}/knowledge-base/embeddings.json")
            except ClientError as e:
                logger.error(f"Failed to save embeddings to S3: {e}")

        # Index in OpenSearch (if endpoint configured)
        if self.opensearch_endpoint and embeddings_data:
            self._index_to_opensearch(embeddings_data)

        logger.info(f"Successfully created {count} embeddings")
        return count

    def _index_to_opensearch(self, embeddings_data: list) -> None:
        """
        Index embeddings to OpenSearch Serverless.

        Note: This is a placeholder. In production, you would use
        the OpenSearch Python client with SigV4 authentication.
        """
        logger.info("OpenSearch indexing would happen here")
        logger.info(f"Would index {len(embeddings_data)} documents to {self.opensearch_endpoint}")

        # Example of what the indexing would look like:
        # from opensearchpy import OpenSearch, RequestsHttpConnection
        # from requests_aws4auth import AWS4Auth
        #
        # credentials = boto3.Session().get_credentials()
        # auth = AWS4Auth(
        #     credentials.access_key,
        #     credentials.secret_key,
        #     self.region,
        #     'aoss',
        #     session_token=credentials.token
        # )
        #
        # client = OpenSearch(
        #     hosts=[{'host': self.opensearch_endpoint, 'port': 443}],
        #     http_auth=auth,
        #     use_ssl=True,
        #     connection_class=RequestsHttpConnection,
        # )
        #
        # for doc in embeddings_data:
        #     client.index(
        #         index='tickets-index',
        #         body={
        #             'id': doc['id'],
        #             'title': doc['title'],
        #             'content': doc['content'],
        #             'embedding': doc['embedding'],
        #             'metadata': {
        #                 'category': doc['category'],
        #                 'tags': doc['tags']
        #             }
        #         }
        #     )

    def verify_setup(self) -> dict:
        """
        Verify the data ingestion setup.

        Returns:
            Dictionary with verification results
        """
        results = {
            "dynamodb": False,
            "bedrock": False,
            "s3": False,
            "opensearch": False,
        }

        # Check DynamoDB
        try:
            table = self.dynamodb.Table(self.tickets_table)
            table.table_status  # This will raise if table doesn't exist
            results["dynamodb"] = True
            logger.info(f"DynamoDB table {self.tickets_table} is accessible")
        except Exception as e:
            logger.error(f"DynamoDB check failed: {e}")

        # Check Bedrock
        try:
            test_embedding = self.get_embedding("test")
            results["bedrock"] = len(test_embedding) > 0
            logger.info(f"Bedrock embedding model is accessible (dimension: {len(test_embedding)})")
        except Exception as e:
            logger.error(f"Bedrock check failed: {e}")

        # Check S3
        if self.vector_bucket:
            try:
                self.s3.head_bucket(Bucket=self.vector_bucket)
                results["s3"] = True
                logger.info(f"S3 bucket {self.vector_bucket} is accessible")
            except Exception as e:
                logger.error(f"S3 check failed: {e}")

        # Check OpenSearch
        if self.opensearch_endpoint:
            # Would add actual health check here
            logger.info("OpenSearch endpoint configured (not verified)")

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Ingest sample data for MSP Support Assistant"
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="AWS region",
    )
    parser.add_argument(
        "--tickets-table",
        default=os.environ.get("TICKETS_TABLE"),
        help="DynamoDB table name for tickets",
    )
    parser.add_argument(
        "--tickets-file",
        default="data/sample_tickets.json",
        help="Path to sample tickets JSON file",
    )
    parser.add_argument(
        "--knowledge-file",
        default="data/knowledge_base.json",
        help="Path to knowledge base JSON file",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify setup, don't load data",
    )
    parser.add_argument(
        "--skip-tickets",
        action="store_true",
        help="Skip loading tickets to DynamoDB",
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip creating knowledge base embeddings",
    )

    args = parser.parse_args()

    ingester = DataIngester(
        region=args.region,
        tickets_table=args.tickets_table,
    )

    if args.verify_only:
        results = ingester.verify_setup()
        print("\nVerification Results:")
        for service, status in results.items():
            status_text = "OK" if status else "FAILED"
            print(f"  {service}: {status_text}")
        sys.exit(0 if all(results.values()) else 1)

    # Load data
    if not args.skip_tickets:
        ingester.load_sample_tickets(args.tickets_file)

    if not args.skip_embeddings:
        ingester.create_knowledge_embeddings(args.knowledge_file)

    print("\nData ingestion complete!")


if __name__ == "__main__":
    main()
