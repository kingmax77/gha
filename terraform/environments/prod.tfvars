# Production Environment Configuration
environment        = "prod"
aws_region         = "us-east-1"
project_name       = "my-app"
vpc_cidr           = "10.2.0.0/16"
availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]

# ECS Configuration
container_port    = 5000
task_cpu          = "1024"
task_memory       = "2048"
ecs_desired_count = 3
ecs_min_capacity  = 3
ecs_max_capacity  = 10

# Lambda Configuration
lambda_memory_size = 1024

# Logging
log_retention_days = 90

# Alerts
alert_email = "prod-alerts@example.com"
