# ===== GENERAL VARIABLES =====
variable "aws_region" {
  description = "AWS region to deploy to"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "my-app"
}

# ===== NETWORKING VARIABLES =====
variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones to use"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

# ===== ECS VARIABLES =====
variable "container_port" {
  description = "Port exposed by the Docker image"
  type        = number
  default     = 5000
}

variable "task_cpu" {
  description = "Amount of CPU units for the task"
  type        = string
  default     = "512"
  validation {
    condition     = contains(["256", "512", "1024", "2048", "4096"], var.task_cpu)
    error_message = "Task CPU must be 256, 512, 1024, 2048, or 4096."
  }
}

variable "task_memory" {
  description = "Amount of memory in MB for the task"
  type        = string
  default     = "1024"
  validation {
    condition     = can(tonumber(var.task_memory))
    error_message = "Task memory must be a valid number."
  }
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 1
  validation {
    condition     = var.ecs_desired_count > 0
    error_message = "ECS desired count must be greater than 0."
  }
}

variable "ecs_min_capacity" {
  description = "Minimum number of ECS tasks for auto-scaling"
  type        = number
  default     = 1
}

variable "ecs_max_capacity" {
  description = "Maximum number of ECS tasks for auto-scaling"
  type        = number
  default     = 4
}

# ===== LAMBDA VARIABLES =====
variable "lambda_memory_size" {
  description = "Memory size for Lambda functions in MB"
  type        = number
  default     = 512
  validation {
    condition     = var.lambda_memory_size >= 128 && var.lambda_memory_size <= 10240
    error_message = "Lambda memory must be between 128 and 10240 MB."
  }
}

# ===== LOGGING VARIABLES =====
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Log retention must be a valid CloudWatch value."
  }
}

# ===== IMAGE VARIABLES =====
variable "image_tag" {
  description = "Docker image tag (defaults to latest)"
  type        = string
  default     = ""
}

# ===== ALERTING VARIABLES =====
variable "alert_email" {
  description = "Email address for alerts"
  type        = string
  sensitive   = true
}

# ===== LOCALS =====
locals {
  common_tags = {
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "Terraform"
  }

  # Environment-specific settings
  env_settings = {
    dev = {
      task_cpu           = "256"
      task_memory        = "512"
      ecs_desired_count  = 1
      ecs_min_capacity   = 1
      ecs_max_capacity   = 2
      lambda_memory_size = 256
      log_retention_days = 7
    }
    staging = {
      task_cpu           = "512"
      task_memory        = "1024"
      ecs_desired_count  = 2
      ecs_min_capacity   = 2
      ecs_max_capacity   = 4
      lambda_memory_size = 512
      log_retention_days = 30
    }
    prod = {
      task_cpu           = "1024"
      task_memory        = "2048"
      ecs_desired_count  = 3
      ecs_min_capacity   = 3
      ecs_max_capacity   = 10
      lambda_memory_size = 1024
      log_retention_days = 90
    }
  }
}
