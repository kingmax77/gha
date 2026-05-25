# Dev Environment Configuration
environment        = "dev"
aws_region         = "us-east-1"
project_name       = "my-app"
vpc_cidr           = "10.0.0.0/16"
availability_zones = ["us-east-1a", "us-east-1b"]

# ECS Configuration
container_port    = 5000
task_cpu          = "256"
task_memory       = "512"
ecs_desired_count = 1
ecs_min_capacity  = 1
ecs_max_capacity  = 2

# Lambda Configuration
lambda_memory_size = 256

# Logging
log_retention_days = 7

# Alerts
alert_email = "dev-alerts@example.com"
