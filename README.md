# Production-Grade CI/CD Pipeline: GitHub Actions + AWS ECS + Lambda + Terraform

## Architecture Overview

This repository contains a complete production-grade CI/CD pipeline that demonstrates:

- **GitHub Actions**: Multi-stage CI/CD workflows with build, test, and deploy stages
- **AWS ECS**: Container orchestration for microservices deployment
- **AWS Lambda**: Serverless functions with Python runtime
- **AWS Step Functions**: Workflow orchestration
- **Terraform**: Infrastructure as Code (IaC) for all AWS resources
- **Multi-Environment**: Separate deployments for dev, staging, and production
- **CloudWatch**: Monitoring, logging, and alerting

## Directory Structure

```
.
├── .github/workflows/
│   ├── ci-cd-pipeline.yml          # Main CI/CD workflow
│   ├── deploy-dev.yml              # Dev environment deployment
│   ├── deploy-staging.yml          # Staging environment deployment
│   └── deploy-prod.yml             # Production environment deployment
├── terraform/
│   ├── main.tf                     # Main infrastructure configuration
│   ├── variables.tf                # Input variables
│   ├── outputs.tf                  # Output values
│   ├── ecs.tf                      # ECS cluster and service definitions
│   ├── lambda.tf                   # Lambda functions configuration
│   ├── step_functions.tf           # Step Functions state machines
│   ├── cloudwatch.tf               # Monitoring and logging
│   ├── iam.tf                      # IAM roles and policies
│   └── environments/
│       ├── dev.tfvars              # Dev environment variables
│       ├── staging.tfvars          # Staging environment variables
│       └── prod.tfvars             # Production environment variables
├── src/
│   ├── app/
│   │   ├── main.py                 # ECS service main application
│   │   ├── requirements.txt        # Python dependencies
│   │   └── Dockerfile              # Container image
│   └── lambda/
│       ├── order_processor.py      # Lambda function 1
│       ├── notification_handler.py # Lambda function 2
│       ├── data_transformer.py     # Lambda function 3
│       └── requirements.txt        # Lambda dependencies
├── tests/
│   ├── test_app.py                 # Application tests
│   ├── test_lambda.py              # Lambda function tests
│   └── test_terraform.py           # Terraform validation tests
├── scripts/
│   ├── build.sh                    # Build script
│   ├── deploy.sh                   # Deploy script
│   └── health-check.py             # Health check script
└── docker-compose.yml              # Local development setup
```

## Features

### 1. **Multi-Stage CI/CD Pipeline**
- Code checkout and setup
- Dependency installation
- Unit and integration tests
- Code quality checks (linting, security scanning)
- Docker image build and push to ECR
- Terraform plan and apply

### 2. **Environment Management**
- Separate workflows for dev, staging, and prod
- Environment-specific configurations
- Approval gates for production deployments
- Secret management via GitHub Secrets and AWS Secrets Manager

### 3. **Infrastructure Components**

#### ECS (Elastic Container Service)
- Fargate launch type (serverless containers)
- Auto-scaling based on CPU and memory metrics
- Load balancer integration
- Health checks and service discovery

#### Lambda Functions
- **Order Processor**: Processes incoming orders
- **Notification Handler**: Sends notifications
- **Data Transformer**: Transforms and enriches data

#### Step Functions
- Orchestrates workflows across Lambda functions
- Error handling and retry logic
- Parallel execution support
- CloudWatch integration

#### CloudWatch
- Custom metrics and dashboards
- Log aggregation and analysis
- Alarms and notifications
- X-Ray tracing integration

## Deployment Flow

```
GitHub Push
    ↓
CI Pipeline (Build & Test)
    ↓
Build & Push Docker Image to ECR
    ↓
Terraform Plan
    ↓
Manual Approval (Prod only)
    ↓
Terraform Apply
    ↓
ECS Service Update
    ↓
Lambda Functions Update
    ↓
Health Checks
    ↓
Success/Failure Notifications
```

## Prerequisites

### Local Development
- Docker & Docker Compose
- Terraform >= 1.0
- Python 3.9+
- AWS CLI v2
- Git

### AWS Account
- ECR repository
- ECS cluster (created by Terraform)
- Lambda execution role
- Step Functions state machine
- CloudWatch log groups
- S3 bucket for Terraform state

### GitHub
- Repository with Actions enabled
- GitHub Secrets configured (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, etc.)

## Setup Instructions

### 1. Clone the Repository
```bash
git clone <repository-url>
cd <repository-name>
```

### 2. Configure AWS Credentials
```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, and default region
```

### 3. Create GitHub Secrets
In GitHub Settings → Secrets and variables → Actions, add:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `ECR_REGISTRY`
- `SLACK_WEBHOOK_URL` (optional)
- `DOCKERHUB_USERNAME` (optional)
- `DOCKERHUB_PASSWORD` (optional)

### 4. Initialize Terraform
```bash
cd terraform
terraform init -backend-config="bucket=your-tf-state-bucket" \
                -backend-config="key=ci-cd-pipeline/terraform.tfstate" \
                -backend-config="region=us-east-1"
```

### 5. Deploy Infrastructure
```bash
# Plan the infrastructure changes
terraform plan -var-file=environments/dev.tfvars -out=tfplan

# Apply the configuration
terraform apply tfplan
```

### 6. Push to GitHub
```bash
git add .
git commit -m "Initial commit: CI/CD pipeline"
git push origin main
```

## Local Development

### Running with Docker Compose
```bash
docker-compose up -d
```

### Running Tests
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=src tests/

# Run specific test file
pytest tests/test_app.py
```

### Building Docker Image Locally
```bash
docker build -t my-app:latest src/app/
docker run -p 5000:5000 my-app:latest
```

## Environment Variables

### Dev Environment
- Instance type: t3.small
- ECS desired count: 1
- Lambda memory: 256 MB
- Auto-scaling: disabled

### Staging Environment
- Instance type: t3.medium
- ECS desired count: 2
- Lambda memory: 512 MB
- Auto-scaling: enabled (2-4 tasks)

### Production Environment
- Instance type: t3.large
- ECS desired count: 3
- Lambda memory: 1024 MB
- Auto-scaling: enabled (3-10 tasks)
- Approval gate: enabled

## Monitoring and Logging

### CloudWatch Dashboards
- ECS service metrics (CPU, memory, task count)
- Lambda execution metrics (duration, errors)
- Step Functions execution metrics
- Custom application metrics

### Alarms
- High CPU utilization (>80%)
- High memory usage (>85%)
- Task failures (any task termination)
- Lambda error rate (>1%)
- Step Functions failed executions

### Log Aggregation
- ECS task logs: `/aws/ecs/my-app-{environment}`
- Lambda logs: `/aws/lambda/my-app-{function-name}`
- Application logs: Structured JSON logging to CloudWatch

## Security Best Practices

1. **Secret Management**
   - Secrets stored in GitHub Secrets and AWS Secrets Manager
   - Sensitive data never logged
   - Rotation policies for credentials

2. **IAM Least Privilege**
   - Task roles with minimal permissions
   - Lambda execution roles scoped to required services
   - Cross-account access via assumed roles (if applicable)

3. **Network Security**
   - VPC with public/private subnets
   - Security groups restrict traffic
   - ALB with WAF (optional)

4. **Code Security**
   - SAST scanning in CI pipeline
   - Dependency vulnerability checks
   - Container image scanning in ECR

## Troubleshooting

### Deployment Fails
1. Check GitHub Actions logs: Actions tab → failed workflow
2. Review Terraform plan output
3. Verify AWS credentials and permissions
4. Check CloudWatch logs for service errors

### ECS Tasks Not Starting
```bash
# Check task status
aws ecs describe-tasks --cluster my-app-cluster \
  --tasks <task-arn> --region us-east-1

# View container logs
aws logs tail /aws/ecs/my-app-prod --follow
```

### Lambda Function Issues
```bash
# Invoke Lambda function
aws lambda invoke --function-name my-app-order-processor \
  --payload '{"test": true}' response.json

# View logs
aws logs tail /aws/lambda/my-app-order-processor --follow
```

## Cost Optimization

- Use Fargate Spot for dev/staging (70% discount)
- Lambda reserved concurrency for critical functions
- CloudWatch log retention: 30 days for dev, 90 days for prod
- Auto-scaling based on actual metrics

## Advanced Topics

### Blue-Green Deployment
The pipeline supports blue-green deployments via ECS service updates.

### Canary Deployments
Step Functions can orchestrate gradual traffic shifting.

### Cross-Region Replication
Terraform can be extended for multi-region deployments.

## Contributing

1. Create a feature branch
2. Make changes and commit
3. Push to GitHub
4. Create a Pull Request
5. GitHub Actions will validate automatically
6. Merge when approved

## Support

For issues or questions:
1. Check the Troubleshooting section
2. Review GitHub Actions logs
3. Consult AWS documentation
4. Check Terraform state files

## License

MIT License - See LICENSE file for details
