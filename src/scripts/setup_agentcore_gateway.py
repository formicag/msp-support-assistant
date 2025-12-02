#!/usr/bin/env python3
"""
AgentCore Gateway Setup Script

This script creates and configures an Amazon Bedrock AgentCore Gateway
with Lambda targets for the MSP Support Assistant.

Usage:
    python setup_agentcore_gateway.py --region us-east-1 --environment demo

Prerequisites:
    - AWS credentials configured
    - Cognito User Pool created (via Terraform)
    - Lambda function deployed (via Terraform)
    - Gateway IAM Role created (via Terraform)
"""

import argparse
import json
import logging
import sys
import time

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AgentCoreGatewaySetup:
    """Set up AgentCore Gateway with Lambda targets."""

    def __init__(self, region: str, environment: str, project_name: str = "msp-support-assistant"):
        self.region = region
        self.environment = environment
        self.project_name = project_name
        self.name_prefix = f"{project_name}-{environment}"

        # Initialize clients
        self.ssm = boto3.client("ssm", region_name=region)
        self.cognito = boto3.client("cognito-idp", region_name=region)

        # Try to initialize AgentCore client
        try:
            self.agentcore = boto3.client("bedrock-agentcore-control", region_name=region)
            logger.info("AgentCore control client initialized")
        except Exception as e:
            logger.warning(f"AgentCore control client not available: {e}")
            self.agentcore = None

        # Load configuration from SSM
        self._load_config()

    def _load_config(self):
        """Load configuration from SSM Parameter Store."""
        try:
            # Get Lambda ARN
            response = self.ssm.get_parameter(
                Name=f"/{self.project_name}/{self.environment}/agentcore-tools-lambda-arn"
            )
            self.lambda_arn = response["Parameter"]["Value"]
            logger.info(f"Lambda ARN: {self.lambda_arn}")

            # Get Gateway Role ARN
            response = self.ssm.get_parameter(
                Name=f"/{self.project_name}/{self.environment}/agentcore-gateway-role-arn"
            )
            self.gateway_role_arn = response["Parameter"]["Value"]
            logger.info(f"Gateway Role ARN: {self.gateway_role_arn}")

        except ClientError as e:
            logger.error(f"Failed to load SSM parameters: {e}")
            logger.info("Make sure to run 'terraform apply' first to create the resources.")
            raise

    def _get_cognito_config(self):
        """Get Cognito configuration for Gateway authentication."""
        # List user pools to find ours
        response = self.cognito.list_user_pools(MaxResults=60)

        for pool in response.get("UserPools", []):
            if self.name_prefix in pool["Name"]:
                pool_id = pool["Id"]
                logger.info(f"Found Cognito User Pool: {pool_id}")

                # Get pool details
                pool_details = self.cognito.describe_user_pool(UserPoolId=pool_id)

                # Get client
                clients = self.cognito.list_user_pool_clients(
                    UserPoolId=pool_id,
                    MaxResults=10
                )

                for client in clients.get("UserPoolClients", []):
                    if "m2m" in client["ClientName"].lower():
                        client_id = client["ClientId"]
                        logger.info(f"Found M2M Client: {client_id}")

                        # Build discovery URL
                        discovery_url = (
                            f"https://cognito-idp.{self.region}.amazonaws.com/"
                            f"{pool_id}/.well-known/openid-configuration"
                        )

                        return {
                            "user_pool_id": pool_id,
                            "client_id": client_id,
                            "discovery_url": discovery_url
                        }

        raise ValueError("Cognito User Pool or M2M Client not found")

    def _define_tool_schemas(self):
        """Define tool schemas for the Gateway."""
        return [
            {
                "name": "list_tickets",
                "description": "List support tickets with optional filters. Returns all tickets or filtered by status.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["Open", "In Progress", "Resolved", "Closed"],
                            "description": "Filter tickets by status"
                        },
                        "customer_id": {
                            "type": "string",
                            "description": "Filter tickets by customer ID"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of tickets to return",
                            "default": 50
                        }
                    }
                }
            },
            {
                "name": "create_ticket",
                "description": "Create a new support ticket in the system. Use this when a user reports an issue or needs help.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Brief summary of the issue (required)"
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed description of the problem (required)"
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["Low", "Medium", "High", "Critical"],
                            "description": "Ticket priority level",
                            "default": "Medium"
                        },
                        "category": {
                            "type": "string",
                            "enum": ["Network", "Hardware", "Software", "Security", "General"],
                            "description": "Issue category",
                            "default": "General"
                        },
                        "customer_id": {
                            "type": "string",
                            "description": "Customer identifier"
                        }
                    },
                    "required": ["title", "description"]
                }
            },
            {
                "name": "get_ticket",
                "description": "Retrieve details of a specific ticket by its ID.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ticket_id": {
                            "type": "string",
                            "description": "The unique ticket identifier (e.g., TKT-20251202-ABC123)"
                        }
                    },
                    "required": ["ticket_id"]
                }
            },
            {
                "name": "update_ticket",
                "description": "Update an existing ticket's status, priority, or add notes.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ticket_id": {
                            "type": "string",
                            "description": "The ticket ID to update (required)"
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
                        },
                        "assigned_to": {
                            "type": "string",
                            "description": "Person to assign the ticket to"
                        }
                    },
                    "required": ["ticket_id"]
                }
            },
            {
                "name": "get_ticket_summary",
                "description": "Get a summary and overview of all tickets including counts by status, priority, and recent activity. Use this to provide ticket analytics and dashboard information.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    def create_gateway(self):
        """Create the AgentCore Gateway."""
        if not self.agentcore:
            logger.error("AgentCore client not available. The bedrock-agentcore-control service may not be available in your region yet.")
            return self._create_gateway_config_file()

        try:
            # Get Cognito configuration
            cognito_config = self._get_cognito_config()

            # Create Gateway
            gateway_name = f"{self.name_prefix}-gateway"

            auth_config = {
                "customJWTAuthorizer": {
                    "allowedClients": [cognito_config["client_id"]],
                    "discoveryUrl": cognito_config["discovery_url"]
                }
            }

            logger.info(f"Creating Gateway: {gateway_name}")

            response = self.agentcore.create_gateway(
                name=gateway_name,
                roleArn=self.gateway_role_arn,
                protocolType="MCP",
                authorizerType="CUSTOM_JWT",
                authorizerConfiguration=auth_config,
                description="MSP Support Assistant AgentCore Gateway"
            )

            gateway_id = response["gatewayId"]
            logger.info(f"Gateway created: {gateway_id}")

            # Wait for gateway to be active
            self._wait_for_gateway(gateway_id)

            # Add Lambda targets
            self._add_lambda_targets(gateway_id)

            # Get Gateway endpoint
            gateway_info = self.agentcore.get_gateway(gatewayIdentifier=gateway_id)
            mcp_endpoint = gateway_info.get("mcpEndpoint")

            logger.info(f"Gateway MCP Endpoint: {mcp_endpoint}")

            # Save to SSM
            self._save_gateway_config(gateway_id, mcp_endpoint, cognito_config)

            return {
                "gateway_id": gateway_id,
                "mcp_endpoint": mcp_endpoint,
                "cognito": cognito_config
            }

        except ClientError as e:
            logger.error(f"Failed to create gateway: {e}")
            raise

    def _wait_for_gateway(self, gateway_id: str, max_attempts: int = 30):
        """Wait for gateway to become active."""
        logger.info("Waiting for gateway to become active...")

        for attempt in range(max_attempts):
            response = self.agentcore.get_gateway(gatewayIdentifier=gateway_id)
            status = response.get("status")

            if status == "ACTIVE":
                logger.info("Gateway is active")
                return

            logger.info(f"Gateway status: {status} (attempt {attempt + 1}/{max_attempts})")
            time.sleep(10)

        raise TimeoutError("Gateway did not become active in time")

    def _add_lambda_targets(self, gateway_id: str):
        """Add Lambda function targets to the Gateway."""
        tool_schemas = self._define_tool_schemas()

        logger.info(f"Adding {len(tool_schemas)} tool targets to gateway")

        for tool in tool_schemas:
            target_config = {
                "mcp": {
                    "lambda": {
                        "lambdaArn": self.lambda_arn,
                        "toolSchema": {
                            "inlinePayload": [tool]
                        }
                    }
                }
            }

            credential_config = [{
                "credentialProviderType": "GATEWAY_IAM_ROLE"
            }]

            try:
                response = self.agentcore.create_gateway_target(
                    gatewayIdentifier=gateway_id,
                    name=tool["name"],
                    description=tool["description"],
                    targetConfiguration=target_config,
                    credentialProviderConfigurations=credential_config
                )
                logger.info(f"Added target: {tool['name']}")

            except ClientError as e:
                logger.error(f"Failed to add target {tool['name']}: {e}")

    def _save_gateway_config(self, gateway_id: str, mcp_endpoint: str, cognito_config: dict):
        """Save gateway configuration to SSM."""
        params = {
            f"/{self.project_name}/{self.environment}/agentcore-gateway-id": gateway_id,
            f"/{self.project_name}/{self.environment}/agentcore-mcp-endpoint": mcp_endpoint,
            f"/{self.project_name}/{self.environment}/cognito-client-id": cognito_config["client_id"],
            f"/{self.project_name}/{self.environment}/cognito-discovery-url": cognito_config["discovery_url"],
        }

        for name, value in params.items():
            try:
                self.ssm.put_parameter(
                    Name=name,
                    Value=value,
                    Type="String",
                    Overwrite=True
                )
                logger.info(f"Saved SSM parameter: {name}")
            except ClientError as e:
                logger.error(f"Failed to save parameter {name}: {e}")

    def _create_gateway_config_file(self):
        """Create a configuration file for manual gateway setup."""
        config = {
            "gateway_name": f"{self.name_prefix}-gateway",
            "role_arn": self.gateway_role_arn,
            "lambda_arn": self.lambda_arn,
            "protocol_type": "MCP",
            "authorizer_type": "CUSTOM_JWT",
            "tools": self._define_tool_schemas(),
            "instructions": [
                "The AgentCore Gateway API is not yet available via boto3 in your region.",
                "You can set up the gateway manually via the AWS Console:",
                "1. Go to Amazon Bedrock > AgentCore > Gateways",
                "2. Create a new gateway with the configuration above",
                "3. Add Lambda targets using the tool schemas provided",
                "4. Note the MCP endpoint URL for the Streamlit app"
            ]
        }

        config_path = f"/tmp/agentcore_gateway_config_{self.environment}.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        logger.info(f"Gateway configuration saved to: {config_path}")
        print(json.dumps(config, indent=2))

        return config


def main():
    parser = argparse.ArgumentParser(description="Set up AgentCore Gateway")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--environment", default="demo", help="Environment name")
    parser.add_argument("--project-name", default="msp-support-assistant", help="Project name")

    args = parser.parse_args()

    try:
        setup = AgentCoreGatewaySetup(
            region=args.region,
            environment=args.environment,
            project_name=args.project_name
        )

        result = setup.create_gateway()
        print("\n" + "=" * 60)
        print("AgentCore Gateway Setup Complete")
        print("=" * 60)
        print(json.dumps(result, indent=2))

    except Exception as e:
        logger.error(f"Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
