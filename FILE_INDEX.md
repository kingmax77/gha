# Project Files Index

## Overview
This is a complete, production-grade CI/CD pipeline project with GitHub Actions, AWS (ECS, Lambda, Step Functions), Terraform, and Python. Below is a comprehensive index of all files and their purposes.

---

## 📋 Documentation Files

### README.md
**Purpose:** Main project documentation with architecture overview, setup instructions, and troubleshooting guide.
**Key Sections:**
- Architecture overview
- Directory structure
- Features overview
- Setup instructions
- Multi-environment deployment flow
- Monitoring and logging
- Security best practices

### SETUP_GUIDE.md
**Purpose:** Complete step-by-step setup and deployment guide for developers and DevOps engineers.
**Key Sections:**
- Prerequisites and installation
- Local development setup
- GitHub configuration
- AWS infrastructure setup
- Deployment steps for each environment
- Monitoring and troubleshooting
- Useful commands reference

---

## 🔧 GitHub Actions Workflow Files

### ci-cd-pipeline.yml
**Purpose:** Main CI/CD workflow that orchestrates the entire pipeline.
**Stages:**
1. Code Quality & Security: Pylint, Flake8, Black, Bandit
2. Unit & Integration Tests: Pytest with coverage
3. Terraform Validation: Format checks, validation
4. Docker Image Build: Build and push to ECR
5. Terraform Plan: For dev and staging
6. Deploy Dev: Automatic deployment to dev
7. Deploy Staging: Automatic deployment to staging
8. Approve Production: Manual approval gate
9. Deploy Production: Production deployment
10. Health Checks: Post-deployment verification
11. Notifications: Slack integration

**Triggered by:**
- Push to main branch
- Push to develop branch
- Pull requests to main/develop

---

## 🏗️ Terraform Infrastructure Files

### terraform-main.tf
**Purpose:** Core infrastructure including VPC, networking, load balancer, and ECR.
**Resources:**
- VPC with public/private subnets across multiple AZs
- Internet Gateway and NAT Gateways
- Route tables and associations
- Security groups (ALB, ECS tasks)
- Application Load Balancer
- Target groups and listeners
- ECR repository with lifecycle policies
- CloudWatch log groups

**Outputs:**
- ALB DNS name
- ECR repository URL
- VPC and subnet IDs
- Security group IDs

### terraform-ecs.tf
**Purpose:** ECS cluster, services, task definitions, and auto-scaling.
**Resources:**
- ECS Cluster with Container Insights
- ECS Task Definition with health checks
- ECS Service with load balancer integration
- Auto-scaling targets and policies
  - CPU-based scaling
  - Memory-based scaling
  - ALB request count scaling
- Capacity provider strategy

**Outputs:**
- ECS cluster name
- ECS service name
- ECS task definition ARN

### terraform-lambda.tf
**Purpose:** Lambda functions, layers, Step Functions state machine, and SQS integration.
**Resources:**
- Order Processor Lambda function
- Notification Handler Lambda function
- Data Transformer Lambda function
- Lambda layer for dependencies
- Lambda reserved concurrency (production)
- Lambda aliases
- Lambda security group
- Step Functions state machine (order workflow)
- SNS topic for error notifications
- SQS queue for order processing
- SQS dead-letter queue

**Outputs:**
- Lambda function ARNs
- Step Functions state machine ARN
- SQS queue URL

### terraform-iam.tf
**Purpose:** IAM roles, policies, and permissions for all services.
**Roles:**
- ECS Task Execution Role (pull images, write logs)
- ECS Task Role (access AWS services)
- Lambda Execution Role (CloudWatch, VPC, S3, SQS, DynamoDB)
- Step Functions Role (invoke Lambda, publish SNS)

**Policies:**
- Least privilege access patterns
- Secrets Manager integration
- CloudWatch metrics and X-Ray
- VPC access for Lambda
- Cross-service communication

**Secrets:**
- Database URL in Secrets Manager
- API Key in Secrets Manager

### terraform-cloudwatch.tf
**Purpose:** Monitoring, dashboards, alarms, and observability.
**Resources:**
- CloudWatch Dashboard with ECS, ALB, Lambda, Step Functions, and SQS metrics
- Alarms:
  - ECS CPU high (>80%)
  - ECS memory high (>85%)
  - ECS task failures
  - Lambda errors
  - Lambda throttles
  - Lambda duration
  - Step Functions failures
  - SQS queue depth
  - ALB unhealthy targets
  - ALB response time
- Composite alarm for overall health
- Log group metric filters
- Custom metrics namespace

**Outputs:**
- CloudWatch dashboard URL

### terraform-variables.tf
**Purpose:** Variable definitions with validation and environment-specific settings.
**Variables:**
- AWS region
- Environment (dev, staging, prod)
- Project name
- VPC CIDR blocks
- Availability zones
- ECS configuration (CPU, memory, counts)
- Lambda configuration
- Logging retention days
- Docker image tags
- Alert email

**Locals:**
- Environment-specific settings
- Common tags

### dev.tfvars
**Purpose:** Development environment configuration.
**Settings:**
- Small instance types (t3.small)
- Minimal task counts (1)
- Short log retention (7 days)
- Lower Lambda memory (256MB)

### staging.tfvars
**Purpose:** Staging environment configuration.
**Settings:**
- Medium instance types (t3.medium)
- 2 task counts
- 30-day log retention
- 512MB Lambda memory

### prod.tfvars
**Purpose:** Production environment configuration.
**Settings:**
- Large instance types (t3.large)
- 3 minimum task counts
- 90-day log retention
- 1024MB Lambda memory
- Deletion protection enabled

---

## 🐍 Python Application Files

### app_main.py
**Purpose:** Flask web application for ECS service.
**Features:**
- Health check endpoints (/health, /live, /ready)
- Order API endpoints (POST, GET, PUT)
- API key authentication
- DynamoDB integration
- SQS queue publishing
- CloudWatch metrics publishing
- Error handling and logging
- CORS support

**Endpoints:**
- POST /api/orders - Create order
- GET /api/orders/{order_id} - Get order details
- PUT /api/orders/{order_id} - Update order status
- GET /health - Health check
- GET /live - Liveness probe
- GET /ready - Readiness probe
- GET /api/status - Service status
- GET /api/metrics - Service metrics

### order_processor.py
**Purpose:** Lambda function for processing orders from SQS.
**Features:**
- Order validation
- DynamoDB persistence
- Step Functions workflow trigger
- Batch message processing
- Error handling and retries
- CloudWatch metrics
- X-Ray tracing
- AWS Lambda Powertools integration

**Functions:**
- validate_order() - Validate order structure
- calculate_total() - Calculate order total
- enrich_order() - Add metadata
- save_order_to_dynamodb() - Persist order
- trigger_workflow() - Start Step Functions
- lambda_handler() - Entry point

### notification_handler.py
**Purpose:** Lambda function for sending notifications.
**Features:**
- Email notifications via SES
- SNS publishing
- Multiple notification types (confirmed, shipped, delivered, failed)
- DynamoDB notification tracking
- Environment-based routing
- CloudWatch metrics

**Functions:**
- format_order_confirmed() - Format confirmed notification
- format_order_shipped() - Format shipped notification
- format_order_failed() - Format failure notification
- send_email() - Send via SES
- send_sns_notification() - Send via SNS
- save_notification_record() - Track notification
- lambda_handler() - Entry point

### data_transformer.py
**Purpose:** Lambda function for data transformation and enrichment.
**Features:**
- Data enrichment and metrics calculation
- Order categorization and prioritization
- Deduplication via hashing
- S3 storage with partitioning
- DynamoDB analytics persistence
- CloudWatch statistics publishing
- Data validation

**Functions:**
- calculate_metrics() - Calculate order metrics
- enrich_order_data() - Enrich with calculated data
- categorize_order_size() - Size categorization
- calculate_priority() - Priority calculation
- transform_order_data() - Main transformation
- validate_transformed_data() - Validation
- save_to_analytics() - DynamoDB persistence
- save_to_s3_parquet() - S3 storage
- generate_statistics() - Statistics generation
- lambda_handler() - Entry point

### health-check.py
**Purpose:** Health check script for post-deployment verification.
**Features:**
- ECS service health verification
- ALB target health checks
- HTTP endpoint health checks
- Lambda function status checks
- Step Functions state machine status
- Retry logic with timeouts
- Comprehensive reporting
- Exit codes for CI/CD integration

**Methods:**
- check_ecs_service() - Verify ECS service
- check_alb_targets() - Verify load balancer targets
- check_endpoint() - HTTP health checks
- check_lambda_function() - Lambda status
- check_step_functions() - Step Functions status
- run_all_checks() - Execute all checks

---

## 📦 Configuration Files

### Dockerfile
**Purpose:** Docker image for Flask ECS application.
**Features:**
- Python 3.11 slim base image
- Non-root user (appuser)
- Health check
- Gunicorn WSGI server
- Security best practices
- Multi-stage build ready

**Ports:** 5000

### docker-compose.yml
**Purpose:** Local development environment with all services.
**Services:**
- LocalStack (AWS emulation)
- Flask application
- PostgreSQL database
- Redis cache
- Prometheus metrics
- Grafana visualization

**Features:**
- Service health checks
- Volume mounts for development
- Network isolation
- Environment variable configuration

### app-requirements.txt
**Purpose:** Python dependencies for Flask application.
**Key Dependencies:**
- Flask and Flask-CORS
- Gunicorn WSGI server
- Boto3 (AWS SDK)
- AWS Lambda Powertools
- Pydantic (validation)
- Testing tools (pytest, pytest-cov, pytest-mock)
- Code quality tools (pylint, flake8, black, isort, bandit)

### lambda-requirements.txt
**Purpose:** Python dependencies for Lambda functions.
**Key Dependencies:**
- Boto3 and botocore
- AWS Lambda Powertools
- Testing and code quality tools
- Pydantic for validation
- Python-dateutil and pytz for date handling

---

## 📊 Project Statistics

**Total Files Created:** 18+
**Lines of Code:** 5,000+
**Terraform Resources:** 100+
**GitHub Actions Jobs:** 10+
**Lambda Functions:** 3
**Endpoints:** 7+

---

## 🗂️ Directory Structure Template

```
.
├── .github/
│   └── workflows/
│       └── ci-cd-pipeline.yml
├── terraform/
│   ├── main.tf
│   ├── ecs.tf
│   ├── lambda.tf
│   ├── iam.tf
│   ├── cloudwatch.tf
│   ├── variables.tf
│   └── environments/
│       ├── dev.tfvars
│       ├── staging.tfvars
│       └── prod.tfvars
├── src/
│   ├── app/
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── lambda/
│       ├── order_processor.py
│       ├── notification_handler.py
│       ├── data_transformer.py
│       └── requirements.txt
├── scripts/
│   ├── build.sh
│   ├── deploy.sh
│   └── health-check.py
├── tests/
│   ├── test_app.py
│   ├── test_lambda.py
│   └── test_terraform.py
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/
├── docker-compose.yml
├── README.md
└── SETUP_GUIDE.md
```

---

## 🚀 Quick Start Checklist

- [ ] Review README.md for overview
- [ ] Follow SETUP_GUIDE.md for environment setup
- [ ] Configure GitHub secrets
- [ ] Set up AWS infrastructure with Terraform
- [ ] Configure LocalStack for local testing
- [ ] Run tests locally with pytest
- [ ] Build Docker image locally
- [ ] Push code to GitHub (develop branch)
- [ ] Monitor CI/CD pipeline execution
- [ ] Verify deployment in AWS console
- [ ] Check CloudWatch dashboards for metrics
- [ ] Run health checks on deployed service
- [ ] Set up monitoring and alerting

---

## 📚 Key Technologies

- **Orchestration:** GitHub Actions
- **Infrastructure:** Terraform, AWS
- **Container:** Docker, ECS
- **Serverless:** Lambda, Step Functions
- **Database:** DynamoDB, PostgreSQL
- **Messaging:** SQS, SNS
- **Web Framework:** Flask
- **Monitoring:** CloudWatch, Prometheus, Grafana
- **Testing:** pytest, moto
- **Code Quality:** Black, Flake8, Pylint, Bandit

---

## 🔐 Security Features

1. **API Authentication:** X-API-Key header validation
2. **IAM Least Privilege:** Role-based access control
3. **Secrets Management:** AWS Secrets Manager
4. **VPC Isolation:** Private subnets for Lambda
5. **Encryption:** S3 encryption, Secrets Manager encryption
6. **Logging:** CloudWatch Logs with audit trails
7. **Code Security:** SAST scanning in pipeline
8. **Dependency Scanning:** Dependency vulnerability checks

---

## 📈 Scalability Features

1. **Auto-scaling:** CPU/memory/request-based scaling
2. **Multi-AZ:** Deployment across availability zones
3. **Load Balancing:** ALB with health checks
4. **Caching:** Redis integration
5. **Batch Processing:** SQS with batch message processing
6. **Asynchronous Workflows:** Step Functions orchestration

---

## 📞 Support

For detailed information on each component, refer to:
- README.md - Project overview
- SETUP_GUIDE.md - Setup and deployment
- Individual file headers for specific implementation details
- AWS and Terraform documentation for deeper understanding

---

**Project Version:** 1.0.0
**Last Updated:** 2024
**Status:** Production Ready ✅
