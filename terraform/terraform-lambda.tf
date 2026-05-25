# ===== LAMBDA FUNCTIONS =====

# Function 1: Order Processor
resource "aws_lambda_function" "order_processor" {
  filename      = "lambda_order_processor.zip"
  function_name = "${var.project_name}-order-processor-${var.environment}"
  role          = aws_iam_role.lambda_role.arn
  handler       = "order_processor.lambda_handler"
  runtime       = "python3.11"
  timeout       = 60
  memory_size   = var.lambda_memory_size

  source_code_hash = filebase64sha256("lambda_order_processor.zip")

  environment {
    variables = {
      ENVIRONMENT   = var.environment
      PROJECT_NAME  = var.project_name
      LOG_LEVEL     = "INFO"
    }
  }

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  layers = [aws_lambda_layer_version.dependencies.arn]

  tags = {
    Name = "${var.project_name}-order-processor"
  }

  depends_on = [aws_iam_role_policy.lambda_policy]
}

# Function 2: Notification Handler
resource "aws_lambda_function" "notification_handler" {
  filename      = "lambda_notification_handler.zip"
  function_name = "${var.project_name}-notification-handler-${var.environment}"
  role          = aws_iam_role.lambda_role.arn
  handler       = "notification_handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = var.lambda_memory_size

  source_code_hash = filebase64sha256("lambda_notification_handler.zip")

  environment {
    variables = {
      ENVIRONMENT   = var.environment
      PROJECT_NAME  = var.project_name
      LOG_LEVEL     = "INFO"
    }
  }

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  layers = [aws_lambda_layer_version.dependencies.arn]

  tags = {
    Name = "${var.project_name}-notification-handler"
  }

  depends_on = [aws_iam_role_policy.lambda_policy]
}

# Function 3: Data Transformer
resource "aws_lambda_function" "data_transformer" {
  filename      = "lambda_data_transformer.zip"
  function_name = "${var.project_name}-data-transformer-${var.environment}"
  role          = aws_iam_role.lambda_role.arn
  handler       = "data_transformer.lambda_handler"
  runtime       = "python3.11"
  timeout       = 120
  memory_size   = var.lambda_memory_size

  source_code_hash = filebase64sha256("lambda_data_transformer.zip")

  environment {
    variables = {
      ENVIRONMENT   = var.environment
      PROJECT_NAME  = var.project_name
      LOG_LEVEL     = "INFO"
    }
  }

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  layers = [aws_lambda_layer_version.dependencies.arn]

  tags = {
    Name = "${var.project_name}-data-transformer"
  }

  depends_on = [aws_iam_role_policy.lambda_policy]
}

# ===== LAMBDA LAYER (Dependencies) =====
resource "aws_lambda_layer_version" "dependencies" {
  filename   = "lambda_layer.zip"
  layer_name = "${var.project_name}-dependencies-${var.environment}"
  
  source_code_hash = filebase64sha256("lambda_layer.zip")

  compatible_runtimes = ["python3.9", "python3.10", "python3.11"]

  # tags = {
  #   Name = "${var.project_name}-layer"
  # }
}

# ===== LAMBDA RESERVED CONCURRENCY =====
resource "aws_lambda_provisioned_concurrency_config" "order_processor" {
  count                             = var.environment == "prod" ? 1 : 0
  function_name                     = aws_lambda_function.order_processor.function_name
  provisioned_concurrent_executions = 10
  qualifier                         = aws_lambda_function.order_processor.version
}

# ===== LAMBDA ALIASES =====
resource "aws_lambda_alias" "order_processor_live" {
  name            = "live"
  description     = "Live alias for order processor"
  function_name   = aws_lambda_function.order_processor.function_name
  function_version = aws_lambda_function.order_processor.version
}

# ===== LAMBDA SECURITY GROUP =====
resource "aws_security_group" "lambda" {
  name_prefix = "lambda-"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-lambda-sg"
  }
}

# ===== STEP FUNCTIONS STATE MACHINE =====
resource "aws_sfn_state_machine" "order_workflow" {
  name       = "${var.project_name}-order-workflow-${var.environment}"
  role_arn   = aws_iam_role.step_functions_role.arn
  definition = jsonencode({
    Comment = "Order processing workflow"
    StartAt = "ProcessOrder"
    States = {
      ProcessOrder = {
        Type     = "Task"
        Resource = aws_lambda_function.order_processor.arn
        Next     = "ParallelProcessing"
        Retry = [
          {
            ErrorEquals = ["States.TaskFailed"]
            IntervalSeconds = 1
            MaxAttempts = 2
            BackoffRate = 2.0
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "HandleOrderError"
          }
        ]
      }

      ParallelProcessing = {
        Type = "Parallel"
        Branches = [
          {
            StartAt = "TransformData"
            States = {
              TransformData = {
                Type     = "Task"
                Resource = aws_lambda_function.data_transformer.arn
                Next     = "StoreResults"
              }
              StoreResults = {
                Type = "Pass"
                End  = true
              }
            }
          },
          {
            StartAt = "SendNotification"
            States = {
              SendNotification = {
                Type     = "Task"
                Resource = aws_lambda_function.notification_handler.arn
                End      = true
              }
            }
          }
        ]
        Next = "OrderComplete"
      }

      OrderComplete = {
        Type = "Succeed"
      }

      HandleOrderError = {
        Type = "Task"
        Resource = "arn:aws:states:::sns:publish"
        Parameters = {
          TopicArn = aws_sns_topic.errors.arn
          Message  = "Order processing failed: $.error"
        }
        Next = "OrderFailed"
      }

      OrderFailed = {
        Type = "Fail"
        Error = "OrderProcessingFailed"
        Cause = "Failed to process order"
      }
    }
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.step_functions.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  tags = {
    Name = "${var.project_name}-order-workflow"
  }
}

# ===== SNS TOPIC FOR ERRORS =====
resource "aws_sns_topic" "errors" {
  name = "${var.project_name}-errors-${var.environment}"

  tags = {
    Name = "${var.project_name}-errors-topic"
  }
}

resource "aws_sns_topic_subscription" "errors_email" {
  count     = var.environment == "prod" ? 1 : 0
  topic_arn = aws_sns_topic.errors.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ===== LAMBDA EVENT SOURCE MAPPINGS =====
resource "aws_lambda_event_source_mapping" "order_processor_sqs" {
  event_source_arn  = aws_sqs_queue.orders.arn
  function_name     = aws_lambda_function.order_processor.arn
  batch_size        = 10
  maximum_batching_window_in_seconds = 5

  function_response_types = ["ReportBatchItemFailures"]

  depends_on = [aws_iam_role_policy.lambda_sqs_policy]
}

# ===== SQS QUEUE =====
resource "aws_sqs_queue" "orders" {
  name                      = "${var.project_name}-orders-${var.environment}"
  delay_seconds             = 0
  max_message_size          = 262144
  message_retention_seconds = 86400
  visibility_timeout_seconds = 300

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.orders_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name = "${var.project_name}-orders-queue"
  }
}

resource "aws_sqs_queue" "orders_dlq" {
  name                      = "${var.project_name}-orders-dlq-${var.environment}"
  message_retention_seconds = 1209600  # 14 days

  tags = {
    Name = "${var.project_name}-orders-dlq"
  }
}

# ===== OUTPUTS =====
output "lambda_order_processor_arn" {
  description = "ARN of the order processor Lambda function"
  value       = aws_lambda_function.order_processor.arn
}

output "lambda_notification_handler_arn" {
  description = "ARN of the notification handler Lambda function"
  value       = aws_lambda_function.notification_handler.arn
}

output "lambda_data_transformer_arn" {
  description = "ARN of the data transformer Lambda function"
  value       = aws_lambda_function.data_transformer.arn
}

output "step_functions_state_machine_arn" {
  description = "ARN of the Step Functions state machine"
  value       = aws_sfn_state_machine.order_workflow.arn
}

output "sqs_queue_url" {
  description = "URL of the SQS queue"
  value       = aws_sqs_queue.orders.url
}
