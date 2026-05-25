# Staging Environment Configuration
environment      = "staging"
aws_region       = "us-east-1"
project_name     = "my-app"
vpc_cidr         = "10.1.0.0/16"
availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]

# ECS Configuration
container_port    = 5000
task_cpu          = "512"
task_memory       = "1024"
ecs_desired_count = 2
ecs_min_capacity  = 2
ecs_max_capacity  = 4

# Lambda Configuration
lambda_memory_size = 512

# Logging
log_retention_days = 30

# Alerts
alert_email = "staging-alerts@example.com"
