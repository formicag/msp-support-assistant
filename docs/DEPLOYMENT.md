# Deployment Summary

This document details the deployed infrastructure for the MSP Support Assistant.

## Deployment Information

- **AWS Account**: 010819240034
- **Region**: us-east-1
- **Environment**: demo
- **Deployed**: December 2, 2025
- **Terraform Resources**: 55

---

## Deployed Endpoints

| Service | URL | Status |
|---------|-----|--------|
| **Streamlit App** | https://ut48uszr3s.us-east-1.awsapprunner.com | RUNNING |
| **API Gateway** | https://p3h9ge8d92.execute-api.us-east-1.amazonaws.com | Active |
| **Health Check (App)** | https://ut48uszr3s.us-east-1.awsapprunner.com/_stcore/health | OK |
| **Health Check (API)** | https://p3h9ge8d92.execute-api.us-east-1.amazonaws.com/health | Healthy |

---

## Infrastructure Components

### Compute

| Resource | Name/ID | Details |
|----------|---------|---------|
| **App Runner** | msp-support-assistant-demo-streamlit | 1 vCPU, 2GB RAM, Auto-scaling 1-5 |
| **Lambda** | msp-support-assistant-demo-ticket-api | Python 3.11, 512MB |

### Storage

| Resource | Name | Purpose |
|----------|------|---------|
| **DynamoDB** | msp-support-assistant-demo-tickets | Ticket storage |
| **DynamoDB** | msp-support-assistant-demo-sessions | Session management |
| **S3** | msp-support-assistant-demo-vector-store-a092fc2f | RAG knowledge base |
| **S3** | msp-support-assistant-demo-artifacts-a092fc2f | Deployment artifacts |

### Search & AI

| Resource | ID/Name | Type |
|----------|---------|------|
| **OpenSearch Serverless** | 6k769knpxp2g355cxeu3 | VECTORSEARCH |
| **OpenSearch Endpoint** | https://6k769knpxp2g355cxeu3.us-east-1.aoss.amazonaws.com | Collection |

### Container Registry

| Repository | URI |
|------------|-----|
| **Streamlit** | 010819240034.dkr.ecr.us-east-1.amazonaws.com/msp-support-assistant-demo-streamlit |
| **Agent** | 010819240034.dkr.ecr.us-east-1.amazonaws.com/msp-support-assistant-demo-agent |

### Networking

| Resource | ID | Details |
|----------|-----|---------|
| **API Gateway** | p3h9ge8d92 | HTTP API |

---

## IAM Roles

| Role | ARN | Purpose |
|------|-----|---------|
| **GitHub Actions** | arn:aws:iam::010819240034:role/GitHubActionsDeployRole | CI/CD deployment |
| **Agent Execution** | arn:aws:iam::010819240034:role/msp-support-assistant-demo-agent-execution-role | Bedrock agent |
| **Lambda Execution** | arn:aws:iam::010819240034:role/msp-support-assistant-demo-lambda-execution-role | Lambda function |
| **App Runner Instance** | arn:aws:iam::010819240034:role/msp-support-assistant-demo-app-runner-instance-role | App Runner |
| **App Runner ECR Access** | arn:aws:iam::010819240034:role/msp-support-assistant-demo-app-runner-ecr-access-role | ECR pull |

---

## SSM Parameters

| Parameter | Value |
|-----------|-------|
| `/msp-support-assistant/demo/api-gateway-endpoint` | https://p3h9ge8d92.execute-api.us-east-1.amazonaws.com/ |
| `/msp-support-assistant/demo/tickets-table-name` | msp-support-assistant-demo-tickets |
| `/msp-support-assistant/demo/vector-store-bucket` | msp-support-assistant-demo-vector-store-a092fc2f |
| `/msp-support-assistant/demo/opensearch-endpoint` | https://6k769knpxp2g355cxeu3.us-east-1.aoss.amazonaws.com |
| `/msp-support-assistant/demo/ecr-streamlit-repo` | 010819240034.dkr.ecr.us-east-1.amazonaws.com/msp-support-assistant-demo-streamlit |
| `/msp-support-assistant/demo/bedrock-claude-model` | anthropic.claude-3-sonnet-20240229-v1:0 |
| `/msp-support-assistant/demo/bedrock-titan-model` | amazon.titan-text-express-v1 |
| `/msp-support-assistant/demo/bedrock-embedding-model` | amazon.titan-embed-text-v2:0 |

---

## Cost Tags

All resources are tagged with:

| Tag | Value |
|-----|-------|
| `Project` | msp-support-assistant |
| `Owner` | Gianluca Formica |
| `Environment` | demo |
| `ManagedBy` | Terraform |
| `GitHubRepo` | https://github.com/formicag/msp-support-assistant |

---

## Terraform State

| Resource | Location |
|----------|----------|
| **State Bucket** | s3://msp-support-assistant-tfstate-a092fc2f |
| **Lock Table** | msp-support-assistant-tflock |
| **State Key** | demo/terraform.tfstate |

---

## GitHub Integration

### Repository

- **URL**: https://github.com/formicag/msp-support-assistant (Private)
- **OIDC Provider**: arn:aws:iam::010819240034:oidc-provider/token.actions.githubusercontent.com

### Security Settings

- Branch protection on `main`
- Secret scanning enabled
- Push protection enabled
- Dependabot alerts enabled

### Secrets Configured

| Secret | Description |
|--------|-------------|
| `AWS_ACCOUNT_ID` | 010819240034 |

---

## Verification Commands

```bash
# Check App Runner status
aws apprunner describe-service \
  --service-arn "arn:aws:apprunner:us-east-1:010819240034:service/msp-support-assistant-demo-streamlit/ad4ca1dd2a84460680a0d1527e6a45d9" \
  --query 'Service.Status'

# Check API health
curl https://p3h9ge8d92.execute-api.us-east-1.amazonaws.com/health

# Check Streamlit health
curl https://ut48uszr3s.us-east-1.awsapprunner.com/_stcore/health

# List tickets
curl https://p3h9ge8d92.execute-api.us-east-1.amazonaws.com/tickets
```

---

## Troubleshooting

### View App Runner Logs

```bash
aws logs tail "/aws/apprunner/msp-support-assistant-demo-streamlit/ad4ca1dd2a84460680a0d1527e6a45d9/application" --follow
```

### View Lambda Logs

```bash
aws logs tail "/aws/lambda/msp-support-assistant-demo-ticket-api" --follow
```

### Trigger App Runner Deployment

```bash
aws apprunner start-deployment \
  --service-arn "arn:aws:apprunner:us-east-1:010819240034:service/msp-support-assistant-demo-streamlit/ad4ca1dd2a84460680a0d1527e6a45d9"
```

---

## Cleanup

To destroy all resources:

```bash
cd terraform
terraform destroy
```

Then manually delete:
- Terraform state bucket: `msp-support-assistant-tfstate-a092fc2f`
- Terraform lock table: `msp-support-assistant-tflock`
- CloudWatch log groups (if any remain)
