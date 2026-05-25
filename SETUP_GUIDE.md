# Complete Setup and Deployment Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [GitHub Configuration](#github-configuration)
4. [AWS Infrastructure Setup](#aws-infrastructure-setup)
5. [Deployment Steps](#deployment-steps)
6. [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)

---

## Prerequisites

### Local Machine
```bash
# Install required tools
- Docker Desktop (for Mac/Windows) or Docker Engine (for Linux)
- Docker Compose v1.29+
- Python 3.9+
- pip package manager
- git
- AWS CLI v2
- Terraform 1.0+
- curl or Postman (for API testing)
```

### AWS Account Requirements
- An AWS account with appropriate permissions
- IAM user with programmatic access
- VPC with internet connectivity
- EC2 key pair created (for troubleshooting)

---

## Local Development Setup

### 1. Clone Repository
```bash
git clone <your-repository-url>
cd <repository-directory>
git checkout develop  # Start with develop branch
```

### 2. Configure Environment Variables
Create `.env` file in the root directory:

```env
# AWS Configuration
AWS_REGION=us-east-1
AWS_PROFILE=default

# Application Configuration
ENVIRONMENT=dev
PROJECT_NAME=my-app
DEBUG=True

# Service URLs (for local development with LocalStack)
AWS_ENDPOINT_URL=http://localstack:4566
ORDERS_QUEUE_URL=http://localstack:4566/000000000000/orders-dev
STATE_MACHINE_ARN=arn:aws:states:us-east-1:000000000000:stateMachine:my-app-order-workflow-dev

# Database Configuration
DATABASE_URL=postgresql://user:password@postgres:5432/myapp
REDIS_URL=redis://redis:6379/0

# API Configuration
API_KEY=your-api-key-here
PORT=5000
```

### 3. Start Local Services
```bash
# Start LocalStack, PostgreSQL, and other services
docker-compose up -d

# Verify services are running
docker-compose ps

# Check service logs
docker-compose logs -f app
```

### 4. Initialize Database
```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U user -d myapp

# Run migrations (if applicable)
python src/app/migrations.py
```

### 5. Run Application Locally
```bash
# Install dependencies
pip install -r src/app/requirements.txt

# Run Flask application
python -m flask run --host=0.0.0.0 --port=5000

# Test the health endpoint
curl http://localhost:5000/health

# Create a test order
curl -X POST http://localhost:5000/api/orders \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key" \
  -d '{
    "customer_id": "CUST-123",
    "items": [{"sku": "ITEM-1", "quantity": 2, "price": 29.99}]
  }'
```

### 6. Run Tests Locally
```bash
# Install test dependencies
pip install pytest pytest-cov pytest-mock moto

# Run all tests
pytest tests/ -v --cov=src --cov-report=html

# Run specific test file
pytest tests/test_app.py -v

# Run with coverage report
pytest tests/ --cov=src --cov-report=term-missing
```

### 7. Code Quality Checks
```bash
# Format code with Black
black src/ tests/

# Sort imports with isort
isort src/ tests/

# Run Pylint
pylint src/

# Run Flake8
flake8 src/ --max-line-length=100

# Security scanning with Bandit
bandit -r src/
```

---

## GitHub Configuration

### 1. Create Repository Secrets
Go to GitHub Repository → Settings → Secrets and Variables → Actions

Add the following secrets:

```
AWS_ACCESS_KEY_ID          # Your AWS access key
AWS_SECRET_ACCESS_KEY      # Your AWS secret key
AWS_REGION                 # us-east-1
ECR_REGISTRY               # Your ECR registry URL
TF_STATE_BUCKET            # S3 bucket for Terraform state
SLACK_WEBHOOK_URL          # Optional: Slack notifications
DOCKERHUB_USERNAME         # Optional: DockerHub credentials
DOCKERHUB_PASSWORD         # Optional: DockerHub credentials
```

### 2. Create GitHub Environments
Go to GitHub Repository → Settings → Environments

Create three environments:
- `development`
- `staging`
- `production`

For each environment, configure:
- Required reviewers (for production)
- Deployment branches
- Environment secrets (optional)

### 3. Configure Branch Protection Rules
Go to Settings → Branches → Add Branch Protection Rule

For `main` branch:
- Require pull request reviews before merging (1 review)
- Require status checks to pass before merging
- Require branches to be up to date before merging
- Include administrators
- Allow force pushes: No

For `develop` branch:
- Similar rules but with 0 required reviews (faster development)

---

## AWS Infrastructure Setup

### 1. Create S3 Bucket for Terraform State
```bash
aws s3api create-bucket \
  --bucket my-app-tf-state-prod \
  --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket my-app-tf-state-prod \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket my-app-tf-state-prod \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

# Block public access
aws s3api put-public-access-block \
  --bucket my-app-tf-state-prod \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

### 2. Create DynamoDB Table for Terraform Locks
```bash
aws dynamodb create-table \
  --table-name terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

### 3. Create ECR Repository
```bash
aws ecr create-repository \
  --repository-name my-app \
  --region us-east-1 \
  --image-scanning-configuration scanOnPush=true

# Get ECR URL
aws ecr describe-repositories \
  --repository-names my-app \
  --region us-east-1 \
  --query 'repositories[0].repositoryUri'
```

### 4. Create S3 Buckets for Application Data
```bash
# Dev environment
aws s3api create-bucket \
  --bucket my-app-data-dev \
  --region us-east-1

# Staging environment
aws s3api create-bucket \
  --bucket my-app-data-staging \
  --region us-east-1

# Production environment
aws s3api create-bucket \
  --bucket my-app-data-prod \
  --region us-east-1 \
  --create-bucket-configuration LocationConstraint=us-east-1
```

### 5. Configure AWS Credentials Locally
```bash
# Configure AWS CLI
aws configure

# Verify configuration
aws sts get-caller-identity
```

---

## Deployment Steps

### 1. Deploy to Development Environment

```bash
# Initialize Terraform
cd terraform

terraform init \
  -backend-config="bucket=my-app-tf-state-prod" \
  -backend-config="key=ci-cd-pipeline/dev/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=terraform-locks"

# Plan the deployment
terraform plan \
  -var-file="environments/dev.tfvars" \
  -out=tfplan

# Apply the configuration
terraform apply tfplan

# Get outputs
terraform output
```

### 2. Deploy to Staging Environment

```bash
# Plan the deployment
terraform plan \
  -var-file="environments/staging.tfvars" \
  -out=tfplan

# Apply the configuration
terraform apply tfplan
```

### 3. Deploy to Production Environment

```bash
# Plan the deployment (review carefully!)
terraform plan \
  -var-file="environments/prod.tfvars" \
  -out=tfplan

# Review the plan
cat tfplan

# Apply the configuration
terraform apply tfplan
```

### 4. Push Code to GitHub

```bash
# Commit changes
git add .
git commit -m "Deploy infrastructure and application"

# For development/testing
git push origin develop

# For staging
git checkout main
git pull origin main
git merge develop
git push origin main

# This automatically triggers:
# 1. CI pipeline (tests, build, validation)
# 2. Staging deployment (with manual approval)
# 3. Production deployment (requires environment approval)
```

---

## Monitoring and Troubleshooting

### 1. View CloudWatch Logs

```bash
# View ECS task logs
aws logs tail /aws/ecs/my-app-dev --follow

# View Lambda logs
aws logs tail /aws/lambda/my-app-order-processor --follow

# View Step Functions logs
aws logs tail /aws/states/my-app-dev --follow

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/ecs/my-app-dev \
  --filter-pattern "ERROR"
```

### 2. Check ECS Service Status

```bash
# List clusters
aws ecs list-clusters

# Describe service
aws ecs describe-services \
  --cluster my-app-cluster-dev \
  --services my-app-service-dev

# List running tasks
aws ecs list-tasks \
  --cluster my-app-cluster-dev \
  --service-name my-app-service-dev

# Describe task
aws ecs describe-tasks \
  --cluster my-app-cluster-dev \
  --tasks <task-arn>

# Get container logs
aws logs get-log-events \
  --log-group-name /aws/ecs/my-app-dev \
  --log-stream-name ecs/my-app-dev/<container-name>/<task-id>
```

### 3. Monitor CloudWatch Metrics

```bash
# Get metric statistics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=my-app-service-dev Name=ClusterName,Value=my-app-cluster-dev \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 300 \
  --statistics Average

# List alarms
aws cloudwatch describe-alarms \
  --alarm-names my-app-ecs-cpu-high-dev

# Get alarm history
aws cloudwatch describe-alarm-history \
  --alarm-name my-app-ecs-cpu-high-dev \
  --max-records 10
```

### 4. Troubleshoot Common Issues

**ECS tasks not starting:**
```bash
# Check task definition
aws ecs describe-task-definition \
  --task-definition my-app-dev:1

# Check service events
aws ecs describe-services \
  --cluster my-app-cluster-dev \
  --services my-app-service-dev \
  --query 'services[0].events[0:10]'

# View container logs for errors
docker logs <container-id>
```

**Lambda function failing:**
```bash
# Invoke Lambda function for testing
aws lambda invoke \
  --function-name my-app-order-processor-dev \
  --payload '{"test": true}' \
  response.json

# View response
cat response.json

# Check function configuration
aws lambda get-function-configuration \
  --function-name my-app-order-processor-dev
```

**Step Functions execution failed:**
```bash
# List executions
aws stepfunctions list-executions \
  --state-machine-arn <state-machine-arn> \
  --status-filter FAILED

# Describe execution
aws stepfunctions describe-execution \
  --execution-arn <execution-arn>

# Get execution history
aws stepfunctions get-execution-history \
  --execution-arn <execution-arn>
```

### 5. Performance Testing

```bash
# Using Apache Bench
ab -n 1000 -c 10 http://<alb-dns-name>/api/orders

# Using curl for load testing
for i in {1..100}; do
  curl -X POST http://<alb-dns-name>/api/orders \
    -H "Content-Type: application/json" \
    -H "X-API-Key: test-key" \
    -d '{"customer_id": "CUST-'$i'", "items": []}' &
done
wait
```

### 6. Rollback Procedure

**If a deployment fails:**

```bash
# Check Terraform state
terraform state list

# Rollback to previous version
terraform destroy \
  -var-file="environments/prod.tfvars"

# Or update to previous commit
git revert <commit-hash>
git push origin main

# Update ECS service with previous image
aws ecs update-service \
  --cluster my-app-cluster-prod \
  --service my-app-service-prod \
  --force-new-deployment
```

---

## Security Best Practices

1. **Secrets Management**
   - Never commit secrets to git
   - Use AWS Secrets Manager for sensitive data
   - Rotate credentials regularly

2. **IAM Permissions**
   - Use least privilege principle
   - Review IAM roles periodically
   - Use temporary credentials via STS

3. **Network Security**
   - Use VPC with private subnets
   - Enable VPC Flow Logs
   - Use security groups to restrict traffic

4. **Monitoring and Logging**
   - Enable CloudTrail for audit logs
   - Set up CloudWatch alarms
   - Review logs regularly

5. **Code Security**
   - Run SAST and DAST scans
   - Keep dependencies updated
   - Review pull requests thoroughly

---

## Useful Commands Summary

```bash
# Terraform
terraform init
terraform plan -var-file="environments/dev.tfvars"
terraform apply
terraform destroy
terraform refresh

# AWS CLI
aws ecs describe-services --cluster <cluster> --services <service>
aws logs tail /aws/ecs/<log-group> --follow
aws cloudwatch describe-alarms --alarm-names <alarm>

# Docker
docker-compose up -d
docker-compose down
docker-compose logs -f <service>
docker build -t my-app:latest .

# Git
git checkout -b feature/new-feature
git commit -am "Description"
git push origin feature/new-feature
git pull origin develop
```

---

## Support and Documentation

- [AWS Documentation](https://docs.aws.amazon.com/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [GitHub Actions](https://docs.github.com/en/actions)
- [Docker Documentation](https://docs.docker.com/)

---

**Last Updated:** 2024
**Version:** 1.0
